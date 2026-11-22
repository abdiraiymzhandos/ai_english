from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest import SkipTest
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import QuizAttempt, UserDevice, UserProfile
from .services.device_access import admit_device, expire_profile
from .test_learning_flow import make_lesson


@override_settings(MAX_ACCOUNT_DEVICES=2)
class DevicePolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test-learner',password='sample-password')
        self.profile = UserProfile.objects.create(user=self.user, phone='+70000000000')

    def browser(self, device=None):
        client = Client()
        client.force_login(self.user)
        if device:
            client.cookies['device_id'] = device
        return client

    def test_first_two_allowed_third_locks_and_retries_preserve_deadline(self):
        first, second, third = (self.browser() for _ in range(3))
        for client in (first,second):
            self.assertEqual(client.get('/profile/').status_code,200)
            self.assertEqual(client.get('/profile/').status_code,200)
        now = timezone.now()
        with patch('django.utils.timezone.now',return_value=now):
            denied = third.get('/profile/')
        self.assertRedirects(denied,'/account-locked/')
        self.assertNotIn('device_id',denied.cookies)
        self.assertNotIn('_auth_user_id',third.session)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.lock_until,now+timedelta(days=5))
        with patch('django.utils.timezone.now',return_value=self.profile.lock_until-timedelta(seconds=1)):
            self.assertRedirects(first.get('/profile/'),'/account-locked/')
            self.assertRedirects(third.post('/login/',{'username':self.user.username,'password':'sample-password'}),'/account-locked/')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.lock_until,now+timedelta(days=5))
        self.assertEqual(self.user.devices.count(),2)

    def test_login_cookie_old_cookie_and_guest_requests(self):
        client = Client()
        self.assertEqual(client.get('/lesson/10000/').status_code,404)
        client.get('/login/')
        identity = client.cookies['device_id'].value
        self.assertTrue(client.cookies['device_id']['httponly'])
        self.assertEqual(client.cookies['device_id']['samesite'],'Lax')
        self.assertEqual(client.post('/login/',{'username':self.user.username,'password':'bad'}).status_code,200)
        self.assertFalse(self.user.devices.exists())
        for _ in range(2):
            self.assertEqual(client.post('/login/',{'username':self.user.username,'password':'sample-password'}).status_code,302)
            self.assertEqual(self.user.devices.get().device_id,identity)
            self.assertEqual(client.post('/logout/').status_code,302)

    def test_missing_cookie_parallel_bootstrap_same_session(self):
        original = self.browser()
        other = Client()
        other.cookies[settings.SESSION_COOKIE_NAME] = original.cookies[settings.SESSION_COOKIE_NAME].value
        for client in (original,other):
            self.assertEqual(client.get('/profile/').status_code,200)
        self.assertEqual(original.cookies['device_id'].value,other.cookies['device_id'].value)
        self.assertEqual(self.user.devices.count(),1)

    @override_settings(MAX_ACCOUNT_DEVICES=3)
    def test_three_then_two_rollout_preserves_known_legacy_devices(self):
        for device in ('legacy-a','legacy-b','legacy-c'):
            # Include a legacy opaque identity actually present at deployment.
            if device == 'legacy-c':
                self.user.devices.create(device_id=device)
            self.assertEqual(self.browser(device).get('/profile/').status_code,200)
        self.assertEqual(self.user.devices.count(),3)
        with override_settings(MAX_ACCOUNT_DEVICES=2):
            self.assertEqual(self.browser('legacy-c').get('/profile/').status_code,200)
        self.assertRedirects(self.browser().get('/profile/'),'/account-locked/')
        self.assertEqual(self.user.devices.count(),3)

    def test_expiry_clears_legacy_registry_before_readmission(self):
        now = timezone.now()
        self.user.devices.bulk_create([UserDevice(user=self.user,device_id=str(i)) for i in range(4)])
        UserProfile.objects.update(lock_until=now)
        with patch('django.utils.timezone.now',return_value=now):
            client = self.browser()
            self.assertEqual(client.get('/profile/').status_code,200)
            self.assertEqual(client.get('/profile/').status_code,200)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.lock_until)
        self.assertEqual(self.user.devices.get().device_id,client.cookies['device_id'].value)
        self.assertIsNone(expire_profile(self.profile.pk))

    def test_notice_bound_to_lock_after_logout_and_expiry(self):
        now = timezone.now()
        deadline = now+timedelta(days=4,hours=12,minutes=18)
        UserProfile.objects.update(lock_until=deadline)
        client = self.browser()
        with patch('django.utils.timezone.now',return_value=now):
            self.assertRedirects(client.get('/profile/'),'/account-locked/')
            page = client.get('/account-locked/')
            self.assertContains(page,'Аккаунтыңыз уақытша құлыпталды')
            self.assertContains(page,'4 күн 12 сағат 18 минут')
            self.assertContains(page,timezone.localtime(deadline).strftime('%H:%M:%S'))
            self.assertContains(page,f'https://wa.me/{settings.COURSE_WHATSAPP_NUMBER}')
            self.assertContains(page,'href="/login/"')
            self.assertNotContains(page,self.user.username)
            self.assertNotContains(page,self.profile.phone)
            self.assertIn('no-store',page['Cache-Control'])
        stranger = Client().get('/account-locked/',{'user':self.user.pk,'lock_until':deadline})
        self.assertNotContains(stranger,'id="countdown"')
        self.assertContains(stranger,'Аккаунт күйін тексеру')
        with patch('django.utils.timezone.now',return_value=deadline):
            self.assertContains(client.get('/account-locked/'),'Алдыңғы шектеу аяқталды')
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.lock_until)
        self.assertNotContains(client.get('/account-locked/'),'id="countdown"')

    def test_old_notice_cannot_track_subsequent_lock(self):
        self.profile.lock()
        client = self.browser()
        client.get('/profile/')
        self.profile.unlock()
        self.profile.lock(days=2)
        self.assertNotContains(client.get('/account-locked/'),'id="countdown"')

    def test_privileged_operators_exempt(self):
        self.profile.lock()
        for fields in ({'is_staff':True},{'is_staff':False,'is_superuser':True}):
            User.objects.filter(pk=self.user.pk).update(**fields)
            client = self.browser()
            self.assertEqual(client.get('/profile/').status_code,200)
            self.assertContains(client.get('/account-locked/'),'Аккаунтыңыз ашық')
        self.assertEqual(self.user.devices.count(),0)

    def test_maintenance_dry_run_and_apply(self):
        self.user.devices.create(device_id='expired')
        UserProfile.objects.update(lock_until=timezone.now())
        for name,deadline in [('active',timezone.now()+timedelta(days=2)),('legacy',None)]:
            u = User.objects.create_user(name)
            UserProfile.objects.create(user=u,lock_until=deadline)
            u.devices.bulk_create([UserDevice(user=u,device_id=str(i)) for i in range(3)])
        for apply,expected in [(False,'devices_on_expired=1'),(True,'cleared=1 removed=1'),(True,'cleared=0 removed=0')]:
            output = StringIO()
            call_command('reconcile_device_locks',apply=apply,stdout=output)
            self.assertIn(expected,output.getvalue())
            self.assertIn('accounts_over_two=2',output.getvalue())
            self.assertEqual(self.user.devices.count(),int(not apply))
            self.assertEqual(UserDevice.objects.exclude(user=self.user).count(),6)
        self.assertEqual(UserProfile.objects.filter(lock_until__isnull=False).count(),1)


class AdminUnlockTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('owner')
        self.staff = User.objects.create_user('operator',is_staff=True)
        self.staff.user_permissions.add(Permission.objects.get(codename='change_userprofile'))
        self.user = User.objects.create_user('learner')
        self.profile = UserProfile.objects.create(user=self.user,is_paid=True,has_voice_access=True,has_translator_access=True,current_lesson=7)
        self.profile.lock()
        make_lesson(1)
        QuizAttempt.objects.create(user_id=str(self.user.pk),lesson_id=1,is_passed=True)
        self.user.devices.create(device_id='registered')
        self.url = reverse('admin:lessons_userprofile_unlock',args=[self.profile.pk])
        self.change = reverse('admin:lessons_userprofile_change',args=[self.profile.pk])

    def test_post_only_csrf_target_audit_and_repeated_unlock(self):
        other = UserProfile.objects.create(user=User.objects.create_user('other'))
        other.lock()
        other.user.devices.create(device_id='other')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertContains(client.get(self.change),'Құлыпты ашу және құрылғыларды тазалау')
        self.assertEqual(client.get(self.url).status_code,405)
        self.assertEqual(client.post(self.url).status_code,403)
        self.assertEqual(self.profile.user.devices.count(),1)
        for n in (1,0):
            page = client.post(self.url,{'csrfmiddlewaretoken':client.cookies['csrftoken'].value},follow=True)
            self.assertContains(page,f'Тазаланған құрылғылар саны: {n}')
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.lock_until)
        self.assertFalse(self.user.devices.exists())
        self.assertEqual((self.profile.is_paid,self.profile.has_voice_access,self.profile.has_translator_access,self.profile.current_lesson),(True,True,True,7))
        self.assertTrue(QuizAttempt.objects.get(user_id=str(self.user.pk)).is_passed)
        self.assertEqual(LogEntry.objects.filter(user=self.owner,object_id=str(self.profile.pk)).count(),2)
        other.refresh_from_db()
        self.assertTrue(other.is_locked())
        self.assertTrue(other.user.devices.exists())

    def test_unlock_preserves_existing_django_session_until_next_request(self):
        learner = Client()
        learner.force_login(self.user)
        self.client.force_login(self.owner)
        self.client.post(self.url)
        self.assertEqual(learner.get('/profile/').status_code,200)
        self.assertEqual(learner.session['_auth_user_id'],str(self.user.pk))
        self.assertEqual(self.user.devices.count(),1)

    def test_staff_denied_individual_and_bulk_superuser_bulk_succeeds(self):
        listing = reverse('admin:lessons_userprofile_changelist')
        action = {'action':'unlock_accounts','_selected_action':str(self.profile.pk)}
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(self.change),'Құлыпты ашу және құрылғыларды тазалау')
        self.assertEqual(self.client.post(self.url).status_code,403)
        self.assertEqual(self.client.post(listing,action).status_code,403)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_locked())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(listing,action).status_code,302)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.lock_until)
        self.assertFalse(self.user.devices.exists())
        self.assertTrue(LogEntry.objects.filter(user=self.owner,object_id=str(self.profile.pk)).exists())


class ConcurrentDeviceTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor == 'sqlite' and connection.is_in_memory_db():
            raise SkipTest('Run with a file-backed SQLite test DB or MySQL for independent writers.')

    def test_concurrent_cookie_bootstrap_and_first_profile(self):
        user = User.objects.create_user('bootstrap-race')
        first, second = Client(), Client()
        first.force_login(user)
        second.cookies[settings.SESSION_COOKIE_NAME] = first.cookies[settings.SESSION_COOKIE_NAME].value
        responses = self.race(lambda: first.get('/profile/'), lambda: second.get('/profile/'))
        self.assertEqual([response.status_code for response in responses], [200,200])
        self.assertEqual(first.cookies['device_id'].value, second.cookies['device_id'].value)
        self.assertEqual(user.devices.count(),1)

    def race(self, *actions):
        barrier = Barrier(len(actions))
        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=8)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            futures = [pool.submit(run, action) for action in actions]
            return [f.result(timeout=15) for f in futures]

    def test_simultaneous_admission_and_duplicate_identity(self):
        user = User.objects.create_user('simultaneous')
        profile = UserProfile.objects.create(user=user)
        uid = user.pk
        self.race(lambda: admit_device(uid,'same'),lambda: admit_device(uid,'same'))
        self.assertEqual(user.devices.count(),1)
        self.race(lambda: admit_device(uid,'another'),lambda: admit_device(uid,'third'))
        profile.refresh_from_db()
        self.assertTrue(profile.is_locked())
        self.assertEqual(user.devices.count(),2)
        deadline = profile.lock_until
        self.race(lambda: admit_device(uid,'same'),lambda: admit_device(uid,'third'))
        profile.refresh_from_db()
        self.assertEqual(profile.lock_until,deadline)

    def test_expiry_racing_login_and_reconciliation(self):
        user = User.objects.create_user('expiry-race')
        profile = UserProfile.objects.create(user=user,lock_until=timezone.now())
        user.devices.create(device_id='old')
        self.race(lambda: admit_device(user.pk,'fresh'),lambda: expire_profile(profile.pk))
        self.assertEqual(list(user.devices.values_list('device_id',flat=True)),['fresh'])
        profile.refresh_from_db()
        self.assertIsNone(profile.lock_until)
