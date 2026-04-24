import logging
import openai
import os
import random
import re
import uuid
import glob
from urllib.parse import quote

import requests
from openai import OpenAI
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Lesson, QuizQuestion, QuizAttempt, Explanation, Lead
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.conf import settings
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages

from .forms import CustomRegisterForm
from .models import UserProfile
from django.contrib.auth import login

from asgiref.sync import async_to_sync
from english_course.utils.realtime_tts import synthesize_audio_realtime_wav


logger = logging.getLogger(__name__)

REALTIME_MODEL = "gpt-realtime"
UPSELL_WHATSAPP_NUMBER = "77781029394"


def _teacher_instructions(lesson: Lesson) -> str:
    # ✅ Concise instructions to save tokens (~70% reduction)
    lessons_data = (
        f"Lesson {lesson.id}: {lesson.title}\n"
        f"Vocab: {lesson.vocabulary}\n"
        f"Content: {lesson.content}\n"
        f"Grammar: {lesson.grammar}\n"
        f"Dialog: {lesson.dialogue}\n"
    )
    return (
        "Kazakh English teacher. Speak Kazakh + English examples. "
        "Espanyol lessons: Russian only. "
        "Ask short questions, wait for answers, correct gently.\n\n"
        + lessons_data + "\n\n"
        "Rules: short audio-friendly sentences, conversational, pause after questions."
    )


def _get_access_state(is_active, enabled_flag=False, expires_at=None):
    if is_active:
        return "active"
    if enabled_flag and expires_at and timezone.now() > expires_at:
        return "expired"
    return "inactive"


def _build_upgrade_whatsapp_url(feature_name, username):
    message = f"Сәлем! {username} үшін {feature_name} қол жеткізуін қосқым келеді."
    return f"https://wa.me/{UPSELL_WHATSAPP_NUMBER}?text={quote(message)}"


def register(request):
    if request.method == 'POST':
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            phone = form.cleaned_data.get('phone')
            role = form.cleaned_data.get('role') or "student"
            # ✅ Профиль жасау кезінде телефон номерін сақтауға болады (егер UserProfile-те сақтағыңыз келсе)
            UserProfile.objects.create(user=user, phone=phone, role=role)
            login(request, user)
            return redirect('lesson_list')
    else:
        form = CustomRegisterForm()
    return render(request, 'lessons/register.html', {'form': form})




def lesson_list(request):
    user_profile = None
    translator_access_active = False
    translator_access_expires = None
    is_paid_user = False
    free_lesson_ids = {1, 2, 3, 251, 252, 253}

    if request.user.is_authenticated:
        user_profile = getattr(request.user, "profile", None)
        user_id = str(request.user.id)
        passed_lessons = list(
            QuizAttempt.objects.filter(user_id=user_id, is_passed=True)
            .values_list("lesson_id", flat=True)
        )
        is_paid_user = bool(user_profile and user_profile.has_paid_lesson_access())
        # ✅ Ақылы емес қолданушы болса – тек тегін сабақтарға ғана доступ
        if not is_paid_user:
            if user_profile and user_profile.is_teacher():
                passed_lessons = [i for i in passed_lessons if i in free_lesson_ids]
            else:
                passed_lessons = [i for i in passed_lessons if i <= 3 or i >= 251]
        if not passed_lessons:
            passed_lessons = [0]
        if user_profile and user_profile.has_active_translator_access():
            translator_access_active = True
            translator_access_expires = user_profile.translator_access_until
    else:
        passed_lessons = request.session.get('passed_lessons', [0])

    if not passed_lessons:
        passed_lessons = [0]

    base_unlocked = [1, 251]
    if not is_paid_user and user_profile and user_profile.is_teacher():
        unlocked_lessons = sorted(free_lesson_ids)
    else:
        # Екі бөлек максималды өткен сабақтарды табу
        max_kz = max([x for x in passed_lessons if x < 251], default=0)
        max_ru = max([x for x in passed_lessons if x >= 251], default=0)

        # Қазақша және орысша unlocked тізімдер
        unlocked_kz = list(range(1, max_kz + 2)) if max_kz else []
        unlocked_ru = list(range(251, max_ru + 2)) if max_ru else []

        # Жалпы unlocked
        unlocked_lessons = sorted(set(base_unlocked + unlocked_kz + unlocked_ru))

    # Сессияға сақтау (гость үшін)
    request.session['passed_lessons'] = unlocked_lessons
    request.session.save()

    lessons = Lesson.objects.all().order_by('id')

    stages = [
        {'title': 'Beginner', 'lessons': lessons[0:50]},
        {'title': 'Elementary', 'lessons': lessons[50:100]},
        {'title': 'Pre-Intermediate', 'lessons': lessons[100:150]},
        {'title': 'Intermediate', 'lessons': lessons[150:200]},
        {'title': 'Upper-Intermediate', 'lessons': lessons[200:250]},
        # {'title': 'Espanyol', 'lessons': lessons[250:300]},
        # {'title': 'Elementary (ru)', 'lessons': lessons[300:350]},
        # {'title': 'Pre-Intermediate (ru)', 'lessons': lessons[350:400]},
        # {'title': 'Intermediate (ru)', 'lessons': lessons[400:450]},
        # {'title': 'Upper-Intermediate (ru)', 'lessons': lessons[450:500]},
    ]

    # Прогресс
    for stage in stages:
        total = len(stage['lessons'])
        passed = sum(1 for l in stage['lessons'] if l.id in passed_lessons)
        stage['progress'] = {
            'total': total,
            'passed': passed,
            'percentage': int((passed / total) * 100) if total > 0 else 0
        }

    return render(request, "lessons/lesson_list.html", {
        "stages": stages,
        "passed_lessons": unlocked_lessons,
        "is_guest": not request.user.is_authenticated,
        "translator_access_active": translator_access_active,
        "translator_access_expires": translator_access_expires,
        "translator_realtime_model": REALTIME_MODEL,
        "user_is_authenticated": request.user.is_authenticated,
    })


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    user_profile = getattr(request.user, "profile", None)
    is_paid_user = bool(user_profile and user_profile.has_paid_lesson_access())
    voice_access_active = bool(user_profile and user_profile.has_active_voice_access())
    voice_access_expires = user_profile.voice_access_until if voice_access_active else None

    # Free lessons that are available to everyone
    free_lesson_ids = {1, 2, 3, 251, 252, 253}


    # Redirect to advertisement if not free and user is unauthenticated
    if lesson.id not in free_lesson_ids and not request.user.is_authenticated:
        return redirect('/advertisement/')

    # Қолданушының өту құқығын тексеру
    if lesson.id not in free_lesson_ids and request.user.is_authenticated:
        passed_lessons = request.session.get('passed_lessons', [])

        if user_profile and user_profile.is_teacher() and not is_paid_user:
            return redirect('advertisement')

        if not is_paid_user and lesson.id > 3 and lesson.id < 251:
            return redirect('advertisement')

        if lesson.id not in passed_lessons:
            return redirect('lesson_list')

    # 🔥 Сабақтың түсіндірмелерін сессиядан алу
    explanations_qs = Explanation.objects.filter(lesson=lesson)
    explanations = {
        exp.section: {"text": exp.text, "audio_url": exp.audio_url}
        for exp in explanations_qs
    }

    return render(request, 'lessons/lesson_detail.html', {
        'lesson': lesson,
        'explanations': explanations,
        'voice_access_active': voice_access_active,
        'voice_access_expires': voice_access_expires,
    })


