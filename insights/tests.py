import json
import uuid
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook

from lessons.models import QuizAttempt, UserProfile
from lessons.test_learning_flow import make_lesson
from whatsapp_agent.services import _build_payment_reply, _build_sales_system_prompt, evaluate_receipt
from .models import Event, PendingEvent, Purchase, Visit, Visitor
from .purchases import confirm_course_payment
from .reports import ZONE, ReportError, options, report
from .tracking import drain
from .workbook import workbook


class FunnelTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('learner')
        self.profile=UserProfile.objects.create(user=self.user)
        self.client.force_login(self.user)
        for pk in (1,2,3,4,251,252,253,254):
            make_lesson(pk)

    def complete(self, lesson):
        data=self.client.get(f'/start-quiz/{lesson}/').json()
        for question in data['questions']:
            payload=dict(attempt_token=data['attempt_token'],question_id=question['id'],
                         answer=question['english_word'].replace('word','meaning'))
            response=self.client.post(f'/submit-answer/{lesson}/',payload).json()
        self.client.post(f'/submit-answer/{lesson}/',payload)
        return response

    def test_boundary_and_persistent_offer(self):
        self.assertIsNone(self.client.get('/lesson/3/').context['subscription_offer'])
        for pk in (1,2,3):
            result=self.complete(pk)
        self.assertIn('3 сабақты',result['subscription_offer']['title'])
        self.assertFalse(result['can_continue'])
        self.assertEqual(self.client.get('/').context['subscription_offer']['url'],'/advertisement/')
        drain()
        self.assertEqual(Event.objects.filter(kind='free_course_completed',user=self.user).count(),1)
        self.assertEqual(Event.objects.filter(kind='lesson_completed',user=self.user).count(),3)
        self.assertEqual(Event.objects.filter(kind='quiz_completed',user=self.user).count(),3)
        self.assertEqual(self.client.get('/lesson/4/').url,'/advertisement/')

    def test_paid_and_russian_exception(self):
        self.profile.is_paid=True
        self.profile.save()
        result=self.complete(3)
        self.assertTrue(result['can_continue'])
        self.assertIsNone(result['subscription_offer'])
        self.profile.is_paid=False
        self.profile.save()
        self.assertTrue(self.complete(253)['can_continue'])
        self.assertEqual(self.client.get('/lesson/254/').status_code,200)
        self.profile.role='teacher'
        self.profile.save()
        self.assertEqual(self.client.get('/lesson/253/').context['subscription_offer']['url'],'/advertisement/?track=ru')
        self.assertEqual(self.client.get('/lesson/254/').url,'/advertisement/?track=ru')

    @override_settings(COURSE_PRICE_KZT=15000)
    def test_prices_and_handoff(self):
        for track,year in [('kk','жыл'),('ru','год')]:
            response=self.client.get('/advertisement/',{'track':track})
            self.assertContains(response,'15 000 ₸')
            self.assertContains(response,'/ '+year)
            for _ in range(2):
                result=self.client.post('/advertisement/purchase/',{'handoff':response.context['handoff']})
                self.assertEqual(urlsplit(result.url).hostname,'wa.me')
                self.assertIn('Kaspi',parse_qs(urlsplit(result.url).query)['text'][0])
        drain()
        self.assertEqual(Event.objects.filter(kind='whatsapp_opened',user=self.user).count(),2)
        self.assertEqual(Event.objects.filter(kind='paywall_purchase_clicked').count(),2)
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(Event.objects.filter(kind='purchase_completed').exists())

    @override_settings(COURSE_PRICE_KZT=16321)
    def test_price_setting_reaches_every_sales_surface(self):
        self.assertContains(self.client.get('/advertisement/'),'16 321')
        self.assertContains(self.client.get('/'),'16 321')
        for lang in ('kk','ru'):
            self.assertIn('16321',_build_sales_system_prompt(lang))
            self.assertIn('16321',_build_payment_reply(Mock(preferred_language=lang,language=lang)))
        with patch('whatsapp_agent.services.analyze_receipt_text',return_value={
            'amount_detected':0,'receiver_phone_detected':False,'receiver_name_detected':False,'timestamp_detected':False,
            'validation_confidence':0,'is_validated':False,'validation_notes':''}) as analyze:
            evaluate_receipt(Mock(file=None))
            self.assertEqual(analyze.call_args.args[1],16321)

    def test_analytics_failure_does_not_undo_pass_or_handoff(self):
        with patch('insights.tracking.PendingEvent.objects.get_or_create',side_effect=OperationalError('offline')):
            self.assertTrue(self.complete(3)['passed'])
            page=self.client.get('/advertisement/')
            self.assertEqual(self.client.post('/advertisement/purchase/',{'handoff':page.context['handoff']}).status_code,302)
        self.assertTrue(QuizAttempt.objects.get(user_id=str(self.user.id),lesson_id=3).is_passed)


class TrackingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client=Client(enforce_csrf_checks=True)
        self.actor = self.client.get('/register/').context['analytics_actor']
        self.token=self.client.cookies['csrftoken'].value

    def post(self,data, **headers):
        return self.client.post('/analytics/events/',json.dumps(data),content_type='application/json',
                                HTTP_X_CSRFTOKEN=self.token,HTTP_X_ANALYTICS_ACTOR=self.actor,**headers)

    def event(self,kind='page_view',path='/register/'):
        return dict(id=str(uuid.uuid4()),type=kind,path=path)

    def test_visitor_linkage_registration_login_and_dedup(self):
        event=self.event()
        event['campaign']={'utm_source':'Threads','utm_campaign':'spring','utm_content':'unsafe@example.org'}
        for _ in range(2):
            self.assertEqual(self.post(event).status_code,204)
        self.assertEqual(Event.objects.filter(kind='page_view').count(),1)
        self.assertIsNone(Event.objects.get(kind='page_view').user_id)
        response=self.client.post('/register/',dict(username='learner',phone='+77011234567',role='student',
            password1='StrongPass123',password2='StrongPass123',csrfmiddlewaretoken=self.token))
        self.assertEqual(response.status_code,302)
        drain()
        self.assertEqual(Visit.objects.count(),1)
        visit=Visit.objects.get()
        self.assertEqual((visit.source,visit.campaign,visit.content),('threads','spring',''))
        self.assertEqual(set(Event.objects.values_list('user_id',flat=True)),{User.objects.get(username='learner').pk})
        for kind in ('signup_completed','login_completed','session_started'):
            self.assertEqual(Event.objects.filter(kind=kind).count(),1)

    def test_denials_and_size(self):
        event=self.event()
        self.assertEqual(self.client.post('/analytics/events/',event,content_type='application/json').status_code,403)
        self.assertEqual(self.post(event,HTTP_ORIGIN='https://other.invalid').status_code,403)
        for changes in ({'type':'purchase_completed'},{'type':'lesson_completed'},{'user_id':1},
                        {'path':'/register/?email=a'},{'campaign':{'phone':'123'}},{'path':'/admin/'},
                        {'id':'bad'},{'path':'/lesson/9999999999999/'}):
            self.assertEqual(self.post(dict(event,**changes)).status_code,400)
        self.assertEqual(self.post(dict(event,metadata='x'*2200)).status_code,413)
        self.assertFalse(Event.objects.exists())

    def test_semantic_events_rate_and_privacy(self):
        self.assertEqual(self.post(self.event('audio_play','/lesson/1/')).status_code,204)
        self.assertEqual(Event.objects.get(kind='audio_play').lesson,1)
        self.assertEqual(self.post(self.event(),HTTP_DNT='1').status_code,204)
        self.assertFalse(Event.objects.filter(kind='page_view').exists())
        Visitor.objects.update(client_events=90, rate_window=timezone.now())
        self.assertEqual(self.post(self.event()).status_code,429)

    def test_inactivity_creates_second_visit(self):
        self.post(self.event())
        Visit.objects.update(started=timezone.now()-timedelta(hours=1),last_seen=timezone.now()-timedelta(minutes=31))
        self.post(self.event())
        self.assertEqual(Visit.objects.count(),2)

    def test_cleanup_preview_apply(self):
        self.post(self.event())
        past=timezone.now()-timedelta(days=190)
        Event.objects.update(at=past)
        Visit.objects.update(started=past,last_seen=past)
        call_command('prune_analytics',dry_run=True,stdout=StringIO())
        self.assertTrue(Event.objects.exists())
        call_command('prune_analytics',apply=True,stdout=StringIO())
        self.assertFalse(Visitor.objects.exists())


