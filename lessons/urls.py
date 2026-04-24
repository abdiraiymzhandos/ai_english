from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import register, lesson_list, lesson_detail, explain_section, chat_with_gpt, motivational_message, advertisement, account_locked, vocabulary_list, register_lead, mint_realtime_token
from .views import start_quiz, submit_answer, service_worker, pwa_manifest, privacy_policy, profile, check_translator_access, mint_translator_token
from .views_classroom import (
    classroom_dashboard,
    classroom_group_create,
    classroom_group_detail,
    classroom_group_edit,
    classroom_student_create,
    classroom_student_add_photo,
    classroom_student_delete,
    classroom_student_voice_embedding,
    classroom_session_select,
    classroom_session,
    classroom_student_photo,
    mint_realtime_classroom_token,
)
from django.conf import settings
from django.conf.urls.static import static
from django.urls import reverse_lazy


urlpatterns = [
    # PWA files - must be served from root
    path('sw.js', service_worker, name='service_worker'),
    path('manifest.json', pwa_manifest, name='pwa_manifest'),

    path('', lesson_list, name='lesson_list'),
    path('lesson/<int:lesson_id>/', lesson_detail, name='lesson_detail'),
    path('lesson/<int:lesson_id>/explain-section/',
         explain_section, name='explain_section'),
    path('chat-with-gpt/<int:lesson_id>/', chat_with_gpt, name='chat_with_gpt'),
    path('motivational-message/', motivational_message, name='motivational_message'),
    path('start-quiz/<int:lesson_id>/', start_quiz, name='start_quiz'),
    path('submit-answer/<int:lesson_id>/', submit_answer, name='submit_answer'),
    path('advertisement/', advertisement, name='advertisement'),
    path('login/', LoginView.as_view(template_name='lessons/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', LogoutView.as_view(next_page=reverse_lazy('login')), name='logout'),
    path('profile/', profile, name='profile'),
    path('account-locked/', account_locked, name='account_locked'),
    path('vocabulary/', vocabulary_list, name='vocabulary_list'),
    path("register-lead/", register_lead, name="register_lead"),
    path('register/', register, name='register'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('api/realtime/token/<int:lesson_id>/', mint_realtime_token, name='mint_realtime_token'),
    path('api/realtime/classroom/<int:lesson_id>/<int:group_id>/', mint_realtime_classroom_token, name='mint_realtime_classroom_token'),
    path('api/translator/check-access/', check_translator_access, name='check_translator_access'),
    path('api/translator/token/', mint_translator_token, name='mint_translator_token'),
    path('classroom/', classroom_dashboard, name='classroom_dashboard'),
    path('classroom/new/', classroom_group_create, name='classroom_group_create'),
    path('classroom/<int:group_id>/', classroom_group_detail, name='classroom_group_detail'),
    path('classroom/<int:group_id>/edit/', classroom_group_edit, name='classroom_group_edit'),
    path('classroom/<int:group_id>/students/new/', classroom_student_create, name='classroom_student_create'),
    path('classroom/student/<int:student_id>/photo/', classroom_student_add_photo, name='classroom_student_add_photo'),
    path('classroom/student/<int:student_id>/voice/', classroom_student_voice_embedding, name='classroom_student_voice_embedding'),
    path('classroom/student/<int:student_id>/delete/', classroom_student_delete, name='classroom_student_delete'),
    path('classroom/photo/<int:photo_id>/', classroom_student_photo, name='classroom_student_photo'),
    path('classroom/session/', classroom_session_select, name='classroom_session_select'),
    path('classroom/session/<int:group_id>/<int:lesson_id>/', classroom_session, name='classroom_session'),
]