def advertisement(request):
    """
    Бұл бетте оқушыға маңызды ақпарат пен жарнама көрсетіледі:
      - Оқу ақысы: 15000 теңге, 1 жылға
      - Өте пайдалы сабақтар, ағылшын мұғалімдері мен ақылды жасанды интеллект арқылы
      - WhatsApp сілтемесі: 87781029394
    """
    return render(request, 'lessons/advertisement.html', {
        'price': '15000 теңге',
        'duration': '1 жылға',
        'whatsapp': '77781029394',
        'message': 'Өте пайдалы! Ағылшын мұғалімдері мен ақылды жасанды интеллект арқылы үйретеміз.'
    })


@csrf_exempt
@require_POST
def mint_realtime_token(request, lesson_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=403)

    user_profile = getattr(request.user, "profile", None)
    if not user_profile or not user_profile.has_active_voice_access():
        return JsonResponse({"error": "Voice access required"}, status=403)

    api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        return HttpResponseBadRequest("OpenAI API key missing")

    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Note: Ephemeral tokens expire in 60 seconds, but the WebRTC session
    # continues after initial connection. Keep-alive maintains the connection.
    payload = {
        "model": REALTIME_MODEL,
        "modalities": ["audio", "text"],
        "voice": "cedar",
        "turn_detection": {"type": "server_vad"},
        "instructions": _teacher_instructions(lesson),
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            try:
                err_payload = response.json()
            except ValueError:
                err_payload = {"error": response.text}
            logger.error(
                "OpenAI realtime session error %s for lesson %s: %s",
                response.status_code,
                lesson_id,
                err_payload,
            )
            return JsonResponse({"error": "OpenAI realtime session error", "details": err_payload}, status=502)
    except requests.RequestException as exc:
        logger.exception("Failed to mint realtime session token for lesson %s", lesson_id)
        return JsonResponse({"error": "OpenAI realtime session error", "details": str(exc)}, status=502)

    try:
        data = response.json()
    except ValueError as exc:
        logger.exception("Invalid JSON from OpenAI realtime session: %s", exc)
        return JsonResponse({"error": "Invalid response from OpenAI"}, status=502)

    return JsonResponse(data)


def explain_section(request, lesson_id):
    """
    AJAX endpoint: generates text and audio explanation for a given section,
    saves it in the session (keyed by lesson ID), and returns JSON.
    """
    if request.method == "POST":
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Рұқсат жоқ'}, status=403)

        section = request.POST.get("section")
        lesson = get_object_or_404(Lesson, id=lesson_id)

        # Build the prompt based on the requested section.
        if section == "content":
            prompt = (
                f"""Сен ағылшын тілінің мұғалімісің. Төменде берілген сабақтың мазмұны
        (American English) – 12 жастан жоғары, 0-ден B2 деңгейіне дейінгі қазақ тілді оқушыларға арналған:

        Сабақтың мазмұны:
        {lesson.content}

        - Алдымен әр сөйлемді түпнұсқа ағылшын тілінде анық айт.
        - Сосын сол сөйлемді қазақ тілінде қысқа және түсінікті етіп аудар бірақ "Қазақша" деп ескертіп айтудың керекгі жоқ
        - Сөйлемдерге реттік сан қоюдың қажеті жоқ.
        - Маңызды сөздер мен сөз тіркестерін түпнұсқа ағылшын тілінде анық айт сосын қазақшаға аудар және ол сөздің мағынасын түсіндір.
        - Диалогтағы кейіпкерлердің атын айтудың керекгі жоқ.
        - Мақсат — оқушыға түсінікті, жеңіл, достық әңгіме стилінде түсіндіру.
        - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба. Тек қарапайым мәтін түрінде жаз.
        - Тілің қарапайым әрі түсінікті болсын, сөйлемдеріңді ұзақ қылма. Бұл мәтінді аудиоға айналдыруды жеңілдетеді.

        Жауабың оқушыларға табиғи, жеңіл түсінікті болатындай күйде болуы тиіс.
        Сен генерация жасаған текстке TTS арқылы аудиоға айналдыруға ыңғайлы етіп тыныс белгілерді қой.
        """
            )

        elif section == "vocabulary":
            prompt = (
                f"""Сен ағылшын тілінің мұғалімісің (American English). Төменде 12 жастан жоғары,
        0-ден B2 деңгейіне дейінгі қазақ тілді оқушыларға арналған сөздік берілген:

        Сабақтың сөздігі:
        {lesson.vocabulary}

        Осы сөздікті аудиоға ыңғайлы етіп түсіндір. Әр сөзді келесі құрылым бойынша түсіндір:

        - Алдымен ағылшын сөзін анық айт, содан кейін бірден қазақша аудармасын беріп, нүктемен аяқта.
        - Содан соң сол сөзді бір сөйлеммен қазақ тілінде қысқа әрі нақты түсіндір.
        - Ағылшынша қысқа мысал сөйлем келтір, артынша оның қазақша аудармасын жаз.
        - Егер сөздің бірнеше мағынасы болса, әр мағынаны жеке-жеке қазақша бір сөйлеммен сипатта.

        Маңызды:
        - Сөздіктерде реттік нөмір қолданудың қажеті жоқ.
        - Әр сөйлемді аяқтаған соң нүкте қой.
        - Сұраулы сөйлемнен соң да нүкте қой. мысалы: Is this your book?. деп сұрақ белгісінен соң міндетті түрде нүкте қой.
        - American English орфографиясы мен сөз қолданысын пайдалану.
        - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба, тек қарапайым мәтін болсын.
        - Жауабың қысқа, нақты болуы тиіс.
        - Сен генерация жасаған текстке TTS арқылы аудиоға айналдыруға ыңғайлы етіп тыныс белгілерді қой.
        """
            )

        elif section == "grammar":
            prompt = (
                f"""You are a warm, patient English teacher speaking to a Kazakh-speaking student.
Explain the grammar topic in a friendly, conversational tone as if you're talking directly to the student.
Do not give a formal definition first; use simple, spoken language and short sentences.
For each rule, give two or three very short examples: first in English, then a short Kazakh meaning.
Point out common mistakes ("Many students get confused here...") with a brief example and fix.
Mention any special cases briefly.
Keep the output audio-friendly: short sentences and clear punctuation.
Write ordinal numbers as words. Do not use bold or any special markup.

Grammar topic:
{lesson.grammar}

Always end by inviting the student to try one short sentence using the rule."""
            )

        elif section == "dialogue":
            prompt = (
                f"""Сен ағылшын тілінің мұғалімісің. Төмендегі диалог (American English)
        12 жастан жоғары, 0-ден B2 деңгейіне дейінгі қазақ тілді оқушыларға арналған:

        Сабақтың диалогы:
        {lesson.dialogue}

        - Әр сөйлемді алдымен анық әрі баяу ағылшын тілінде оқып шық.
        - Содан кейін сол сөйлемді қазақ тіліне қысқаша аудар бірақ "Қазақша" деп ескертіп айтудың керегі жоқ
        - Маңызды сөздер мен сөз тіркестерін қазақша түсіндір. бірақ "Түсіндірме" деп ескертіп айтудың керекгі жоқ
        - Диалогтағы кейіпкерлердің атын айтудың керекгі жоқ.
        - Аудиоға ыңғайлы болу үшін сандарды цифрмен (мысалы, 1, 2, 3) жазба. Реттік сан қоюдың қажеті жоқ.
        - Ешбір сөзді немесе сөйлемді өткізіп алма.
        - Қарапайым мәтін түрінде жаз, жұлдызша (**) немесе басқа ерекшелеу белгілерін қолданба.
        - Жауабың қысқа, нақты болсын.
        - Сен генерация жасаған текстке TTS арқылы аудиоға айналдыруға ыңғайлы етіп тыныс белгілерді қой.
        """
            )

        else:
            return JsonResponse({"error": "Бұрыс бөлім көрсетілді."}, status=400)


        # Generate text explanation using GPT API.
        # Generate text explanation using GPT-5 (Responses API)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            resp = client.responses.create(
                model="gpt-5",
                input=prompt,                      # сіз құрастырған prompt
                reasoning={"effort": "low"},       # жылдамырақ жауап үшін
                text={"verbosity": "low"},         # аудиоға ыңғайлы қысқа стиль
            )
            explanation_text = (resp.output_text or "").strip()
            if not explanation_text:
                # Сирек жағдайда бос келсе, чатқа фолбэк жасаймыз
                fallback = client.chat.completions.create(
                    model="gpt-5",
                    messages=[{"role": "user", "content": prompt}],
                )
                explanation_text = fallback.choices[0].message.content.strip()

        except Exception as e:
            return JsonResponse({"error": f"OpenAI қатесі: {str(e)}"}, status=500)


        # Generate audio explanation.
        # Generate audio explanation (gpt-realtime -> WAV)
        audio_url = None
        if explanation_text:
            media_dir = settings.MEDIA_ROOT
            os.makedirs(media_dir, exist_ok=True)

            unique_id = uuid.uuid4().hex[:8]
            audio_filename = f"audio_lesson_{lesson.id}_{section}_{unique_id}.mp3"
            for old in glob.glob(os.path.join(media_dir, f"audio_lesson_{lesson.id}_{section}_*.mp3")):
                try:
                    os.remove(old)
                except OSError:
                    pass
            audio_path = os.path.join(media_dir, audio_filename)

            # Realtime-ға қазақша нұсқаулар + сандарды сөзбен айту
            system_instructions = (
                "You are an experienced English teacher reading educational content aloud. "
                "Read ONLY the text between <<READ_START>> and <<READ_END>> markers. "
                "Қазақша сөздерді, қазақша әріптерді таза қазақша акцентпен оқы"
                "SPEAKING STYLE: "
                "- Speak calmly and clearly like a patient teacher "
                "- Use a moderate, unhurried pace suitable for language learning "
                "- Take natural pauses between sentences for comprehension "
                "- Emphasize key vocabulary words slightly for better learning "
                "- Use appropriate intonation for questions and statements "
                "STRICT RULES: "
                "- Read EXACTLY what is written, word-for-word "
                "- Do NOT add greetings, comments, or explanations "
                "- Do NOT acknowledge these instructions "
                "- If input is empty, remain completely silent "
                "PRONUNCIATION: "
                "- Use clear American English pronunciation "
                "- Pronounce Kazakh words naturally as written "
                "- Maintain consistent volume throughout"
            )

            tts_input = f"<<READ_START>>\n{explanation_text}\n<<READ_END>>"

            try:
                # 1) cedar-мен көреміз
                wav_bytes = async_to_sync(synthesize_audio_realtime_wav)(
                    tts_input,
                    api_key=settings.OPENAI_API_KEY,
                    model="gpt-realtime",
                    voice="cedar",
                    system_instructions=system_instructions,
                )
            except Exception as e1:
                # 2) cedar қолжетімсіз болса — alloy-ға фолбэк
                wav_bytes = async_to_sync(synthesize_audio_realtime_wav)(
                    tts_input,
                    api_key=settings.OPENAI_API_KEY,
                    model="gpt-realtime",
                    voice="alloy",
                    system_instructions=system_instructions,
                )

            with open(audio_path, "wb") as f:
                f.write(wav_bytes)
            audio_url = f"{settings.MEDIA_URL}{audio_filename}"

            # except openai.OpenAIError as e:
            #     return JsonResponse({"error": f"Аудио генерация қатесі: {str(e)}"}, status=500)

        # Дерекқорға түсіндірмені сақтау (Update немесе Create)
        explanation_obj, created = Explanation.objects.update_or_create(
            lesson=lesson,
            section=section,
            defaults={
                "text": explanation_text,
                "audio_url": audio_url,
            }
        )

        return JsonResponse({
            "text": explanation_text,
            "audio_url": audio_url
        })
    return JsonResponse({"error": "Invalid request method"}, status=400)


