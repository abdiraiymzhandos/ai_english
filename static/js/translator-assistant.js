/**
 * AI Translator Assistant - Real-time Speech-to-Speech Translation
 * Uses OpenAI GPT Realtime API for live translation and conversation
 */

class TranslatorAssistant {
    constructor(config = {}) {
        this.config = Object.assign({
            checkAccessUrl: '/api/translator/check-access/',
            tokenUrl: '/api/translator/token/',
            realtimeModel: 'gpt-realtime',
            csrfCookieName: 'csrftoken'
        }, config || {});

        this.peerConnection = null;
        this.dataChannel = null;
        this.eventsChannel = null;
        this.remoteAudioEl = null;
        this.remoteStream = null;

        this.audioContext = null;
        this.microphone = null;
        this.isRecording = false;
        this.isConnected = false;
        this.clientSecret = null;

        this.volumeMeter = null;
        this.volumeAnimationFrame = null;

        this.sessionStartTime = null;
        this.maxSessionDuration = 30 * 60 * 1000; // 30 minutes max
        this.sessionTimeoutCheck = null;

        this.keepAliveInterval = null;
        this.useKeepAlive = true;
        this.awaitingResponse = false;
        this.activeAIMessage = null;
        this.isTerminating = false;
        this.pendingResponseTimeout = null;

        this.audioConstraints = {
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1
            },
            video: false
        };

