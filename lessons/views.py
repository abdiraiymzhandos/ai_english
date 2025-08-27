import openai
from openai import OpenAI
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Lesson, QuizQuestion, QuizAttempt, Explanation, Lead
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from .forms import CustomRegisterForm
from .models import UserProfile
from django.contrib.auth import login

import random
import os
import glob
import uuid
import re


def register(request):
    if request.method == 'POST':
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            phone = form.cleaned_data.get('phone')
            # ✅ Профиль жасау кезінде телефон номерін сақтауға болады (егер UserProfile-те сақтағыңыз келсе)
            UserProfile.objects.create(user=user, phone=phone)
            login(request, user)
            return redirect('lesson_list')
    else:
        form = CustomRegisterForm()
    return render(request, 'lessons/register.html', {'form': form})




def lesson_list(request):
    if request.user.is_authenticated:
        user_id = str(request.user.id)
        passed_lessons = list(
            QuizAttempt.objects.filter(user_id=user_id, is_passed=True)
            .values_list("lesson_id", flat=True)
        )
        # ✅ Ақылы емес қолданушы болса – тек 1–15 сабаққа ғана доступ
        if not request.user.profile.is_paid:
            passed_lessons = [i for i in passed_lessons if i <= 10 or i >= 251]
        if not passed_lessons:
            passed_lessons = [0]
    else:
        passed_lessons = request.session.get('passed_lessons', [0])

    if not passed_lessons:
        passed_lessons = [0]

    max_passed = max(passed_lessons)
    base_unlocked = [1, 251]
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
        # {'title': 'Beginner (ru)', 'lessons': lessons[250:300]},
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
        "is_guest": not request.user.is_authenticated
    })


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Free lessons that are available to everyone
    free_lesson_ids = {1, 2, 3, 251, 252, 253}


    # Redirect to advertisement if not free and user is unauthenticated
    if lesson.id not in free_lesson_ids and not request.user.is_authenticated:
        return redirect('/advertisement/')

    # Қолданушының өту құқығын тексеру
    if lesson.id not in free_lesson_ids and request.user.is_authenticated:
        passed_lessons = request.session.get('passed_lessons', [])

        if not request.user.profile.is_paid and lesson.id > 10 and lesson.id < 251:
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
                f"""Сен ағылшын тілі мұғалімісің. Төменде Американдық ағылшын тіліндегі сабақ материалы берілген – ол қазақ тілді, жасы 12-ден асқан, деңгейі 0-ден B2-ге дейінгі оқушыларға арналған:

        Сабақтың мазмұны:
        {lesson.content}

        Осы мәтінді аудио файл түрінде айтуға ыңғайлы болатындай етіп түсіндіріп бер:

        - Әуелі әрбір сөйлемді ағылшын тілінде анық және түсінікті етіп айт.
        - Әрбір сөйлемді баяу және анық айт.
        - Содан соң сол сөйлемді қазақ тіліне қысқа әрі түсінікті етіп аудар.
        - Реттік сандарды (1, 2, 3) қолданба. Сөйлемдерді нөмірлеудің қажеті жоқ.
        - Әрбір сөйлемді нүктемен аяқта.
        - Тіпті сұраулы сөйлемнен кейін де нүкте қой. Мысалы: Is this your book?.
        - Қиын немесе көпмағыналы сөз тіркестеріне тоқталып, олардың мағынасын қазақ тілінде қысқаша түсіндір.
        - Сөздерді қысқартпа, оларды толық айт. Қиын тұстарын да назардан тыс қалдырма.
        - Ешқандай сөзді немесе сөйлемді қалдырма.
        - Сөздерді бөлектеп көрсету үшін жұлдызшаларды (**) қолданба. Мәтінді қарапайым мәтін форматында жаз.
        - Қарапайым, түсінікті тіл пайдалан, ұзын сөйлемдерден аулақ бол. Бұл мәтінді дыбыстауды жеңілдетеді.

        Жауабың табиғи, оқушыларға оңай түсінікті және аудио форматқа тікелей айналдыруға дайын болуы керек.
        """
            )

        elif section == "vocabulary":
            prompt = (
                f"""Сен ағылшын тілі мұғалімісің (Американдық ағылшын). Төменде 12 жастан асқан, деңгейі 0-ден B2-ге дейінгі қазақтілді оқушыларға арналған сабақтың сөздігі берілген:

        Сабақтың сөздігі:
        {lesson.vocabulary}

        Осы сөздерді аудиофайлға оңай айналдыруға болатындай етіп түсіндіріп жаз. Әрбір сөзді түсіндіру үшін келесі құрылымды ұстан:

        - Алдымен ағылшынша сөзді анық айт, содан кейін дереу оның қазақша аудармасын айтып, соңына нүкте қой.
        - Әрбір сөйлемді баяу және анық айт.
        - Содан кейін осы сөздің мағынасын қазақ тілінде бір сөйлеммен қысқа әрі түсінікті етіп түсіндір.
        - Ағылшын тілінде қысқа мысал сөйлем жаз да, және оның қазақша аудармасын көрсет.
        - Егер сөздің бірнеше мағынасы болса, әр мағынасын жеке қысқа қазақша сөйлеммен сипатта.
        - Мысал келтіргенде "Example" сөзін қолданба. Мысал сөйлемді ешқандай белгілерсіз тікелей келтір.

        Маңызды:
        - Сөздердің тізімінде реттік нөмірлерді қолданба.
        - Әрбір сөйлемді нүктемен аяқта.
        - Тіпті сұраулы сөйлемнен кейін де нүкте қой. Мысалы: Is this your book?.
        - Ешбір сөзді немесе сөйлемді тастап кетпе.
        - Американдық ағылшынның емлесі мен лексикасын қолдан.
        - Сөздерді қысқартпай, бөліктерін тастамай айт – бәрін анық және толық жеткіз.
        - Жұлдызшалар (**) немесе өзге ерекшелеу белгілерін пайдаланба – тек жай мәтін жаз.
        - Жауап мазмұны қысқа, нақты және дауысқа салуға қолайлы болуы керек.
        """
            )

        elif section == "grammar":
            prompt = (
                f"""Сен ағылшын тілі мұғалімісің. Төменде Американдық ағылшын тіліндегі бір грамматикалық ереже берілген. Осы ережені 12 жастан асқан, деңгейі 0-ден B2-ге дейінгі қазақтілді оқушыларға өте қарапайым тілмен түсіндіріп бер:

        Сабақтың грамматикалық ережесі:
        {lesson.grammar}

        Грамматиканы аудио форматта айтуға ыңғайлы болу үшін түсіндіруді келесі бағытта жүргіз:

        - Әрбір сөйлемді баяу және анық айт.
        - Ережені мүмкіндігінше қарапайым, түсінікті тілмен түсіндір. Күрделі грамматикалық терминдерді қолданба.
        - Әр ережеге қатысты кемінде екі қысқа мысал келтір. Мысалдарды алдымен ағылшынша беріп, кейін олардың қазақша аудармасын жаз.
        - Оқушылар жиі жіберетін қателіктерге жеке тоқтал. Қате қолданудың үлгісін көрсетіп, оны дұрыс түсіндір.
        - Егер ерекше жағдайлар немесе қосымша ескертпелер болса – оларды да қысқаша атап өт.

        Маңызды:
        - Тізімде реттік тәртіпті көрсету үшін цифрларды қолданба (мысалы, «біріншіден», «екіншіден» деп сөзбен жаз).
        - Сөздерді қысқартпай, анық және толық айт.
        - Ешбір сөзді немесе сөйлемді қалдырма.
        - Әрбір сөйлемді нүктемен аяқта.
        - Тіпті сұраулы сөйлемнен кейін де нүкте қой. Мысалы: Is this your book?.
        - Мәтінді жай мәтін түрінде жаз, жұлдызша (**) немесе басқа ерекшелеу тәсілдерін қолданба.
        - Жауап қысқа, анық және аудиоға оңай түрленетін болсын.
        """
            )

        elif section == "dialogue":
            prompt = (
                f"""Сен ағылшын тілі мұғалімісің. Келесі диалог (Американдық ағылшын) 12 жастан асқан, деңгейі 0-ден B2-ге дейінгі қазақтілді оқушыларға арналған:

        Сабақтың диалогы:
        {lesson.dialogue}

        Диалогты аудио форматта айтуға ыңғайлы болатындай етіп түсіндіріп бер:

        - Әрбір сөйлемді баяу және анық айт.
        - Содан соң сол сөйлемнің мағынасын қысқаша қазақша аудар.
        - Әр сөйлемге байланысты қосымша түсініктеме бер:
            - Егер ерекше немесе маңызды грамматикалық құрылым қолданылса, оны қарапайым сөздермен түсіндір.
            - Сол сөйлемдегі маңызды сөздер мен тұрақты тіркестердің мағынасын қазақ тілінде түсіндіріп өт.

        Маңызды:
        - Мәтінді дыбыстауға ыңғайлы болуы үшін нөмірлеу үшін цифрлар (1, 2, 3) қолданба. Бұл жерде нөмірлеудің қажеті жоқ.
        - Сөздерді қалдырмай, әр сөзді анық және толық айт.
        - Ешбір сөйлемді немесе сөзді назардан шығарма.
        - Әрбір сөйлемді нүктемен аяқта.
        - Тіпті сұраулы сөйлемнен кейін де нүкте қой. Мысалы: Is this your book?.
        - Мәтінді кәдімгі мәтін форматында жаз, жұлдызшалар (**) немесе басқа бөлектегіш таңбаларды қолданба.
        - Жауап қысқа, нақты және аудиоға айналдыруға қолайлы болуы керек.
        """
            )

        else:
            return JsonResponse({"error": "Бұрыс бөлім көрсетілді."}, status=400)


        # Generate text explanation using GPT API.
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-5",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
            )
            explanation_text = response.choices[0].message.content
        except Exception as e:
            return JsonResponse({"error": f"OpenAI қатесі: {str(e)}"}, status=500)

        # Generate audio explanation.
        audio_url = None
        if explanation_text:
            media_dir = settings.MEDIA_ROOT
            # Create a unique filename by appending a short uuid string
            unique_id = uuid.uuid4().hex[:8]
            audio_filename = f"audio_lesson_{lesson.id}_{section}_{unique_id}.mp3"
            # Remove previous audio files for this lesson & section.
            pattern = os.path.join(media_dir, f"audio_lesson_{lesson.id}_{section}_*.mp3")
            for old_audio in glob.glob(pattern):
                os.remove(old_audio)
            audio_path = os.path.join(media_dir, audio_filename)
            try:
                speech_response = openai.audio.speech.create(
                    model="tts-1-hd",
                    voice="alloy",
                    input=explanation_text,
                )
                with open(audio_path, "wb") as audio_file:
                    for chunk in speech_response.iter_bytes():
                        audio_file.write(chunk)
                audio_url = f"{settings.MEDIA_URL}{audio_filename}"
            except openai.OpenAIError as e:
                return JsonResponse({"error": f"Аудио генерация қатесі: {str(e)}"}, status=500)

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
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question},
                ],
                temperature=0.7,
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
                model="gpt-4o-mini",  # Use your preferred model.
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
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
        if profile and profile.lock_until:
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
