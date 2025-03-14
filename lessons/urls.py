from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import lesson_list, lesson_detail, explain_section, chat_with_gpt, motivational_message
from .views import start_quiz, submit_answer
from django.conf import settings
from django.conf.urls.static import static
from django.urls import reverse_lazy


urlpatterns = [
    path('', lesson_list, name='lesson_list'),
    path('lesson/<int:lesson_id>/', lesson_detail, name='lesson_detail'),
    path('lesson/<int:lesson_id>/explain-section/',
         explain_section, name='explain_section'),
    path('chat-with-gpt/', chat_with_gpt, name='chat_with_gpt'),
    path('motivational-message/', motivational_message, name='motivational_message'),
    path('start-quiz/<int:lesson_id>/', start_quiz, name='start_quiz'),
    path('submit-answer/<int:lesson_id>/', submit_answer, name='submit_answer'),
    path('login/', LoginView.as_view(template_name='lessons/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', LogoutView.as_view(next_page=reverse_lazy('login')), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
