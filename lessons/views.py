import openai
from openai import OpenAI
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Lesson, QuizQuestion, QuizAttempt, Explanation
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
import random
import os
import glob
import uuid
import re


def lesson_list(request):
    if request.user.is_authenticated:
        user_id = str(request.user.id)
        passed_lessons = list(
            QuizAttempt.objects.filter(user_id=user_id, is_passed=True)
            .values_list("lesson_id", flat=True)
        )
        if not passed_lessons:
            passed_lessons = [0]
    else:
        passed_lessons = request.session.get('passed_lessons', [0])

    if not passed_lessons:
        passed_lessons = [0]

    max_passed = max(passed_lessons)
    unlocked_lessons = list(range(1, max_passed + 2))
    request.session['passed_lessons'] = unlocked_lessons
    request.session.save()

    lessons = Lesson.objects.all().order_by('id')

    stages = [
        {'title': 'Beginner', 'lessons': lessons[0:50]},
        {'title': 'Elementary', 'lessons': lessons[50:100]},
        {'title': 'Pre-Intermediate', 'lessons': lessons[100:150]},
        {'title': 'Intermediate', 'lessons': lessons[150:200]},
        {'title': 'Upper-Intermediate', 'lessons': lessons[200:250]},
    ]

    # Calculate progress for each stage
    for stage in stages:
        total_lessons = len(stage['lessons'])
        passed_in_stage = sum(1 for lesson in stage['lessons'] if lesson.id in passed_lessons)
        stage['progress'] = {
            'total': total_lessons,
            'passed': passed_in_stage,
            'percentage': int((passed_in_stage / total_lessons) * 100) if total_lessons > 0 else 0
        }

    return render(request, "lessons/lesson_list.html", {
        "stages": stages,
        "passed_lessons": unlocked_lessons,
        "is_guest": not request.user.is_authenticated
    })


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Free lessons that are available to everyone
    free_lesson_ids = {1, 2, 3, 15, 14,11}

    # Redirect to advertisement if not free and user is unauthenticated
    if lesson.id not in free_lesson_ids and not request.user.is_authenticated:
        return redirect('/advertisement/')

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
      - Оқу ақысы: 5000 теңге, 1 жылға
      - Өте пайдалы сабақтар, ағылшын мұғалімдері мен ақылды жасанды интеллект арқылы
      - WhatsApp сілтемесі: 87781029394
    """
    return render(request, 'lessons/advertisement.html', {
        'price': '5000 теңге',
        'duration': '1 жылға',
        'whatsapp': '77761703124',
        'message': 'Өте пайдалы! Ағылшын мұғалімдері мен ақылды жасанды интеллект арқылы үйретеміз.'
    })


def explain_section(request, lesson_id):
    """
    AJAX endpoint: generates text and audio explanation for a given section,
    saves it in the session (keyed by lesson ID), and returns JSON.
    """
    if request.method == "POST":
        section = request.POST.get("section")
        lesson = get_object_or_404(Lesson, id=lesson_id)

        # Build the prompt based on the requested section.
        if section == "content":
            prompt = (
                f"""Сабақтың мазмұны:\n{lesson.content}\n\n
                Осы мәтінді аудиоға айналдыруға ыңғайлы етіп түсіндір:
                
                - Әр сөйлемді оқығанда алдымен түпнұсқа ағылшын тілінде анық айт.
                - Сосын оның қазақ тіліндегі аудармасын түсінікті, қысқа сөйлеммен бер.
                - Түсіндірген кезде реттік сандарды (мысалы: 1,2,3...) қолданба.
                
                Сөз тіркестеріне бөлек тоқталғанда:
                - Қиын немесе көп мағыналы сөз тіркестерін теріп ал.
                - Әр сөз тіркесінің мағынасын жеке сөйлеммен қысқа түсіндір.

                Маңызды:
                - Аудиоға түсіруге қиындық туғызбау үшін, сандарды цифрмен (мысалы: 1, 2, 3) жазба. Міндетті түрде жазбаша түрін пайдалан (бірінші, екінші, үшінші).
                - Мүмкіндігінше сөздерді қысқартып немесе өткізіп алма, анық әрі толық сөйле.
                - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба. Сөздер тек қарапайым мәтін түрінде жазылсын.

                Жауабың аудиоға айналдыруға қолайлы, табиғи әрі түсінікті болуы қажет.
                """
            )

        elif section == "vocabulary":
            prompt = (
                f"""Сабақтың сөздігі:\n{lesson.vocabulary}\n\n
                Осы сөздікті аудиоға ыңғайлы етіп түсіндір:

                Құрылым:
                - Алдымен ағылшын сөзін анық айт, сосын бірден қазақша аудармасын келтіріп, нүктемен аяқта.
                - Әр сөзге қысқа әрі нақты түсіндірме бер.
                - Әр сөзге ағылшынша қысқа мысал келтіріп оны қазақша аударып бер.
                - Егер сөздің бірнеше мағынасы болса, әр мағынасын бөлек қысқаша түсіндір.

                Маңызды:
                - Аудиоға айналдыруға қиындық тудырмау үшін реттік сандарды цифрмен (мысалы: 1, 2, 3) жазба. Сөздіктерге реттік нөмір керек емес.
                - Сөздерді өткізіп алма, анық әрі толық айт.
                - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба. Сөздер тек қарапайым мәтін түрінде жазылсын.
                - Жауабың қысқа, нақты әрі аудио түрінде түсінуге ыңғайлы болсын.
                """
            )

        elif section == "grammar":
            prompt = (
                f"""Сабақтың грамматикасы:\n{lesson.grammar}\n\n
                Грамматиканы аудиоға түсіруге ыңғайлы түрде түсіндір:

                Құрылым:
                - Грамматикалық ережені өте қарапайым, түсінікті тілмен түсіндір. Күрделі терминдерді қолданба.
                - Әр ережеге кемінде екі қысқа мысал келтіріп, оларды міндетті түрде қазақшаға аудар.
                - Оқушылар жиі қателесетін жерлерді атап өт, мысалдармен түсіндір.
                - Ерекше жағдайлар немесе қосымша түсіндіру қажет болса, қысқаша бөлек түсіндірме бер.

                Маңызды:
                - Аудио жасауға қиындық тудырмас үшін, реттік сандарды цифрмен (мысалы: 1, 2, 3) жазба. Реттік сан қою мүлдем керек емес
                - Сөздерді өткізіп алма, анық әрі толық айт.
                - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба. Сөздер тек қарапайым мәтін түрінде жазылсын.
                - Жауап қысқа, нақты, анық және аудиоға ыңғайлы болуы тиіс.
                """
            )
        elif section == "dialogue":
            prompt = (
                f"""Сабақтың диалогы:\n{lesson.dialogue}\n\n
                Диалогты аудиоға түсіруге ыңғайлы түрде түсіндір:

                Құрылым:
                - Әр сөйлемді алдымен анық әрі баяу ағылшын тілінде оқып шық.
                - Содан кейін қазақ тіліне қысқаша аудар.
                - Әр сөйлемге қысқаша мағыналық түсіндірме бер:
                    - Ерекше грамматикалық құрылым болса, түсіндір.
                    - Маңызды сөздер мен сөз тіркестерінің мағынасын қысқа әрі түсінікті етіп ашып айт.

                Маңызды:
                - Аудиоға ыңғайлы болуы үшін сандарды цифрмен (мысалы: 1, 2, 3) жазба. Реттік сан қою мүлдем керек емес
                - Сөздерді өткізіп алма, анық әрі толық айт.
                - Сөздерді қою (қалың) ету үшін жұлдызша (**) қолданба. Сөздер тек қарапайым мәтін түрінде жазылсын.
                - Жауап қысқа, нақты және аудио ретінде түсінікті болуы қажет.
                """
            )
        else:
            return JsonResponse({"error": "Бұрыс бөлім көрсетілді."}, status=400)

        # Generate text explanation using GPT API.
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
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
                    model="tts-1",
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
