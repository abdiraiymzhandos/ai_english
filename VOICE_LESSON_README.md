# 🎙️ AI Voice Lesson Feature

## Overview
This feature integrates OpenAI's GPT-4 Realtime API to provide a natural conversation system where Kazakh students can practice English with an AI teacher.

## Features
- **Real-time conversation**: Natural conversation flow with AI teacher
- **Feedback prevention**: Advanced audio processing to prevent feedback loops
- **Male voice**: Uses OpenAI's "cedar" voice for consistent male teacher persona
- **Kazakh instruction**: AI speaks primarily in Kazakh with English examples
- **Premium feature**: Available only to authenticated users with subscription

## Technical Implementation

### Architecture
1. **Django Channels**: WebSocket support for real-time communication
2. **OpenAI Realtime API**: Speech-to-speech processing
3. **Audio Processing**: PCM16 format for optimal quality
4. **Feedback Prevention**: Automatic audio management to prevent echo

### Files Structure
```
lessons/
├── consumers.py          # WebSocket consumer for OpenAI bridge
├── routing.py           # WebSocket URL routing
├── templates/lessons/
│   └── lesson_detail.html  # Updated template with voice feature
static/
├── js/
│   └── voice-lesson.js  # Frontend audio streaming logic
└── css/
    └── voice-lesson.css # Premium UI styles
```

### Key Components

#### 1. WebSocket Consumer (`consumers.py`)
- Handles bidirectional communication between frontend and OpenAI
- Manages audio format conversion (WebM to PCM16)
- Implements feedback prevention logic
- Provides Kazakh teacher persona instructions

#### 2. Frontend JavaScript (`voice-lesson.js`)
- Manages microphone access and audio recording
- Handles WebSocket communication
- Implements audio visualization
- Prevents feedback loops by pausing recording during AI speech

#### 3. Premium UI (`voice-lesson.css`)
- Beautiful premium-looking interface
- WhatsApp integration for subscription
- Responsive design for mobile/desktop
- Advertisement for non-authenticated users

## Setup Instructions

### 1. Install Dependencies
```bash
pip install channels channels-redis websockets
```

### 2. Update Django Settings
```python
INSTALLED_APPS = [
    # ... existing apps
    'channels',
    'lessons',
]

ASGI_APPLICATION = "english_course.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}
```

### 3. Environment Variables
Ensure OpenAI API key is set:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Collect Static Files
```bash
python manage.py collectstatic
```

## Usage

### For Authenticated Users
1. Navigate to any lesson detail page
2. See the premium AI Voice Teacher section
3. Click "WhatsApp арқылы жазылу" to subscribe
4. After subscription, the voice lesson interface becomes available

### For Non-authenticated Users
1. See advertisement for the voice lesson feature
2. Options to register or login
3. After authentication, can view subscription options

## Audio Feedback Prevention

The system implements multiple layers of feedback prevention:

1. **Echo Cancellation**: Browser-level audio constraints
2. **Recording Pause**: Automatically pauses user recording during AI speech
3. **Audio Context Management**: Proper audio stream management
4. **Voice Activity Detection**: OpenAI's server-side VAD for turn-taking

## Pricing
- **Monthly subscription**: 22,500 KZT per month
- **Contact**: WhatsApp +77781029394
- **Payment**: Through WhatsApp consultation

## AI Teacher Persona

The AI teacher is configured with these characteristics:
- Speaks primarily in Kazakh
- Provides English examples and corrections
- Patient and encouraging
- Adapts to student's level
- Corrects grammar and pronunciation gently
- Uses male voice (Cedar) from OpenAI

## Troubleshooting

### Common Issues

1. **Microphone Permission Denied**
   - Ensure HTTPS is enabled for production
   - Check browser permissions

2. **WebSocket Connection Failed**
   - Verify Django Channels is properly configured
   - Check firewall settings

3. **Audio Quality Issues**
   - Ensure stable internet connection
   - Use headphones to prevent feedback

4. **OpenAI API Errors**
   - Verify API key is valid
   - Check OpenAI account limits

### Debug Mode
Enable debug logging in Django settings:
```python
LOGGING = {
    'loggers': {
        'lessons.consumers': {
            'level': 'DEBUG',
        },
    },
}
```

## Security Considerations

1. **API Key Protection**: OpenAI API key is server-side only
2. **User Authentication**: Premium feature requires authentication
3. **Rate Limiting**: Consider implementing rate limiting for WebSocket connections
4. **Audio Data**: Audio is processed in real-time, not stored

## Performance Optimization

1. **Audio Compression**: Uses WebM with Opus codec for efficient streaming
2. **Real-time Processing**: PCM16 format for optimal OpenAI compatibility
3. **Memory Management**: Proper cleanup of audio contexts and streams

## Future Enhancements

1. **Progress Tracking**: Track conversation time and improvements
2. **Lesson Integration**: Better integration with specific lesson content
3. **Recording Playback**: Option to review conversation sessions
4. **Multiple Voices**: Support for different AI teacher voices
5. **Language Mixing**: Better control over Kazakh/English ratio

## Support

For technical support or subscription questions, contact via WhatsApp: +77781029394