class ReportTests(TestCase):
    url='/admin/insights/visit/'

    def setUp(self):
        self.owner=User.objects.create_superuser('owner')
        self.learner=User.objects.create_user('private-email@example.com')
        self.profile=UserProfile.objects.create(user=self.learner)
        self.client.force_login(self.owner)

    def test_verified_manual_activation_is_idempotent(self):
        qs=UserProfile.objects.filter(pk=self.profile.pk)
        with self.assertRaises(PermissionDenied):
            confirm_course_payment(self.learner,qs)
        self.assertEqual(confirm_course_payment(self.owner,qs),1)
        self.assertEqual(confirm_course_payment(self.owner,qs),0)
        drain()
        self.assertEqual(Purchase.objects.get().confirmed_by,self.owner)
        self.assertEqual(Event.objects.get(kind='purchase_completed').user,self.learner)
        self.assertTrue(qs.get().is_paid)
        other=UserProfile.objects.create(user=User.objects.create_user('legacy'),is_paid=True)
        self.assertEqual(confirm_course_payment(self.owner,UserProfile.objects.filter(pk=other.pk)),0)
        self.assertFalse(Purchase.objects.filter(user=other.user).exists())

    def test_presets(self):
        now=datetime(2026,11,20,16,tzinfo=ZONE)
        for preset,first,last in [('today',20,20),('yesterday',19,19),('seven',13,19),('fourteen',6,19),('month',1,20),
                                  ('previous',1,31),('thirty',21,19)]:
            a,b,_=options({'preset':preset},now)
            self.assertEqual((a.day,b.day),(first,last))
        for a,b in [('bad','2026-11-20'),('2026-11-21','2026-11-20')]:
            with self.assertRaises(ReportError):
                options({'preset':'custom','start':a,'end':b},now)

    def test_range_cohort_funnel_and_export(self):
        a=datetime(2024,3,8,0,tzinfo=ZONE)
        User.objects.filter(pk=self.learner.pk).update(date_joined=a)
        visit=Visit.objects.create(user=self.learner,visitor=Visitor.objects.create(first_source='threads',first_campaign='march'),landing='/',started=a,last_seen=a,source='threads',campaign='march')
        for n,(kind,lesson) in enumerate([('signup_completed',None),('page_view',None),('lesson_opened',1),('lesson_completed',1),('lesson_completed',2),
                                          ('lesson_completed',3),('free_course_completed',3),('paywall_viewed',None),
                                          ('paywall_purchase_clicked',None),('whatsapp_opened',None)]):
            Event.objects.create(visit=visit,user=self.learner,kind=kind,at=a+timedelta(seconds=n),page='quiz',path='/',lesson=lesson,track='kk')
        paid_at=a+timedelta(days=1)
        Purchase.objects.create(user=self.learner,confirmed_by=self.owner,confirmed_at=paid_at)
        Event.objects.create(user=self.learner,at=paid_at,kind='purchase_completed',page='payment',origin='staff')
        params={'preset':'custom','start':'2024-03-08','end':'2024-03-08'}
        activity=report(params)
        self.assertEqual((activity['totals']['free'],activity['totals']['paid'],activity['totals']['active']),(1,0,1))
        self.assertEqual(activity['funnel'][-1]['drop'],1)
        self.assertEqual(activity['totals']['wa_rate'],1)
        cohort=report(dict(params,mode='cohort'))
        self.assertEqual(cohort['totals']['reg_rate'],1)
        self.assertEqual(cohort['funnel'][-1]['initial'],1)
        self.assertEqual(cohort['sources'][0][:2],['threads','march'])
        self.assertEqual(cohort['sources'][0][-1],1)
        view=self.client.get(self.url,dict(params,user=self.learner.pk))
        self.assertContains(view,'private-email@example.com')
        self.assertContains(view,'WhatsApp')
        response=self.client.get(self.url,dict(params,export='xlsx'))
        self.assertEqual(response.status_code,200)
        book=load_workbook(BytesIO(b''.join(response.streaming_content)))
        self.assertEqual(book.sheetnames,['Overview','Funnel','Users','User_Journeys','Events','Sources','Definitions'])
        self.assertEqual(book['Events'].max_row,11)
        self.assertEqual(book['User_Journeys'].max_row,11)
        self.assertEqual(book['Funnel']['C3'].number_format,'0.0%')
        self.assertEqual(book['Users']['A2'].value,self.learner.pk)
        self.assertEqual(book['Events']['E2'].value,a.replace(tzinfo=None))
        self.assertNotIn(self.learner.username,str([r for s in book for r in s.values]))
        self.assertTrue(LogEntry.objects.filter(user=self.owner,object_repr='Analytics XLSX').exists())

    def test_empty_report_legacy_unknown_and_spreadsheet_strings(self):
        params={'preset':'custom','start':'2010-01-01','end':'2010-01-01'}
        data=report(params)
        self.assertIsNone(data['totals']['reg_rate'])
        self.assertIsNone(data['totals']['revenue'])
        self.assertEqual(load_workbook(workbook(data))['Users'].max_row,1)
        data=report({'preset':'today','mode':'cohort'})
        self.assertFalse(data['users'][0]['first'])
        data['users'][0]['source']='=1+2'
        self.assertEqual(load_workbook(workbook(data))['Users']['C2'].data_type,'s')

    def test_user_segment_and_distinct_actors(self):
        now = timezone.now()
        visit = Visit.objects.create(visitor=Visitor.objects.create(first_source='return-campaign'),user=self.learner,landing='/')
        for _ in range(3):
            Event.objects.create(kind='paywall_viewed',user=self.learner,visit=visit,page='advertisement',
                                 path='/advertisement/',origin='client',at=now)
        view = self.client.get(self.url, {'preset':'today','segment':'view'})
        self.assertEqual(view.context_data['people'][0]['source'],'unknown')
        self.assertEqual(view.context_data['totals']['view'],1)
        self.assertEqual([u['id'] for u in view.context_data['people']],[self.learner.pk])
        self.assertEqual(view.context_data['totals']['paid_rate'],0)
        self.assertEqual(view.context_data['totals']['visits'],1)
        self.assertEqual(self.client.get(self.url,{'preset':'today','segment':'wa'}).context_data['people'].paginator.count,0)

    def test_authorization_and_invalid_range(self):
        self.assertEqual(self.client.get(self.url,{'preset':'custom'}).status_code,400)
        self.client.logout()
        self.assertEqual(self.client.get(self.url,{'export':'xlsx'}).status_code,302)
        self.learner.is_staff=True
        self.learner.save()
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get(self.url,{'export':'xlsx'}).status_code,403)
        self.learner.user_permissions.add(Permission.objects.get(codename='view_visit'))
        self.assertEqual(self.client.get(self.url).status_code,200)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentAnalyticsTests(TransactionTestCase):
    def race(self, action):
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return action()
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            return [f.result(timeout=20) for f in futures]

    def test_confirmation_race_creates_one_purchase(self):
        actor = User.objects.create_superuser('reviewer')
        user = User.objects.create_user('student')
        profile = UserProfile.objects.create(user=user)
        self.assertEqual(sorted(self.race(lambda: confirm_course_payment(
            User.objects.get(pk=actor.pk), UserProfile.objects.filter(pk=profile.pk)))), [0, 1])
        drain()
        self.assertEqual(Event.objects.filter(kind='purchase_completed').count(), 1)

    def test_concurrent_client_uuid_and_visit(self):
        from django.db import transaction
        from .tracking import save_event
        visitor = Visitor.objects.create()
        event_id = uuid.uuid4()

        def send():
            with transaction.atomic():
                save_event(visitor.pk,None,timezone.now(),'page_view','lesson_list','/',None,'',event_id,'client')
        self.race(send)
        self.assertEqual(Visit.objects.count(), 1)
        self.assertEqual(Event.objects.filter(kind='page_view').count(), 1)
