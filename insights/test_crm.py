import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Event as Signal
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.db import connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from lessons.models import QuizAttempt, UserProfile
from lessons.services.registration_notifications import whatsapp_digits
from lessons.test_learning_flow import make_lesson
from .models import Event, Purchase, Visit, Visitor
from .reports import ReportError, report


class CustomerReports(TestCase):
    url = '/admin/insights/visit/'
    params = {'preset': 'today'}

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_superuser('owner')
        cls.viewer = User.objects.create_user('staff', is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(codename='view_visit'))
        cls.person = User.objects.create_user('crm-learner')
        cls.profile = UserProfile.objects.create(user=cls.person, phone='+7 (701) 123-45-67')
        cls.visit = Visit.objects.create(user=cls.person, visitor=Visitor.objects.create(), landing='/')

    def record(self, kind, **extra):
        return Event.objects.create(user=self.person, visit=self.visit, path='/', kind=kind, **extra)

    def export(self, **params):
        response = self.client.post(self.url, dict(self.params, export='xlsx', **params))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        return load_workbook(BytesIO(b''.join(response.streaming_content)))

    def test_segments_follow_progress_and_intent_across_date_boundaries(self):
        def check(segment, *flags):
            data = report(self.params)
            customer, = data['users']
            self.assertEqual(customer['segment'], segment)
            self.assertTrue(set(flags) <= customer['flags'])
            self.assertEqual(data['crm_summary'][segment], 1)
            self.assertEqual(sum(data['crm_summary'][s] for s in ('HOT','WARM','COLD','PAID')), 1)
        check('COLD','registered')
        self.record('lesson_opened')
        check('COLD','opened')
        for pk, flag in [(1,'one'),(2,'two'),(3,'three')]:
            make_lesson(pk)
            QuizAttempt.objects.update_or_create(user_id=str(self.person.pk), lesson_id=pk, defaults={'is_passed':True})
            check('WARM' if pk == 3 else 'COLD', flag)
        check('WARM','no_view')
        QuizAttempt.objects.all().delete()
        self.record('paywall_viewed', at=timezone.now()-timedelta(days=10))
        check('WARM','view')
        self.record('whatsapp_opened')
        check('HOT','wa')
        self.record('paywall_purchase_clicked')
        self.record('paywall_purchase_clicked')
        check('HOT','click')
        UserProfile.objects.update(is_paid=True)
        check('PAID')
        self.assertIsNone(report(self.params)['users'][0]['confirmed_at'])
        Purchase.objects.create(user=self.person)
        check('PAID','buyer')

    def test_identity_search_profile_and_manual_contact(self):
        self.client.force_login(self.owner)
        for term in ('m-LEARN', '123-45', '8701123', str(self.person.pk)):
            response = self.client.post(self.url, dict(self.params,q=term,user=self.person.pk))
            self.assertContains(response, self.person.username)
            self.assertContains(response, self.profile.phone)
            self.assertContains(response, 'Расталмаған')
            self.assertContains(response, 'https://wa.me/77011234567')
            url = reverse('admin:lessons_userprofile_change',args=[self.profile.pk])
            self.assertContains(response,url)
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertFalse(Event.objects.exists())
        for bad in ('javascript:77701234567', '+8 7011234567', '７７０１１２３４５６７', '+77#011234567'):
            self.assertFalse(whatsapp_digits(bad))
        self.assertEqual(whatsapp_digits('8 (701) 123-45-67'), '77011234567')

    def test_permissions_and_literal_identifiers_in_both_exports(self):
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(self.url,self.params), self.person.username)
        for forged in ({'contacts':1,'export':'xlsx'}, {'internal':1}, {'q':'crm-learner'}):
            self.assertEqual(self.client.post(self.url,dict(self.params,**forged)).status_code,403)
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_customer_contacts'))
        self.assertContains(self.client.post(self.url,self.params), self.person.username)
        self.assertEqual(self.client.post(self.url,dict(self.params,contacts=1,export='xlsx')).status_code,403)
        self.viewer.user_permissions.add(Permission.objects.get(codename='export_customer_contacts'))
        for prefix in '=+-@':
            name = prefix+'example'
            User.objects.filter(pk=self.person.pk).update(username=name)
            book = self.export(contacts=1)
            sheet = book['Users']
            self.assertEqual([(c.value,c.data_type) for c in sheet[2][1:3]], [(name,'s'),(self.profile.phone,'s')])
        plain = self.export()
        self.assertEqual(book.sheetnames,plain.sheetnames)
        self.assertNotIn('Current username', list(plain['Users'].values)[0])
        for sheet in plain:
            self.assertNotIn(self.profile.phone,str(list(sheet.values)))
        entries = LogEntry.objects.filter(object_repr='Analytics XLSX')
        self.assertEqual(entries.filter(change_message__contains='contacts=True').count(),4)
        self.assertEqual(entries.filter(change_message__contains='contacts=False').count(),1)

    def test_filter_scope_sort_limits_and_bounded_queries(self):
        self.record('paywall_viewed')
        cold = User.objects.create_user('new')
        self.client.force_login(self.owner)
        params = dict(self.params,segment='WARM',q='crm')
        view = self.client.post(self.url,params)
        self.assertEqual([u['id'] for u in view.context_data['people']], [self.person.pk])
        book = self.export(segment='WARM',q='crm')
        self.assertEqual(list(book['Users'].values)[1][0],self.person.pk)
        self.assertEqual(book['Users'].max_row,2)
        self.assertEqual(book['User_Journeys'].max_row,2)
        self.assertEqual(dict((k,v) for k,v,_ in list(book['Overview'].values)[1:])['WARM'],1)
        self.assertEqual(report(dict(self.params,sort='joined'))['users'][0]['id'],cold.pk)
        with patch('insights.reports.LIMIT_USERS',1), self.assertRaises(ReportError):
            report(self.params)
        with CaptureQueriesContext(connection) as before:
            report(self.params,contacts=True)
        User.objects.bulk_create([User(username=f'bench-{i}') for i in range(1000)])
        UserProfile.objects.bulk_create([UserProfile(user_id=pk) for pk in
                                         User.objects.filter(username__startswith='bench-').values_list('pk',flat=True)])
        with CaptureQueriesContext(connection) as after:
            data = report(self.params,contacts=True)
        self.assertEqual(len(after), len(before))
        self.assertEqual(len(data['users']), 1002)

    def test_internal_visits_exclusion_preserves_unrelated_anonymous_visit(self):
        group = Group.objects.create(name='OqyAI Analytics Test')
        marked = User.objects.create_user('manually-marked')
        marked.groups.add(group)
        for user in (self.owner,self.viewer,marked,None):
            visit = Visit.objects.create(visitor=self.visit.visitor,user=user,landing='/')
            Event.objects.create(user=None,visit=visit,kind='page_view',path='/')
        self.client.force_login(self.owner)
        normal = report(self.params)
        self.assertEqual((normal['totals']['visits'],len(normal['events']),len(normal['users'])),(1,1,1))
        book = self.export()
        self.assertEqual(book['Events'].max_row,2)
        debug = self.export(internal=1)
        self.assertEqual((debug['Events'].max_row,debug['Users'].max_row),(5,5))


