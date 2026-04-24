"""
❌ DEPRECATED - DO NOT USE - CAUSES DOUBLE BILLING ❌

This WebSocket consumer creates a SECOND connection to OpenAI Realtime API,
resulting in DOUBLE COSTS ($1/minute instead of $0.25/minute).

The voice lesson now uses WebRTC ONLY via voice-lesson.js.

This file is kept for historical reference only. It is NO LONGER ROUTED by
`lessons/routing.py` or exposed from `english_course/asgi.py`.

Do not use this consumer for the active voice lesson architecture. The current
interactive path is:
1. Backend token minting in `lessons.views.mint_realtime_token`
2. Browser WebRTC session setup in `static/js/voice-lesson.js`

If you see websocket voice traffic or duplicate OpenAI session usage, verify
that this historical consumer has not been reintroduced into routing.
"""

import os
import asyncio
import websockets
import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

class VoiceLessonConsumer(AsyncWebsocketConsumer):
    """
    ❌ DEPRECATED - This consumer is NOT IN USE
    Voice lessons use WebRTC directly (see: static/js/voice-lesson.js)
    """
    async def connect(self):
        self.lesson_id = self.scope['url_route']['kwargs']['lesson_id']
        self.openai_ws = None
        self.listen_task = None
        self.has_pending_audio = False
        self.awaiting_response = False
        self.user_is_speaking = False

        try:
            logger.info(f"🔌 New WebSocket connection request for lesson {self.lesson_id}")

            # Get lesson data
            lesson = await self.get_lesson_data()
            if not lesson:
                logger.error(f"❌ Lesson {self.lesson_id} not found!")
                await self.close()
                return

            await self.accept()
            logger.info(f"✅ WebSocket connected for lesson {self.lesson_id}")

            # Connect to OpenAI Realtime API
            await self.connect_to_openai(lesson)

        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception args: {e.args}")
            await self.close()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected with code {close_code}")
        if self.openai_ws:
            try:
                await self.openai_ws.close()
            except Exception as e:
                logger.error(f"Error closing OpenAI WebSocket: {e}")
        if self.listen_task and not self.listen_task.done():
            self.listen_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming audio data from frontend"""
        try:
            if bytes_data and self.openai_ws and hasattr(self.openai_ws, 'open') and self.openai_ws.open:
                # Convert bytes to base64 for OpenAI
                audio_base64 = base64.b64encode(bytes_data).decode('utf-8')

                # Send audio data to OpenAI
                audio_message = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_base64
                }
                await self.openai_ws.send(json.dumps(audio_message))
                logger.debug(f"Sent audio chunk of {len(bytes_data)} bytes")
                self.has_pending_audio = True

            elif text_data:
                # Handle text commands (like starting/stopping)
                data = json.loads(text_data)
                logger.debug(f"Received text command: {data.get('type')}")

                if data.get('type') == 'start_recording':
                    # Don't create another response if AI is already responding
                    logger.info("Recording started, AI should already be responding from initial greeting")
                elif data.get('type') == 'stop_recording':
                    await self._finalize_user_audio(reason="client_stop")
                    await self.stop_conversation()

        except websockets.exceptions.ConnectionClosed:
            logger.warning("OpenAI WebSocket connection closed during receive")
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Аудио деректерін өңдеуде қате'
            }))

    async def connect_to_openai(self, lesson):
        """Connect to OpenAI Realtime API and configure session"""
        try:
            logger.info("🚀 Starting OpenAI connection process...")

            # Create lesson instructions
            lesson_instructions = self.create_lesson_instructions(lesson)
            logger.info(f"📝 Lesson instructions created: {len(lesson_instructions)} characters")

            # Connect to OpenAI
            headers = [
                ("Authorization", f"Bearer {settings.OPENAI_API_KEY}"),
                ("OpenAI-Beta", "realtime=v1"),
            ]
            logger.info("🔑 Connecting to OpenAI with headers...")

            self.openai_ws = await websockets.connect(
                "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
                additional_headers=headers,
            )
            logger.info("✅ OpenAI WebSocket connection established!")

            # Configure session
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": lesson_instructions,
                    "voice": "ash",  # Use clearer voice (ash or alloy)
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    },
                    "tools": [],
                    "tool_choice": "auto",
                    "temperature": 0.8,
                    "max_response_output_tokens": 4096
                }
            }

            logger.info("📤 Sending session configuration to OpenAI...")
            await self.openai_ws.send(json.dumps(session_config))
            logger.info("✅ Session configuration sent to OpenAI")

            # Start listening to OpenAI responses
            logger.info("👂 Starting OpenAI listener task...")
            self.listen_task = asyncio.create_task(self.listen_to_openai())

            # Wait a moment for session to be configured
            await asyncio.sleep(1)

            # Immediately start the lesson with AI greeting
            logger.info("🎤 Starting lesson immediately...")
            await self.start_lesson_immediately()

        except Exception as e:
            logger.error(f"❌ Failed to connect to OpenAI: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception args: {e.args}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Мүмкін емес AI-мен байланысуға: {str(e)}'
            }))

    async def listen_to_openai(self):
        """Listen for responses from OpenAI Realtime API"""
        try:
            logger.info("👂 Starting to listen for OpenAI messages...")
            async for message in self.openai_ws:
                data = json.loads(message)
                msg_type = data.get('type', 'unknown')
                logger.info(f"📨 Received from OpenAI: {msg_type}")

                # Handle different types of responses
                if msg_type == "session.updated":
                    logger.info("✅ Session successfully updated by OpenAI")

                elif msg_type == "response.audio.delta":
                    # Send audio delta back to frontend
                    delta_len = len(data.get('delta', ''))
                    logger.info(f"🔊 Received audio delta: {delta_len} characters")
                    if delta_len > 0:
                        audio_bytes = base64.b64decode(data["delta"])
                        await self.send(bytes_data=audio_bytes)
                        logger.info(f"📤 Sent {len(audio_bytes)} audio bytes to frontend")

                elif msg_type == "response.audio.done":
                    # Audio response complete
                    logger.info("✅ Audio response completed")
                    await self.send(text_data=json.dumps({
                        'type': 'audio_complete'
                    }))
                    self.awaiting_response = False

                elif msg_type == "response.created":
                    logger.info("🎬 OpenAI response created")
                    self.awaiting_response = True

                elif msg_type == "response.done":
                    logger.info("✅ OpenAI response done")
                    self.awaiting_response = False

                elif msg_type == "conversation.item.created":
                    logger.info("💬 Conversation item created")

                elif msg_type == "input_audio_buffer.speech_started":
                    # User started speaking - stop any ongoing AI audio
                    logger.info("👤 User speech started")
                    self.user_is_speaking = True
                    await self.send(text_data=json.dumps({
                        'type': 'user_speech_started'
                    }))

                elif msg_type == "input_audio_buffer.speech_stopped":
                    # User stopped speaking
                    logger.info("🔇 User speech stopped")
                    self.user_is_speaking = False
                    await self.send(text_data=json.dumps({
                        'type': 'user_speech_stopped'
                    }))
                    await self._finalize_user_audio(reason="vad_stop")

                elif msg_type == "conversation.item.input_audio_transcription.completed":
                    # Send transcription to frontend for debugging
                    transcript = data.get("transcript", "")
                    logger.info(f"📝 Transcription: {transcript}")
                    await self.send(text_data=json.dumps({
                        'type': 'transcription',
                        'text': transcript
                    }))

                elif msg_type == "error":
                    logger.error(f"❌ OpenAI API error: {data}")
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'AI қызметінде қате орын алды'
                    }))

                else:
                    # Log all other message types for debugging
                    logger.info(f"📋 OpenAI message [{msg_type}]: {json.dumps(data, indent=2)}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 OpenAI WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ Error listening to OpenAI: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception args: {e.args}")

    async def start_conversation(self):
        """Start a new conversation turn"""
        try:
            if self.openai_ws:
                # Create a response to trigger AI to speak
                response_create = {
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"]
                    }
                }
                await self.openai_ws.send(json.dumps(response_create))

        except Exception as e:
            logger.error(f"Error starting conversation: {e}")

    async def stop_conversation(self):
        """Stop current conversation"""
        try:
            if self.openai_ws:
                # Cancel any ongoing response
                cancel_message = {
                    "type": "response.cancel"
                }
                await self.openai_ws.send(json.dumps(cancel_message))

        except Exception as e:
            logger.error(f"Error stopping conversation: {e}")

    async def start_lesson_immediately(self):
        """Start the lesson with AI greeting and introduction"""
        try:
            if not self.openai_ws:
                logger.error("❌ OpenAI WebSocket is not available!")
                return

            logger.info("💬 Creating initial greeting message...")

            # Create an immediate response to make AI start talking
            greeting_message = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Сәлеметсіз бе! Мен ағылшын тілін үйренгім келеді. Осы сабақты бастап, маған көмектесе аласыз ба?"
                        }
                    ]
                }
            }

            # Send the greeting message
            logger.info("📤 Sending greeting message to OpenAI...")
            await self.openai_ws.send(json.dumps(greeting_message))
            logger.info("✅ Sent initial greeting to OpenAI")

            # Wait a moment before creating response
            logger.info("⏱️ Waiting 0.5 seconds before creating response...")
            await asyncio.sleep(0.5)

            # Create a response to trigger AI to speak
            response_create = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "Сәлемдесіп, өзіңізді таныстырыңыз және сабақты бастаңыз. Қазақша сөйлеңіз."
                }
            }

            logger.info("📤 Sending response.create to trigger AI speech...")
            await self.openai_ws.send(json.dumps(response_create))
            logger.info("✅ Triggered AI response for lesson start")
            self.awaiting_response = True

        except Exception as e:
            logger.error(f"❌ Error starting lesson immediately: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception args: {e.args}")

    def create_lesson_instructions(self, lesson):
        """Create detailed instructions for the AI teacher"""
        lesson_data = (
            f"Lesson {lesson.id}: {lesson.title}\n"
            f"Content: {lesson.content}\n"
            f"Vocabulary: {lesson.vocabulary}\n"
            f"Grammar: {lesson.grammar}\n"
            f"Dialogue: {lesson.dialogue}\n"
        )

        instructions = f"""
        Сіз қазақ тілінде сөйлейтін ағылшын тілі мұғаліміссіз. Сіздің міндетіңіз - қазақстандық студенттерге ағылшын тілін үйрету.

        МАҢЫЗДЫ НҰСҚАУЛАР:
        1. МІНДЕТТІ ТҮРДЕ қазақ тілінде сөйлеңіз, ағылшынша мысалдар беріңіз
        2. БЕЛСЕНДІ болыңыз - сұрақтар қойыңыз, жауап күтіңіз
        3. Сабақты ДЕРЕУ бастаңыз - студентті қарсы алып, өзіңізді таныстырыңыз
        4. Грамматика мен айтылымды жұмсақ түрде түзетіңіз
        5. Қысқа және түсінікті сөйлемдер қолданыңыз
        6. Студенттің жауабын күтіп, одан кейін жалғастырыңыз

        САБАҚ МАТЕРИАЛЫ:
        {lesson_data}

        АЛҒАШҚЫ СӘЛЕМДЕСУ (міндетті):
        "Сәлеметсіз бе! Мен сіздің ағылшын тілі мұғаліміңізбін. Менің атым Айдана. Бүгін біз '{lesson.title}' сабағын өтеміз. Сіздің атыңыз кім? Дайынсыз ба?"

        Осылай бастап, студенттің жауабын күтіңіз.
        """

        return instructions.strip()

    async def get_lesson_data(self):
        """Get lesson data from database"""
        try:
            from asgiref.sync import sync_to_async
            from .models import Lesson

            @sync_to_async
            def fetch_lesson():
                try:
                    return Lesson.objects.get(id=self.lesson_id)
                except Lesson.DoesNotExist:
                    return None

            return await fetch_lesson()

        except Exception as e:
            logger.error(f"Error fetching lesson: {e}")
            return None

    async def _finalize_user_audio(self, *, reason: str = "unknown"):
        """Commit buffered audio and ask the model to respond."""
        if not self.openai_ws:
            logger.warning(f"Finalize requested ({reason}) but OpenAI socket missing")
            return

        if self.awaiting_response:
            logger.info(f"Skipping finalize ({reason}) — already awaiting response")
            return

        if not self.has_pending_audio:
            logger.info(f"No pending audio to commit on finalize ({reason})")
            return

        try:
            logger.info(f"🔒 Committing audio buffer due to {reason}")
            await self.openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

            response_payload = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": (
                        "Студент жауап берді. Сабақты қазақ тілінде жалғастырып, түсінікті түрде"
                        " жауап беріңіз, әрі қарай сұрақ қойыңыз."
                    )
                }
            }

            await self.openai_ws.send(json.dumps(response_payload))
            logger.info("📨 Requested AI response after user speech")
            self.awaiting_response = True
            self.has_pending_audio = False

        except Exception as e:
            logger.error(f"❌ Failed to finalize audio ({reason}): {e}")