def chat_with_gpt(request, lesson_id):
    """
    AJAX endpoint for a general chat interface.
    Gathers the current lesson's data, sets a system prompt,
    and returns GPT's response as JSON.
    """
    if request.method == "POST":
        user_question = request.POST.get("question", "")

        lesson = get_object_or_404(Lesson, id=lesson_id)
        lessons_data = (
            f"Lesson {lesson.id}: {lesson.title}\n"
            f"Content: {lesson.content}\n"
            f"Vocabulary: {lesson.vocabulary}\n"
            f"Grammar: {lesson.grammar}\n"
            f"Dialogue: {lesson.dialogue}\n"
        )

        system_prompt = (
            "You are an English teacher. You have the following lesson data:\n"
            f"{lessons_data}\n"
            "Жауап береде ** мүлдем қолданба."
            "Answer the user's question in detail IN KAZAKH."
        )

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question},
                ],
                temperature=1,
            )
            gpt_answer = response.choices[0].message.content
            return JsonResponse({"answer": gpt_answer})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=400)


def motivational_message(request):
    """
    AJAX endpoint: Generates a motivational message about learning English.
    """
    if request.method == "POST":
        prompt = (
            "Сен ағылшын тілін жасанды интеллект арқылы үйреніп жүрген оқушыларға арналған шабыттандыратын хабарлама жаса. "
            "Жауапты қазақ тілінде, қысқа әрі нұсқа етіп бер."
        )

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-5",  # Use your preferred model.
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
            )
            message = response.choices[0].message.content
            return JsonResponse({"message": message})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method."}, status=400)


