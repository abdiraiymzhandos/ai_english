from django.urls import path
from .views import lesson_list, lesson_detail, explain_section, chat_with_gpt, motivational_message
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', lesson_list, name='lesson_list'),
    path('lesson/<int:lesson_id>/', lesson_detail, name='lesson_detail'),
    path('lesson/<int:lesson_id>/explain-section/',
         explain_section, name='explain_section'),
    path('chat-with-gpt/', chat_with_gpt, name='chat_with_gpt'),
    path('motivational-message/', motivational_message, name='motivational_message'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
