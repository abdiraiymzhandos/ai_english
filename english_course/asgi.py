"""
ASGI config for english_course project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'english_course.settings')

# Interactive realtime voice now uses backend-minted OpenAI session tokens and
# browser WebRTC, so this ASGI app does not expose the old Django websocket
# bridge. Keep ASGI explicit and HTTP-only unless a new websocket architecture is
# intentionally introduced.
application = get_asgi_application()