class DeliveryIdentityTests(TestCase):
    def test_old_document_rejected_after_account_switch_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        one, two = (User.objects.create_user(n) for n in ('one','two'))
        client.force_login(one)
        actor = client.get('/').context['analytics_actor']
        def post(token):
            return client.post('/analytics/events/', {'type':'page_view','id':str(uuid.uuid4()),'path':'/'},
                content_type='application/json',HTTP_X_ANALYTICS_ACTOR=token,HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(post(actor).status_code,204)
        client.force_login(two)
        self.assertEqual(post(actor).status_code,403)
        second = client.get('/').context['analytics_actor']
        self.assertEqual(post(second).status_code,204)
        client.logout()
        client.get('/')
        self.assertEqual(post(second).status_code,403)
        self.assertEqual(Event.objects.filter(kind='page_view').count(),2)

    def test_only_allowlisted_audio_context_accepted(self):
        actor = self.client.get('/').context['analytics_actor']
        data = dict(type='audio_error',path='/lesson/1/',id=str(uuid.uuid4()))
        context = dict(section='content',phase='preload',error='source')
        for ctx in (dict(context,url='/private'),dict(context,error='raw-url'),dict(context,phase='unknown')):
            self.assertEqual(self.client.post('/analytics/events/',dict(data,context=ctx),
                content_type='application/json',HTTP_X_ANALYTICS_ACTOR=actor).status_code,400)
        self.assertEqual(self.client.post('/analytics/events/',dict(data,context=context),
            content_type='application/json',HTTP_X_ANALYTICS_ACTOR=actor).status_code,204)
        self.assertEqual(Event.objects.get(kind='audio_error').context,context)


class LockedIngestionTests(TransactionTestCase):
    def test_concurrent_writer_returns_503_then_stable_uuid_succeeds_once(self):
        client = Client()
        actor = client.get('/register/').context['analytics_actor']
        def post(key):
            return client.post('/analytics/events/',dict(type='page_view',path='/register/',id=str(key)),
                               content_type='application/json',HTTP_X_ANALYTICS_ACTOR=actor)
        self.assertEqual(post(uuid.uuid4()).status_code,204)
        if connection.vendor == 'mysql':
            with connection.cursor() as cursor:
                cursor.execute('SET SESSION innodb_lock_wait_timeout = 1')
        locked, release = Signal(), Signal()
        def hold_lock():
            try:
                with transaction.atomic():
                    Visitor.objects.update(client_events=0)
                    locked.set()
                    release.wait(15)
            finally:
                connections.close_all()
        key = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(hold_lock)
            try:
                self.assertTrue(locked.wait(5))
                with self.assertLogs('insights.views',level='WARNING') as logs:
                    self.assertEqual(post(key).status_code,503)
                self.assertIn(f'vendor={connection.vendor} reason=lock',logs.output[0])
                self.assertFalse(Event.objects.filter(pk=key).exists())
            finally:
                release.set()
            future.result()
        self.assertEqual(post(key).status_code,204)
        self.assertEqual(post(key).status_code,204)
        self.assertEqual(Event.objects.filter(pk=key).count(),1)


class NotificationClaimTests(TransactionTestCase):
    def test_second_worker_cannot_resend_an_inflight_registration_alert(self):
        from lessons.models import RegistrationNotification
        from lessons.services.registration_notifications import process_registration_notifications

        user = User.objects.create_user('signup')
        UserProfile.objects.create(user=user)
        job = RegistrationNotification.objects.create(user=user)
        claimed, release = Signal(), Signal()
        def send(*args):
            claimed.set()
            return release.wait(10)

        def worker():
            try:
                return process_registration_notifications(1)
            finally:
                connections.close_all()
        with patch('lessons.services.registration_notifications.send_registration_notification', side_effect=send) as network:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(worker)
                try:
                    self.assertTrue(claimed.wait(5))
                    self.assertEqual(process_registration_notifications(1),0)
                finally:
                    release.set()
                self.assertEqual(future.result(),1)
            network.assert_called_once()
        job.refresh_from_db()
        self.assertEqual((job.status,job.attempts),('sent',1))
