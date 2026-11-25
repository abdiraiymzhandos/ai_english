"""
URL configuration for english_course project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/whatsapp/', include('whatsapp_agent.urls')),
    path('', include('lessons.urls')),
]

if settings.DEBUG:
    from pathlib import Path
    from django.http import Http404
    from django.views.static import serve

    def development_media(request, path, document_root):
        # Canonical lesson MP3 URLs have an access-controlled view above. The generic
        # debug file server must also reject alternate paths resolving to the same file.
        name = (Path(document_root) / path).resolve().name
        if name.startswith("audio_lesson_") and name.endswith(".mp3"):
            raise Http404
        return serve(request, path, document_root=document_root)

    urlpatterns += static(settings.MEDIA_URL, view=development_media, document_root=settings.MEDIA_ROOT)
