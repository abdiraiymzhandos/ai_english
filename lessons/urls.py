from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import register, lesson_list, lesson_detail, explain_section, chat_with_gpt, motivational_message, advertisement, account_locked, vocabulary_list, register_lead, mint_realtime_token
from .views import start_quiz, submit_answer, service_worker, pwa_manifest, privacy_policy, profile
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
]