        this.modal = null;
        this.timerInterval = null;
    }

    async checkAccess() {
        try {
            const response = await fetch(this.config.checkAccessUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                credentials: 'same-origin'
            });

            const status = response.status;
            const contentType = response.headers.get('content-type') || '';

            if (status === 401 || status === 403) {
                return { has_access: false, error: 'Жүйеге кіру керек' };
            }

            if (!response.ok) {
                const data = await response.json();
                return { has_access: false, error: data.error || 'Қол жеткізу қатесі' };
            }

            if (!contentType.includes('application/json')) {
                return { has_access: false, error: 'Жүйеге кіріп, аудармашыны қайта ашыңыз' };
            }

            return await response.json();
        } catch (error) {
            console.error('Access check error:', error);
            return { has_access: false, error: 'Байланыс қатесі' };
        }
    }

    async showTranslator() {
        if (!this.config.isAuthenticated) {
            this.showAccessDeniedModal('Жүйеге кіріңіз');
            return;
        }

        if (!this.config.hasTranslatorAccess) {
            this.showAccessDeniedModal('Premium қол жеткізу қажет');
            return;
        }

        const accessCheck = await this.checkAccess();

        if (!accessCheck.has_access) {
            this.showAccessDeniedModal(accessCheck.error || 'Аудармашы көмекшісіне қол жеткізу жоқ');
            return;
        }

        this.createModal();
        this.modal.style.display = 'flex';
    }

    showAccessDeniedModal(message) {
        const isAuthError = message && /кіру|login/i.test(message);
        const loginUrl = this.config.loginUrl || '/login/';
        const loginContent = `
            <div class="translator-ad-hero login">
                <div class="translator-ad-badge">Account</div>
                <h4>AI аудармашыны пайдалану үшін жүйеге кіріңіз</h4>
                <p>Сессия ашу үшін өз аккаунтыңызды белсенділеңіз.</p>
            </div>
            <p class="translator-ad-note">
                ${message || 'Жүйеге кіріңіз'}
            </p>
            <a class="btn-translator-primary translator-login-btn" href="${loginUrl}" rel="nofollow">
                Жүйеге кіру
            </a>
        `;

        const marketingContent = `
            <div class="translator-ad-hero">
                <div class="translator-ad-badge">Premium</div>
                <h4>AI Аудармашы Көмекшісі</h4>
                <p>Нақты уақыттағы сөйлеуден-сөйлеуге аударма</p>
            </div>
            <ul class="translator-feature-list">
                <li><strong>30 минут</strong> үздіксіз аударма сессиясы</li>
                <li><strong>Көп тіл:</strong> қазақ, ағылшын, орыс, түрік және тағы басқалары</li>
                <li><strong>Екі бағыт:</strong> сіздің сөзіңізді де, қарсы жауапты да түсіндіреді</li>
            </ul>
            <p class="translator-ad-note">
                ${message || 'Premium қол жеткізу қажет'}
            </p>
            <div class="translator-cta">
                <span>Қол жеткізу алу:</span>
                <a class="btn-translator-wa" href="https://wa.me/77781029394" target="_blank" rel="noopener" title="WhatsApp">
                    <i class="fab fa-whatsapp"></i>
                </a>
            </div>
        `;

        const bodyContent = isAuthError ? loginContent : marketingContent;
        const headerTitle = isAuthError ? '🔐 Жүйеге кіру қажет' : '🌐 Premium Аудармашы';

        const modalHtml = `
            <div class="translator-modal" id="access-denied-modal" style="display: flex;">
                <div class="translator-modal-content translator-info-modal" style="max-width: 520px;">
                    <div class="translator-modal-header">
                        <h3>${headerTitle}</h3>
                        <button class="translator-close" onclick="document.getElementById('access-denied-modal').remove()">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="translator-modal-body translator-access-modal">
                        ${bodyContent}
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    createModal() {
        if (this.modal) {
            return;
        }

        const modalHtml = `
            <div class="translator-modal" id="translator-modal">
                <div class="translator-modal-content">
                    <div class="translator-modal-header">
                        <h3>
                            <span class="translator-icon">🌐</span>
                            AI Аудармашы Көмекшісі
                        </h3>
                        <button class="translator-close" id="close-translator">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <div class="translator-modal-body">
                        <div class="translator-status-bar">
                            <div class="translator-status">
                                <span class="status-dot offline" id="translator-status-dot"></span>
                                <span id="translator-status-text">Дайын</span>
                            </div>
                            <div class="translator-timer" id="translator-timer">00:00</div>
                        </div>

                        <div class="translator-conversation" id="translator-conversation">
                            <div class="translator-message ai-message">
                                <span class="message-icon">🤖</span>
                                <div class="message-content">
                                    <p>Сәлеметсіз бе! Мен сіздің аудармашы көмекшіңізмін.</p>
                                    <p>Мысалы: "Мен қонақ үйден 3 адамға бөлме алғым келеді және 5-қабатта болуы керек, мұны ресепшионистке ағылшын тілінде аударып беріңіз" дегендей айтыңыз.</p>
                                </div>
                            </div>
                        </div>

                        <div class="translator-volume-meter">
                            <span class="volume-label">Микрофон деңгейі</span>
                            <div class="volume-bar-container">
                                <div class="volume-bar-fill" id="translator-volume-bar"></div>
                            </div>
                            <span id="translator-volume-percentage">0%</span>
                        </div>

                        <div class="translator-controls">
                            <button class="btn-translator-primary" id="start-translator">
                                <i class="fas fa-play"></i>
                                <span>Бастау</span>
                            </button>
                            <button class="btn-translator-secondary" id="stop-translator" style="display: none;">
                                <i class="fas fa-square"></i>
                                <span>Тоқтату</span>
                            </button>
                        </div>

                        <div class="translator-footer">
                            <p>⏱ Максималды уақыт: 30 минут</p>
                        </div>
                    </div>
                </div>

                <audio id="translator-remote-audio" autoplay playsinline style="display: none;"></audio>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.modal = document.getElementById('translator-modal');
        this.remoteAudioEl = document.getElementById('translator-remote-audio');

        // Attach event listeners
        document.getElementById('close-translator').addEventListener('click', () => this.closeModal());
        document.getElementById('start-translator').addEventListener('click', () => this.startSession());
        document.getElementById('stop-translator').addEventListener('click', () => this.stopSession());

        // Close modal when clicking outside
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.closeModal();
            }
        });
    }

    closeModal() {
        if (this.isConnected) {
            this.stopSession();
        }
        if (this.modal) {
            this.modal.remove();
            this.modal = null;
        }
    }

    async startSession() {
        if (this.peerConnection) {
            console.warn('Session already active');
            return;
        }

        console.log('Starting translator session...');
        this.updateUI('connecting');

        try {
            this.sessionStartTime = Date.now();
            this.awaitingResponse = false;
            if (this.pendingResponseTimeout) {
                clearTimeout(this.pendingResponseTimeout);
                this.pendingResponseTimeout = null;
            }
            this.resetConversation();

            console.log('Initializing audio...');
            await this.initializeAudio();
            this.startRecording();

            console.log('Starting realtime session...');
            await this.startRealtimeSession();

            console.log('Session started successfully');
            this.updateUI('connected');
            this.startTimer();
            this.startSessionTimeoutCheck();

        } catch (error) {
            console.error('Error starting translator session:', error);
            this.updateUI('error', error.message || 'Байланыс қатесі');
            await this.stopRealtimeSession();
            this.stopRecording();
            this.cleanup();
        }
    }

    async stopSession() {
        try {
            this.updateUI('disconnecting');
            await this.stopRealtimeSession();
            this.stopRecording();
            this.cleanup();
            this.updateUI('disconnected');
        } catch (error) {
            console.error('Error stopping session:', error);
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

            const volumeBar = document.getElementById('translator-volume-bar');
            const volumeText = document.getElementById('translator-volume-percentage');
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

    async fetchRealtimeToken() {
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        const csrfToken = this.getCSRFToken();
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        const response = await fetch(this.config.tokenUrl, {
            method: 'POST',
            headers,
            body: JSON.stringify({}),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || 'Токен алу мүмкін болмады');
        }

        return await response.json();
    }

    async startRealtimeSession() {
        const tokenPayload = await this.fetchRealtimeToken();
        const clientSecret = tokenPayload?.client_secret?.value || tokenPayload?.client_secret;
        if (!clientSecret) {
            throw new Error('OpenAI-тен дұрыс емес жауап алынды');
        }
        this.clientSecret = clientSecret;

        const pc = new RTCPeerConnection({
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' }
            ]
        });
        this.peerConnection = pc;

        const audioEl = this.remoteAudioEl;
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
            }

            const track = event.track;
            if (track) {
                track.onended = () => {
                    console.log('Audio track ended');
                };
            }
        };

        pc.onconnectionstatechange = () => {
            const state = pc.connectionState;
            switch (state) {
                case 'connected':
                    this.isConnected = true;
                    this.updateUI('connected');
                    break;
                case 'disconnected':
                    console.warn('PeerConnection disconnected - waiting for recovery');
                    this.updateUI('connecting');
                    this.scheduleConnectionCheck();
                    break;
                case 'failed':
                    console.error('PeerConnection failed');
                    this.safeTerminateSession('Байланыс сәтсіз аяқталды');
                    break;
                case 'closed':
                    this.isConnected = false;
                    break;
                default:
                    break;
            }
        };

        pc.oniceconnectionstatechange = () => {
            const iceState = pc.iceConnectionState;
            if (iceState === 'failed') {
                console.error('ICE connection failed');
                this.safeTerminateSession('ICE байланысы үзілді');
            }
        };

        // Dual data channel setup
        pc.ondatachannel = (event) => {
            const channel = event.channel;
            this.eventsChannel = channel;
            channel.onmessage = (e) => this.handleRealtimeMessage(e.data);

            channel.onopen = () => {
                console.log('OpenAI data channel opened');
                try {
                    channel.send(JSON.stringify({
                        type: 'session.update',
                        session: { modalities: ['audio', 'text'] }
                    }));
                    console.log('Sent initial session.update');
                } catch (err) {
                    console.warn('Failed to send via OpenAI channel:', err);
                }
            };
        };

        this.dataChannel = pc.createDataChannel('translator-events');
        this.dataChannel.onmessage = (e) => this.handleRealtimeMessage(e.data);
        this.dataChannel.onopen = () => {
            console.log('Custom data channel opened');
            if (!this.eventsChannel || this.eventsChannel.readyState !== 'open') {
                try {
                    this.dataChannel.send(JSON.stringify({
                        type: 'session.update',
                        session: { modalities: ['audio', 'text'] }
                    }));
                    console.log('Sent session.update');
                } catch (err) {
                    console.warn('Failed to send via custom channel:', err);
                }
            }

            if (this.useKeepAlive) {
                this.startKeepAlive();
                console.log('Keep-alive started');
            }
        };

        this.dataChannel.onclose = () => {
            console.log('Data channel closed');
            this.stopKeepAlive();
        };

        this.dataChannel.onerror = (err) => {
            console.error('Data channel error:', err);
            this.stopKeepAlive();
        };

        if (this.microphone) {
            this.microphone.getAudioTracks().forEach((track) => {
                pc.addTrack(track, this.microphone);
            });
        }

        const offer = await pc.createOffer({ offerToReceiveAudio: true });
        await pc.setLocalDescription(offer);
        await this.waitForIceGatheringComplete(pc);

        const realtimeModel = encodeURIComponent(this.config.realtimeModel || 'gpt-realtime');
        const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=${realtimeModel}`, {
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

    waitForIceGatheringComplete(pc) {
        if (!pc) return Promise.resolve();
        if (pc.iceGatheringState === 'complete') {
            return Promise.resolve();
        }

        return new Promise((resolve) => {
            let timeoutId;
            const checkState = () => {
                if (pc.iceGatheringState === 'complete') {
                    cleanup();
                }
            };
            const cleanup = () => {
                if (timeoutId) {
                    clearTimeout(timeoutId);
                }
                pc.removeEventListener('icegatheringstatechange', checkState);
                resolve();
            };

            pc.addEventListener('icegatheringstatechange', checkState);
            timeoutId = setTimeout(cleanup, 2000);
        });
    }

    async stopRealtimeSession() {
        this.stopKeepAlive();

        if (this.dataChannel) {
            try { this.dataChannel.close(); } catch (e) { /* ignore */ }
            this.dataChannel = null;
        }

        if (this.eventsChannel) {
            try { this.eventsChannel.close(); } catch (e) { /* ignore */ }
            this.eventsChannel = null;
        }

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
        this.awaitingResponse = false;
        if (this.pendingResponseTimeout) {
            clearTimeout(this.pendingResponseTimeout);
            this.pendingResponseTimeout = null;
        }

        if (this.remoteAudioEl) {
            this.remoteAudioEl.pause();
            this.remoteAudioEl.srcObject = null;
            this.remoteAudioEl.style.display = 'none';
        }

        this.remoteStream = null;
        this.stopTimer();
        this.stopSessionTimeoutCheck();
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
            case 'response.audio_transcript.delta':
            case 'response.output_text.delta': {
                const textDelta = data?.delta || '';
                if (textDelta) {
                    this.appendAIText(textDelta);
                }
                break;
            }

            case 'response.audio_transcript.done':
            case 'response.output_text.done':
                this.completeAIMessage();
                break;

            case 'response.created':
                this.awaitingResponse = true;
                if (this.pendingResponseTimeout) {
                    clearTimeout(this.pendingResponseTimeout);
                    this.pendingResponseTimeout = null;
                }
                break;

            case 'response.completed':
            case 'response.done':
                this.awaitingResponse = false;
                if (this.pendingResponseTimeout) {
                    clearTimeout(this.pendingResponseTimeout);
                    this.pendingResponseTimeout = null;
                }
                break;

            case 'response.error':
            case 'response.failed':
                console.error('Realtime response error:', data);
                this.awaitingResponse = false;
                if (this.pendingResponseTimeout) {
                    clearTimeout(this.pendingResponseTimeout);
                    this.pendingResponseTimeout = null;
                }
                break;

            case 'conversation.item.input_audio_transcription.completed': {
                const userText = data?.transcript || '';
                if (userText) {
                    this.addMessage('user', userText);
                    this.scheduleResponseRequest();
                }
                break;
            }

            case 'input_audio_buffer.speech_started':
                this.showSpeechIndicator(true);
                break;

            case 'input_audio_buffer.speech_stopped':
                this.showSpeechIndicator(false);
                break;

            case 'session.expired':
                console.warn('Realtime session expired:', data);
                this.safeTerminateSession('Сессияның уақыты аяқталды');
                break;

            case 'error':
                if (data.error?.message) {
                    this.updateUI('error', data.error.message);
                }
                break;

            default:
                if (type && !type.startsWith('response.audio') && !type.startsWith('response.output_text')) {
                    console.debug('Realtime event:', data);
                }
        }
    }

    scheduleResponseRequest() {
        if (this.pendingResponseTimeout) {
            clearTimeout(this.pendingResponseTimeout);
        }
        this.pendingResponseTimeout = setTimeout(() => {
            this.pendingResponseTimeout = null;
            this.requestResponse();
        }, 350);
    }

    requestResponse(force = false) {
        if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
            return;
        }
        if (this.awaitingResponse && !force) {
            return;
        }

        try {
            this.dataChannel.send(JSON.stringify({
                type: 'response.create',
                response: {}
            }));
            this.awaitingResponse = true;
        } catch (error) {
            console.error('Failed to request response:', error);
            this.awaitingResponse = false;
        }
    }

    startKeepAlive() {
        if (this.keepAliveInterval) {
            clearInterval(this.keepAliveInterval);
        }

        this.keepAliveInterval = setInterval(() => {
            if (this.dataChannel && this.dataChannel.readyState === 'open') {
                try {
                    this.dataChannel.send(JSON.stringify({
                        type: 'session.update',
                        session: {}
                    }));
                    console.debug('Keep-alive sent');
                } catch (err) {
                    console.warn('Keep-alive failed:', err);
                }
            }
        }, 15000);
    }

    stopKeepAlive() {
        if (this.keepAliveInterval) {
            clearInterval(this.keepAliveInterval);
            this.keepAliveInterval = null;
        }
    }

    startSessionTimeoutCheck() {
        this.sessionTimeoutCheck = setInterval(() => {
            const elapsed = Date.now() - this.sessionStartTime;
            if (elapsed >= this.maxSessionDuration) {
                console.warn('Session timeout reached (30 minutes)');
                alert('Сессия уақыты біттті (30 минут). Автоматты тоқтатылды.');
                this.stopSession();
            }
        }, 10000);
    }

    stopSessionTimeoutCheck() {
        if (this.sessionTimeoutCheck) {
            clearInterval(this.sessionTimeoutCheck);
            this.sessionTimeoutCheck = null;
        }
    }

    scheduleConnectionCheck() {
        if (!this.peerConnection) return;
        setTimeout(() => {
            if (!this.peerConnection) return;
            if (this.peerConnection.connectionState === 'disconnected') {
                console.warn('PeerConnection did not recover');
                this.safeTerminateSession('Байланыс үзілді');
            }
        }, 5000);
    }

    safeTerminateSession(message = '') {
        if (this.isTerminating) return;
        this.isTerminating = true;

        Promise.resolve()
            .then(() => this.stopRealtimeSession())
            .catch((err) => console.warn('Error during session termination:', err))
            .finally(() => {
                this.stopRecording();
                this.cleanup();
                if (message) {
                    this.updateUI('error', message);
                } else {
                    this.updateUI('disconnected');
                }
                this.isTerminating = false;
            });
    }

    resetConversation() {
        const box = document.getElementById('translator-conversation');
        if (!box) return;
        box.innerHTML = `
            <div class="translator-message ai-message">
                <span class="message-icon">🤖</span>
                <div class="message-content">
                    <p>Сәлеметсіз бе! Мен сіздің аудармашы көмекшіңізмін.</p>
                    <p>Мысалы: "Мен қонақ үйден 3 адамға бөлме алғым келеді және 5-қабатта болуы керек, мұны ресепшионистке ағылшын тілінде аударып беріңіз" дегендей айтыңыз.</p>
                </div>
            </div>
        `;
        this.activeAIMessage = null;
    }

    appendAIText(text) {
        const box = document.getElementById('translator-conversation');
        if (!box) return;

        let currentMessage = this.activeAIMessage;
        if (!currentMessage || !currentMessage.isConnected) {
            currentMessage = document.createElement('div');
            currentMessage.className = 'translator-message ai-message active';

            const icon = document.createElement('span');
            icon.className = 'message-icon';
            icon.textContent = '🤖';

            const content = document.createElement('div');
            content.className = 'message-content';
            const textP = document.createElement('p');
            content.appendChild(textP);

            currentMessage.appendChild(icon);
            currentMessage.appendChild(content);

            box.appendChild(currentMessage);
            this.activeAIMessage = currentMessage;
        }

        const textP = currentMessage.querySelector('.message-content p');
        if (textP) {
            textP.textContent += text;
        }

        box.scrollTop = box.scrollHeight;
    }

    completeAIMessage() {
        if (this.activeAIMessage && this.activeAIMessage.classList) {
            this.activeAIMessage.classList.remove('active');
        }
        this.activeAIMessage = null;
    }

    addMessage(role, text) {
        const box = document.getElementById('translator-conversation');
        if (!box || !text) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = `translator-message ${role === 'user' ? 'user-message' : 'ai-message'}`;

        const icon = document.createElement('span');
        icon.className = 'message-icon';
        icon.textContent = role === 'user' ? '👤' : '🤖';

        const content = document.createElement('div');
        content.className = 'message-content';
        const textP = document.createElement('p');
        textP.textContent = text;
        content.appendChild(textP);

        msgDiv.appendChild(icon);
        msgDiv.appendChild(content);
        box.appendChild(msgDiv);
        box.scrollTop = box.scrollHeight;

        if (role !== 'user') {
            this.activeAIMessage = msgDiv;
        }
    }

    startRecording() {
        if (this.isRecording) return;
        this.isRecording = true;
        this.animateVisualizer(true);
        if (this.volumeMeter) {
            this.volumeMeter();
        }
    }

    stopRecording() {
        if (!this.isRecording) return;
        this.isRecording = false;
        this.animateVisualizer(false);
        if (this.volumeAnimationFrame) {
            cancelAnimationFrame(this.volumeAnimationFrame);
            this.volumeAnimationFrame = null;
        }
        const volumeBar = document.getElementById('translator-volume-bar');
        const volumeText = document.getElementById('translator-volume-percentage');
        if (volumeBar) volumeBar.style.width = '0%';
        if (volumeText) volumeText.textContent = '0%';
    }

    animateVisualizer(active) {
        const visualizer = document.getElementById('translator-visualizer');
        if (!visualizer) return;
        if (active) {
            visualizer.classList.add('active');
        } else {
            visualizer.classList.remove('active');
        }
    }

    showSpeechIndicator(speaking) {
        const visualizer = document.getElementById('translator-visualizer');
        if (!visualizer) return;
        if (speaking) {
            visualizer.classList.add('user-speaking');
        } else {
            visualizer.classList.remove('user-speaking');
        }
    }

    updateUI(state, message = '') {
        const statusDot = document.getElementById('translator-status-dot');
        const statusText = document.getElementById('translator-status-text');
        const startBtn = document.getElementById('start-translator');
        const stopBtn = document.getElementById('stop-translator');

        if (!statusDot || !statusText || !startBtn || !stopBtn) return;

        switch (state) {
            case 'connecting':
                statusDot.className = 'status-dot connecting';
                statusText.textContent = 'Байланысуда...';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-flex';
                break;
            case 'connected':
                statusDot.className = 'status-dot online';
                statusText.textContent = 'Байланысты';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-flex';
                break;
            case 'disconnecting':
                statusDot.className = 'status-dot connecting';
                statusText.textContent = 'Тоқтатылуда...';
                break;
            case 'disconnected':
                statusDot.className = 'status-dot offline';
                statusText.textContent = 'Дайын';
                startBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                break;
            case 'error':
                statusDot.className = 'status-dot error';
                statusText.textContent = 'Қате: ' + message;
                startBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                break;
        }
    }

    startTimer() {
        this.sessionStartTime = Date.now();
        this.updateTimerDisplay(0);
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        this.timerInterval = setInterval(() => {
            const elapsed = Date.now() - this.sessionStartTime;
            this.updateTimerDisplay(elapsed);

            if (elapsed >= 29.5 * 60 * 1000 && elapsed < 29.6 * 60 * 1000) {
                alert('⏱ 30 секунд қалды!');
            }
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.sessionStartTime = null;
        this.updateTimerDisplay(0);
    }

    updateTimerDisplay(ms) {
        const timerEl = document.getElementById('translator-timer');
        if (!timerEl) return;
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const seconds = String(totalSeconds % 60).padStart(2, '0');

        if (totalSeconds >= 28 * 60) {
            timerEl.style.color = '#ff4444';
        } else {
            timerEl.style.color = '';
        }

        timerEl.textContent = `${minutes}:${seconds}`;
    }

    cleanup() {
        this.stopKeepAlive();
        this.stopTimer();
        this.stopSessionTimeoutCheck();

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
        this.awaitingResponse = false;
        this.activeAIMessage = null;
        if (this.pendingResponseTimeout) {
            clearTimeout(this.pendingResponseTimeout);
            this.pendingResponseTimeout = null;
        }
    }

    getCSRFToken() {
        if (this.config.csrfToken) {
            return this.config.csrfToken;
        }
        const name = this.config.csrfCookieName || 'csrftoken';
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + '=')) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
        return null;
    }
}

// Initialize translator
const translatorAssistantConfig = window.translatorAssistantConfig || {};
window.translatorAssistant = new TranslatorAssistant(translatorAssistantConfig);
