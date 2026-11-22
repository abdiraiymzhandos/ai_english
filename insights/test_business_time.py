import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.timezone import localtime
from openpyxl import load_workbook

from lessons.models import UserProfile
from .models import Event
from .reports import ZONE, options

UTC = timezone.utc


class BusinessCalendarTests(SimpleTestCase):
    def test_fresh_wsgi_and_management_startup(self):
        env = dict(os.environ, USE_MYSQL='0', DJANGO_SETTINGS_MODULE='english_course.settings')
        env.pop('PYTHONTZPATH', None)
        check = """import zoneinfo, tzdata
from django.utils import timezone
from datetime import datetime
assert zoneinfo.TZPATH == () and tzdata.__version__ == '2026.6'
assert datetime(2026,11,22,tzinfo=timezone.get_default_timezone()).utcoffset().total_seconds() == 18000
"""
        # The WSGI host may already have looked up this key using an obsolete system file.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Asia').mkdir()
            (root / 'Asia/Almaty').write_bytes(files('tzdata.zoneinfo.Etc').joinpath('GMT-6').read_bytes())
            preload = f"""import zoneinfo
from datetime import datetime
zoneinfo.reset_tzpath([{directory!r}])
stale = zoneinfo.ZoneInfo('Asia/Almaty')
assert datetime(2026,11,22,tzinfo=stale).utcoffset().total_seconds() == 21600
from english_course.wsgi import application
"""
            for args in (['-c', preload + check], ['manage.py', 'shell', '-c', check]):
                subprocess.run([sys.executable, *args], cwd=settings.BASE_DIR, env=env,
                               check=True, capture_output=True, timeout=20)

    def test_historical_offset_and_local_midnight(self):
        self.assertEqual(settings.TIME_ZONE, 'Asia/Almaty')
        self.assertTrue(settings.USE_TZ)
        for stamp, expected in (
            ('2024-02-28T18:00:00', '2024-02-29T00:00:00+06:00'),
            ('2024-02-29T19:00:00', '2024-03-01T00:00:00+05:00'),
            ('2026-11-21T18:59:59', '2026-11-21T23:59:59+05:00'),
            ('2026-11-21T19:00:00', '2026-11-22T00:00:00+05:00'),
        ):
            instant = datetime.fromisoformat(stamp).replace(tzinfo=UTC)
            self.assertEqual(localtime(instant).isoformat(), expected)

    def test_inclusive_and_complete_calendar_days(self):
        midnight = datetime(2026, 11, 21, 19, tzinfo=UTC)
        for key, days in [('seven',7), ('fourteen',14), ('thirty',30)]:
            for inclusive in (True,False):
                preset = key + '_inclusive' if inclusive else key
                start,end,_ = options({'preset':preset},midnight)
                self.assertEqual(end,date(2026,11,22 if inclusive else 21))
                self.assertEqual((end-start).days+1,days)
        self.assertEqual(options({},midnight)[:2],(date(2026,11,16),date(2026,11,22)))
        self.assertEqual(options({},midnight-timedelta(seconds=1))[1],date(2026,11,21))
        # The February rollback made this local calendar day 25 hours long.
        start = datetime(2024,2,29,tzinfo=ZONE).astimezone(UTC)
        end = datetime(2024,3,1,tzinfo=ZONE).astimezone(UTC)
        self.assertEqual(end-start,timedelta(hours=25))


class ReportClockTests(TestCase):
    def test_storage_admin_dashboard_and_xlsx_agree(self):
        owner = User.objects.create_superuser('clock-owner')
        self.client.force_login(owner)
        midnight = datetime(2026,11,21,19,tzinfo=UTC)
        learner = User.objects.create_user('midnight-learner',date_joined=midnight)
        UserProfile.objects.create(user=learner)
        Event.objects.create(user=learner,at=midnight,kind='signup_completed',page='register',path='/register/')
        User.objects.create_user('before-window',date_joined=midnight-timedelta(days=6,seconds=1))
        User.objects.create_user('future',date_joined=midnight+timedelta(hours=2))
        self.assertEqual(connection.timezone_name, 'UTC')
        with connection.cursor() as cursor:
            cursor.execute('SELECT date_joined FROM auth_user WHERE id = %s', [learner.pk])
            self.assertEqual(str(cursor.fetchone()[0]), '2026-11-21 19:00:00')
        self.assertContains(self.client.get(reverse('admin:lessons_userprofile_changelist')), '2026-11-22 00:00')
        user_change = self.client.get(reverse('admin:auth_user_change',args=[learner.pk]))
        self.assertContains(user_change,'value="2026-11-22"')
        self.assertContains(user_change,'value="00:00:00"')
        with patch('insights.reports.timezone.now', return_value=midnight+timedelta(minutes=1)):
            for mode in ('activity','cohort'):
                url = reverse('admin:insights_visit_changelist')
                page = self.client.get(url,{'mode':mode, 'user':learner.pk})
                self.assertEqual(page.context_data['totals']['registrations'],1)
                self.assertEqual([u['id'] for u in page.context_data['users']],[learner.pk])
                self.assertContains(page,'2026-11-22 00:00')
                self.assertContains(page,'2026-11-22 00:01')
                download = self.client.post(url,{'export':'xlsx','mode':mode,'q':'midnight-learner'})
                book = load_workbook(BytesIO(b''.join(download.streaming_content)))
                self.assertEqual(book['Users']['B2'].value, datetime(2026,11,22))
                overview = {k:v for k,v,_ in book['Overview'].values}
                self.assertEqual(overview['Start'].date(),date(2026,11,16))
                self.assertEqual(overview['End'].date(),date(2026,11,22))
                self.assertEqual(overview['Observation cutoff'],datetime(2026,11,22,0,1))
                self.assertEqual(overview['Latest event'],datetime(2026,11,22))
                book.close()
        learner.refresh_from_db()
        self.assertEqual(learner.date_joined,midnight)