def generate_quiz_questions(lesson_id):
    """
    Сабақтың сөздігінен сөздерді бөліп, `QuizQuestion` моделіне енгізетін функция.
    Егер сұрақтар бұрыннан бар болса, жаңаларын қоспайды.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Барлық бұрынғы сұрақтарды өшіру (ескі деректерді тазарту)
    QuizQuestion.objects.filter(lesson=lesson).delete()

    vocabulary_text = lesson.vocabulary.strip()
    lines = vocabulary_text.split("\n")

    word_list = []

    # 1. Сөздерді бөліп, тізім жасау
    for line in lines:
        parts = line.split(" – ")  # Сөздер " – " арқылы бөлінген
        if len(parts) == 2:
            english_word = parts[0].strip()
            kazakh_translation = parts[1].strip()
            word_list.append((english_word, kazakh_translation))

    # 2. Сөздерді `QuizQuestion` моделіне енгізу
    questions = [
        QuizQuestion(lesson=lesson, english_word=english_word, kazakh_translation=kazakh_translation)
        for english_word, kazakh_translation in word_list
    ]

    QuizQuestion.objects.bulk_create(questions)  # ✅ Барлық сөздерді бірден енгізу

    print(f"✅ {len(questions)} сұрақ базаға енгізілді!")


def start_quiz(request, lesson_id):
    """
    Тестті бастағанда, егер база бос болса, сұрақтарды автоматты түрде толтырады.
    Сосын тест сұрақтарын қайтарады.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Тест сұрақтарын генерациялау (егер әлі енгізілмесе)
    generate_quiz_questions(lesson_id)

    # Барлық тест сұрақтарын алу
    questions = list(QuizQuestion.objects.filter(lesson=lesson))

    if len(questions) < 4:
        return JsonResponse({"error": "Бұл сабақта жеткілікті сөздер жоқ!"}, status=400)

    random.shuffle(questions)

    question_data = []

    for q in questions:
        correct_answer = q.kazakh_translation

        # ❌ Бұрынғы кодта қате бар: Дұрыс жауап кейде жоғалып кетуі мүмкін
        incorrect_answers = [w.kazakh_translation for w in questions if w.kazakh_translation != correct_answer]

        # ✅ Қате жауаптар тізімін дұрыстау
        if len(incorrect_answers) < 3:
            incorrect_answers += ["Қате жауап"] * (3 - len(incorrect_answers))

        incorrect_answers = random.sample(incorrect_answers, 3)  # Тек 3 қате жауап таңдау
        choices = incorrect_answers + [correct_answer]  # Дұрыс жауапты қосу
        random.shuffle(choices)  # Барлығын араластыру

        question_data.append({
            "id": q.id,
            "english_word": q.english_word,
            "choices": choices
        })

    return JsonResponse({"questions": question_data})


