/**
 * Voice Lesson JavaScript for OpenAI Realtime WebRTC Integration
 * Handles microphone capture, ephemeral token minting, WebRTC session, and UI interactions.
 */

class VoiceLessonManager {
    constructor(lessonId) {
        this.lessonId = lessonId;
        this.peerConnection = null;
        this.dataChannel = null;
        this.remoteAudioEl = null;
        this.remoteStream = null;

        this.audioContext = null;
        this.microphone = null;
        this.isRecording = false;
        this.isConnected = false;
        this.clientSecret = null;

        this.volumeMeter = null;
        this.volumeAnimationFrame = null;

        this.audioConstraints = {
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1
            },
            video: false
        };

        this.lessonStartTime = null;
        this.lessonTimerInterval = null;
        this.eventsChannel = null;

        this.injectPremiumStyles();
        this.initializeUI();
    }

    initializeUI() {
        this.createVoiceLessonUI();
        this.attachEventListeners();
    }

    createVoiceLessonUI() {
        const container = document.getElementById('voice-lesson-container');
        if (!container) return;

        container.innerHTML = `
            <div class="voice-lesson-card premium">
                <div class="voice-lesson-header">
                    <div class="voice-title">
                        <span class="voice-icon">🎧</span>
                        <div>
                            <h3>AI Premium Voice Coach</h3>
                            <p>Kazakh mentor • English mastery</p>
                        </div>
                    </div>
                    <div class="voice-meta">
                        <div class="connection-status" id="connection-status">
                            <span class="status-indicator offline"></span>
                            <span class="status-text">Байланыс жоқ</span>
                        </div>
                        <div class="lesson-timer" id="lesson-timer">00:00</div>
                    </div>
                </div>

                <div class="voice-lesson-content">
                    <div class="voice-controls">
                        <div class="visualizer-wrap">
                            <div class="audio-visualizer" id="audio-visualizer">
                                <div class="wave-container">
                                    <div class="wave-bar"></div>
                                    <div class="wave-bar"></div>
                                    <div class="wave-bar"></div>
                                    <div class="wave-bar"></div>
                                    <div class="wave-bar"></div>
                                </div>
                            </div>
                            <div class="volume-meter premium">
                                <span>Mic level</span>
                                <div class="volume-bar-container">
                                    <div class="volume-bar" id="volume-bar"></div>
                                </div>
                                <span id="volume-percentage">0%</span>
                            </div>
                        </div>

                        <div class="lesson-controls">
                            <button id="start-voice-lesson" class="btn-voice-primary">
                                <i class="fas fa-play"></i>
                                <span>Сессияны бастау</span>
                            </button>
                            <button id="stop-voice-lesson" class="btn-voice-secondary" style="display: none;">
                                <i class="fas fa-square"></i>
                                <span>Тоқтату</span>
                            </button>
                        </div>

                        <div class="connection-info">
                            <span id="audio-status-text">Күту режимі</span>
                        </div>
                    </div>

                    <div class="voice-footer">
                        <p>Наушник қолданыңыз — айқын дыбыс және кері байланыссыз тәжірибе.</p>
                    </div>

                    <audio id="voice-lesson-remote-${this.lessonId}" autoplay playsinline style="display: none;"></audio>
                </div>
            </div>
        `;

        this.remoteAudioEl = document.getElementById(`voice-lesson-remote-${this.lessonId}`);
        if (this.remoteAudioEl) {
            this.remoteAudioEl.autoplay = true;
            this.remoteAudioEl.playsInline = true;
        }
    }

    attachEventListeners() {
        const startBtn = document.getElementById('start-voice-lesson');
        const stopBtn = document.getElementById('stop-voice-lesson');

        if (startBtn) {
            startBtn.addEventListener('click', () => this.startVoiceLesson());
        }

        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopVoiceLesson());
        }
    }

    async startVoiceLesson() {
        if (this.peerConnection) {
            console.warn('Voice lesson already active');
            return;
        }

        try {
            this.updateUI('connecting');

            await this.initializeAudio();
            this.startRecording();

            await this.startRealtimeSession();
            this.updateUI('connected');
            this.updateAudioStatus('recording');
            this.startLessonTimer();
        } catch (error) {
            console.error('Error starting voice lesson:', error);
            this.updateUI('error', error.message || 'Байланыс қатесі');
            this.updateAudioStatus('stopped');
            await this.stopRealtimeSession();
            this.stopRecording();
            this.cleanup();
        }
    }

    async stopVoiceLesson() {
        try {
            this.updateUI('disconnecting');
            await this.stopRealtimeSession();
            this.stopRecording();
            this.cleanup();
            this.updateUI('disconnected');
        } catch (error) {
            console.error('Error stopping voice lesson:', error);
            this.updateUI('error', error.message || 'Тоқтату кезінде қате');
        }
    }

    async initializeAudio() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Микрофонға қол жеткізу мүмкін емес');
        }

        if (!this.audioContext) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContextClass();
        }

        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        if (!this.microphone) {
            const stream = await this.requestMicrophoneStream();
            this.microphone = stream;

            const source = this.audioContext.createMediaStreamSource(stream);
            this.setupVolumeMeter(source);
        }
    }

    setupVolumeMeter(source) {
        const analyser = this.audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        this.volumeMeter = () => {
            analyser.getByteFrequencyData(dataArray);

            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
            }
            const average = sum / bufferLength;
            const volumePercentage = Math.round((average / 255) * 100);

            const volumeBar = document.getElementById('volume-bar');
            const volumeText = document.getElementById('volume-percentage');
            if (volumeBar && volumeText) {
                volumeBar.style.width = volumePercentage + '%';
                volumeText.textContent = volumePercentage + '%';

                if (volumePercentage > 60) {
                    volumeBar.style.backgroundColor = '#4CAF50';
                } else if (volumePercentage > 20) {
                    volumeBar.style.backgroundColor = '#FFC107';
                } else {
                    volumeBar.style.backgroundColor = '#f44336';
                }
            }

            if (this.isRecording) {
                this.volumeAnimationFrame = requestAnimationFrame(this.volumeMeter);
            }
        };
    }

    ensureRemoteAudioElement() {
        if (this.remoteAudioEl && this.remoteAudioEl.isConnected) {
            return this.remoteAudioEl;
        }

        let audioEl = document.getElementById(`voice-lesson-remote-${this.lessonId}`);
        if (!audioEl) {
            audioEl = document.createElement('audio');
            audioEl.id = `voice-lesson-remote-${this.lessonId}`;
            audioEl.style.display = 'none';
            audioEl.autoplay = true;
            audioEl.playsInline = true;
            const container = document.getElementById('voice-lesson-container');
            (container || document.body).appendChild(audioEl);
        }

        audioEl.autoplay = true;
        audioEl.playsInline = true;
        this.remoteAudioEl = audioEl;
        return audioEl;
    }

    async fetchRealtimeToken() {
        const response = await fetch(`/api/realtime/token/${this.lessonId}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || 'Эфемералды токен алу мүмкін болмады');
        }

        return response.json();
    }

    async startRealtimeSession() {
        const tokenPayload = await this.fetchRealtimeToken();
        const clientSecret = tokenPayload?.client_secret?.value || tokenPayload?.client_secret;
        if (!clientSecret) {
            throw new Error('OpenAI-тен дұрыс емес жауап алынды');
        }
        this.clientSecret = clientSecret;

        const pc = new RTCPeerConnection();
        this.peerConnection = pc;

        const audioEl = this.ensureRemoteAudioElement();
        pc.ontrack = (event) => {
            const [stream] = event.streams;
            if (stream) {
                this.remoteStream = stream;
                audioEl.srcObject = stream;
                audioEl.style.display = 'none';
                const playPromise = audioEl.play();
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch((err) => console.warn('Remote audio play blocked:', err));
                }
                this.updateAudioStatus('ai_talking');
            }

            const track = event.track;
            if (track) {
                track.onended = () => {
                    this.updateAudioStatus('recording');
                };
            }
        };

        pc.onconnectionstatechange = () => {
            if (pc.connectionState === 'connected') {
                this.isConnected = true;
                this.updateUI('connected');
                this.updateAudioStatus('recording');
            } else if (pc.connectionState === 'failed') {
                this.updateUI('error', 'Байланыс сәтсіз аяқталды');
            } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
                this.isConnected = false;
            }
        };

        pc.ondatachannel = (event) => {
            const channel = event.channel;
            this.eventsChannel = channel;
            channel.onmessage = (e) => this.handleRealtimeMessage(e.data);
            channel.onopen = () => {
                // ensure modalities include text + audio
                try {
                    channel.send(JSON.stringify({
                        type: 'session.update',
                        session: { modalities: ['audio', 'text'] },
                    }));
                    channel.send(JSON.stringify({ type: 'response.create' }));
                } catch (err) {
                    console.warn('Failed to send session update on events channel:', err);
                }
            };
        };

        this.dataChannel = pc.createDataChannel('lesson-events');
        this.dataChannel.onmessage = (e) => this.handleRealtimeMessage(e.data);
        this.dataChannel.onopen = () => {
            if (!this.eventsChannel || this.eventsChannel.readyState !== 'open') {
                try {
                    this.dataChannel.send(JSON.stringify({
                        type: 'session.update',
                        session: { modalities: ['audio', 'text'] },
                    }));
                    this.dataChannel.send(JSON.stringify({ type: 'response.create' }));
                } catch (err) {
                    console.warn('Failed to send session update on custom channel:', err);
                }
            }
        };

        if (this.microphone) {
            this.microphone.getAudioTracks().forEach((track) => {
                pc.addTrack(track, this.microphone);
            });
        }

        const offer = await pc.createOffer({ offerToReceiveAudio: true });
        await pc.setLocalDescription(offer);

        const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=gpt-realtime`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${clientSecret}`,
                'Content-Type': 'application/sdp'
            },
            body: offer.sdp
        });

        if (!sdpResponse.ok) {
            const text = await sdpResponse.text();
            throw new Error(text || 'OpenAI Realtime SDP қатесі');
        }

        const answerSDP = await sdpResponse.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSDP });

        this.isConnected = true;
    }

    async stopRealtimeSession() {
        if (this.dataChannel) {
            try { this.dataChannel.close(); } catch (e) { /* ignore */ }
            this.dataChannel = null;
        }

        this.eventsChannel = null;

        if (this.peerConnection) {
            try {
                this.peerConnection.getSenders().forEach((sender) => {
                    if (sender && sender.track) {
                        sender.track.stop();
                    }
                });
                this.peerConnection.close();
            } catch (e) {
                console.warn('Error closing peer connection:', e);
            }
        }

        this.peerConnection = null;
        this.clientSecret = null;
        this.isConnected = false;

        if (this.remoteAudioEl) {
            this.remoteAudioEl.pause();
            this.remoteAudioEl.srcObject = null;
            this.remoteAudioEl.style.display = 'none';
        }

        this.remoteStream = null;
        this.stopLessonTimer();
    }

    handleRealtimeMessage(payload) {
        if (!payload) return;

        let data;
        try {
            data = typeof payload === 'string' ? JSON.parse(payload) : payload;
        } catch (error) {
            console.warn('Non-JSON realtime message:', payload);
            return;
        }

        const type = data?.type || '';
        if (!type) return;

        switch (type) {
            case 'response.completed':
            case 'response.done':
                this.updateAudioStatus('recording');
                break;

            // === Speech activity ===
            case 'input_audio_buffer.speech_started':
                this.showSpeechIndicator(true);
                break;
            case 'input_audio_buffer.speech_stopped':
                this.showSpeechIndicator(false);
                break;

            // === Error handling ===
            case 'error':
                if (data.error?.message) {
                    this.updateUI('error', data.error.message);
                }
                break;

            default:
                console.debug('Realtime event:', data);
        }
    }

    startRecording() {
        if (this.isRecording) return;
        this.isRecording = true;
        this.animateVisualizer(true);
        if (this.volumeMeter) {
            this.volumeMeter();
        }
        this.updateAudioStatus('recording');
    }

    stopRecording() {
        if (!this.isRecording) return;
        this.isRecording = false;
        this.animateVisualizer(false);
        if (this.volumeAnimationFrame) {
            cancelAnimationFrame(this.volumeAnimationFrame);
            this.volumeAnimationFrame = null;
        }
        this.updateAudioStatus('stopped');
        const volumeBar = document.getElementById('volume-bar');
        const volumeText = document.getElementById('volume-percentage');
        if (volumeBar) volumeBar.style.width = '0%';
        if (volumeText) volumeText.textContent = '0%';
    }

    updateAudioStatus(status) {
        const statusText = document.getElementById('audio-status-text');
        if (!statusText) return;

        switch (status) {
            case 'recording':
                statusText.textContent = '🔴 Жазылуда...';
                statusText.style.color = '#4CAF50';
                break;
            case 'ai_talking':
                statusText.textContent = '🟢 Мұғалім сөйлеп тұр...';
                statusText.style.color = '#2196F3';
                break;
            case 'paused':
                statusText.textContent = '⏸️ Кідіртілді';
                statusText.style.color = '#FFC107';
                break;
            case 'stopped':
                statusText.textContent = '⏹️ Тоқтатылды';
                statusText.style.color = '#757575';
                break;
            case 'connecting':
                statusText.textContent = '🔄 Байланысуда...';
                statusText.style.color = '#757575';
                break;
            default:
                statusText.textContent = 'Күту режимі';
                statusText.style.color = '#757575';
        }
    }

    showSpeechIndicator(speaking) {
        const visualizer = document.getElementById('audio-visualizer');
        if (!visualizer) return;
        if (speaking) {
            visualizer.classList.add('user-speaking');
        } else {
            visualizer.classList.remove('user-speaking');
        }
    }

    animateVisualizer(active) {
        const visualizer = document.getElementById('audio-visualizer');
        if (!visualizer) return;
        if (active) {
            visualizer.classList.add('active');
        } else {
            visualizer.classList.remove('active');
        }
    }

    cleanup() {
        if (this.microphone) {
            this.microphone.getTracks().forEach((track) => track.stop());
            this.microphone = null;
        }

        if (this.audioContext) {
            try {
                this.audioContext.close();
            } catch (e) {
                console.warn('AudioContext close error:', e);
            }
            this.audioContext = null;
        }

        if (this.volumeAnimationFrame) {
            cancelAnimationFrame(this.volumeAnimationFrame);
            this.volumeAnimationFrame = null;
        }
        this.volumeMeter = null;
        this.isRecording = false;
        this.clientSecret = null;
        this.stopLessonTimer();
        this.eventsChannel = null;
    }

    async requestMicrophoneStream() {
        try {
            return await navigator.mediaDevices.getUserMedia(this.audioConstraints);
        } catch (error) {
            console.warn('Primary getUserMedia failed:', error);

            const needsFallback = this.isIOSDevice() ||
                (error && typeof error.message === 'string' && /mimetype/i.test(error.message)) ||
                (error && error.name === 'NotSupportedError');

            if (!needsFallback) {
                throw new Error('Микрофонға қол жеткізу мүмкін емес: ' + (error?.message || error?.name || 'Белгісіз қате'));
            }

            const fallbackConstraints = { audio: true, video: false };
            try {
                const stream = await navigator.mediaDevices.getUserMedia(fallbackConstraints);
                this.audioConstraints = fallbackConstraints;
                return stream;
            } catch (fallbackError) {
                console.error('Fallback getUserMedia failed:', fallbackError);
                throw new Error('Микрофонға қол жеткізу мүмкін емес: ' + (fallbackError?.message || fallbackError?.name || 'Белгісіз қате'));
            }
        }
    }

    isIOSDevice() {
        const ua = navigator.userAgent || '';
        const platform = navigator.platform || '';
        const isIOS = /iPad|iPhone|iPod/.test(ua) || /iPad|iPhone|iPod/.test(platform);
        const isTouchMac = platform === 'MacIntel' && navigator.maxTouchPoints > 1;
        return isIOS || isTouchMac;
    }

    updateUI(state, message = '') {
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        const startBtn = document.getElementById('start-voice-lesson');
        const stopBtn = document.getElementById('stop-voice-lesson');

        if (!statusIndicator || !statusText || !startBtn || !stopBtn) return;

        switch (state) {
            case 'connecting':
                statusIndicator.className = 'status-indicator connecting';
                statusText.textContent = 'Байланысуда...';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-flex';
                this.updateAudioStatus('connecting');
                break;
            case 'connected':
                statusIndicator.className = 'status-indicator online';
                statusText.textContent = 'Байланысты';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-flex';
                break;
            case 'disconnecting':
                statusIndicator.className = 'status-indicator connecting';
                statusText.textContent = 'Тоқтатылуда...';
                break;
            case 'disconnected':
                statusIndicator.className = 'status-indicator offline';
                statusText.textContent = 'Байланыс жоқ';
                startBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                break;
            case 'error':
                statusIndicator.className = 'status-indicator error';
                statusText.textContent = 'Қате: ' + message;
                startBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                break;
        }
    }

    startLessonTimer() {
        this.lessonStartTime = Date.now();
        this.updateTimerDisplay(0);
        if (this.lessonTimerInterval) {
            clearInterval(this.lessonTimerInterval);
        }
        this.lessonTimerInterval = setInterval(() => {
            const elapsed = Date.now() - this.lessonStartTime;
            this.updateTimerDisplay(elapsed);
        }, 1000);
    }

    stopLessonTimer() {
        if (this.lessonTimerInterval) {
            clearInterval(this.lessonTimerInterval);
            this.lessonTimerInterval = null;
        }
        this.lessonStartTime = null;
        this.updateTimerDisplay(0);
    }

    updateTimerDisplay(ms) {
        const timerEl = document.getElementById('lesson-timer');
        if (!timerEl) return;
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const seconds = String(totalSeconds % 60).padStart(2, '0');
        timerEl.textContent = `${minutes}:${seconds}`;
    }

    injectPremiumStyles() {
        if (document.getElementById('voice-lesson-premium-styles')) {
            return;
        }

        const style = document.createElement('style');
        style.id = 'voice-lesson-premium-styles';
        style.textContent = `
            .voice-lesson-card.premium {
                background: linear-gradient(145deg, rgba(19,25,34,0.95), rgba(43,54,72,0.9));
                border-radius: 24px;
                padding: 24px;
                color: #f5f7fb;
                box-shadow: 0 18px 45px rgba(9, 14, 26, 0.35);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255,255,255,0.08);
            }
            .voice-lesson-header {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
            }
            .voice-title {
                display: flex;
                gap: 16px;
                align-items: center;
            }
            .voice-title h3 {
                margin: 0;
                font-size: 1.4rem;
                letter-spacing: 0.02em;
            }
            .voice-title p {
                margin: 4px 0 0;
                font-size: 0.85rem;
                color: rgba(245,247,251,0.65);
            }
            .voice-icon {
                background: linear-gradient(135deg, #58afff, #7a5bff);
                border-radius: 14px;
                padding: 10px 12px;
                font-size: 1.3rem;
            }
            .voice-meta {
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 8px;
            }
            .lesson-timer {
                font-family: 'SF Pro Display', 'Helvetica Neue', sans-serif;
                font-size: 1.2rem;
                background: rgba(255,255,255,0.08);
                padding: 6px 18px;
                border-radius: 999px;
                letter-spacing: 0.1em;
            }
            .voice-lesson-content {
                margin-top: 24px;
                display: flex;
                flex-direction: column;
                gap: 18px;
            }
            .voice-controls {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 18px;
                align-items: center;
            }
            .visualizer-wrap {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .audio-visualizer {
                background: rgba(255,255,255,0.04);
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid rgba(255,255,255,0.06);
            }
            .wave-bar {
                background: linear-gradient(180deg, #6ad4ff, #7c5cff);
            }
            .volume-meter.premium span:first-child {
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                color: rgba(245,247,251,0.55);
            }
            .lesson-controls {
                display: flex;
                gap: 12px;
                justify-content: center;
            }
            .btn-voice-primary, .btn-voice-secondary {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                border-radius: 999px;
                padding: 12px 20px;
                font-weight: 600;
                border: none;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                font-size: 0.95rem;
                min-width: 180px;
                justify-content: center;
            }
            .btn-voice-primary {
                background: linear-gradient(135deg, #5cc6ff, #7d5dff);
                color: #0d1221;
                box-shadow: 0 10px 25px rgba(80, 145, 255, 0.35);
            }
            .btn-voice-secondary {
                background: rgba(255,255,255,0.08);
                color: #f5f7fb;
                border: 1px solid rgba(255,255,255,0.12);
                box-shadow: 0 10px 25px rgba(9, 14, 26, 0.25);
            }
            .btn-voice-primary:hover, .btn-voice-secondary:hover {
                transform: translateY(-2px);
            }
            .voice-footer {
                font-size: 0.8rem;
                color: rgba(245,247,251,0.55);
                text-align: center;
                margin-top: 6px;
            }
            @media (max-width: 768px) {
                .voice-lesson-card.premium {
                    padding: 18px;
                }
                .lesson-controls {
                    flex-direction: column;
                }
                .btn-voice-primary, .btn-voice-secondary {
                    width: 100%;
                }
                .voice-meta {
                    align-items: flex-start;
                }
                .voice-lesson-header {
                    flex-direction: column;
                    align-items: flex-start;
                }
            }
        `;

        document.head.appendChild(style);
    }
}

window.VoiceLessonManager = VoiceLessonManager;
