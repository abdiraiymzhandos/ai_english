import os
import subprocess
import sys
from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from lessons.models import RegistrationNotification, UserProfile
from .management.commands import run_background_worker as worker
from .models import Event, PendingEvent


class WorkerSchedulingTests(SimpleTestCase):
    def test_database_guard_and_positive_intervals(self):
        with patch.object(worker, 'connection', vendor='sqlite'):
            with self.assertRaisesMessage(CommandError, 'MySQL is required'):
                call_command('run_background_worker')
            for option in ('notification_interval','analytics_interval','notification_limit','analytics_limit'):
                with self.assertRaisesMessage(CommandError, 'positive integers'):
                    call_command('run_background_worker', allow_sqlite=True, **{option:0})

    def test_failure_cleanup_and_bounded_polling(self):
        stopping = Mock()
        stopping.is_set.return_value = False
        stopping.wait.side_effect = [False, False, True]
        def process(command, *, limit, stdout, stop_requested):
            self.assertEqual((command,limit),('process_analytics',31))
            if run.call_count == 1:
                raise OperationalError('private-diagnostic-text')
            stdout.write('0' if run.call_count == 2 else '7')
        with patch.object(worker, 'call_command',side_effect=process) as run, \
                patch.object(worker.connections, 'close_all') as close, self.assertLogs(worker.logger) as logs:
            worker.poll('process_analytics',31,12,stopping)
        self.assertEqual(close.call_count,3)
        self.assertEqual([c.args for c in stopping.wait.call_args_list],[(12,)]*3)
        self.assertEqual(len(logs.output),2)
        self.assertIn('OperationalError',logs.output[0])
        self.assertNotIn('private-diagnostic-text',logs.output[0])
        self.assertIn('processed 7',logs.output[1])

    def test_real_signals_and_independent_pollers_in_fresh_process(self):
        # Keep analytics in flight while notifications run twice. Use no live DB or network.
        script = """
import os, signal, threading, time
from unittest.mock import patch
import django
django.setup()
from django.core.management import call_command
from insights.management.commands import run_background_worker as worker
active = threading.Event()
complete = threading.Event()
polls = []
def batch(command, *, limit, stdout, stop_requested):
    if command == 'process_analytics':
        assert limit == 5000
        active.set()
        assert complete.wait(8)
    else:
        assert limit == 100 and active.wait(8)
        polls.append(time.monotonic())
        if len(polls) == 2:
            os.kill(os.getpid(), signal.SIGNAL_NAME)
            until = time.monotonic()+5
            while not stop_requested() and time.monotonic()<until:
                time.sleep(0.01)
            assert stop_requested()
            complete.set()
    stdout.write('0')
with patch.object(worker,'call_command',side_effect=batch), patch.object(django,'setup',side_effect=AssertionError):
    call_command('run_background_worker',allow_sqlite=True,notification_interval=1)
assert len(polls)==2 and polls[1]-polls[0]>=0.95
"""
        for sig in ('SIGTERM','SIGINT'):
            result = subprocess.run([sys.executable,'-c',script.replace('SIGNAL_NAME',sig)],
                cwd=settings.BASE_DIR, env=dict(os.environ, USE_MYSQL='0', DJANGO_SETTINGS_MODULE='english_course.settings'),
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('worker started (sqlite)',result.stderr)
            self.assertIn('worker stopped',result.stderr)


class WorkerQueueTests(TransactionTestCase):
    def test_real_commands_keep_unclaimed_work_and_deduplicate(self):
        since = timezone.now()-timedelta(seconds=1)
        for username in ('first', 'second'):
            user = User.objects.create_user(username)
            UserProfile.objects.create(user=user)
            RegistrationNotification.objects.create(user=user,next_attempt=since)
            PendingEvent.objects.create(user=user,kind='signup_completed',page='register',path='/register/')

        with patch('lessons.services.registration_notifications.send_telegram_message',return_value=True) as send:
            for command in ('process_registration_notifications','process_analytics'):
                stopping = Mock()
                # Enter the loop, take one job, then stop before claiming the second.
                stopping.is_set.side_effect = [False,False,True]
                stopping.wait.return_value = True
                worker.poll(command,100,15,stopping)
            self.assertEqual(RegistrationNotification.objects.filter(status='pending').count(),1)
            self.assertEqual(PendingEvent.objects.count(),1)
            for _ in range(2):
                for command in ('process_registration_notifications','process_analytics'):
                    stopping = Mock()
                    stopping.is_set.return_value = False
                    stopping.wait.return_value = True
                    worker.poll(command,100,15,stopping)
            self.assertEqual(send.call_count,2)
        self.assertEqual(RegistrationNotification.objects.filter(status='sent').count(),2)
        self.assertEqual(Event.objects.filter(kind='signup_completed').count(),2)
        self.assertFalse(PendingEvent.objects.exists())