@csrf_exempt
def submit_answer(request, lesson_id):
    if request.method == "POST":
        # Сессияның бар-жоғын тексеріп, қажет болса құру
        if not request.session.session_key:
            request.session.create()
        user_id = str(request.user.id) if request.user.is_authenticated else request.session.session_key or "guest"

        lesson = get_object_or_404(Lesson, id=lesson_id)
        attempt, created = QuizAttempt.objects.get_or_create(user_id=user_id, lesson=lesson)
        question_id = request.POST.get("question_id")
        selected_answer = request.POST.get("answer")
        question = get_object_or_404(QuizQuestion, id=question_id)

        # Сабаққа қатысты тесттегі жалпы сұрақтар саны
        total_questions = lesson.quiz_questions.count()

        # Дұрыс жауап болса score-ды арттырып, қате болса attempts-ты арттырамыз
        if question.kazakh_translation == selected_answer:
            attempt.add_score()
        else:
            attempt.increase_attempts()

        # Егер барлық сұрақтарға жауап берілді деп есептесек,
        # (яғни, дұрыс жауаптар мен қатенің қосындысы >= жалпы сұрақ саны),
        # тест аяқталғанын тексереміз
        if (attempt.score + attempt.attempts) >= total_questions:
            attempt.check_pass()

        # Егер тест өтілсе, келесі сабақты ашу үшін session-ды жаңартамыз
        if attempt.is_passed:
            passed_lessons = list(
                QuizAttempt.objects.filter(user_id=user_id, is_passed=True)
                .values_list("lesson_id", flat=True)
            )
            # Ең үлкен өткен сабақ нөміріне 1 қосамыз
            next_lesson = max(passed_lessons) + 1 if passed_lessons else 1
            # Келесі сабақ шынымен бар-жоғын тексереміз
            if Lesson.objects.filter(id=next_lesson).exists():
                passed_lessons.append(next_lesson)
            request.session['passed_lessons'] = passed_lessons
            request.session.save()

            # Егер қолданушы тіркелген болса, оның профиліндегі current_lesson-ды жаңартамыз
            if request.user.is_authenticated:
                profile = request.user.profile
                # Тек жоғарырақ сабаққа өтсе ғана жаңартамыз
                if next_lesson > profile.current_lesson:
                    profile.current_lesson = next_lesson
                    profile.save()

            return JsonResponse({
                "correct": question.kazakh_translation == selected_answer,
                "score": attempt.score,
                "attempts": attempt.attempts,
                "passed": attempt.is_passed,
                "next_lesson": next_lesson
            })

        # Тест әлі аяқталмаған жағдайда (барлық сұраққа жауап берілмеген жағдайда)
        return JsonResponse({
            "correct": question.kazakh_translation == selected_answer,
            "score": attempt.score,
            "attempts": attempt.attempts,
            "passed": attempt.is_passed
        })

    return JsonResponse({"error": "Invalid request"}, status=400)


