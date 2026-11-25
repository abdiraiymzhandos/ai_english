"""Optional Chromium smoke checks using an already installed Selenium.

Run explicitly: manage.py test lessons.browser_checks (see the performance report).
Uses Django's disposable test DB/server. External CDN requests are blocked and
all AI requests are mocked; no real accounts, messages, or paid API calls.
"""
import os
import time
import unittest

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import StaleElementReferenceException
    from selenium.webdriver.chrome.service import Service
except ImportError:
    webdriver = None

from .test_learning_flow import make_lesson


@unittest.skipIf(webdriver is None, 'Optional Selenium is not installed in this interpreter')
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, DEBUG=True)
class LearningBrowserChecks(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-proxy-server')
        options.binary_location = os.getenv('OQYAI_CHROMIUM', '/snap/bin/chromium')
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        cls.browser = webdriver.Chrome(options=options, service=Service(executable_path=os.getenv('OQYAI_CHROMEDRIVER')))
        cls.browser.set_script_timeout(10)
        print('BROWSER_VERSION', cls.browser.capabilities['browserVersion'])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'browser'):
            cls.browser.quit()
        super().tearDownClass()

    def setUp(self):
        for pk in (1, 2, 3):
            make_lesson(pk)
        # Isolate input focus, navigation history and site state between journeys.
        self.browser.switch_to.new_window("tab")
        self.addCleanup(self.close_test_tab)
        self.browser.set_window_size(390, 844)
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True,
        })
        self.browser.execute_cdp_cmd('Network.enable', {})
        self.browser.execute_cdp_cmd('Network.setBlockedURLs', {'urls': [
            '*://cdn.jsdelivr.net/*', '*://cdnjs.cloudflare.com/*', '*://fonts.googleapis.com/*',
            '*://fonts.gstatic.com/*', '*://www.googletagmanager.com/*', '*://wa.me/*',
        ]})
        self.browser.execute_cdp_cmd("Storage.clearDataForOrigin", {"origin": self.live_server_url, "storageTypes": "all"})
        self.browser.get(self.live_server_url + '/lesson/1/')
        self.wait = WebDriverWait(self.browser, 8, ignored_exceptions=(StaleElementReferenceException,))
        self.wait.until(lambda d: d.execute_script('return !!window.OqyLoading && document.querySelector("#quiz-container").dataset.mounted'))
        self.browser.execute_script('window.confirm = () => true;')

    def close_test_tab(self):
        self.browser.get("about:blank")
        self.browser.close()
        self.browser.switch_to.window(self.browser.window_handles[0])

    def element(self, id):
        return self.browser.find_element(By.ID, id)

    def click(self, id):
        self.element(id).click()

    def start_quiz(self):
        self.click('start-quiz-btn')
        self.wait.until(lambda _: self.element('question-text').text == 'word1_0')

    def answer(self, correct=True):
        word = self.element('question-text').text
        choice = word.replace('word', 'meaning')
        self.wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())
        buttons = self.browser.find_elements(By.CSS_SELECTOR, '#answer-buttons button')
        button = next(button for button in buttons if (button.text == choice) == correct)
        button.click()
        return word

    def complete(self):
        for _ in range(4):
            word = self.answer()
            self.wait.until(lambda _: self.element('question-text').text != word or self.element('quiz-summary').is_displayed())

    def test_locked_account_layout_and_recovery(self):
        from datetime import timedelta
        from django.conf import settings
        from django.utils import timezone
        from .models import UserProfile
        self.login_profile_user()
        profile = UserProfile.objects.get()
        profile.lock()
        self.browser.get(self.live_server_url + '/profile/')
        self.wait.until(lambda d: d.current_url.endswith('/account-locked/'))
        self.assertEqual(self.browser.find_element(By.TAG_NAME, 'h1').text, 'Аккаунтыңыз уақытша құлыпталды')
        self.assertIn(timezone.localtime(profile.lock_until).strftime('%H:%M:%S'),
                      self.browser.find_element(By.TAG_NAME,'time').text)
        self.assertEqual(self.browser.find_element(By.CSS_SELECTOR,'.support').get_attribute('href'),
                         'https://wa.me/' + settings.COURSE_WHATSAPP_NUMBER)
        for width in (320,375,390,430,1024):
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width':width, 'height':800, 'deviceScaleFactor':1, 'mobile':width<768})
            self.assertTrue(self.browser.execute_script("""
                const links = [...document.querySelectorAll('footer a')].map(a=>a.getBoundingClientRect());
                return document.documentElement.scrollWidth <= innerWidth &&
                    getComputedStyle(document.querySelector('article')).borderRadius !== '0px' &&
                    links.every(r=>r.width>=44 && r.height>=44 && r.left>=0 && r.right<=innerWidth) &&
                    (links[0].bottom<=links[1].top || links[0].right<=links[1].left);
            """))
        self.browser.execute_script("document.querySelector('.support').focus()")
        self.browser.switch_to.active_element.send_keys(Keys.TAB)
        self.assertEqual(self.browser.switch_to.active_element.get_attribute('href'),self.live_server_url+'/login/')
        self.assertGreater(int(self.element('countdown').get_attribute('data-end')),
                           int(self.element('countdown').get_attribute('data-now')))
        # The displayed clock advances using monotonic elapsed time, independent of the device wall clock.
        old_text = self.element('countdown').text
        self.browser.execute_script("""
            const original = performance.now.bind(performance);
            performance.now = () => original() + 120000;
        """)
        self.wait.until(lambda _: self.element('countdown').text != old_text)
        UserProfile.objects.filter(pk=profile.pk).update(lock_until=timezone.now()-timedelta(seconds=1))
        self.browser.refresh()
        self.assertFalse(self.browser.find_elements(By.ID,'countdown'))
        self.browser.find_element(By.CSS_SELECTOR,'.login').click()
        self.wait.until(lambda d: d.current_url.endswith('/login/'))
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width':390, 'height':844, 'deviceScaleFactor':1, 'mobile':True})

    def test_locked_countdown_recovers_without_manual_refresh(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import UserProfile
        self.login_profile_user()
        profile = UserProfile.objects.get()
        UserProfile.objects.filter(pk=profile.pk).update(lock_until=timezone.now()+timedelta(seconds=4))
        self.browser.get(self.live_server_url + '/profile/')
        self.wait.until(lambda _: self.element('countdown').is_displayed())
        self.wait.until(lambda d: 'Алдыңғы шектеу аяқталды' in d.find_element(By.TAG_NAME,'main').text)
        self.assertFalse(self.browser.find_elements(By.ID,'countdown'))
        profile.refresh_from_db()
        self.assertIsNone(profile.lock_until)
        self.assertFalse(profile.user.devices.exists())
        self.assertTrue(self.browser.find_element(By.CSS_SELECTOR,'a.login').is_displayed())

    def test_owner_analytics_filters_and_mobile_journey(self):
        from django.contrib.auth.models import User, Permission
        self.login_profile_user()
        user = User.objects.get(username='mobile-learner-with-a-long-username')
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        user.user_permissions.add(Permission.objects.get(codename='view_visit'))
        learner = User.objects.create_user('crm-browser-learner')
        self.browser.get(self.live_server_url + '/admin/insights/visit/')
        self.assertIn('Сатылым аналитикасы', self.browser.title)
        preset = self.browser.find_element(By.NAME, 'preset')
        self.assertEqual(preset.get_attribute('value'), 'seven_inclusive')
        self.assertIn('Соңғы 7 күн (бүгінді қоса)', preset.text)
        self.assertIn('Соңғы 7 толық күн', preset.text)
        for width in (320, 390, 1024):
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width':width,'height':740,'deviceScaleFactor':1,'mobile':width<768})
            self.assertTrue(self.browser.execute_script("""
                return document.documentElement.scrollWidth<=innerWidth &&
                       document.querySelector('button[value=xlsx]').offsetWidth > 0
            """))
        self.browser.find_element(By.CSS_SELECTOR,'a[href*="user="][href$="#journey"]').click()
        self.wait.until(lambda _: self.element('journey').is_displayed())
        self.assertIn(str(learner.pk), self.element('journey').text)
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})

    def test_threads_signup_checkout_return_campaign_and_workbook(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from django.contrib.auth.models import User
        from insights.models import Event, PendingEvent, Visit
        from insights.tracking import drain
        self.browser.get('about:blank')
        self.browser.execute_cdp_cmd('Storage.clearDataForOrigin', {'origin': self.live_server_url, 'storageTypes': 'all'})
        self.browser.get(self.live_server_url + '/?utm_source=threads&utm_medium=social&utm_campaign=test')
        self.wait.until(lambda _: Visit.objects.filter(user=None, source='threads', medium='social', campaign='test').exists())
        self.browser.get(self.live_server_url + '/register/')
        for field,value in [('username','threads-learner'),('phone','7012345678'),('password1','StudyCourse9876'),('password2','StudyCourse9876')]:
            self.element('id_' + field).send_keys(value)
        self.browser.execute_script("document.querySelector('[name=role][value=student]').click()")
        self.browser.find_element(By.CSS_SELECTOR, '.register-form button').click()
        self.wait.until(lambda _: self.browser.current_url == self.live_server_url + '/')
        user = User.objects.get(username='threads-learner')
        self.browser.get(self.live_server_url + '/lesson/1/')
        self.wait.until(lambda _: Event.objects.filter(kind='lesson_opened',user=user).exists())
        self.browser.get(self.live_server_url + '/advertisement/')
        self.wait.until(lambda _: Event.objects.filter(kind='paywall_viewed',visit__source='threads',user=user).exists())
        self.browser.find_element(By.CSS_SELECTOR,'form button').click()
        self.wait.until(lambda _: PendingEvent.objects.filter(kind='whatsapp_opened', user=user).exists())
        self.wait.until(lambda d: not d.current_url.startswith(self.live_server_url))
        self.browser.get(self.live_server_url + '/?utm_source=tiktok&utm_campaign=return')
        self.wait.until(lambda _: Visit.objects.filter(user=user,source='tiktok').exists())
        drain()
        self.assertTrue(Event.objects.filter(kind='whatsapp_opened',user=user,visit__source='threads').exists())
        self.client.force_login(User.objects.create_superuser('workbook-owner'))
        response = self.client.post('/admin/insights/visit/', {'preset':'today','mode':'cohort','export':'xlsx'})
        book = load_workbook(BytesIO(b''.join(response.streaming_content)))
        columns, row = list(book['Users'].values)
        values = dict(zip(columns,row))
        self.assertEqual((values['First recorded source'],values['Campaign'],values['Customer segment (now)']),
                         ('threads','test','HOT'))
        self.assertEqual(list(book['Sources'].values)[1][:3], ('threads','test',1))

    def test_observable_audio_failures(self):
        from insights.models import Event
        from .models import Explanation
        Explanation.objects.create(lesson_id=1,section='grammar',text='test',audio_url='/missing-test-audio.mp3')
        self.browser.get(self.live_server_url + '/lesson/1/')
        errors = Event.objects.filter(kind='audio_error', lesson=1)
        self.wait.until(lambda _: errors.filter(context__section='grammar',context__phase='preload').exists())
        attempt = self.browser.execute_cdp_cmd('Runtime.evaluate', {
            'userGesture': True, 'awaitPromise': True, 'returnByValue': True,
            'expression': """(async () => {
                const audio = document.createElement('audio');
                audio.preload = 'none';
                document.querySelector('#vocabulary-section').append(audio);
                audio.src = '/missing-playback-test.mp3';
                try { await audio.play(); return 'played'; } catch (error) { return error.name; }
            })()""",
        })
        self.assertEqual(attempt['result'].get('value'), 'NotSupportedError')
        self.wait.until(lambda _: errors.filter(context__section='vocabulary',context__phase='playback').exists())
        self.browser.execute_script("""
          document.querySelector('#grammar-section audio').dispatchEvent(new Event('error'));
          const marker = document.createElement('button');
          marker.dataset.analyticsAction = 'quiz_catalog_clicked';
          document.body.append(marker);
          marker.click();
        """)
        self.wait.until(lambda _: Event.objects.filter(kind='quiz_catalog_clicked').exists())
        self.assertEqual(errors.filter(context__section='grammar').count(), 1)

    def test_subscription_result_offer_and_whatsapp_handoff(self):
        from insights.models import Event, PendingEvent, Purchase
        from insights.tracking import drain
        from .models import QuizAttempt, UserProfile
        self.login_profile_user(translator=False)
        uid = UserProfile.objects.get().user_id
        for pk in (1, 2):
            QuizAttempt.objects.create(user_id=str(uid), lesson_id=pk, is_passed=True, completed=True)
        self.browser.get(self.live_server_url + '/lesson/3/')
        self.click('start-quiz-btn')
        self.wait.until(lambda _: self.element('question-text').text == 'word3_0')
        self.complete()
        self.assertIn('3 сабақты', self.element('quiz-result').text)
        self.wait.until(lambda _: Event.objects.filter(kind='subscription_cta_viewed', user_id=uid).exists())
        for width, height in ((320,480),(375,667),(390,844),(430,932)):
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
            geometry = self.browser.execute_script("""
                const e=document.querySelector('#subscription-result'), r=e.getBoundingClientRect();
                const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
                return {top:r.top, bottom:r.bottom, left:r.left, right:r.right, height:innerHeight,
                        width:innerWidth, hit:hit?.id, visible:e.contains(hit)};
            """)
            self.assertTrue(geometry['top'] >= 0 and geometry['bottom'] <= geometry['height']
                            and geometry['left'] >= 0 and geometry['right'] <= geometry['width']
                            and geometry['visible'], geometry)
        screenshot_dir = os.environ.get('OQYAI_FUNNEL_SCREENSHOTS')
        if screenshot_dir:
            self.browser.save_screenshot(os.path.join(screenshot_dir, 'oqyai-free-course-result.png'))
        self.click('subscription-result')
        self.wait.until(lambda _: Event.objects.filter(kind='paywall_viewed',user_id=uid).exists())
        self.assertTrue(Event.objects.filter(kind='subscription_cta_clicked',user_id=uid).exists())
        for width in (320,375,390,430,1024):
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width':width,'height':667,'deviceScaleFactor':1,'mobile':width<768})
            self.assertTrue(self.browser.execute_script("""
                const b=document.querySelector('form button'), r=b.getBoundingClientRect();
                return document.documentElement.scrollWidth<=innerWidth && r.height>=44 &&
                       r.left>=0 && r.right<=innerWidth;
            """))
            if screenshot_dir and width == 390:
                self.browser.save_screenshot(os.path.join(screenshot_dir, 'oqyai-annual-course-offer.png'))
        self.browser.find_element(By.CSS_SELECTOR,'form button').click()
        self.wait.until(lambda _: PendingEvent.objects.filter(kind='whatsapp_opened').exists())
        drain()
        self.assertTrue(Event.objects.filter(kind='paywall_purchase_clicked',user_id=uid).exists())
        self.assertFalse(Purchase.objects.exists())
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})

    def test_mobile_pass_next_retake_failed_retake_and_keyboard(self):
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, 'script[src$="loading.js"]')), 1)
        self.browser.execute_script('''
            window.quizLatencies = [];
            let started;
            document.addEventListener('click', event => {
              if (event.target.closest('#answer-buttons button')) started = performance.now();
            }, true);
            new MutationObserver(() => {
              if (started !== undefined) { quizLatencies.push(performance.now() - started); started = undefined; }
            }).observe(document.getElementById('question-text'), {childList: true});
        ''')
        self.start_quiz()
        self.complete()
        self.assertIn('4', self.element('quiz-result-detail').text)
        self.assertFalse(self.element('timer').is_displayed())
        self.assertTrue(self.element('next-lesson-link').is_displayed())
        self.browser.save_screenshot('/tmp/oqyai-refined-pass.png')
        self.assertTrue(self.element('next-lesson-link').get_attribute('href').endswith('/lesson/2/'))
        self.assertEqual(self.browser.execute_script('return document.activeElement.id'), 'retake-quiz-btn')
        print('BROWSER_QUIZ_TRANSITION_MS', self.browser.execute_script('return window.quizLatencies'))
        if os.getenv('OQYAI_BROWSER_SCREENSHOT'):
            self.browser.execute_script("document.getElementById('quiz-container').scrollIntoView({block: 'center'});")
            self.browser.save_screenshot(os.environ['OQYAI_BROWSER_SCREENSHOT'])
        self.element('retake-quiz-btn').send_keys(Keys.ENTER)
        self.wait.until(lambda _: self.element('quiz-content').is_displayed())
        self.assertEqual(self.element('score').text, '✓ Ұпай: 0')
        self.assertEqual(self.element('timer').get_attribute('aria-valuenow'), '5')
        for index in range(3):
            word = self.answer(correct=False)
            if index == 2:
                WebDriverWait(self.browser, 2, poll_frequency=0.03).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, '#attempts .spent')) == 3
                )
                self.assertTrue(self.browser.find_element(By.CSS_SELECTOR, '.quiz-answer.btn-danger').is_displayed())
                self.assertTrue(self.browser.find_element(By.CSS_SELECTOR, '.quiz-answer.btn-success').is_displayed())
            self.wait.until(lambda _: self.element('question-text').text != word or self.element('quiz-summary').is_displayed())
        self.assertEqual(self.element('quiz-dialog').get_attribute('data-result'), 'fail')
        self.assertFalse(self.element('timer').is_displayed())
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, '#attempts i:not(.spent)')), 0)
        self.browser.save_screenshot('/tmp/oqyai-refined-fail.png')
        self.browser.get(self.live_server_url + '/')
        self.assertIn('1/3', self.browser.find_element(By.CSS_SELECTOR, '.progress-text').text)
        self.browser.get(self.live_server_url + '/lesson/1/')
        self.assertIn('қайта тапсыру', self.element('start-quiz-btn').text)
        self.assertEqual(self.element('quiz-previous-value').text, '4 / 4')
        self.browser.execute_script("window.scrollTo(0, document.documentElement.scrollHeight)")
        self.browser.find_element(By.CSS_SELECTOR, '.quiz-launch').screenshot('/tmp/oqyai-polish-retake.png')
        self.click('start-quiz-btn')
        self.wait.until(lambda _: self.element('question-text').text == 'word1_0')
        self.assertEqual(self.element('score').text, '✓ Ұпай: 0')

    def test_lost_answer_response_retries_idempotently_and_advances(self):
        self.start_quiz()
        self.browser.execute_script('''
            const realFetch = window.fetch;
            let once = true;
            window.fetch = async (...args) => {
              const response = await realFetch(...args);
              if (once && String(args[0]).includes('/submit-answer/')) {
                once = false; throw new Error('Simulated lost response');
              }
              return response;
            };
        ''')
        self.answer()
        self.wait.until(lambda _: self.element('quiz-retry-btn').is_displayed())
        self.click('quiz-retry-btn')
        self.wait.until(lambda _: self.element('question-text').text == 'word1_1')
        self.assertEqual(self.element('score').text, '✓ Ұпай: 1')
        self.assertTrue(self.browser.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())

    def test_five_second_timeout_counts_once_and_resume_after_history_restore(self):
        self.start_quiz()
        begin = time.perf_counter()
        self.wait.until(lambda _: self.element('question-text').text == 'word1_1')
        elapsed = time.perf_counter() - begin
        self.assertGreaterEqual(elapsed, 4.5)
        self.assertLess(elapsed, 7)
        self.assertEqual(self.element('attempts').get_attribute('aria-label'), '2 мүмкіндік қалды')
        self.browser.execute_script("window.dispatchEvent(new PageTransitionEvent('pagehide')); window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));")
        self.wait.until(lambda _: self.browser.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())
        self.assertEqual(self.element('score').text, '✓ Ұпай: 0')
        self.assertEqual(self.element('attempts').get_attribute('aria-label'), '2 мүмкіндік қалды')

    def test_shared_loading_timeout_concurrency_failure_and_restoration(self):
        result = self.browser.execute_async_script('''
            const done = arguments[0];
            (async () => {
              const button = document.getElementById('start-quiz-btn');
              const realFetch = window.fetch;
              window.fetch = () => new Promise(() => {});
              const request = OqyLoading.json('/hang', {}, {button, timeout: 230});
              const immediate = button.disabled && button.getAttribute('aria-busy') === 'true';
              let timeout = false;
              try { await request; } catch (error) { timeout = error.name === 'TimeoutError'; }
              const restored = !button.disabled && !button.hasAttribute('aria-busy');
              const finishA = OqyLoading.begin({delay: 0});
              const finishB = OqyLoading.begin({delay: 0});
              finishA();
              const concurrent = document.getElementById('oqy-loading-bar').classList.contains('is-loading');
              finishB();
              OqyLoading.navigate(button);
              window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
              const cleared = !document.getElementById('oqy-loading-bar').classList.contains('is-loading');
              window.fetch = async () => ({ok: false, status: 500, json: async () => ({error: 'Server error'})});
              let failed = false;
              try { await OqyLoading.json('/fail', {}, {button}); } catch (error) { failed = error.status === 500; }
              window.fetch = realFetch;
              done({immediate, timeout, restored, concurrent, cleared, failed, enabled: !button.disabled});
            })().catch(error => done({error: String(error)}));
        ''')
        self.assertEqual(result, {key: True for key in ['immediate', 'timeout', 'restored', 'concurrent', 'cleared', 'failed', 'enabled']})

    def test_navigation_ignores_external_download_hash_and_modifier_links(self):
        result = self.browser.execute_script('''
            const outcomes = [];
            window.addEventListener('click', event => event.preventDefault());
            for (const [href, attributes, modifiers] of [
              ['https://example.com/payment', {}, {}], ['#vocabulary-section', {}, {}],
              ['/lesson/2/', {download: ''}, {}], ['/lesson/2/', {target: '_blank'}, {}],
              ['/lesson/2/', {}, {ctrlKey: true}], ['/lesson/2/', {}, {}],
            ]) {
              const link = document.createElement('a'); link.href = href;
              for (const [name, value] of Object.entries(attributes)) link.setAttribute(name, value);
              document.body.appendChild(link);
              link.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, button: 0, ...modifiers}));
              outcomes.push(!!document.getElementById('oqy-loading-bar')?.classList.contains('is-loading'));
              OqyLoading.reset(); link.remove();
            }
            return outcomes;
        ''')
        self.assertEqual(result, [False, False, False, False, False, True])

    def test_native_form_guard_preserves_submitter_and_releases_on_restore(self):
        result = self.browser.execute_script('''
            const form = document.createElement('form'); form.action = '/login/'; form.method = 'post';
            const button = document.createElement('button'); button.type = 'submit'; button.name = 'action'; button.value = 'save';
            form.appendChild(button); document.body.appendChild(form);
            const send = () => {
              const event = new SubmitEvent('submit', {bubbles: true, cancelable: true, submitter: button});
              return form.dispatchEvent(event);
            };
            const first = send(), second = send();
            const preserved = !button.disabled && new FormData(form, button).get('action') === 'save';
            window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
            const third = send(); OqyLoading.reset(); form.remove();
            return {first, second, third, preserved};
        ''')
        self.assertEqual(result, {'first': True, 'second': False, 'third': True, 'preserved': True})

    def test_chat_loading_error_and_section_switch_do_not_reload(self):
        self.browser.execute_script('''
            window.requestCount = 0;
            window.fetch = async () => {
              window.requestCount++;
              await new Promise(resolve => setTimeout(resolve, 350));
              return {ok: false, status: 500, json: async () => ({error: 'Simulated AI failure'})};
            };
        ''')
        self.browser.find_element(By.CSS_SELECTOR, '.lesson-btn[data-section="grammar"]').click()
        self.assertIn('active', self.element('grammar-section').get_attribute('class'))
        self.assertEqual(self.browser.execute_script('return window.requestCount'), 0)
        self.click('chat-open-btn')
        self.element('chat-input').send_keys('Synthetic question')
        self.click('chat-send-btn')
        self.assertFalse(self.element('chat-send-btn').is_enabled())
        self.wait.until(lambda _: self.element('chat-send-btn').is_enabled())
        self.assertIn('Simulated AI failure', self.element('chat-messages').text)
        self.assertEqual(self.browser.execute_script('return window.requestCount'), 1)

    def test_real_back_navigation_clears_loading_and_desktop_layout_mounts(self):
        self.browser.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})
        self.browser.set_window_size(1280, 900)
        self.wait.until(lambda d: d.execute_script("return innerWidth >= 1000"))
        self.browser.find_element(By.CSS_SELECTOR, 'a[href="/"]').send_keys(Keys.ENTER)
        self.wait.until(lambda d: d.current_url == self.live_server_url + '/')
        self.browser.back()
        self.wait.until(lambda d: d.current_url == self.live_server_url + '/lesson/1/')
        self.wait.until(lambda d: not d.execute_script("return document.getElementById('oqy-loading-bar')?.classList.contains('is-loading')"))
        self.assertTrue(self.element('start-quiz-btn').is_enabled())
        self.browser.set_window_size(390, 844)
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True,
        })

    def test_reduced_motion_feedback_has_no_overlay_or_animation(self):
        self.browser.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        try:
            result = self.browser.execute_script('''
                const finish = OqyLoading.begin({delay: 0});
                const style = getComputedStyle(document.getElementById('oqy-loading-bar'));
                const result = {animation: style.animationName, pointer: style.pointerEvents, height: style.height};
                finish(); return result;
            ''')
            self.assertEqual(result, {'animation': 'none', 'pointer': 'none', 'height': '3px'})
            self.assertEqual(self.browser.execute_script("return getComputedStyle(document.querySelector('#attempts i')).transitionDuration"), '0s')
            self.start_quiz()
            self.wait.until(lambda _: self.element('timer').get_attribute('aria-valuenow') == '4')
            self.assertEqual(self.browser.execute_script("return document.getElementById('timer-fill').style.transform"), 'scaleX(0.8)')
            colors = self.browser.execute_script('''
                const button = document.createElement('button'); button.className = 'quiz-answer btn-success';
                document.getElementById('answer-buttons').append(button);
                const correct = getComputedStyle(button).backgroundColor;
                button.className = 'quiz-answer btn-danger';
                const incorrect = getComputedStyle(button).backgroundColor;
                button.remove(); return {correct, incorrect};
            ''')
            self.assertEqual(colors, {'correct': 'rgb(215, 246, 223)', 'incorrect': 'rgb(255, 226, 229)'})
        finally:
            self.browser.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': []})

    def test_overlapping_requests_on_one_button_restore_initial_state(self):
        result = self.browser.execute_script('''
            const button = document.getElementById('start-quiz-btn');
            const finishA = OqyLoading.begin({button, delay: 0});
            const finishB = OqyLoading.begin({button, delay: 0});
            finishA();
            const stillBusy = button.disabled && button.getAttribute('aria-busy') === 'true';
            finishB();
            const restored = !button.disabled && !button.hasAttribute('aria-busy') && !button.classList.contains('oqy-busy');
            return {stillBusy, restored};
        ''')
        self.assertEqual(result, {'stillBusy': True, 'restored': True})

    def test_form_watchdogs_are_cancelled_on_navigation_restoration(self):
        result = self.browser.execute_script('''
            const realSet = window.setTimeout, realClear = window.clearTimeout;
            const timers = new Map(); let id = 1000000;
            window.setTimeout = (fn, delay, ...args) => {
              if (delay === 30000) { timers.set(++id, fn); return id; }
              return realSet(fn, delay, ...args);
            };
            window.clearTimeout = key => { if (!timers.delete(key)) realClear(key); };
            const form = document.createElement('form'); form.method = 'post'; form.action = '/login/';
            const button = document.createElement('button'); button.type = 'submit'; form.append(button);
            document.body.append(form);
            form.dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true, submitter: button}));
            OqyLoading.reset();
            const remaining = timers.size;
            window.setTimeout = realSet; window.clearTimeout = realClear; form.remove();
            return remaining;
        ''')
        self.assertEqual(result, 0)

    def login_profile_user(self, translator=True):
        from django.contrib.auth.models import User
        from .models import UserProfile
        user = User.objects.create_user('mobile-learner-with-a-long-username', email='long.email.address.for.layout@example.test')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.has_translator_access = translator
        profile.phone = '+70000000000'
        profile.save()
        self.client.force_login(user)
        from django.conf import settings
        self.browser.add_cookie({'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'path': '/'})
        self.browser.get(self.live_server_url + '/profile/')

    def test_profile_mobile_widths_details_and_navigation(self):
        self.login_profile_user()
        try:
            for width in (320, 375, 390, 430, 1024):
                self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': width, 'height':844, 'deviceScaleFactor':1, 'mobile':width < 768})
                self.assertEqual(self.browser.execute_script("return getComputedStyle(document.querySelector('.profile-shell')).display"), 'grid')
                self.assertTrue(self.browser.execute_script('''const panels=[...document.querySelectorAll('.profile-shell > *')];
                  return panels.every((el,i)=>!i || el.getBoundingClientRect().top>=panels[i-1].getBoundingClientRect().bottom);
                '''))
                self.assertTrue(self.browser.execute_script('return document.documentElement.scrollWidth <= innerWidth'))
                self.assertTrue(self.browser.execute_script('''return [...document.querySelectorAll('.feature-row,.continue-link,summary,.account-action')].every(el => {
                  const r=el.getBoundingClientRect();return r.height>=44 && r.left>=0 && r.right<=innerWidth;
                })'''))
                self.assertFalse(self.browser.execute_script('return document.getElementById("personal-info").open'))
                summary = self.browser.find_element(By.CSS_SELECTOR, '#personal-info summary')
                summary.send_keys(Keys.ENTER)
                self.assertTrue(self.browser.execute_script('return document.getElementById("personal-info").open'))
                self.assertTrue(self.browser.execute_script('''return [...document.querySelectorAll('.personal-info dd')].every(el=>el.scrollWidth<=el.clientWidth)'''))
                summary.send_keys(Keys.ENTER)
                self.browser.save_screenshot('/tmp/oqyai-profile-%s.png' % width)
            self.assertFalse(self.browser.execute_script("return performance.getEntriesByType('resource').some(r=>r.name.includes('translator-assistant'))"))
            self.browser.find_element(By.CSS_SELECTOR,'.continue-link').click()
            self.wait.until(lambda d:'/lesson/1/' in d.current_url)
            self.browser.back()
            self.wait.until(lambda d:'/profile/' in d.current_url)
            self.assertFalse(self.browser.execute_script("return !!document.querySelector('[aria-busy=true]')"))
        finally:
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})

    def test_translator_opens_from_profile_without_starting_microphone(self):
        self.login_profile_user()
        self.click('translator-link')
        self.wait.until(lambda d:d.find_elements(By.ID,'open-translator'))
        self.click('open-translator')
        self.wait.until(lambda d:d.find_elements(By.ID,'close-translator'))
        self.assertEqual(self.browser.execute_script('return document.activeElement.id'), 'close-translator')
        self.assertFalse(self.browser.execute_script('return window.translatorAssistant.isConnected'))
        self.element('close-translator').send_keys(Keys.ESCAPE)
        self.assertFalse(self.browser.find_elements(By.ID,'translator-modal'))
        self.assertEqual(self.browser.execute_script('return document.activeElement.id'), 'open-translator')
        self.browser.back()
        self.wait.until(lambda d:'/profile/' in d.current_url)


    def test_translator_access_error_releases_loader_and_can_retry(self):
        self.login_profile_user()
        self.click('translator-link')
        self.wait.until(lambda d:d.find_elements(By.ID, 'open-translator'))
        self.browser.execute_script("""
          window.originalTranslatorFetch = window.fetch;
          window.fetch = async () => new Response(JSON.stringify({has_access:false,error:'Қол жеткізу жоқ'}), {headers:{'Content-Type':'application/json'}});
        """)
        self.click('open-translator')
        self.wait.until(lambda d:d.find_element(By.ID,'translator-page-status').text == 'Қол жеткізу жоқ')
        self.assertTrue(self.element('open-translator').is_enabled())
        self.assertFalse(self.browser.find_elements(By.ID,'translator-modal'))
        self.assertFalse(self.browser.execute_script("return !!document.querySelector('[aria-busy=true]')"))
        self.browser.execute_script('window.fetch = window.originalTranslatorFetch')
        self.click('open-translator')
        self.wait.until(lambda d:d.find_elements(By.ID,'close-translator'))
        self.assertEqual(self.element('translator-page-status').text, '')
        self.click('close-translator')

    def test_dashboard_profile_navigation_and_logout_mobile_desktop(self):
        self.login_profile_user()
        try:
            for width in (320, 390, 1024):
                self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<768})
                self.browser.get(self.live_server_url + '/')
                self.assertFalse(self.browser.find_elements(By.CSS_SELECTOR, 'form[action="/logout/"]'))
                profile_link = self.browser.find_element(By.CSS_SELECTOR, '.auth-buttons a[href="/profile/"]')
                self.assertTrue(profile_link.is_displayed())
                self.browser.save_screenshot('/tmp/oqyai-dashboard-logout-%s.png' % width)
                self.assertTrue(self.browser.execute_script('''const r=arguments[0].getBoundingClientRect();
                  const v=document.querySelector('.auth-buttons a[href="/vocabulary/"]').getBoundingClientRect();
                  return r.left>=0 && r.right<=innerWidth && (r.top>=v.bottom || r.left>=v.right || r.bottom<=v.top);
                ''', profile_link))
                profile_link.click()
                self.wait.until(lambda d:'/profile/' in d.current_url)
                self.assertIn('Аккаунттан шығу', self.browser.find_element(By.CSS_SELECTOR,'form[action="/logout/"]').text)
            self.browser.find_element(By.CSS_SELECTOR,'form[action="/logout/"] button').click()
            self.wait.until(lambda d:'/login/' in d.current_url)
            self.browser.get(self.live_server_url + '/profile/')
            self.wait.until(lambda d:'/login/' in d.current_url)
        finally:
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})


    def test_quiz_viewport_choices_close_and_scroll_restore(self):
        try:
            for width,height in ((320,568),(375,667),(390,844),(430,932),(320,480),(1024,768)):
                self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<768})
                # Each viewport exercises a fresh learner's five-second question.
                self.browser.delete_all_cookies()
                self.browser.get(self.live_server_url + '/lesson/1/')
                launch = self.browser.find_element(By.CSS_SELECTOR, '.quiz-launch')
                self.assertTrue(self.browser.execute_script("""const el=arguments[0], r=el.getBoundingClientRect();
                  return r.left>=0 && r.right<=innerWidth && el.scrollWidth<=el.clientWidth &&
                    r.height<=innerHeight && document.getElementById('start-quiz-btn').offsetHeight>=44;""", launch))
                self.browser.execute_script("window.scrollTo(0, document.documentElement.scrollHeight)")
                self.assertTrue(self.browser.execute_script("""
                    const btn = document.getElementById('start-quiz-btn'), r = btn.getBoundingClientRect();
                    return [r.left + 10, r.right - 10].every(x =>
                      btn.contains(document.elementFromPoint(x, r.top + r.height / 2)));
                """))
                previous = self.browser.execute_script("""
                    const before = scrollY;
                    document.getElementById('start-quiz-btn').click();
                    return before;
                """)
                self.wait.until(lambda d:d.find_element(By.ID,'question-text').text=='word1_0')
                self.wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#answer-buttons button').is_enabled())
                self.assertTrue(self.browser.execute_script("return document.getElementById('quiz-dialog').open"))
                self.assertTrue(self.browser.execute_script("""return [...document.querySelectorAll('#question-text,#answer-buttons button,.quiz-header,#close-quiz-btn')].every(el=>{
                  const r=el.getBoundingClientRect();return r.top>=0 && r.bottom<=innerHeight && r.left>=0 && r.right<=innerWidth && el.scrollWidth<=el.clientWidth;
                })"""))
                self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR,'#answer-buttons button')),4)
                self.browser.save_screenshot('/tmp/oqyai-quiz-%sx%s.png' % (width,height))
                self.click('close-quiz-btn')
                self.assertAlmostEqual(self.browser.execute_script('return scrollY'), previous, delta=2, msg=(width, height))
                self.assertEqual(self.browser.execute_script('return document.activeElement.id'),'start-quiz-btn')
                self.assertFalse(self.browser.execute_script("return document.body.classList.contains('quiz-page-locked')"))
        finally:
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})

    def test_quiz_slow_load_background_and_duplicate_taps(self):
        self.browser.execute_script("""
          const realFetch=window.fetch;
          window.submits=0;
          window.fetch=async (...args)=>{
            if(String(args[0]).includes('/start-quiz/')) await new Promise(r=>setTimeout(r,1200));
            if(String(args[0]).includes('/submit-answer/')) { window.submits++; await new Promise(r=>setTimeout(r,800)); }
            return realFetch(...args);
          };
        """)
        self.click('start-quiz-btn')
        self.assertTrue(self.element('quiz-loading').is_displayed())
        self.wait.until(lambda d:d.find_elements(By.CSS_SELECTOR,'#answer-buttons button') and d.find_element(By.CSS_SELECTOR,'#answer-buttons button').is_enabled())
        self.assertEqual(self.element('timer').get_attribute('aria-valuenow'), '5')
        self.browser.execute_script("Object.defineProperty(document,'hidden',{configurable:true,value:true}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertFalse(self.browser.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())
        time.sleep(1.1)
        self.browser.execute_script("Object.defineProperty(document,'hidden',{configurable:true,value:false}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.element('question-text').text,'word1_0')
        self.wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#answer-buttons button').is_enabled())
        self.assertLessEqual(int(self.element('timer').get_attribute('aria-valuenow')), 4)
        self.browser.execute_script("const opts=[...document.querySelectorAll('#answer-buttons button')]; const good=opts.find(b=>b.textContent==='meaning1_0'); for(let i=0;i<10;i++) good.click(); opts.find(b=>b!==good).click();")
        frozen = self.element('timer-fill').get_attribute('style')
        time.sleep(0.35)
        self.assertEqual(self.element('timer-fill').get_attribute('style'), frozen)
        self.wait.until(lambda d:d.find_element(By.ID,'question-text').text=='word1_1')
        self.assertEqual(self.browser.execute_script('return window.submits'),1)
        self.assertEqual(self.element('score').text, '✓ Ұпай: 1')
        self.assertFalse(self.element('quiz-summary').is_displayed())
        self.assertEqual(self.element('timer').get_attribute('aria-valuenow'), '5')

    def test_single_timer_tracks_question_deadline(self):
        from .models import Lesson

        Lesson.objects.filter(pk=1).update(vocabulary='garden – бақша\nriver – өзен\ncloud – бұлт\nforest – орман')
        self.browser.refresh()
        launch = self.browser.find_element(By.CSS_SELECTOR, '.quiz-launch')
        self.assertIn('4 сұрақ', launch.text)
        self.assertFalse(self.element('quiz-previous-score').is_displayed())
        self.browser.execute_script("window.scrollTo(0, document.documentElement.scrollHeight)")
        launch.screenshot('/tmp/oqyai-polish-start.png')
        self.browser.execute_script("""
            const fill = document.getElementById('timer-fill');
            window.watched = {samples: [], posts: []};
            new MutationObserver(() => {
              if (document.getElementById('question-text').textContent === 'garden') {
                watched.samples.push([performance.now(), fill.getBoundingClientRect().width / fill.parentNode.clientWidth]);
              }
            }).observe(fill, {attributes: true, attributeFilter: ['style']});
            const fetchQuiz = window.fetch;
            window.fetch = (...args) => {
              if (String(args[0]).includes('/submit-answer/')) {
                watched.posts.push([performance.now(), args[1].body.get('timed_out')]);
              }
              return fetchQuiz(...args);
            };
        """)
        self.click('start-quiz-btn')
        self.wait.until(lambda _: self.element('timer').is_displayed())
        self.assertEqual(self.element('timer').text, '')
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, '#quiz-dialog [role="progressbar"]')), 1)
        self.assertEqual(self.element('timer').size['height'], 9)
        self.assertEqual(self.element('question-count').text, '1 / 4 сұрақ')
        self.browser.save_screenshot('/tmp/oqyai-polish-active.png')
        self.wait.until(lambda _: self.element('timer').get_attribute('aria-valuenow') == '1')
        self.browser.save_screenshot('/tmp/oqyai-polish-expiry.png')
        self.wait.until(lambda _: self.element('question-text').text == 'river')
        self.assertEqual(self.element('timer').get_attribute('aria-valuenow'), '5')
        self.assertEqual(self.element('attempts').get_attribute('aria-label'), '2 мүмкіндік қалды')
        samples, posts = self.browser.execute_script('return [watched.samples, watched.posts]')
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], 'true')
        self.assertAlmostEqual(posts[0][0] - samples[0][0], 5000, delta=180)
        fractions = [sample[1] for sample in samples]
        self.assertGreater(fractions[0], .99)
        self.assertEqual(fractions[-1], 0)
        self.assertEqual(fractions, sorted(fractions, reverse=True))
        self.assertGreater(len(set(fractions)), 30)

    def test_reload_resumes_same_question_deadline(self):
        self.start_quiz()
        self.wait.until(lambda _: self.element('timer').get_attribute('aria-valuenow') == '3')
        self.browser.refresh()
        self.start_quiz()
        self.wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())
        self.assertLessEqual(int(self.element('timer').get_attribute('aria-valuenow')), 3)
        self.wait.until(lambda _: self.element('question-text').text == 'word1_1')
        self.assertEqual(self.element('attempts').get_attribute('aria-label'), '2 мүмкіндік қалды')

    def test_expired_background_question_submits_once_on_return(self):
        self.start_quiz()
        self.wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '#answer-buttons button').is_enabled())
        self.browser.execute_script("""
            const fetchQuiz = window.fetch;
            window.timeoutPosts = 0;
            window.quizWasHidden = false;
            document.addEventListener('visibilitychange', () => { if (document.hidden) quizWasHidden = true; });
            window.fetch = (...args) => {
              if (String(args[0]).includes('/submit-answer/') && args[1].body.get('timed_out') === 'true') timeoutPosts++;
              return fetchQuiz(...args);
            };
        """)
        original = self.browser.current_window_handle
        self.browser.switch_to.new_window('tab')
        try:
            time.sleep(5.2)
        finally:
            self.browser.close()
            self.browser.switch_to.window(original)
        WebDriverWait(self.browser, 3).until(lambda _: self.element('question-text').text == 'word1_1')
        self.assertTrue(self.browser.execute_script('return quizWasHidden'))
        self.assertEqual(self.browser.execute_script('return timeoutPosts'), 1)
        self.assertEqual(self.element('attempts').get_attribute('aria-label'), '2 мүмкіндік қалды')

    def test_quiz_long_answers_scroll_internally_and_escape_closes(self):
        self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':320,'height':480,'deviceScaleFactor':1,'mobile':True})
        try:
            self.browser.execute_script("""
              const realFetch=window.fetch;
              window.fetch=async (...args)=>{
                const response=await realFetch(...args);
                if(!String(args[0]).includes('/start-quiz/')) return response;
                const data=await response.json();
                data.questions[0].english_word='LongVocabulary'.repeat(7);
                data.questions[0].choices=Array.from({length:4},(_,i)=>String(i)+'Ұзақ аударма '.repeat(18));
                return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
              };
            """)
            self.click('start-quiz-btn')
            self.wait.until(lambda d:d.find_elements(By.CSS_SELECTOR,'#answer-buttons button') and d.find_element(By.CSS_SELECTOR,'#answer-buttons button').is_enabled())
            self.assertTrue(self.browser.execute_script("const a=document.getElementById('answer-buttons');return a.scrollHeight>a.clientHeight && a.scrollWidth<=a.clientWidth"))
            self.browser.execute_script("document.getElementById('answer-buttons').scrollTop=9999")
            self.assertTrue(self.browser.execute_script("const r=document.querySelector('.quiz-header').getBoundingClientRect();return r.top>=0 && r.bottom<innerHeight"))
            self.browser.save_screenshot('/tmp/oqyai-quiz-long.png')
            self.element('close-quiz-btn').send_keys(Keys.ESCAPE)
            self.assertFalse(self.browser.execute_script("return document.getElementById('quiz-dialog').open"))
        finally:
            self.browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})

    def test_answer_reveal_and_wrong_retry_spend_one_heart(self):
        self.start_quiz()
        self.assertTrue(self.element('timer-fill').is_displayed())
        self.assertFalse(self.browser.find_elements(By.ID, 'progress-bar'))
        self.answer()
        WebDriverWait(self.browser, 2, poll_frequency=0.03).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, '.quiz-answer.btn-success')
        )
        self.browser.save_screenshot('/tmp/oqyai-refined-correct.png')
        self.wait.until(lambda _: self.element('question-text').text == 'word1_1')
        # Lose the first response after the server records the wrong answer.
        self.browser.execute_script("""
          const realFetch = window.fetch;
          window.fetch = async (...args) => {
            const response = await realFetch(...args);
            if (String(args[0]).includes('/submit-answer/')) {
              window.fetch = realFetch;
              throw new Error('Simulated lost acknowledgement');
            }
            return response;
          };
        """)
        self.answer(correct=False)
        self.wait.until(lambda _: self.element('quiz-retry-btn').is_displayed())
        self.click('quiz-retry-btn')
        self.wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '.quiz-answer.btn-danger'))
        self.assertEqual(self.browser.find_element(By.CSS_SELECTOR,'.quiz-answer.btn-success').text,'meaning1_1')
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR,'#attempts .spent')),1)
        self.browser.save_screenshot('/tmp/oqyai-refined-wrong.png')
        self.wait.until(lambda _: self.element('question-text').text == 'word1_2')
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR,'#attempts .spent')),1)

    @override_settings(LIVE_EXPLANATIONS_ENABLED=True)
    def test_shared_explanation_player_in_all_sections(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import AsyncMock, patch
        from django.conf import settings
        from django.contrib.auth.models import User
        from .models import LiveExplanation
        from .test_live_explanations import sample_pcm, tts
        from .services.live_explanations import execute_next

        owner = User.objects.create_superuser("narration-owner", "test@example.test")
        self.client.force_login(owner)
        self.browser.add_cookie({"name":settings.SESSION_COOKIE_NAME, "value":self.client.cookies[settings.SESSION_COOKIE_NAME].value, "path":"/"})
        self.browser.get(self.live_server_url + "/lesson/1/")
        binary = tts.encode_mp3(sample_pcm())
        script = "Country. Ел. I’m from Kazakhstan.\n\nСөз City дегенді білдіреді. <em>Example</em>"
        find = lambda css: self.browser.find_element(By.CSS_SELECTOR, css)
        with TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp, PRIVATE_EXPLANATION_ROOT=temp), \
                patch("lessons.views.OpenAI") as astra, patch("lessons.services.live_explanations.OpenAI") as fresh_astra, \
                patch("lessons.views.synthesize_audio_realtime_mp3", new_callable=AsyncMock, return_value=binary), \
                patch("lessons.services.live_explanations.synthesize_audio_live_mp3", new_callable=AsyncMock,
                      return_value=tts.Narration(binary, {}, validated=True)) as live:
            astra.return_value.__enter__.return_value.responses.create.return_value.output_text = script
            # Exercise the unchecked button before any legacy text or recording exists.
            fresh_client = fresh_astra.return_value.__enter__.return_value
            fresh_client.responses.create.return_value.status = "completed"
            fresh_client.responses.create.return_value.output_text = "Independent fresh script."
            self.assertFalse(find("#live-vocabulary input[type=checkbox]").is_selected())
            find('[data-live-button="vocabulary"]').click()
            self.wait.until(lambda _: LiveExplanation.objects.filter(section="vocabulary", status="queued").exists())
            self.assertTrue(execute_next())
            def source(section):
                return find("#explanation-" + section + " audio").get_attribute("src") or ""

            def finish(section):
                self.wait.until(lambda _: LiveExplanation.objects.filter(section=section, status="queued").exists())
                self.assertTrue(execute_next())
                self.wait.until(lambda _: find(f'[data-live-button="{section}"]').is_enabled())

            self.wait.until(lambda _: "/live/" in source("vocabulary"))
            astra.assert_not_called()
            find('#live-vocabulary [data-live-options] summary').click()
            find("#live-vocabulary [data-live-retry]").click()
            finish("vocabulary")
            self.assertEqual(live.await_args.args, ("Independent fresh script.",))
            for section in ("vocabulary", "content", "grammar", "dialogue"):
                find(f'.lesson-btn[data-section="{section}"]').click()
                if section == "grammar":
                    self.click("themeToggle")
                panel, root = "#live-" + section, "#explanation-" + section
                find(root + ' .explain-btn').click()
                self.wait.until(lambda _: "/audio/" in source(section))
                self.assertFalse(find(root + " [data-explanation]").get_attribute("open"))
                realtime_url = source(section)
                options = find(panel + " [data-live-options]")
                if not options.get_attribute("open"):
                    options.find_element(By.TAG_NAME, "summary").click()
                find(panel + " input[type=checkbox]").click()
                find(f'[data-live-button="{section}"]').send_keys(Keys.ENTER)
                finish(section)
                self.assertIn("/live/", source(section))
                self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, root + " audio")), 1)
                player = find(root + " audio")
                details = find(root + " [data-explanation]")
                self.assertTrue(player.is_displayed())
                self.assertFalse(details.get_attribute("open"))
                self.assertFalse(find(panel + " [data-diagnostics]").get_attribute("open"))
                summary = details.find_element(By.TAG_NAME, "summary")
                self.browser.execute_script("arguments[0].muted=true; arguments[0].loop=true; arguments[0].play()",player)
                self.wait.until(lambda _: self.browser.execute_script("return arguments[0].currentTime > .05", player))
                self.browser.execute_script("window.mediaInterruptions=[]; for(const e of ['pause','emptied','loadstart','seeking']) arguments[0].addEventListener(e,()=>mediaInterruptions.push(e))",player)
                summary.click()
                text = find(root + " .explanation-content")
                self.assertEqual(text.get_attribute("textContent"), script)
                bold = [e.get_attribute("textContent") for e in text.find_elements(By.TAG_NAME, "strong")]
                self.assertTrue(self.browser.execute_script("""
                    const text = arguments[0];
                    return Number(getComputedStyle(text.querySelector('strong')).fontWeight) >
                           Number(getComputedStyle(text).fontWeight);
                """, text))
                self.assertIn("I’m from Kazakhstan.", bold)
                self.assertIn("Country.", bold)
                self.assertIn("City", bold)
                self.assertFalse(text.find_elements(By.TAG_NAME, "em"))
                summary.click()
                self.assertEqual(find(root + " audio"), player)
                self.assertTrue(self.browser.execute_script("return !arguments[0].paused && !mediaInterruptions.length",player))
                self.browser.execute_script("arguments[0].pause()",player)
                select = find(panel + " select")
                def choose(value):
                    self.browser.execute_script("arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('change'))", select, value)
                choose("realtime")
                self.assertEqual(source(section), realtime_url)
                choose("live")
                self.assertLessEqual(self.browser.execute_script("return document.documentElement.scrollWidth"),390)
            live.return_value = tts.Narration(binary, {"transcript":"Білім", "coverage_percent":25}, validated=False)
            good = source("dialogue")
            find('[data-live-button="dialogue"]').click()
            finish("dialogue")
            self.assertEqual(source("dialogue"), good)
            self.assertFalse(find(panel + " [data-live-warning]").is_displayed())
            review = select.find_elements(By.TAG_NAME, "option")[-1].get_attribute("value")
            choose(review)
            self.assertTrue(find(panel + " [data-live-warning]").is_displayed())
            self.assertTrue(source("dialogue").endswith(review))
            self.browser.refresh()
            self.wait.until(lambda _: source("dialogue").endswith(review))
            self.assertIn("/live/", source("vocabulary"))
            self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, ".explanation-container audio")), 4)
            find('.lesson-btn[data-section="dialogue"]').click()
            find(panel + " [data-diagnostics] summary").click()
            self.assertEqual(find(panel + ' [data-field="coverage_percent"]').text, "25%")
            find(panel + " [data-live-options] summary").click()
            find(panel + " input[type=checkbox]").click()
            live.side_effect = tts.LiveError("mock failure")
            find('[data-live-button="dialogue"]').click()
            finish("dialogue")
            self.assertTrue(source("dialogue").endswith(review))
            self.assertEqual(live.await_count, 8)
            fresh_client.responses.create.assert_called_once()
            self.assertEqual(astra.return_value.__enter__.return_value.responses.create.call_count, 4)
            for width in (320, 1024):
                self.browser.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": width, "height": 844, "deviceScaleFactor": 1, "mobile": width < 768})
                self.assertLessEqual(self.browser.execute_script("return document.documentElement.scrollWidth"), width)
                self.assertTrue(find(root + " audio").is_displayed())
            # Previewing a take is private. Explicitly publish Realtime for just Dialogue.
            select = find(panel + " select")
            choose("realtime")
            find(panel + " [data-publish]").click()
            self.wait.until(lambda _: not find(panel + " [data-publish]").is_displayed())
            student = User.objects.create_user("browser-listener")
            self.client.force_login(student)
            self.browser.add_cookie({"name":settings.SESSION_COOKIE_NAME,
                "value":self.client.cookies[settings.SESSION_COOKIE_NAME].value, "path":"/"})
            self.browser.refresh()
            self.assertFalse(self.browser.find_elements(By.CSS_SELECTOR, ".live-preview, .explain-btn"))
            self.assertIn("/audio/", source("dialogue"))
            self.assertIn("/explanation/", source("vocabulary"))
            player = find("#explanation-vocabulary audio")
            playback = self.browser.execute_cdp_cmd("Runtime.evaluate", {
                "userGesture": True, "awaitPromise": True, "returnByValue": True,
                "expression": """(async () => {
                    const audio = document.querySelector('#explanation-vocabulary audio');
                    audio.muted = true;
                    try { await audio.play(); return 'playing'; } catch (e) { return e.name; }
                })()""",
            })
            self.assertEqual(playback["result"].get("value"), "playing")
            self.wait.until(lambda _: self.browser.execute_script("return arguments[0].currentTime > 0", player))
            self.browser.execute_script("arguments[0].pause(); arguments[0].currentTime=.3", player)
            summary = find('#explanation-vocabulary [data-explanation] summary')
            summary.click()
            summary.click()
            self.assertTrue(self.browser.execute_script("return arguments[0].paused && Math.abs(arguments[0].currentTime-.3)<.03", player))
            self.assertEqual(live.await_count, 8)
