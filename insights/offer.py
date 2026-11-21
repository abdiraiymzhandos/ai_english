from urllib.parse import urlencode
import uuid
import re

from django.conf import settings
from django.core import signing
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from lessons.models import Lesson
from lessons.services.course_progress import lesson_access_denial, passed_lesson_ids
from .tracking import schedule_event, event_key, visitor_id


def offer_url(track):
    url = reverse('advertisement')
    return url + '?track=ru' if track == 'ru' else url


def boundary_offer(request, lesson_id):
    if lesson_id not in (3, 253) or lesson_id not in passed_lesson_ids(request):
        return None
    if lesson_access_denial(request, Lesson(pk=lesson_id + 1)) != 'payment_required':
        return None
    ru = lesson_id == 253
    count = len(passed_lesson_ids(request).intersection(range(lesson_id-2, lesson_id+1)))
    return {
        'url': offer_url('ru' if ru else 'kk'), 'cta': 'Продолжить обучение' if ru else 'Оқуды жалғастыру',
        'title': (('Поздравляем! Вы прошли три бесплатных урока!' if ru else 'Құттықтаймыз! Алғашқы 3 сабақты аяқтадыңыз!')
                  if count == 3 else ('Урок пройден!' if ru else 'Сабақ аяқталды!')),
        'detail': 'Откройте полный курс и продолжайте учиться.' if ru else 'Енді толық курспен оқуды жалғастырыңыз.',
    }


def formatted_price():
    return f'{settings.COURSE_PRICE_KZT:,}'.replace(',', ' ')


@never_cache
def advertisement(request):
    ru = request.GET.get('track') == 'ru'
    start = 251 if ru else 1
    return render(request, 'lessons/advertisement.html', {
        'ru': ru, 'track': 'ru' if ru else 'kk', 'price': formatted_price(),
        'completed': len(passed_lesson_ids(request).intersection(range(start, start+3))),
        'handoff': signing.dumps([str(uuid.uuid4()), 'ru' if ru else 'kk'], salt='course-sale'),
    })


@require_POST
@never_cache
def purchase_handoff(request):
    try:
        nonce, track = signing.loads(request.POST.get('handoff',''), salt='course-sale')
    except signing.BadSignature:
        return HttpResponseBadRequest()
    if not re.fullmatch(r'[1-9][0-9]{6,14}', settings.COURSE_WHATSAPP_NUMBER):
        return HttpResponseBadRequest()
    text = ('Здравствуйте! Хочу приобрести годовой курс OqyAI. Пришлите инструкции по оплате через Kaspi.'
            if track == 'ru' else 'Сәлеметсіз бе! OqyAI жылдық курсын сатып алғым келеді. Kaspi арқылы төлеу жолын жіберіңізші.')
    for kind in ('paywall_purchase_clicked', 'whatsapp_opened'):
        schedule_event(request, kind, key=event_key(visitor_id(request), nonce, kind), page='advertisement', path='/advertisement/', track=track)
    return redirect(f'https://wa.me/{settings.COURSE_WHATSAPP_NUMBER}?' + urlencode({'text': text}))