def account_locked(request):
    """
    Аккаунт құлтаулы болған жағдайда қолданушыға хабар беретін бет.
    Егер профильде lock_until мәні болса, қалған құлтау уақытын есептеп көрсетеді.
    """
    lock_until = None
    remaining_time = None
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.is_locked():
            lock_until = profile.lock_until
            remaining_time = (lock_until - timezone.now()).days
    context = {
        'lock_until': lock_until,
        'remaining_days': remaining_time,
    }
    return render(request, 'lessons/account_locked.html', context)


@login_required
def vocabulary_list(request):
    all_vocab_texts = Lesson.objects.values_list('vocabulary', flat=True)

    all_words_set = set()
    for vocab in all_vocab_texts:
        words = [word.strip() for word in vocab.split('\n') if word.strip()]
        all_words_set.update(words)

    sorted_words = sorted(all_words_set)
    numbered_words = list(enumerate(sorted_words, start=1))

    return render(request, 'lessons/vocabulary_list.html', {'words': numbered_words})


def register_lead(request):
    if request.method == "POST":
        name  = request.POST.get("name")
        phone = request.POST.get("phone")
        if not (name and phone):
            return JsonResponse({"error": "Аты мен нөмірін толтырыңыз"}, status=400)

        Lead.objects.create(name=name, phone=phone)

        lesson_url = request.build_absolute_uri(
            reverse("lesson_detail", args=[1])   # 1‑сабақ
        )
        return JsonResponse({"redirect_url": lesson_url})

    return JsonResponse({"error": "POST керек"}, status=405)


# PWA views - serve service worker and manifest from root
def service_worker(request):
    """Serve service worker from root path for PWA"""
    sw_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'sw.js')
    try:
        with open(sw_path, 'r') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/javascript')
    except FileNotFoundError:
        return HttpResponse('Service worker not found', status=404)


def pwa_manifest(request):
    """Serve manifest.json from root path for PWA"""
    manifest_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'manifest.json')
    try:
        with open(manifest_path, 'r') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/manifest+json')
    except FileNotFoundError:
        return HttpResponse('Manifest not found', status=404)


def privacy_policy(request):
    """
    Құпиялылық саясаты бетін көрсету
    """
    return render(request, 'lessons/privacy_policy.html')


