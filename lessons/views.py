import openai
from openai import OpenAI
from django.shortcuts import render, get_object_or_404
from .models import Lesson
from django.http import JsonResponse
from django.conf import settings
import os
import glob
import uuid
import re


def lesson_list(request):
    lessons = Lesson.objects.all()
    return render(request, 'lessons/lesson_list.html', {'lessons': lessons})

def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    # Retrieve explanations specific to this lesson, using its ID as key.
    all_explanations = request.session.get('explanations', {})
    explanations = all_explanations.get(str(lesson.id), {})
    return render(request, 'lessons/lesson_detail.html', {
        'lesson': lesson,
        'explanations': explanations
    })


# def explain_section(request, lesson_id):
    """
    AJAX endpoint: Uses multi-step prompting to generate a detailed explanation 
    (both text and audio) for a given section. The explanation is saved in the session
    (keyed by lesson ID) and returned as JSON.
    """
    if request.method == "POST":
        section = request.POST.get("section")
        lesson = get_object_or_404(Lesson, id=lesson_id)

        # Build the base text (lesson data) and instructions based on the section.
        if section == "content":
            lesson_data = lesson.content
            section_title = "Сабақтың мазмұны"
            instruction_outline = "Осы сабақ мазмұнын түсіндіру үшін егжей-тегжейлі жоспар жасаңыз. Жоспарда жалпы қысқаша мазмұны, негізгі идеялар және маңызды бөлшектер көрсетілсін."
            instruction_expand = "Осы жоспардың әр тармағын кеңінен, нақты мысалдармен және аудармалармен түсіндіріңіз. Қазақ тілінде түсіндіріңіз."
        elif section == "vocabulary":
            lesson_data = lesson.vocabulary
            section_title = "Сабақтың сөздігі"
            instruction_outline = "Осы сабақ сөздігін түсіндіру үшін егжей-тегжейлі жоспар жасаңыз. Әрбір сөздің мағынасы, қолданылуы және мысалдарын қамтыңыз."
            instruction_expand = "Осы жоспарды пайдаланып, әрбір сөздің мағынасын, қолданылуын және мысалдарын кеңінен түсіндіріңіз. Қазақ тілінде түсіндіріңіз."
        elif section == "grammar":
            lesson_data = lesson.grammar
            section_title = "Сабақтың грамматикасы"
            instruction_outline = "Осы сабақтың грамматикасын түсіндіру үшін егжей-тегжейлі жоспар жасаңыз. Негізгі ережелер мен қолдану мысалдарын қамтыңыз."
            instruction_expand = "Осы жоспарды пайдаланып, грамматикалық ережелерді және мысалдарды кеңінен түсіндіріңіз. Қазақ тілінде түсіндіріңіз."
        elif section == "dialogue":
            lesson_data = lesson.dialogue
            section_title = "Сабақтың диалогы"
            instruction_outline = "Осы диалогты түсіндіру үшін егжей-тегжейлі жоспар жасаңыз. Әр сөйлемді бөлек қарастырып, аудармасын беріңіз."
            instruction_expand = "Осы жоспарды пайдаланып, әр сөйлемді аударып, мағынасын және қолданылуын кеңінен түсіндіріңіз. Қазақ тілінде түсіндіріңіз."
        else:
            return JsonResponse({"error": "Бұрыс бөлім көрсетілді."}, status=400)

        # STEP 1: Generate an outline.
        outline_prompt = (
            f"{section_title}:\n{lesson_data}\n\n"
            f"{instruction_outline}\n\n"
            "Жоспарды нөмірленген тізім түрінде беріңіз."
        )
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            outline_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": outline_prompt}],
                temperature=0.7,
            )
            outline_text = outline_response.choices[0].message.content
        except Exception as e:
            return JsonResponse({"error": f"OpenAI қатесі (outline): {str(e)}"}, status=500)

        # STEP 2: Expand the outline.
        expand_prompt = (
            f"Міне, жоспар:\n{outline_text}\n\n"
            f"{instruction_expand}\n\n"
            f"Сабақтың толық деректері:\n"
            f"Title: {lesson.title}\n"
            f"{section_title}: {lesson_data}\n\n"
            "Жауапты қазақ тілінде беріңіз."
        )
        try:
            expand_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": expand_prompt}],
                temperature=0.7,
            )
            detailed_explanation = expand_response.choices[0].message.content
        except Exception as e:
            return JsonResponse({"error": f"OpenAI қатесі (expand): {str(e)}"}, status=500)

        # Use detailed_explanation as final explanation_text.
        explanation_text = detailed_explanation

        # Generate audio explanation as before.
        audio_url = None
        if explanation_text:
            media_dir = settings.MEDIA_ROOT
            audio_filename = f"audio_lesson_{lesson.id}_{section}.mp3"
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

        # Save the explanation in session.
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
                "Әр сөйлемді оқып, түсіндіріп, аударып бер. Сөздерді қою қара ету үшін ** қолданба."
            )
        elif section == "vocabulary":
            prompt = (
                f"Сабақтың сөздігі:\n{lesson.vocabulary}\n\n"
                "Әрбір сөздің мағынасын және қолданылуын түсіндір. Мысал келтіру керек емес. Сөздерді қою қара ету үшін ** қолданба."
            )
        elif section == "grammar":
            prompt = (
                f"Сабақтың грамматикасы:\n{lesson.grammar}\n\n"
                "Грамматикалық ережелерді нақты мысалдармен түсіндір. Сөздерді қою қара ету үшін ** қолданба."
            )
        elif section == "dialogue":
            prompt = (
                f"Сабақтың диалогы:\n{lesson.dialogue}\n\n"
                "Диалогтағы сөйлемдерді ағылшыншасын оқып, түсіндіріп аударып бер. Сөздерді қою қара ету үшін ** қолданба."
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
