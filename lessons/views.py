import openai
from openai import OpenAI
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from .models import Lesson, QuizQuestion, QuizAttempt
from django.http import JsonResponse
from django.conf import settings
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

    # unlocked_lessons есептеу (мысалы, максималды өткен сабақ + 1)
    max_passed = max(passed_lessons)
    unlocked_lessons = list(range(1, max_passed + 2))
    request.session['passed_lessons'] = unlocked_lessons
    request.session.save()

    lessons = Lesson.objects.all()
    return render(request, "lessons/lesson_list.html", {
        "lessons": lessons,
        "passed_lessons": unlocked_lessons,
        "is_guest": not request.user.is_authenticated
    })


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # ✅ Егер 3-шы сабақтан жоғары болса және қолданушы кірмеген болса, логинге жібереді
    if lesson.id > 3 and not request.user.is_authenticated:
        return redirect('/login/')

    # 🔥 Сабақтың түсіндірмелерін сессиядан алу
    all_explanations = request.session.get('explanations', {})
    explanations = all_explanations.get(str(lesson.id), {})

    return render(request, 'lessons/lesson_detail.html', {
        'lesson': lesson,
        'explanations': explanations,
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
                f"Сабақтың мазмұны:\n{lesson.content}\n\n"
                """Мәтіндегі әр сөйлемді оқып, алдымен түпнұсқа күйінде айт.
                Содан кейін қазақ тіліне аударып бер.

                Сөз тіркестерін бөлек талдап түсіндір:
                - Қиын немесе мағынасы кең сөз тіркестерін теріп ал.
                - Әрбір сөз тіркесінің нақты мағынасын айт.

                Сөздерді қою қара ету үшін ** қолданба.

                Барынша анық, қысқа әрі нақты жауап бер.
                """
            )

        elif section == "vocabulary":
            prompt = (
                f"Сабақтың сөздігі:\n{lesson.vocabulary}\n\n"
                """Әрбір сөзді түсінікті етіп талда:

                Құрылым:
                1. Бірінші ағылшынша сөзді айтып сосын қазақшасын айт.
                Сөдің қазақшасын жазған соң нүкте қой.
                3. Қысқа әрі нақты түсіндірме жаз.
                4. Әр сөзге ағылшынша қысқа мысал келтіріп оны қазақша аударып бер.
                5. Егер сөздің бірнеше мағынасы болса, әрқайсысын бөлек түсіндір.

                Маңызды:
                - Сөздерді қою қара ету үшін ** қолданба.
                - Жауап қысқа, анық және оқу оңай болсын.
                Адам сияқты жауап бер. 
                """
            )

        elif section == "grammar":
            prompt = (
                f"Сабақтың грамматикасы:\n{lesson.grammar}\n\n"
                """Грамматикалық ережелерді түсінікті әрі қысқа түрде нақты мысалдармен түсіндір.

                Құрылым:
                1. Ережені қарапайым тілмен түсіндір – Оқушыға түсінікті болуы үшін, күрделі терминдерді қажетсіз қолданба.
                2. Әр ереже үшін кемінде 2 нақты мысал келтір.
                3. Оқушылар жиі қателесетін тұстарды атап өт.
                4. Қосымша түсініктеме бер (егер қажет болса) – Егер ереже ерекше жағдайларға ие болса, оны да түсіндір.

                Маңызды:
                - Сөздерді қою қара ету үшін ** қолданба.
                - Түсінікті, анық, әрі оқу оңай болатындай етіп жауап бер.
                """
            )
        elif section == "dialogue":
            prompt = (
                f"Сабақтың диалогы:\n{lesson.dialogue}\n\n"
                """Диалогтағы әр сөйлемді бөлек оқып, анық және түсінікті етіп аудар.

                Құрылым:
                1. Сөйлемді ағылшын тілінде айт.
                2. Қазақшаға аудар.
                3. Мағыналық түсіндірме бер:
                - Егер сөйлем ерекше құрылымға ие болса, оны түсіндір.
                - Кездесетін маңызды сөздер мен сөз тіркестерінің мағынасын аш.

                Маңызды:
                - Сөздерді қою қара ету үшін ** қолданба.
                - Жауап қысқа, нақты және түсінікті болсын.
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

        # Load all explanations from session and update only this lesson.
        all_explanations = request.session.get('explanations', {})
        lesson_explanations = all_explanations.get(str(lesson.id), {})
        lesson_explanations[section] = {
            'text': explanation_text,
            'audio_url': audio_url
        }
        all_explanations[str(lesson.id)] = lesson_explanations
        request.session['explanations'] = all_explanations

        return JsonResponse({
            "text": explanation_text,
            "audio_url": audio_url
        })
    return JsonResponse({"error": "Invalid request method"}, status=400)


def chat_with_gpt(request):
    """
    AJAX endpoint for a general chat interface.
    Gathers all lessons data, sets a system prompt,
    and returns GPT's response as JSON.
    """
    if request.method == "POST":
        user_question = request.POST.get("question", "")

        # Gather data from all lessons
        all_lessons = Lesson.objects.all()
        lessons_data = ""
        for lesson in all_lessons:
            lessons_data += (
                f"Lesson {lesson.id}: {lesson.title}\n"
                f"Content: {lesson.content}\n"
                f"Vocabulary: {lesson.vocabulary}\n"
                f"Grammar: {lesson.grammar}\n"
                f"Dialogue: {lesson.dialogue}\n\n"
            )

        # System prompt: user is an English teacher, with full access to lessons data
        system_prompt = (
            "You are an English teacher. You have the following lessons data:\n"
            f"{lessons_data}\n"
            "Answer the user's question in detail IN KAZAKH."
        )

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",  # Or whichever model you prefer
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
            "You are an inspiring English teacher. "
            "Generate a motivational message in Kazakh that encourages someone to learn English. "
            "Include uplifting language, practical advice, and enthusiasm."
        )
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",  # Use your preferred model.
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