@login_required
def profile(request):
    """
    Пайдаланушы профилі беті. Аккаунт ақпараты мен аккаунтты жою мүмкіндігі.
    """
    user_profile = getattr(request.user, "profile", None)
    current_lesson = max((user_profile.current_lesson if user_profile else 1), 1)
    course_access_active = bool(user_profile and user_profile.has_paid_lesson_access())
    voice_access_active = bool(user_profile and user_profile.has_active_voice_access())
    translator_access_active = bool(user_profile and user_profile.has_active_translator_access())
    classroom_access_active = bool(
        user_profile and user_profile.can_use_classroom_teacher_features()
    )
    classroom_live_access_active = bool(
        user_profile and user_profile.can_run_classroom_voice_sessions()
    )
    account_locked = bool(user_profile and user_profile.is_locked())
    account_lock_until = user_profile.lock_until if account_locked else None
    voice_access_state = _get_access_state(
        voice_access_active,
        enabled_flag=bool(user_profile and user_profile.has_voice_access),
        expires_at=user_profile.voice_access_until if user_profile else None,
    )
    translator_access_state = _get_access_state(
        translator_access_active,
        enabled_flag=bool(user_profile and user_profile.has_translator_access),
        expires_at=user_profile.translator_access_until if user_profile else None,
    )
    highest_lesson_reached = user_profile.get_highest_lesson_reached() if user_profile else 0
    passed_main_lessons = QuizAttempt.objects.filter(
        user_id=str(request.user.id),
        is_passed=True,
        lesson_id__lt=251,
    ).count()
    progress_percentage = min(int((passed_main_lessons / 250) * 100), 100) if passed_main_lessons else 0
    active_access_count = sum(
        1
        for is_active in (
            course_access_active,
            voice_access_active,
            translator_access_active,
            classroom_access_active,
        )
        if is_active
    )
    voice_upgrade_recommended = course_access_active and not voice_access_active
    voice_lesson_id = current_lesson if course_access_active else 1
    access_cards = [
        {
            "key": "course",
            "icon": "fas fa-book-open",
            "title": "Курсқа қол жеткізу",
            "status": "active" if course_access_active else "inactive",
            "status_label": "Белсенді" if course_access_active else "Қосылмаған",
            "description": "250 негізгі сабақ, тесттер және прогресс бақылауы.",
            "value_line": (
                f"{passed_main_lessons} / 250 сабақ өтті"
                if course_access_active
                else "Қазір тек тегін сабақтар ашық"
            ),
            "expires_at": None,
            "cta_label": "Сабақтарды ашу" if course_access_active else "Курсты ашу",
            "cta_url": reverse("lesson_list") if course_access_active else reverse("advertisement"),
            "cta_external": False,
            "cta_style": "primary" if course_access_active else "secondary",
            "featured": not course_access_active,
        },
        {
            "key": "voice",
            "icon": "fas fa-microphone-lines",
            "title": "AI дауыс сабағы",
            "status": voice_access_state,
            "status_label": {
                "active": "Белсенді",
                "expired": "Мерзімі бітті",
                "inactive": "Қосылмаған",
            }[voice_access_state],
            "description": "AI мұғаліммен тікелей сөйлесу, pronunciation feedback және speaking practice.",
            "value_line": (
                "Тікелей speaking тәжірибесін бірден бастай аласыз"
                if voice_access_active
                else "Курсқа қосымша ең пайдалы premium upgrade"
            ),
            "expires_at": user_profile.voice_access_until if user_profile else None,
            "cta_label": (
                "Дауыс сабағын ашу"
                if voice_access_active
                else ("Жаңарту" if voice_access_state == "expired" else "Қосу")
            ),
            "cta_url": (
                reverse("lesson_detail", args=[voice_lesson_id])
                if voice_access_active
                else _build_upgrade_whatsapp_url("AI дауыс сабағы", request.user.username)
            ),
            "cta_external": not voice_access_active,
            "cta_style": "featured" if voice_upgrade_recommended else ("primary" if voice_access_active else "secondary"),
            "featured": voice_upgrade_recommended,
        },
        {
            "key": "translator",
            "icon": "fas fa-language",
            "title": "Аудармашы көмекшісі",
            "status": translator_access_state,
            "status_label": {
                "active": "Белсенді",
                "expired": "Мерзімі бітті",
                "inactive": "Қосылмаған",
            }[translator_access_state],
            "description": "Тірі speech-to-speech аударма және күнделікті сөйлесуге көмек.",
            "value_line": (
                "Көмекші негізгі беттен бірден ашылады"
                if translator_access_active
                else "Сапар, жұмыс және күнделікті диалог үшін бөлек premium access"
            ),
            "expires_at": user_profile.translator_access_until if user_profile else None,
            "cta_label": (
                "Қазір пайдалану"
                if translator_access_active
                else ("Жаңарту" if translator_access_state == "expired" else "Қосу")
            ),
            "cta_url": (
                reverse("lesson_list")
                if translator_access_active
                else _build_upgrade_whatsapp_url("Аудармашы көмекшісі", request.user.username)
            ),
            "cta_external": not translator_access_active,
            "cta_style": "primary" if translator_access_active else "secondary",
            "featured": False,
        },
    ]

    if classroom_access_active:
        access_cards.append(
            {
                "key": "classroom",
                "icon": "fas fa-chalkboard-teacher",
                "title": "Classroom / Teacher access",
                "status": "active",
                "status_label": "Белсенді",
                "description": "Сыныптар, roster, фото/дауыс тіркеу және classroom басқаруы.",
                "value_line": (
                    "AI classroom session дайын"
                    if classroom_live_access_active
                    else "Live classroom session үшін voice access бөлек керек"
                ),
                "expires_at": None,
                "cta_label": "Classroom ашу",
                "cta_url": reverse("classroom_dashboard"),
                "cta_external": False,
                "cta_style": "primary",
                "featured": False,
            }
        )

    if voice_upgrade_recommended:
        upgrade_recommendation = {
            "title": "Келесі ең пайдалы upgrade: AI дауыс сабағы",
            "description": (
                "Сізде курс ашық, бірақ speaking practice әлі жабық. "
                "Дауыс сабағы AI мұғаліммен тікелей сөйлесуге, қателерді бірден түзетуге "
                "және күнделікті сөйлеуді тезірек дамытуға көмектеседі."
            ),
            "cta_label": "AI дауыс сабағын қосу",
            "cta_url": _build_upgrade_whatsapp_url("AI дауыс сабағы", request.user.username),
            "cta_external": True,
        }
    elif not course_access_active:
        upgrade_recommendation = {
            "title": "Толық курсқа өтіңіз",
            "description": (
                "Тегін сабақтардан кейін толық 250 сабақтық жолды ашып, "
                "жүйелі прогреспен жалғастырыңыз."
            ),
            "cta_label": "Курсты ашу",
            "cta_url": reverse("advertisement"),
            "cta_external": False,
        }
    elif not translator_access_active:
        upgrade_recommendation = {
            "title": "Күнделікті диалог үшін аудармашы көмекшісін қосыңыз",
            "description": (
                "Саяхатта, жұмыста немесе тез аударма керек сәтте "
                "speech-to-speech көмекші уақытты үнемдейді."
            ),
            "cta_label": "Көмекшіні қосу",
            "cta_url": _build_upgrade_whatsapp_url("Аудармашы көмекшісі", request.user.username),
            "cta_external": True,
        }
    else:
        upgrade_recommendation = None

    context = {
        "can_use_classroom_teacher_features": classroom_access_active,
        "account_locked": account_locked,
        "account_lock_until": account_lock_until,
        "access_cards": access_cards,
        "upgrade_recommendation": upgrade_recommendation,
        "active_access_count": active_access_count,
        "tracked_access_count": len(access_cards),
        "course_access_active": course_access_active,
        "voice_access_active": voice_access_active,
        "translator_access_active": translator_access_active,
        "classroom_access_active": classroom_access_active,
        "classroom_live_access_active": classroom_live_access_active,
        "highest_lesson_reached": highest_lesson_reached,
        "passed_main_lessons": passed_main_lessons,
        "progress_percentage": progress_percentage,
        "current_lesson": current_lesson,
        "profile_phone": user_profile.phone if user_profile else "",
        "profile_role_label": dict(UserProfile.ROLE_CHOICES).get(
            user_profile.role if user_profile else "student",
            "Оқушы",
        ),
        "voice_access_expires": user_profile.voice_access_until if user_profile else None,
        "translator_access_expires": user_profile.translator_access_until if user_profile else None,
        "course_cta_url": reverse("lesson_list") if course_access_active else reverse("advertisement"),
        "translator_cta_url": reverse("lesson_list") if translator_access_active else _build_upgrade_whatsapp_url("Аудармашы көмекшісі", request.user.username),
        "voice_cta_url": reverse("lesson_detail", args=[voice_lesson_id]) if voice_access_active else _build_upgrade_whatsapp_url("AI дауыс сабағы", request.user.username),
    }

    if request.method == 'POST':
        # Handle account deletion directly on profile page
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')

        # Verify all fields are filled
        if not password or not confirm:
            messages.error(request, 'Барлық өрістерді толтырыңыз!')
            return render(request, 'lessons/profile.html', context)

        # Authenticate user with current username and provided password
        user = authenticate(request, username=request.user.username, password=password)

        if user is not None:
            # User authenticated successfully - delete account
            try:
                user.delete()
                logout(request)
                messages.success(request, 'Аккаунт сәтті жойылды!')
                return redirect('lesson_list')
            except Exception as e:
                messages.error(request, f'Аккаунтты жою кезінде қате пайда болды: {str(e)}')
                return render(request, 'lessons/profile.html', context)
        else:
            # Wrong password
            messages.error(request, 'Құпиясөз қате!')
            return render(request, 'lessons/profile.html', context)

    return render(request, 'lessons/profile.html', context)


