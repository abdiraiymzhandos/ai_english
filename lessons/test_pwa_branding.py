"""Home Screen metadata on real pages and brand assets served over HTTP."""
import json
from html.parser import HTMLParser
from io import BytesIO
from urllib.request import urlopen

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import UserProfile
from .test_learning_flow import make_lesson


class DocumentHead(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.in_head = False
        self.tags = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        elif self.in_head and tag in ('meta', 'link'):
            self.tags.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


class PageBrandingTests(TestCase):
    def assert_page_branding(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        tags = DocumentHead(response.content.decode()).tags
        for name in ('apple-mobile-web-app-title', 'application-name'):
            self.assertEqual([tag['content'] for tag in tags if tag.get('name') == name], ['OqyAI'])
        for rel, href in (
            ('manifest', '/static/manifest.json'),
            ('icon', '/static/images/icon-72x72.png'),
            ('apple-touch-icon', '/static/images/icon-180x180.png'),
        ):
            matches = [tag for tag in tags if rel in tag.get('rel', '').split()]
            self.assertEqual([tag['href'] for tag in matches], [href])
            if rel == 'apple-touch-icon':
                self.assertEqual(matches[0]['sizes'], '180x180')

    def test_public_pages(self):
        lesson = make_lesson(1)
        self.assertEqual(reverse('lesson_list'), '/')
        for url in ('/', reverse('lesson_detail', args=[lesson.pk]), '/login/', '/register/',
                    '/privacy-policy/', '/advertisement/', '/account-locked/'):
            with self.subTest(url=url):
                self.assert_page_branding(url)

    def test_signed_in_pages(self):
        user = User.objects.create_user('pwa-learner')
        UserProfile.objects.create(user=user)
        self.client.force_login(user)
        for url in ('/profile/', '/vocabulary/', '/'):
            with self.subTest(url=url):
                self.assert_page_branding(url)


@override_settings(DEBUG=True)
class BrandingAssetTests(StaticLiveServerTestCase):
    def test_manifest_icons_and_favicon_over_http(self):
        with urlopen(self.live_server_url + '/static/manifest.json') as response:
            self.assertEqual(response.status, 200)
            manifest = json.load(response)
        self.assertEqual(manifest['name'], 'OqyAI')
        self.assertEqual(manifest['short_name'], 'OqyAI')
        self.assertEqual((manifest['start_url'], manifest['scope'], manifest['display']), ('/', '/', 'standalone'))
        with urlopen(self.live_server_url + '/manifest.json') as response:
            self.assertEqual(response.headers.get_content_type(), 'application/manifest+json')
            self.assertEqual(json.load(response), manifest)

        icons = {icon['src']: icon['sizes'] for icon in manifest['icons']}
        for size in (192, 512):
            self.assertEqual(icons[f'/static/images/icon-{size}x{size}.png'], f'{size}x{size}')
        icons['/static/images/icon-180x180.png'] = '180x180'
        for path, sizes in icons.items():
            with self.subTest(path=path), urlopen(self.live_server_url + path) as response:
                self.assertEqual(response.headers.get_content_type(), 'image/png')
                data = response.read()
                with Image.open(BytesIO(data)) as icon:
                    self.assertEqual(icon.format, 'PNG')
                    self.assertEqual(icon.size, tuple(map(int, sizes.split('x'))))
                    icon.verify()
                with Image.open(BytesIO(data)) as icon:
                    icon.load()
        with urlopen(self.live_server_url + '/favicon.ico') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.url, self.live_server_url + '/static/images/icon-72x72.png')
            self.assertEqual(response.headers.get_content_type(), 'image/png')