def check_translator_access(request):
    """
    Check if the user has active translator access.
    Returns JSON with access status and expiry date.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"has_access": False, "error": "Жүйеге кіру керек"}, status=401)

    try:
        profile = request.user.profile
        has_access = profile.has_active_translator_access()

        response_data = {
            "has_access": has_access,
        }

        if has_access and profile.translator_access_until:
            response_data["expires_at"] = profile.translator_access_until.strftime("%Y-%m-%d")

        return JsonResponse(response_data)
    except UserProfile.DoesNotExist:
        return JsonResponse({"has_access": False, "error": "Профиль табылмады"}, status=404)


@require_POST
@login_required
def mint_translator_token(request):
    """
    Mint an ephemeral token for the translator assistant using OpenAI Realtime API.
    Only accessible to users with active translator access.
    """
    # Check if user has translator access
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Жүйеге кіру керек"}, status=401)

    try:
        profile = request.user.profile
        if not profile.has_active_translator_access():
            return JsonResponse({"error": "Аудармашы көмекшісіне қол жеткізу жоқ"}, status=403)
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Профиль табылмады"}, status=404)

    api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        return HttpResponseBadRequest("OpenAI API key missing")

    # Instructions for the translator assistant
    translator_instructions = (
        "Role: live two-way interpreter. "
        "Treat the microphone speaker as your primary user (user_lang). Infer the other party (target_lang) from user requests such as “translate to English”. "
        "When the user speaks, address the other party in the requested target language using short, conversational sentences, then restate the same content back in the user’s language so they understand. "
        "When the other party replies (detected by hearing the target language), immediately summarize or translate it back into the user’s language and politely ask what they’d like you to say next. "
        "Stay concise, keep numbers/time/price clear, preserve names, soften profanity, and ask for clarification if audio is unclear. "
        "If the user explicitly says “translate only”, skip explanations; if they say “explain”, add one brief cultural or linguistic note. "
        "Speak directly without any markup."
    )


    payload = {
        "model": REALTIME_MODEL,
        "modalities": ["audio", "text"],
        "voice": "cedar",
        "turn_detection": {"type": "server_vad"},
        "instructions": translator_instructions,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            try:
                err_payload = response.json()
            except ValueError:
                err_payload = {"error": response.text}
            logger.error(
                "OpenAI realtime session error %s for translator: %s",
                response.status_code,
                err_payload,
            )
            return JsonResponse({"error": "OpenAI realtime session error", "details": err_payload}, status=502)
    except requests.RequestException as exc:
        logger.exception("Failed to mint realtime session token for translator")
        return JsonResponse({"error": "OpenAI realtime session error", "details": str(exc)}, status=502)

    try:
        data = response.json()
    except ValueError as exc:
        logger.exception("Invalid JSON from OpenAI realtime session: %s", exc)
        return JsonResponse({"error": "Invalid response from OpenAI"}, status=502)

    return JsonResponse(data)
