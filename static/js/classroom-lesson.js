class ClassroomLessonManager extends window.VoiceLessonManager {
    constructor(config) {
        super(config.lessonId);
        this.groupId = config.groupId;
        this.roster = config.roster || [];
        this.studentIdByName = new Map(
            this.roster
                .filter((student) => student && student.name)
                .map((student) => [student.name, student.id])
        );
        this.cameraStream = null;

        this.videoEl = document.getElementById('classroom-camera');
        this.overlayEl = document.getElementById('classroom-overlay');
        this.overlayCtx = this.overlayEl ? this.overlayEl.getContext('2d') : null;
        this.recognitionModeEl = document.getElementById('classroom-recognition-mode');
        this.currentSpeakerEl = document.getElementById('classroom-current-speaker');
        this.systemStatusEls = {
            ai: document.getElementById('classroom-system-ai'),
            camera: document.getElementById('classroom-system-camera'),
            detection: document.getElementById('classroom-system-detection'),
            voice: document.getElementById('classroom-system-voice')
        };

        this.faceModelBase = window.CLASSROOM_FACE_MODEL_URL || '/static/models/face-api';
        this.handsAssetBase = window.CLASSROOM_HANDS_ASSET_URL || 'https://cdn.jsdelivr.net/npm/@mediapipe/hands';
        this.faceDetectorAssetBase = window.CLASSROOM_FACE_DETECTOR_ASSET_URL || 'https://cdn.jsdelivr.net/npm/@mediapipe/face_detection';
        this.faceDetectorMinConfidence = typeof window.CLASSROOM_FACE_DETECTOR_MIN_CONF === 'number'
            ? window.CLASSROOM_FACE_DETECTOR_MIN_CONF
            : 0.5;
        this.maxReferencePhotos = typeof window.CLASSROOM_MAX_REFERENCE_PHOTOS === 'number'
            ? window.CLASSROOM_MAX_REFERENCE_PHOTOS
            : 4;
        this.detectionInputWidth = typeof window.CLASSROOM_DETECTION_INPUT_WIDTH === 'number'
            ? window.CLASSROOM_DETECTION_INPUT_WIDTH
            : 960;
        this.faceApiWarmupPromise = null;
        this.arcFaceWarmupPromise = null;
        this.processingCanvas = null;
        this.processingCtx = null;

        this.useArcFace = typeof window.CLASSROOM_USE_ARCFACE === 'boolean' ? window.CLASSROOM_USE_ARCFACE : true;
        this.usingArcFace = false;
        this.arcFaceModelUrl = window.CLASSROOM_ARCFACE_MODEL_URL || '/static/models/arcface/arcface.onnx';
        this.arcFaceWarmupTimeoutMs = typeof window.CLASSROOM_ARCFACE_MODEL_TIMEOUT_MS === 'number'
            ? window.CLASSROOM_ARCFACE_MODEL_TIMEOUT_MS
            : 6000;
        this.arcFaceInputSize = 112;
        this.arcFaceThreshold = typeof window.CLASSROOM_ARCFACE_THRESHOLD === 'number' ? window.CLASSROOM_ARCFACE_THRESHOLD : 0.45;
        this.arcFaceColorOrder = window.CLASSROOM_ARCFACE_COLOR_ORDER || 'rgb';
        this.arcFaceMinFaceSize = typeof window.CLASSROOM_MIN_FACE_SIZE === 'number' ? window.CLASSROOM_MIN_FACE_SIZE : 40;
        this.arcFaceFacesPerCycle = typeof window.CLASSROOM_ARCFACE_FACES_PER_CYCLE === 'number'
            ? window.CLASSROOM_ARCFACE_FACES_PER_CYCLE
            : 4;
        this.arcFaceScanCursor = 0;
        this.arcFaceSession = null;
        this.arcFaceInputName = null;
        this.arcFaceOutputName = null;
        this.arcFaceInputShape = null;
        this.arcFaceEmbeddings = [];
        this.arcFaceCanvas = null;
        this.arcFaceCanvasCtx = null;
        this.faceDetector = null;
        this.faceDetectorResults = null;

        this.modelsLoaded = false;
        this.faceApiLoaded = false;
        this.arcFaceLoaded = false;
        this.faceOptions = null;
        this.faceMatcher = null;
        this.faceMatchThreshold = typeof window.CLASSROOM_FACE_MATCH_THRESHOLD === 'number'
            ? window.CLASSROOM_FACE_MATCH_THRESHOLD
            : 0.56;
        this.faceInFlight = false;

        this.hands = null;
        this.handInFlight = false;
        this.handRaiseMargin = typeof window.CLASSROOM_HAND_RAISE_MARGIN === 'number'
            ? window.CLASSROOM_HAND_RAISE_MARGIN
            : 0.1;
        this.handRaiseCooldownMs = 12000;
        this.lastHandRaiseAt = new Map();

        this.isDetecting = false;
        this.detectionInterval = null;
        this.detectionIntervalMs = typeof window.CLASSROOM_DETECTION_INTERVAL_MS === 'number'
            ? window.CLASSROOM_DETECTION_INTERVAL_MS
            : 250;
        this.arcFaceDetectionIntervalMs = typeof window.CLASSROOM_ARCFACE_INTERVAL_MS === 'number'
            ? window.CLASSROOM_ARCFACE_INTERVAL_MS
            : Math.max(this.detectionIntervalMs, 500);
        this.maxFaces = typeof window.CLASSROOM_MAX_FACES === 'number' ? window.CLASSROOM_MAX_FACES : 10;

        this.lastFaceDetections = [];
        this.lastHandMatches = [];
        this.lastSignalByName = new Map();

        this.voiceEmbeddings = new Map();
        this.voiceEmbeddingSize = typeof window.CLASSROOM_VOICE_EMBEDDING_SIZE === 'number'
            ? window.CLASSROOM_VOICE_EMBEDDING_SIZE
            : 13;
        this.voiceMatchThreshold = typeof window.CLASSROOM_VOICE_MATCH_THRESHOLD === 'number'
            ? window.CLASSROOM_VOICE_MATCH_THRESHOLD
            : 0.78;
        this.voiceDisplayThreshold = typeof window.CLASSROOM_VOICE_DISPLAY_THRESHOLD === 'number'
            ? window.CLASSROOM_VOICE_DISPLAY_THRESHOLD
            : Math.max(0.6, this.voiceMatchThreshold - 0.1);
        this.voiceMinRms = typeof window.CLASSROOM_VOICE_MIN_RMS === 'number'
            ? window.CLASSROOM_VOICE_MIN_RMS
            : 0.01;
        this.voiceEnrollSeconds = typeof window.CLASSROOM_VOICE_ENROLL_SECONDS === 'number'
            ? window.CLASSROOM_VOICE_ENROLL_SECONDS
            : 3;
        this.voiceEnrollment = null;
        this.voiceEnrollmentTimer = null;
        this.voiceAnalyzer = null;
        this.voiceAnalyzerActive = false;
        this.voiceSource = null;
        this.voiceNoiseFloor = null;
        this.voiceActive = false;
        this.voiceFrames = [];
        this.voiceMinFrames = typeof window.CLASSROOM_VOICE_MIN_FRAMES === 'number'
            ? window.CLASSROOM_VOICE_MIN_FRAMES
            : 24;
        this.voiceMaxFrames = 80;
        this.voiceCooldownMs = typeof window.CLASSROOM_VOICE_COOLDOWN_MS === 'number'
            ? window.CLASSROOM_VOICE_COOLDOWN_MS
            : 12000;
        this.lastVoiceEventAt = new Map();
        this.lastVoiceMatch = new Map();
        this.lastVoiceUiAt = 0;
        this.voiceUiCooldownMs = 4000;
        this.voiceStatusTimeoutMs = typeof window.CLASSROOM_VOICE_STATUS_TIMEOUT_MS === 'number'
            ? window.CLASSROOM_VOICE_STATUS_TIMEOUT_MS
            : 6000;
        this.voiceStatusTimer = null;
        this.voiceFreshWindowMs = typeof window.CLASSROOM_VOICE_FRESH_WINDOW_MS === 'number'
            ? window.CLASSROOM_VOICE_FRESH_WINDOW_MS
            : 15000;

        this.fusionThreshold = typeof window.CLASSROOM_FUSION_THRESHOLD === 'number'
            ? window.CLASSROOM_FUSION_THRESHOLD
            : 0.7;
        this.fusionFaceWeight = typeof window.CLASSROOM_FUSION_FACE_WEIGHT === 'number'
            ? window.CLASSROOM_FUSION_FACE_WEIGHT
            : 0.5;
        this.fusionVoiceWeight = typeof window.CLASSROOM_FUSION_VOICE_WEIGHT === 'number'
            ? window.CLASSROOM_FUSION_VOICE_WEIGHT
            : 0.35;
        this.fusionHandWeight = typeof window.CLASSROOM_FUSION_HAND_WEIGHT === 'number'
            ? window.CLASSROOM_FUSION_HAND_WEIGHT
            : 0.15;

        this.lastSeenAt = new Map();
        this.attendanceWindowMs = typeof window.CLASSROOM_ATTENDANCE_WINDOW_MS === 'number'
            ? window.CLASSROOM_ATTENDANCE_WINDOW_MS
            : 120000;
        this.attendanceIntervalMs = typeof window.CLASSROOM_ATTENDANCE_INTERVAL_MS === 'number'
            ? window.CLASSROOM_ATTENDANCE_INTERVAL_MS
            : 30000;
        this.attendanceInterval = null;
        this.lastAttendanceKey = '';

        this.timeUpdateInterval = null;
        this.lastTimeUpdateMinutes = null;

        this.loadVoiceEmbeddingsFromRoster();
        this.bindRosterControls();
        this.bindCameraControls();
        this.bindDetectionControls();
        this.bindVideoEvents();
        this.bindRollCallControls();
        this.simplifyVoicePanel();
        this.initializeUiState();
        this.scheduleRecognitionWarmup();
    }

    simplifyVoicePanel() {
        const titleEl = document.querySelector('#voice-lesson-container .voice-title h3');
        if (titleEl) {
            titleEl.textContent = 'AI мұғалім';
        }

        const subtitleEl = document.querySelector('#voice-lesson-container .voice-title p');
        if (subtitleEl) {
            subtitleEl.textContent = 'Дауысы мен мәтіні бір экранда.';
        }

        const volumeLabelEl = document.querySelector('#voice-lesson-container .volume-meter.premium span');
        if (volumeLabelEl) {
            volumeLabelEl.textContent = 'Mic';
        }

        this.updateAudioStatus('ready');
        this.markInitialReaderPlaceholder();
        this.syncReaderState();
    }

    markInitialReaderPlaceholder() {
        const initialMessage = document.querySelector('#voice-conversation-box .message.ai-message');
        if (!initialMessage) return;

        const textEl = initialMessage.querySelector('.message-text');
        if (textEl) {
            textEl.textContent = 'Сабақты бастауға дайынмын.';
        }

        initialMessage.dataset.readerPlaceholder = 'true';
    }

    syncReaderState() {
        const box = this.getConversationBox();
        if (!box) return;

        const messages = Array.from(box.querySelectorAll('.message'));
        const aiMessages = messages.filter((message) => message.classList.contains('ai-message'));
        const hasRealAiMessage = aiMessages.some((message) => message.dataset.readerPlaceholder !== 'true');

        let currentMessage = box.querySelector('.message.ai-message.active');
        if (!currentMessage) {
            currentMessage = aiMessages[aiMessages.length - 1] || null;
        }

        messages.forEach((message) => {
            message.classList.remove(
                'reader-current',
                'reader-history',
                'reader-user-history',
                'reader-placeholder',
                'reader-ready-hidden'
            );

            if (message.classList.contains('user-message')) {
                message.classList.add('reader-user-history');
                return;
            }

            if (message === currentMessage) {
                message.classList.add('reader-current');
            } else {
                message.classList.add('reader-history');
            }

            if (message.dataset.readerPlaceholder === 'true') {
                if (!hasRealAiMessage && message === currentMessage) {
                    message.classList.add('reader-placeholder');
                } else {
                    message.classList.add('reader-ready-hidden');
                }
            }
        });

        box.classList.toggle('reader-placeholder-mode', !hasRealAiMessage);
        box.dataset.readerState = hasRealAiMessage ? 'active' : 'placeholder';
    }

    resetConversation() {
        super.resetConversation();
        this.markInitialReaderPlaceholder();
        this.syncReaderState();
    }

    appendAIText(text) {
        super.appendAIText(text);
        if (this.activeAIMessage) {
            this.activeAIMessage.dataset.readerPlaceholder = 'false';
        }
        this.syncReaderState();
    }

    completeAIMessage() {
        super.completeAIMessage();
        this.syncReaderState();
    }

    addMessage(role, text) {
        super.addMessage(role, text);

        if (role !== 'user') {
            const box = this.getConversationBox();
            const latestAiMessage = box ? Array.from(box.querySelectorAll('.message.ai-message')).pop() : null;
            if (latestAiMessage) {
                latestAiMessage.dataset.readerPlaceholder = 'false';
            }
        }

        this.syncReaderState();
    }

    updateAudioStatus(status) {
        const statusText = document.getElementById('audio-status-text');
        const statusPill = document.querySelector('#voice-lesson-container .connection-info');
        if (!statusText) return;

        const labels = {
            recording: 'Тыңдап тұр',
            ai_talking: 'AI сөйлеп тұр',
            paused: 'Кідіртілді',
            stopped: 'Тоқтады',
            connecting: 'Байланысуда',
            ready: 'Дайын'
        };

        const nextState = labels[status] ? status : 'ready';
        statusText.textContent = labels[nextState];
        statusText.style.color = '';

        if (statusPill) {
            statusPill.dataset.state = nextState;
        }
    }

    updateUI(state, message = '') {
        const container = document.getElementById('voice-lesson-container');
        const statusIndicator = container ? container.querySelector('.status-indicator') : null;
        const statusText = container ? container.querySelector('.status-text') : null;
        const startBtn = document.getElementById('start-voice-lesson');
        const stopBtn = document.getElementById('stop-voice-lesson');

        const setButtonDisplay = (button, value) => {
            if (!button) return;
            button.style.setProperty('display', value, 'important');
        };

        const setStatus = (indicatorClass, text) => {
            if (statusIndicator) {
                statusIndicator.className = indicatorClass;
            }
            if (statusText) {
                statusText.textContent = text;
            }
        };

        switch (state) {
            case 'connecting':
                setStatus('status-indicator connecting', 'Байланысуда...');
                if (startBtn) {
                    setButtonDisplay(startBtn, 'none');
                    startBtn.disabled = true;
                }
                if (stopBtn) {
                    setButtonDisplay(stopBtn, 'inline-flex');
                    stopBtn.disabled = false;
                }
                this.updateAudioStatus('connecting');
                break;
            case 'connected':
                setStatus('status-indicator online', 'Байланысты');
                if (startBtn) {
                    setButtonDisplay(startBtn, 'none');
                    startBtn.disabled = true;
                }
                if (stopBtn) {
                    setButtonDisplay(stopBtn, 'inline-flex');
                    stopBtn.disabled = false;
                }
                break;
            case 'disconnecting':
                setStatus('status-indicator connecting', 'Тоқтатылуда...');
                if (startBtn) startBtn.disabled = true;
                if (stopBtn) stopBtn.disabled = true;
                break;
            case 'disconnected':
                setStatus('status-indicator offline', 'Дайын');
                if (startBtn) {
                    setButtonDisplay(startBtn, 'inline-flex');
                    startBtn.disabled = false;
                }
                if (stopBtn) {
                    setButtonDisplay(stopBtn, 'none');
                    stopBtn.disabled = false;
                }
                this.updateAudioStatus('ready');
                break;
            case 'error':
                setStatus('status-indicator error', message ? `Қате: ${message}` : 'Қате');
                if (startBtn) {
                    setButtonDisplay(startBtn, 'inline-flex');
                    startBtn.disabled = false;
                }
                if (stopBtn) {
                    setButtonDisplay(stopBtn, 'none');
                    stopBtn.disabled = false;
                }
                break;
            default:
                break;
        }
    }

    initializeUiState() {
        this.updateRecognitionModeLabel('Тану: дайындалуда');
        this.setSystemState('ai', 'ready', 'AI: өшірулі');
        this.setSystemState('camera', 'ready', 'Камера: өшірулі');
        this.setSystemState('detection', 'ready', 'Тану: күту');
        this.setSystemState('voice', 'ready', this.voiceEmbeddings.size ? 'Дауыс: күту' : 'Дауыс: үлгі аз');
        this.setCurrentSpeaker('Әзірге жоқ');
        this.updateVoiceStatus('Күту');
        this.roster.forEach((student) => {
            this.updateRosterSignal(student.name, 'Күту', 'ready');
        });
    }

    setSystemState(key, state, text) {
        const el = this.systemStatusEls[key];
        if (!el) return;
        el.className = 'system-pill';
        if (state && state !== 'ready') {
            el.classList.add(state);
        }
        el.textContent = text || '';
    }

    updateRecognitionModeLabel(text) {
        if (this.recognitionModeEl) {
            this.recognitionModeEl.textContent = text || 'Тану: дайындық';
        }
    }

    setCurrentSpeaker(text) {
        if (this.currentSpeakerEl) {
            this.currentSpeakerEl.textContent = text || 'Әзірге жоқ';
        }
    }

    updateRosterSignal(name, text, tone = 'ready') {
        if (!name) return;
        const studentId = this.studentIdByName.get(name);
        if (!studentId) return;
        const pill = document.querySelector(`[data-live-status="${studentId}"]`);
        const card = document.querySelector(`[data-roster-card="${studentId}"]`);
        if (pill) {
            pill.textContent = text || 'Күту';
            pill.className = 'signal-pill';
            if (tone === 'active' || tone === 'warn') {
                pill.classList.add(tone);
            }
        }
        if (card) {
            card.classList.remove('active', 'warn');
            if (tone === 'active' || tone === 'warn') {
                card.classList.add(tone);
            }
        }
        this.lastSignalByName.set(name, { text, tone, at: Date.now() });
    }

    scheduleRecognitionWarmup() {
        const triggerWarmup = () => {
            this.warmFaceApiPipeline();
            if (this.useArcFace) {
                window.setTimeout(() => {
                    this.warmArcFacePipeline();
                }, 1200);
            }
        };
        if (typeof window.requestIdleCallback === 'function') {
            window.requestIdleCallback(triggerWarmup, { timeout: 1500 });
        } else {
            window.setTimeout(triggerWarmup, 350);
        }
    }

    async warmFaceApiPipeline(force = false) {
        if (this.faceApiWarmupPromise && !force) {
            return this.faceApiWarmupPromise;
        }
        this.faceApiWarmupPromise = (async () => {
            try {
                await this.loadFaceApiModels();
                await this.buildFaceMatcher();
                if (this.faceMatcher) {
                    this.updateRecognitionModeLabel('Тану: fast дайын');
                    if (!this.isDetecting) {
                        this.setSystemState('detection', 'ready', 'Тану: fast дайын');
                    }
                }
            } catch (error) {
                console.warn('Face-api warmup failed:', error);
            }
            return Boolean(this.faceMatcher);
        })();
        return this.faceApiWarmupPromise;
    }

    async warmArcFacePipeline(force = false) {
        if (!this.useArcFace) return false;
        if (this.arcFaceWarmupPromise && !force) {
            return this.arcFaceWarmupPromise;
        }
        this.arcFaceWarmupPromise = (async () => {
            try {
                await this.withTimeout(this.loadArcFaceModels(), this.arcFaceWarmupTimeoutMs, 'ArcFace warmup timeout');
                await this.buildArcFaceEmbeddings();
                if (this.arcFaceEmbeddings.length) {
                    if (this.isDetecting) {
                        this.usingArcFace = true;
                        this.startDetectionLoop();
                        this.setSystemState('detection', 'active', 'Тану: precise');
                    }
                    this.updateRecognitionModeLabel('Тану: precise дайын');
                }
            } catch (error) {
                console.warn('ArcFace warmup skipped:', error);
            }
            return Boolean(this.arcFaceEmbeddings.length);
        })();
        return this.arcFaceWarmupPromise;
    }

    async withTimeout(promise, timeoutMs, message) {
        if (!timeoutMs) return promise;
        return Promise.race([
            promise,
            new Promise((_, reject) => {
                window.setTimeout(() => reject(new Error(message || 'Operation timed out')), timeoutMs);
            })
        ]);
    }

    async ensureDetectionPipelineReady() {
        const faceReady = await this.warmFaceApiPipeline();
        if (faceReady) {
            return 'faceapi';
        }

        if (this.useArcFace) {
            const arcFaceReady = await this.warmArcFacePipeline(true);
            if (arcFaceReady) {
                return 'arcface';
            }
        }
        return null;
    }

    ensureProcessingCanvas(width, height) {
        if (!this.processingCanvas) {
            this.processingCanvas = document.createElement('canvas');
            this.processingCtx = this.processingCanvas.getContext('2d', { willReadFrequently: true });
        }
        if (!this.processingCtx) {
            return null;
        }
        if (this.processingCanvas.width !== width || this.processingCanvas.height !== height) {
            this.processingCanvas.width = width;
            this.processingCanvas.height = height;
        }
        return this.processingCanvas;
    }

    getDetectionSourceFrame() {
        const size = this.getVideoSize();
        if (!size || !this.videoEl) return null;
        if (size.width <= this.detectionInputWidth) {
            return {
                source: this.videoEl,
                ratioX: 1,
                ratioY: 1
            };
        }

        const targetWidth = this.detectionInputWidth;
        const targetHeight = Math.round(size.height * (targetWidth / size.width));
        const canvas = this.ensureProcessingCanvas(targetWidth, targetHeight);
        if (!canvas || !this.processingCtx) {
            return {
                source: this.videoEl,
                ratioX: 1,
                ratioY: 1
            };
        }
        this.processingCtx.drawImage(this.videoEl, 0, 0, targetWidth, targetHeight);
        return {
            source: canvas,
            ratioX: size.width / targetWidth,
            ratioY: size.height / targetHeight
        };
    }

    scaleDetectionsToVideo(detections, ratioX, ratioY) {
        if (!ratioX || !ratioY || (ratioX === 1 && ratioY === 1)) {
            return detections;
        }
        return detections.map((item) => ({
            ...item,
            box: {
                x: item.box.x * ratioX,
                y: item.box.y * ratioY,
                width: item.box.width * ratioX,
                height: item.box.height * ratioY
            },
            keypoints: Array.isArray(item.keypoints)
                ? item.keypoints.map((point) => ({
                    x: point.x * ratioX,
                    y: point.y * ratioY
                }))
                : []
        }));
    }

    async fetchRealtimeToken() {
        const response = await fetch(`/api/realtime/classroom/${this.lessonId}/${this.groupId}/`, {
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

    getEventChannel() {
        if (this.eventsChannel && this.eventsChannel.readyState === 'open') {
            return this.eventsChannel;
        }
        if (this.dataChannel && this.dataChannel.readyState === 'open') {
            return this.dataChannel;
        }
        return null;
    }

    sendJson(payload) {
        const channel = this.getEventChannel();
        if (!channel) {
            console.warn('No open data channel for classroom event');
            return false;
        }
        channel.send(JSON.stringify(payload));
        return true;
    }

    sendTeacherEvent(eventText) {
        if (!eventText) return;
        const created = this.sendJson({
            type: 'conversation.item.create',
            item: {
                type: 'message',
                role: 'user',
                content: [{ type: 'input_text', text: eventText }]
            }
        });
        if (!created) return;
        this.sendJson({ type: 'response.create', response: {} });
        this.awaitingResponse = true;
    }

    sendControlEvent(eventText) {
        if (!eventText) return;
        this.sendJson({
            type: 'conversation.item.create',
            item: {
                type: 'message',
                role: 'user',
                content: [{ type: 'input_text', text: eventText }]
            }
        });
    }

    handleHandRaise(name, options = {}) {
        if (!name) return;
        if (!this.isConnected) {
            this.updateStatus('AI сессиясы басталмаған. Алдымен дауысты қосыңыз.');
            return;
        }
        const manual = Boolean(options.manual);
        const faceConfidence = typeof options.faceConfidence === 'number' ? options.faceConfidence : null;
        const voiceConfidence = typeof options.voiceConfidence === 'number' ? options.voiceConfidence : null;
        const handRaise = Boolean(options.handRaise);

        if (!manual) {
            const fused = this.computeFusionConfidence({ faceConfidence, voiceConfidence, handRaise });
            const fusedText = this.formatConfidence(fused);
            if (fused < this.fusionThreshold) {
                this.sendTeacherEvent(`EVENT: CONFIRM_STUDENT candidate=${name} confidence=${fusedText || '0.00'}`);
                this.updateStatus(`⚠️ Растау сұралды: ${name}`);
                return;
            }
            this.sendTeacherEvent(`EVENT: HAND_RAISE name=${name}${fusedText ? ` confidence=${fusedText}` : ''}`);
            this.updateStatus(`✅ Сұрақ қойылды: ${name}`);
            return;
        }

        this.sendTeacherEvent(`EVENT: HAND_RAISE name=${name}`);
        this.updateStatus(`✅ Сұрақ қойылды: ${name}`);
    }

    bindRosterControls() {
        const buttons = document.querySelectorAll('[data-hand-raise]');
        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const studentName = btn.getAttribute('data-student-name');
                this.handleHandRaise(studentName, { manual: true });
            });
        });

        const voiceButtons = document.querySelectorAll('[data-voice-enroll]');
        voiceButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const studentId = btn.getAttribute('data-student-id');
                const studentName = btn.getAttribute('data-student-name');
                if (!studentId || !studentName) return;
                this.startVoiceEnrollment({
                    id: Number(studentId),
                    name: studentName
                });
            });
        });
    }

    bindCameraControls() {
        const startBtn = document.getElementById('classroom-start-camera');
        const stopBtn = document.getElementById('classroom-stop-camera');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startCameraPreview());
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopCameraPreview());
        }
    }

    bindDetectionControls() {
        const startBtn = document.getElementById('classroom-start-detection');
        const stopBtn = document.getElementById('classroom-stop-detection');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startDetection());
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopDetection());
        }
    }

    bindVideoEvents() {
        if (!this.videoEl) return;
        this.videoEl.addEventListener('loadedmetadata', () => this.syncOverlayCanvas());
    }

    bindRollCallControls() {
        const rollCallBtn = document.getElementById('classroom-roll-call');
        if (!rollCallBtn) return;
        rollCallBtn.addEventListener('click', () => {
            if (!this.isConnected) {
                this.updateStatus('AI қосыңыз');
                return;
            }
            this.sendTeacherEvent('EVENT: ROLL_CALL');
        });
    }

    async startVoiceLesson() {
        await super.startVoiceLesson();
        if (!this.isConnected) return;
        this.setSystemState('ai', 'active', 'AI: қосылды');
        this.updateStatus('AI қосылды. Камераны қосыңыз.');
        this.updateVoiceStatus('Тыңдап тұр');
        this.startTimeUpdates();
        this.startAttendanceLoop();
        await this.ensureVoiceAnalyzer();
        this.emitTimeUpdate(true);
        this.emitAttendanceUpdate(true);
    }

    async stopVoiceLesson() {
        await super.stopVoiceLesson();
        this.stopTimeUpdates();
        this.stopAttendanceLoop();
        this.stopVoiceAnalyzer();
        this.setSystemState('ai', 'ready', 'AI: өшірулі');
        this.setCurrentSpeaker('Әзірге жоқ');
        this.updateStatus('AI тоқтады');
        this.updateVoiceStatus('Күту');
    }

    async startCameraPreview() {
        if (this.cameraStream) {
            return;
        }
        try {
            const constraints = {
                video: {
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    frameRate: { ideal: 30 }
                },
                audio: false
            };
            let stream = null;
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraints);
            } catch (error) {
                console.warn('High-res camera request failed, using default constraints', error);
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            }
            this.cameraStream = stream;
            if (this.videoEl) {
                this.videoEl.srcObject = stream;
                await this.videoEl.play();
            }
            this.syncOverlayCanvas();
            this.setSystemState('camera', 'active', 'Камера: қосылды');
            this.updateStatus('Камера қосылды. Тануды қосыңыз.');
        } catch (error) {
            console.error('Camera error:', error);
            this.setSystemState('camera', 'error', 'Камера: қате');
            this.updateStatus('Камераға қол жеткізу мүмкін емес');
        }
    }

    stopCameraPreview() {
        this.stopDetection();
        if (!this.cameraStream) return;
        this.cameraStream.getTracks().forEach((track) => track.stop());
        this.cameraStream = null;
        if (this.videoEl) {
            this.videoEl.srcObject = null;
        }
        this.clearOverlay();
        this.setSystemState('camera', 'ready', 'Камера: өшірулі');
        this.updateStatus('Камера тоқтатылды');
    }

    async startDetection() {
        if (this.isDetecting) return;
        if (!this.cameraStream || !this.videoEl) {
            this.updateStatus('Алдымен камераны қосыңыз');
            return;
        }

        try {
            this.setSystemState('detection', 'warn', 'Тану: жүктелуде');
            this.updateStatus('Тану жүктелуде...');
            const readyMode = await this.ensureDetectionPipelineReady();
            if (!readyMode) {
                throw new Error('Оқушы фотолары бойынша үлгі құру мүмкін болмады');
            }

            this.usingArcFace = readyMode === 'arcface' && this.arcFaceEmbeddings.length > 0;
            if (!this.usingArcFace && this.useArcFace) {
                this.warmArcFacePipeline();
                this.updateStatus('Fast тану қосылды.');
                this.updateRecognitionModeLabel('Тану: fast');
            } else {
                this.updateRecognitionModeLabel('Тану: precise');
                this.updateStatus('Тану қосылды.');
            }

            this.modelsLoaded = true;
            this.initHands();
            this.isDetecting = true;
            this.startDetectionLoop();
            this.setSystemState('detection', 'active', this.usingArcFace ? 'Тану: precise' : 'Тану: fast');
        } catch (error) {
            console.error('Detection init error:', error);
            const message = error && error.message ? error.message : 'Тану іске қосылмады';
            this.setSystemState('detection', 'error', 'Тану: қате');
            this.updateStatus(`Тану іске қосылмады: ${message}`);
        }
    }

    stopDetection() {
        this.isDetecting = false;
        if (this.detectionInterval) {
            clearInterval(this.detectionInterval);
            this.detectionInterval = null;
        }
        this.lastFaceDetections = [];
        this.lastHandMatches = [];
        this.faceInFlight = false;
        this.clearOverlay();
        if (this.cameraStream) {
            this.setSystemState('detection', 'ready', 'Тану: тоқтатылды');
            this.updateStatus('Тану тоқтады');
        }
    }

    startTimeUpdates() {
        if (this.timeUpdateInterval) return;
        this.timeUpdateInterval = setInterval(() => {
            this.emitTimeUpdate(false);
        }, 10000);
    }

    stopTimeUpdates() {
        if (this.timeUpdateInterval) {
            clearInterval(this.timeUpdateInterval);
            this.timeUpdateInterval = null;
        }
        this.lastTimeUpdateMinutes = null;
    }

    getRemainingMs() {
        if (!this.lessonStartTime) return this.maxSessionDuration;
        const elapsed = Date.now() - this.lessonStartTime;
        return Math.max(0, this.maxSessionDuration - elapsed);
    }

    emitTimeUpdate(force = false) {
        if (!this.isConnected) return;
        const remainingMs = this.getRemainingMs();
        const minutes = Math.floor(remainingMs / 60000);
        const seconds = Math.floor((remainingMs % 60000) / 1000);
        const isFinalMinutes = remainingMs <= 5 * 60 * 1000;

        if (!force) {
            if (!isFinalMinutes && this.lastTimeUpdateMinutes === minutes) {
                return;
            }
            if (isFinalMinutes && seconds % 30 !== 0 && this.lastTimeUpdateMinutes === minutes) {
                return;
            }
        }

        this.lastTimeUpdateMinutes = minutes;
        this.sendControlEvent(`EVENT: TIME_REMAINING minutes=${minutes} seconds=${seconds}`);
    }

    startAttendanceLoop() {
        if (this.attendanceInterval) return;
        this.attendanceInterval = setInterval(() => {
            this.emitAttendanceUpdate(false);
        }, this.attendanceIntervalMs);
    }

    stopAttendanceLoop() {
        if (this.attendanceInterval) {
            clearInterval(this.attendanceInterval);
            this.attendanceInterval = null;
        }
    }

    emitAttendanceUpdate(force = false) {
        if (!this.isConnected || !this.roster.length) return;
        const now = Date.now();
        const present = [];
        const missing = [];

        this.roster.forEach((student) => {
            const lastSeen = this.lastSeenAt.get(student.name) || 0;
            if (now - lastSeen <= this.attendanceWindowMs) {
                present.push(student.name);
            } else {
                missing.push(student.name);
            }
        });

        this.updatePresenceIndicators();

        const presentText = present.join(', ') || 'none';
        const missingText = missing.join(', ') || 'none';
        const key = `${presentText}|${missingText}`;
        if (!force && key === this.lastAttendanceKey) {
            return;
        }
        this.lastAttendanceKey = key;
        this.sendControlEvent(`EVENT: ATTENDANCE present=${presentText} missing=${missingText}`);
    }

    trackFacePresence() {
        const now = Date.now();
        this.lastFaceDetections.forEach((face) => {
            if (face.label && face.label !== 'unknown') {
                this.lastSeenAt.set(face.label, now);
                const confidenceText = typeof face.confidence === 'number'
                    ? `Камера ${Math.round(face.confidence * 100)}%`
                    : 'Камерадан танылды';
                this.updateRosterSignal(face.label, confidenceText, 'active');
            }
        });
        this.updatePresenceIndicators();
    }

    updatePresenceIndicators() {
        if (!this.roster.length) return;
        const now = Date.now();
        this.roster.forEach((student) => {
            const indicator = document.querySelector(`[data-presence-id="${student.id}"]`);
            if (!indicator) return;
            const lastSeen = this.lastSeenAt.get(student.name) || 0;
            const isPresent = now - lastSeen <= this.attendanceWindowMs;
            indicator.textContent = isPresent ? 'Көрінді' : 'Күтілуде';
            indicator.classList.toggle('present', isPresent);
        });
    }

    async loadFaceApiModels() {
        if (this.faceApiLoaded) return;
        if (!window.faceapi) {
            throw new Error('face-api.js жүктелмеді');
        }

        if (faceapi.tf && faceapi.tf.ready) {
            await faceapi.tf.ready();
        }

        const bases = [this.faceModelBase];
        if (this.faceModelBase !== '/static/models/face-api') {
            bases.push('/static/models/face-api');
        }

        let lastError = null;
        for (const base of bases) {
            try {
                await Promise.all([
                    faceapi.nets.tinyFaceDetector.loadFromUri(base),
                    faceapi.nets.faceLandmark68TinyNet.loadFromUri(base),
                    faceapi.nets.faceRecognitionNet.loadFromUri(base)
                ]);
                this.faceOptions = new faceapi.TinyFaceDetectorOptions({
                    inputSize: 352,
                    scoreThreshold: 0.42
                });
                this.faceModelBase = base;
                this.faceApiLoaded = true;
                return;
            } catch (error) {
                lastError = error;
            }
        }

        throw lastError || new Error('Face model жүктелмеді');
    }

    async buildFaceMatcher() {
        if (!this.faceApiLoaded) return;
        if (this.faceMatcher) return;
        const labeledDescriptors = [];
        const rosterCount = this.roster.length;
        let rosterIndex = 0;

        for (const student of this.roster) {
            rosterIndex += 1;
            this.updateStatus(`Фото үлгілері дайындалуда: ${rosterIndex}/${rosterCount}`);
            const photoUrls = this.getStudentPhotos(student);
            const descriptors = [];

            for (const url of photoUrls) {
                try {
                    const img = await faceapi.fetchImage(url);
                    const detection = await faceapi
                        .detectSingleFace(img, this.faceOptions)
                        .withFaceLandmarks(true)
                        .withFaceDescriptor();
                    if (detection && detection.descriptor) {
                        descriptors.push(detection.descriptor);
                    }
                } catch (error) {
                    console.warn('Face descriptor error:', error);
                }
            }

            if (descriptors.length) {
                labeledDescriptors.push(new faceapi.LabeledFaceDescriptors(student.name, descriptors));
            }
        }

        if (!labeledDescriptors.length) {
            this.faceMatcher = null;
            this.updateStatus('Оқушы фотолары танылмады.');
            return;
        }

        this.faceMatcher = new faceapi.FaceMatcher(labeledDescriptors, this.faceMatchThreshold);
    }

    getStudentPhotos(student) {
        if (student && Array.isArray(student.photos) && student.photos.length) {
            return student.photos.slice(0, this.maxReferencePhotos);
        }
        if (student && student.photo_url) {
            return [student.photo_url];
        }
        return [];
    }

    loadVoiceEmbeddingsFromRoster() {
        this.voiceEmbeddings.clear();
        this.roster.forEach((student) => {
            const raw = Array.isArray(student.voice_embeddings) ? student.voice_embeddings : [];
            const normalized = raw
                .map((embedding) => {
                    if (!Array.isArray(embedding)) return null;
                    const cleaned = embedding
                        .filter((value) => typeof value === 'number')
                        .slice(0, this.voiceEmbeddingSize);
                    if (cleaned.length < this.voiceEmbeddingSize) {
                        return null;
                    }
                    return this.normalizeEmbedding(cleaned);
                })
                .filter((embedding) => embedding && embedding.length >= this.voiceEmbeddingSize);
            if (normalized.length) {
                this.voiceEmbeddings.set(student.name, normalized);
            }
        });
    }

    updateVoiceStatus(message) {
        const statusEl = document.getElementById('classroom-voice-status');
        if (statusEl) {
            statusEl.textContent = message || '';
        }
    }

    announceVoiceRecognition(name) {
        if (!name) return;
        this.lastVoiceUiAt = Date.now();
        const statusEl = document.getElementById('classroom-voice-status');
        const message = `Сөйлеп тұрған: ${name}`;
        this.setCurrentSpeaker(name);
        this.updateRosterSignal(name, 'Дауыс', 'active');
        this.updateVoiceStatus(message);
        if (this.voiceStatusTimer) {
            clearTimeout(this.voiceStatusTimer);
        }
        this.voiceStatusTimer = setTimeout(() => {
            if (statusEl && statusEl.textContent === message) {
                this.updateVoiceStatus('Күту');
            }
        }, this.voiceStatusTimeoutMs);
    }

    announceVoiceCandidate(name) {
        if (!name) return;
        const now = Date.now();
        if (now - this.lastVoiceUiAt < this.voiceUiCooldownMs) return;
        this.lastVoiceUiAt = now;
        this.setCurrentSpeaker(`${name}?`);
        this.updateRosterSignal(name, 'Күмәнді', 'warn');
        this.updateVoiceStatus(`Мүмкін: ${name}`);
        if (this.voiceStatusTimer) {
            clearTimeout(this.voiceStatusTimer);
        }
        this.voiceStatusTimer = setTimeout(() => {
            this.updateVoiceStatus('Күту');
        }, this.voiceStatusTimeoutMs);
    }

    announceVoiceUnknown() {
        const now = Date.now();
        if (now - this.lastVoiceUiAt < this.voiceUiCooldownMs) return;
        this.lastVoiceUiAt = now;
        this.updateVoiceStatus('Дауыс танылмады');
        if (this.voiceStatusTimer) {
            clearTimeout(this.voiceStatusTimer);
        }
        this.voiceStatusTimer = setTimeout(() => {
            this.updateVoiceStatus('Күту');
        }, this.voiceStatusTimeoutMs);
    }

    updateVoiceCount(studentId, count) {
        const countEl = document.querySelector(`[data-voice-count="${studentId}"]`);
        if (countEl) {
            countEl.textContent = String(count);
        }
    }

    toggleVoiceEnrollButtons(disabled) {
        const voiceButtons = document.querySelectorAll('[data-voice-enroll]');
        voiceButtons.forEach((btn) => {
            btn.disabled = disabled;
        });
    }

    async loadArcFaceModels() {
        if (this.arcFaceLoaded) return;
        if (!window.ort) {
            throw new Error('onnxruntime-web жүктелмеді');
        }
        if (!window.FaceDetection) {
            throw new Error('MediaPipe Face Detection жүктелмеді');
        }

        const wasmBase = window.CLASSROOM_ORT_WASM_URL;
        if (wasmBase && ort.env && ort.env.wasm) {
            ort.env.wasm.wasmPaths = wasmBase;
        }
        if (ort.env && ort.env.wasm && typeof navigator !== 'undefined') {
            const threads = Math.max(1, Math.min(4, navigator.hardwareConcurrency || 4));
            ort.env.wasm.numThreads = threads;
        }

        this.initFaceDetector();

        const providers = [];
        if (typeof navigator !== 'undefined' && navigator.gpu) {
            providers.push('webgpu');
        }
        providers.push('webgl', 'wasm');

        const options = { executionProviders: providers };
        const candidates = [this.arcFaceModelUrl];
        if (this.arcFaceModelUrl !== '/static/models/arcface/arcface.onnx') {
            candidates.push('/static/models/arcface/arcface.onnx');
        }

        let lastError = null;
        for (const url of candidates) {
            try {
                this.arcFaceSession = await ort.InferenceSession.create(url, options);
                this.arcFaceModelUrl = url;
                this.arcFaceInputName = this.arcFaceSession.inputNames[0];
                this.arcFaceOutputName = this.arcFaceSession.outputNames[0];
                const metadata = this.arcFaceSession.inputMetadata
                    ? this.arcFaceSession.inputMetadata[this.arcFaceInputName]
                    : null;
                this.arcFaceInputShape = metadata && Array.isArray(metadata.dimensions)
                    ? metadata.dimensions
                    : null;
                this.arcFaceLoaded = true;
                this.initArcFaceCanvas();
                return;
            } catch (error) {
                lastError = error;
            }
        }

        throw lastError || new Error('ArcFace моделін жүктеу мүмкін болмады');
    }

    initArcFaceCanvas() {
        if (this.arcFaceCanvas) return;
        this.arcFaceCanvas = document.createElement('canvas');
        this.arcFaceCanvas.width = this.arcFaceInputSize;
        this.arcFaceCanvas.height = this.arcFaceInputSize;
        this.arcFaceCanvasCtx = this.arcFaceCanvas.getContext('2d', { willReadFrequently: true });
        if (this.arcFaceCanvasCtx) {
            this.arcFaceCanvasCtx.imageSmoothingEnabled = true;
            this.arcFaceCanvasCtx.imageSmoothingQuality = 'high';
        }
    }

    initFaceDetector() {
        if (this.faceDetector || !window.FaceDetection) return;
        this.faceDetector = new FaceDetection({
            locateFile: (file) => `${this.faceDetectorAssetBase}/${file}`
        });
        const modelType = window.CLASSROOM_FACE_DETECTOR_MODEL || 'full';
        const modelSelection = modelType === 'full' || modelType === 1 ? 1 : 0;
        this.faceDetector.setOptions({
            model: modelType,
            modelSelection,
            minDetectionConfidence: this.faceDetectorMinConfidence
        });
        this.faceDetector.onResults((results) => {
            this.faceDetectorResults = results;
        });
    }

    async detectFaces(source) {
        if (!this.faceDetector) return [];
        this.faceDetectorResults = null;
        await this.faceDetector.send({ image: source });
        const results = this.faceDetectorResults;
        const size = this.getSourceSize(source);
        if (!results || !results.detections || !size) return [];
        return this.extractFaceDetections(results.detections, size);
    }

    extractFaceDetections(detections, size) {
        const output = [];
        detections.forEach((detection) => {
            const location = detection.locationData || detection;
            const relBox = location.relativeBoundingBox || detection.boundingBox || detection.relativeBoundingBox || location.boundingBox;
            if (!relBox) return;

            let relX = 0;
            let relY = 0;
            let relW = 0;
            let relH = 0;

            if (typeof relBox.xmin === 'number') {
                relX = relBox.xmin;
                relY = relBox.ymin;
                relW = relBox.width;
                relH = relBox.height;
            } else if (typeof relBox.xCenter === 'number') {
                relW = relBox.width;
                relH = relBox.height;
                relX = relBox.xCenter - relW / 2;
                relY = relBox.yCenter - relH / 2;
            } else {
                return;
            }

            const x = Math.max(0, relX * size.width);
            const y = Math.max(0, relY * size.height);
            const width = Math.min(size.width - x, relW * size.width);
            const height = Math.min(size.height - y, relH * size.height);
            if (!width || !height) return;

            const relKeypoints = location.relativeKeypoints || detection.relativeKeypoints || detection.keypoints || [];
            const keypoints = relKeypoints.map((point) => ({
                x: point.x * size.width,
                y: point.y * size.height
            }));

            const score = Array.isArray(detection.score) ? detection.score[0] : detection.score;

            output.push({
                box: { x, y, width, height },
                keypoints,
                score
            });
        });
        return output;
    }

    getSourceSize(source) {
        if (!source) return null;
        if (source.videoWidth && source.videoHeight) {
            return { width: source.videoWidth, height: source.videoHeight };
        }
        if (source.naturalWidth && source.naturalHeight) {
            return { width: source.naturalWidth, height: source.naturalHeight };
        }
        if (source.width && source.height) {
            return { width: source.width, height: source.height };
        }
        return null;
    }

    pickBestFace(detections) {
        if (!detections || !detections.length) return null;
        let best = null;
        let bestScore = -Infinity;
        detections.forEach((item) => {
            const score = typeof item.score === 'number'
                ? item.score
                : item.box.width * item.box.height;
            if (score > bestScore) {
                bestScore = score;
                best = item;
            }
        });
        return best;
    }

    async buildArcFaceEmbeddings() {
        if (!this.arcFaceLoaded) return;
        if (this.arcFaceEmbeddings.length) return;
        const labeledEmbeddings = [];
        const rosterCount = this.roster.length;
        let rosterIndex = 0;

        for (const student of this.roster) {
            rosterIndex += 1;
            this.updateStatus(`ArcFace фото үлгілері дайындалуда: ${rosterIndex}/${rosterCount}`);
            const photoUrls = this.getStudentPhotos(student);
            const embeddings = [];

            for (const url of photoUrls) {
                try {
                    const img = await this.loadImage(url);
                    const detections = await this.detectFaces(img);
                    const best = this.pickBestFace(detections);
                    if (!best) continue;
                    const embedding = await this.computeArcFaceEmbedding(img, best);
                    if (embedding) {
                        embeddings.push(embedding);
                    }
                } catch (error) {
                    console.warn('ArcFace embedding error:', error);
                }
            }

            if (embeddings.length) {
                labeledEmbeddings.push({ label: student.name, embeddings });
            }
        }

        if (!labeledEmbeddings.length) {
            this.arcFaceEmbeddings = [];
            this.updateStatus('Оқушы фотолары танылмады.');
            return;
        }

        this.arcFaceEmbeddings = labeledEmbeddings;
    }

    loadImage(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error(`Image load failed: ${url}`));
            img.src = url;
        });
    }

    async computeArcFaceEmbedding(source, detection) {
        if (!this.arcFaceSession || !this.arcFaceInputName || !this.arcFaceOutputName) return null;
        if (!this.arcFaceCanvasCtx) return null;
        if (detection.box.width < this.arcFaceMinFaceSize || detection.box.height < this.arcFaceMinFaceSize) {
            return null;
        }
        const sourceSize = this.getSourceSize(source);
        if (!sourceSize) return null;
        this.drawAlignedFace(source, detection, sourceSize);
        const inputTensor = this.arcFaceTensorFromCanvas(this.arcFaceCanvasCtx, this.arcFaceInputSize);
        if (!inputTensor) return null;
        const feeds = { [this.arcFaceInputName]: inputTensor };
        const results = await this.arcFaceSession.run(feeds);
        const output = results[this.arcFaceOutputName];
        if (!output || !output.data) return null;
        return this.normalizeEmbedding(output.data);
    }

    drawAlignedFace(source, detection, sourceSize) {
        if (!this.arcFaceCanvasCtx) return;
        const ctx = this.arcFaceCanvasCtx;
        const size = this.arcFaceInputSize;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, size, size);

        const eyes = this.getEyePoints(detection.keypoints);
        if (eyes.left && eyes.right) {
            const targetLeft = { x: 38.2946, y: 51.6963 };
            const targetRight = { x: 73.5318, y: 51.5014 };
            const dx = eyes.right.x - eyes.left.x;
            const dy = eyes.right.y - eyes.left.y;
            const srcDist = Math.hypot(dx, dy);
            const dstDx = targetRight.x - targetLeft.x;
            const dstDy = targetRight.y - targetLeft.y;
            const dstDist = Math.hypot(dstDx, dstDy);

            if (srcDist > 1e-6 && dstDist > 0) {
                const scale = dstDist / srcDist;
                const srcAngle = Math.atan2(dy, dx);
                const dstAngle = Math.atan2(dstDy, dstDx);
                const rotation = dstAngle - srcAngle;
                const cos = Math.cos(rotation);
                const sin = Math.sin(rotation);

                const a = scale * cos;
                const b = scale * sin;
                const c = -scale * sin;
                const d = scale * cos;
                const e = targetLeft.x - a * eyes.left.x - c * eyes.left.y;
                const f = targetLeft.y - b * eyes.left.x - d * eyes.left.y;

                ctx.setTransform(a, b, c, d, e, f);
                ctx.drawImage(source, 0, 0, sourceSize.width, sourceSize.height);
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                return;
            }
        }

        const box = this.expandBox(detection.box, sourceSize, 0.18);
        ctx.drawImage(source, box.x, box.y, box.width, box.height, 0, 0, size, size);
    }

    getEyePoints(keypoints) {
        if (!keypoints || keypoints.length < 2) return {};
        let left = keypoints[0];
        let right = keypoints[1];
        if (left.x > right.x) {
            const tmp = left;
            left = right;
            right = tmp;
        }
        return { left, right };
    }

    expandBox(box, sourceSize, padding) {
        const padX = box.width * padding;
        const padY = box.height * padding;
        let x = box.x - padX;
        let y = box.y - padY;
        let width = box.width + padX * 2;
        let height = box.height + padY * 2;

        x = Math.max(0, x);
        y = Math.max(0, y);
        width = Math.min(sourceSize.width - x, width);
        height = Math.min(sourceSize.height - y, height);
        return { x, y, width, height };
    }

    arcFaceTensorFromCanvas(ctx, size) {
        if (!window.ort) return null;
        const imageData = ctx.getImageData(0, 0, size, size);
        const data = imageData.data;
        const mean = 127.5;
        const std = 128.0;

        const shape = this.arcFaceInputShape;
        const isNHWC = Array.isArray(shape) && shape.length === 4 && shape[3] === 3;
        const isNCHW = Array.isArray(shape) && shape.length === 4 && shape[1] === 3;
        const useNHWC = isNHWC || !isNCHW;

        if (useNHWC) {
            const floatData = new Float32Array(size * size * 3);
            for (let i = 0; i < size * size; i += 1) {
                const idx = i * 4;
                const r = data[idx];
                const g = data[idx + 1];
                const b = data[idx + 2];
                const offset = i * 3;

                if (this.arcFaceColorOrder === 'rgb') {
                    floatData[offset] = (r - mean) / std;
                    floatData[offset + 1] = (g - mean) / std;
                    floatData[offset + 2] = (b - mean) / std;
                } else {
                    floatData[offset] = (b - mean) / std;
                    floatData[offset + 1] = (g - mean) / std;
                    floatData[offset + 2] = (r - mean) / std;
                }
            }
            return new ort.Tensor('float32', floatData, [1, size, size, 3]);
        }

        const floatData = new Float32Array(3 * size * size);
        for (let i = 0; i < size * size; i += 1) {
            const idx = i * 4;
            const r = data[idx];
            const g = data[idx + 1];
            const b = data[idx + 2];

            if (this.arcFaceColorOrder === 'rgb') {
                floatData[i] = (r - mean) / std;
                floatData[i + size * size] = (g - mean) / std;
                floatData[i + 2 * size * size] = (b - mean) / std;
            } else {
                floatData[i] = (b - mean) / std;
                floatData[i + size * size] = (g - mean) / std;
                floatData[i + 2 * size * size] = (r - mean) / std;
            }
        }

        return new ort.Tensor('float32', floatData, [1, 3, size, size]);
    }

    normalizeEmbedding(rawEmbedding) {
        const data = rawEmbedding instanceof Float32Array ? rawEmbedding : new Float32Array(rawEmbedding);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
            sum += data[i] * data[i];
        }
        const norm = Math.sqrt(sum);
        if (!norm) return data;
        const normalized = new Float32Array(data.length);
        for (let i = 0; i < data.length; i += 1) {
            normalized[i] = data[i] / norm;
        }
        return normalized;
    }

    cosineSimilarity(a, b) {
        let dot = 0;
        const len = Math.min(a.length, b.length);
        for (let i = 0; i < len; i += 1) {
            dot += a[i] * b[i];
        }
        return dot;
    }

    scoreToConfidence(score, threshold) {
        if (typeof score !== 'number' || typeof threshold !== 'number') return null;
        if (score <= threshold) return 0;
        const range = 1 - threshold;
        if (!range) return 0;
        return Math.min(1, Math.max(0.45, 0.45 + ((score - threshold) / range) * 0.55));
    }

    distanceToConfidence(distance, threshold) {
        if (typeof distance !== 'number' || typeof threshold !== 'number') return null;
        if (distance >= threshold) return 0;
        return Math.min(1, Math.max(0.45, 0.45 + (1 - (distance / threshold)) * 0.55));
    }

    getVoiceConfidence(label) {
        if (!label) return null;
        const entry = this.lastVoiceMatch.get(label);
        if (!entry) return null;
        const age = Date.now() - entry.at;
        if (age > this.voiceFreshWindowMs) return null;
        return entry.confidence;
    }

    computeFusionConfidence({ faceConfidence, voiceConfidence, handRaise }) {
        let sum = 0;
        let weight = 0;
        if (typeof faceConfidence === 'number') {
            sum += faceConfidence * this.fusionFaceWeight;
            weight += this.fusionFaceWeight;
        }
        if (typeof voiceConfidence === 'number') {
            sum += voiceConfidence * this.fusionVoiceWeight;
            weight += this.fusionVoiceWeight;
        }
        if (handRaise) {
            sum += 1 * this.fusionHandWeight;
            weight += this.fusionHandWeight;
        }
        if (!weight) return 0;
        return sum / weight;
    }

    formatConfidence(value) {
        if (typeof value !== 'number' || !Number.isFinite(value)) return null;
        return value.toFixed(2);
    }

    matchArcFaceEmbedding(embedding) {
        if (!embedding || !this.arcFaceEmbeddings.length) {
            return { label: 'unknown', score: null };
        }
        let bestScore = -1;
        let bestLabel = 'unknown';
        this.arcFaceEmbeddings.forEach((entry) => {
            entry.embeddings.forEach((stored) => {
                const score = this.cosineSimilarity(embedding, stored);
                if (score > bestScore) {
                    bestScore = score;
                    bestLabel = entry.label;
                }
            });
        });
        if (bestScore < this.arcFaceThreshold) {
            return { label: 'unknown', score: bestScore };
        }
        return { label: bestLabel, score: bestScore };
    }

    initHands() {
        if (this.hands || !window.Hands) return;
        this.hands = new Hands({
            locateFile: (file) => `${this.handsAssetBase}/${file}`
        });
        this.hands.setOptions({
            maxNumHands: 4,
            modelComplexity: 0,
            minDetectionConfidence: 0.6,
            minTrackingConfidence: 0.6
        });
        this.hands.onResults((results) => this.handleHandsResults(results));
    }

    async ensureVoiceAnalyzer() {
        if (this.voiceAnalyzer) {
            if (!this.voiceAnalyzerActive && this.voiceAnalyzer.start) {
                this.voiceAnalyzer.start();
                this.voiceAnalyzerActive = true;
            }
            return;
        }
        if (!window.Meyda) {
            this.setSystemState('voice', 'warn', 'Дауыс тану: кітапхана жоқ');
            this.updateVoiceStatus('Дауыс тану кітапханасы жүктелмеді.');
            return;
        }

        if (!this.audioContext || !this.microphone) {
            try {
                await this.initializeAudio();
            } catch (error) {
                console.warn('Voice analyzer audio init failed:', error);
                this.setSystemState('voice', 'error', 'Дауыс тану: микрофон жоқ');
                this.updateVoiceStatus('Микрофонды іске қосу мүмкін емес.');
                return;
            }
        }

        if (!this.audioContext || !this.microphone) {
            return;
        }

        this.voiceSource = this.audioContext.createMediaStreamSource(this.microphone);
        this.voiceAnalyzer = window.Meyda.createMeydaAnalyzer({
            audioContext: this.audioContext,
            source: this.voiceSource,
            bufferSize: 512,
            featureExtractors: ['mfcc', 'rms'],
            callback: (features) => this.handleVoiceFeatures(features)
        });
        this.voiceAnalyzer.start();
        this.voiceAnalyzerActive = true;
        this.setSystemState('voice', 'active', 'Дауыс тану: тыңдап тұр');
        this.updateVoiceStatus('Дауыс тану қосылды.');
    }

    stopVoiceAnalyzer() {
        if (this.voiceAnalyzer && this.voiceAnalyzer.stop) {
            this.voiceAnalyzer.stop();
        }
        if (this.voiceSource) {
            try {
                this.voiceSource.disconnect();
            } catch (error) {
                console.warn('Voice source disconnect error:', error);
            }
        }
        this.voiceAnalyzer = null;
        this.voiceSource = null;
        this.voiceAnalyzerActive = false;
        this.voiceActive = false;
        this.voiceFrames = [];
        this.voiceNoiseFloor = null;
        this.lastVoiceMatch.clear();
        this.cancelVoiceEnrollment('');
        this.setSystemState('voice', 'ready', this.voiceEmbeddings.size ? 'Дауыс тану: күту режимі' : 'Дауыс тану: үлгі аз');
    }

    async startVoiceEnrollment(student) {
        if (!student || !student.id || !student.name) return;
        if (this.voiceEnrollment) {
            this.updateVoiceStatus('Дауыс үлгісі жазылып жатыр.');
            return;
        }

        await this.ensureVoiceAnalyzer();
        if (!this.voiceAnalyzerActive) {
            return;
        }

        this.voiceEnrollment = {
            id: student.id,
            name: student.name,
            frames: [],
            startedAt: Date.now()
        };
        this.toggleVoiceEnrollButtons(true);
        this.updateVoiceStatus(`🎙 ${student.name} үшін дауыс үлгісі жазылуда...`);

        if (this.voiceEnrollmentTimer) {
            clearTimeout(this.voiceEnrollmentTimer);
        }
        this.voiceEnrollmentTimer = setTimeout(() => {
            this.finishVoiceEnrollment();
        }, this.voiceEnrollSeconds * 1000);
    }

    cancelVoiceEnrollment(message) {
        if (this.voiceEnrollmentTimer) {
            clearTimeout(this.voiceEnrollmentTimer);
            this.voiceEnrollmentTimer = null;
        }
        this.voiceEnrollment = null;
        this.toggleVoiceEnrollButtons(false);
        if (message) {
            this.updateVoiceStatus(message);
        }
    }

    async finishVoiceEnrollment() {
        const enrollment = this.voiceEnrollment;
        if (!enrollment) return;
        this.voiceEnrollment = null;

        if (this.voiceEnrollmentTimer) {
            clearTimeout(this.voiceEnrollmentTimer);
            this.voiceEnrollmentTimer = null;
        }

        const embedding = this.computeVoiceEmbedding(enrollment.frames || []);
        if (!embedding) {
            this.toggleVoiceEnrollButtons(false);
            this.updateVoiceStatus('Дауыс үлгісі жеткіліксіз. Сәл анық сөйлеп қайта көріңіз.');
            return;
        }

        const saved = await this.saveVoiceEmbedding(enrollment.id, embedding);
        this.toggleVoiceEnrollButtons(false);
        if (saved) {
            this.updateVoiceStatus(`✅ ${enrollment.name} үлгісі сақталды.`);
        } else {
            this.updateVoiceStatus('Дауыс үлгісін сақтау мүмкін болмады.');
        }
    }

    handleVoiceFeatures(features) {
        if (!features) return;
        const mfcc = Array.isArray(features.mfcc) ? features.mfcc : null;
        const rms = typeof features.rms === 'number' ? features.rms : 0;

        if (!this.voiceNoiseFloor && rms > 0) {
            this.voiceNoiseFloor = rms;
        }

        if (this.voiceNoiseFloor !== null && rms > 0) {
            this.voiceNoiseFloor = this.voiceNoiseFloor * 0.98 + rms * 0.02;
        }

        const threshold = Math.max(this.voiceMinRms, (this.voiceNoiseFloor || 0) * 2.1);
        const isSpeech = rms > threshold;

        if (isSpeech && mfcc) {
            if (!this.voiceActive) {
                this.voiceActive = true;
                this.voiceFrames = [];
            }
            this.voiceFrames.push(mfcc.slice(0, this.voiceEmbeddingSize));
            if (this.voiceFrames.length > this.voiceMaxFrames) {
                this.voiceFrames.shift();
            }
            if (this.voiceEnrollment && Array.isArray(this.voiceEnrollment.frames)) {
                this.voiceEnrollment.frames.push(mfcc.slice(0, this.voiceEmbeddingSize));
            }
            return;
        }

        if (this.voiceActive) {
            const frames = this.voiceFrames.slice();
            this.voiceActive = false;
            this.voiceFrames = [];
            if (frames.length >= this.voiceMinFrames) {
                this.processVoiceFrames(frames);
            }
        }
    }

    processVoiceFrames(frames) {
        const embedding = this.computeVoiceEmbedding(frames);
        if (!embedding) return;
        const best = this.findBestVoiceMatch(embedding);
        if (!best || !best.label || best.label === 'unknown' || best.score === null) {
            this.announceVoiceUnknown();
            return;
        }

        if (best.score < this.voiceMatchThreshold) {
            if (best.score >= this.voiceDisplayThreshold) {
                this.announceVoiceCandidate(best.label);
            } else {
                this.announceVoiceUnknown();
            }
            return;
        }

        const voiceConfidence = this.scoreToConfidence(best.score, this.voiceMatchThreshold);
        this.announceVoiceRecognition(best.label);
        this.lastVoiceMatch.set(best.label, {
            score: best.score,
            confidence: voiceConfidence,
            at: Date.now()
        });
        if (!this.shouldTriggerVoiceEvent(best.label)) return;
        this.lastVoiceEventAt.set(best.label, Date.now());
        this.lastSeenAt.set(best.label, Date.now());
        this.updatePresenceIndicators();
        if (this.isConnected) {
            const score = typeof voiceConfidence === 'number' ? voiceConfidence.toFixed(2) : '0.00';
            this.sendControlEvent(`EVENT: VOICE_DETECTED name=${best.label} confidence=${score}`);
        }
    }

    computeVoiceEmbedding(frames) {
        if (!frames || !frames.length) return null;
        const size = this.voiceEmbeddingSize;
        const sums = new Array(size).fill(0);
        let count = 0;
        frames.forEach((frame) => {
            if (!Array.isArray(frame)) return;
            for (let i = 0; i < size; i += 1) {
                const value = typeof frame[i] === 'number' ? frame[i] : 0;
                sums[i] += value;
            }
            count += 1;
        });
        if (!count) return null;
        const avg = sums.map((value) => value / count);
        return this.normalizeEmbedding(avg);
    }

    matchVoiceEmbedding(embedding) {
        if (!embedding || !this.voiceEmbeddings.size) {
            return { label: 'unknown', score: null };
        }
        let bestScore = -1;
        let bestLabel = 'unknown';
        for (const [label, samples] of this.voiceEmbeddings.entries()) {
            samples.forEach((sample) => {
                const score = this.cosineSimilarity(embedding, sample);
                if (score > bestScore) {
                    bestScore = score;
                    bestLabel = label;
                }
            });
        }
        if (bestScore < this.voiceMatchThreshold) {
            return { label: 'unknown', score: bestScore };
        }
        return { label: bestLabel, score: bestScore };
    }

    findBestVoiceMatch(embedding) {
        if (!embedding || !this.voiceEmbeddings.size) {
            return { label: 'unknown', score: null };
        }
        let bestScore = -1;
        let bestLabel = 'unknown';
        for (const [label, samples] of this.voiceEmbeddings.entries()) {
            samples.forEach((sample) => {
                const score = this.cosineSimilarity(embedding, sample);
                if (score > bestScore) {
                    bestScore = score;
                    bestLabel = label;
                }
            });
        }
        if (bestScore < 0) {
            return { label: 'unknown', score: null };
        }
        return { label: bestLabel, score: bestScore };
    }

    shouldTriggerVoiceEvent(label) {
        const lastAt = this.lastVoiceEventAt.get(label) || 0;
        return Date.now() - lastAt > this.voiceCooldownMs;
    }

    async saveVoiceEmbedding(studentId, embedding) {
        const csrfToken = this.getCsrfToken();
        try {
            const response = await fetch(`/classroom/student/${studentId}/voice/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ embedding: Array.from(embedding) })
            });
            if (!response.ok) {
                const text = await response.text();
                console.warn('Voice embedding save failed:', text);
                return false;
            }
            const payload = await response.json();
            const student = this.roster.find((item) => item.id === studentId);
            if (student) {
                const list = this.voiceEmbeddings.get(student.name) || [];
                list.push(embedding);
                const count = payload && typeof payload.count === 'number' ? payload.count : list.length;
                if (list.length > count) {
                    list.splice(0, list.length - count);
                }
                this.voiceEmbeddings.set(student.name, list);
                this.updateVoiceCount(studentId, count);
                student.voice_count = count;
                this.updateRosterSignal(student.name, 'Дауыс үлгісі жаңартылды', 'active');
            }
            return true;
        } catch (error) {
            console.warn('Voice embedding save error:', error);
            return false;
        }
    }

    getCsrfToken() {
        const name = 'csrftoken=';
        const decodedCookie = decodeURIComponent(document.cookie || '');
        const parts = decodedCookie.split(';');
        for (let i = 0; i < parts.length; i += 1) {
            const part = parts[i].trim();
            if (part.startsWith(name)) {
                return part.substring(name.length, part.length);
            }
        }
        return '';
    }

    startDetectionLoop() {
        if (this.detectionInterval) {
            clearInterval(this.detectionInterval);
        }
        const intervalMs = this.usingArcFace ? this.arcFaceDetectionIntervalMs : this.detectionIntervalMs;
        this.detectionInterval = setInterval(() => {
            this.processFrame();
        }, intervalMs);
    }

    async processFrame() {
        if (!this.isDetecting || !this.videoEl || !this.modelsLoaded) return;
        if (this.faceInFlight) return;
        if (this.videoEl.readyState < 2) return;

        this.faceInFlight = true;
        try {
            if (this.usingArcFace) {
                await this.processFrameArcFace();
            } else {
                await this.processFrameFaceApi();
            }
        } catch (error) {
            console.warn('Face detection error:', error);
        } finally {
            this.faceInFlight = false;
            this.trackFacePresence();
            this.renderOverlay();
            this.runHandsDetection();
        }
    }

    async processFrameFaceApi() {
        const frame = this.getDetectionSourceFrame();
        if (!frame || !frame.source) return;
        const detections = await faceapi
            .detectAllFaces(frame.source, this.faceOptions)
            .withFaceLandmarks(true)
            .withFaceDescriptors();

        const frameSize = this.getSourceSize(frame.source);
        const displaySize = frameSize || {
            width: this.videoEl.videoWidth || this.videoEl.width,
            height: this.videoEl.videoHeight || this.videoEl.height
        };

        const resized = faceapi.resizeResults(detections, displaySize);
        this.lastFaceDetections = resized.map((item) => {
            const bestMatch = this.faceMatcher ? this.faceMatcher.findBestMatch(item.descriptor) : null;
            const distance = bestMatch ? bestMatch.distance : null;
            const confidence = this.distanceToConfidence(distance, this.faceMatchThreshold);
            const box = {
                x: item.detection.box.x * frame.ratioX,
                y: item.detection.box.y * frame.ratioY,
                width: item.detection.box.width * frame.ratioX,
                height: item.detection.box.height * frame.ratioY
            };
            return {
                box,
                label: bestMatch ? bestMatch.label : 'unknown',
                distance,
                confidence
            };
        });
    }

    async processFrameArcFace() {
        const frame = this.getDetectionSourceFrame();
        if (!frame || !frame.source) return;
        let detections = await this.detectFaces(frame.source);
        detections = this.scaleDetectionsToVideo(detections, frame.ratioX, frame.ratioY);
        const faces = [];

        const sortedDetections = detections
            .slice()
            .sort((a, b) => (b.box.width * b.box.height) - (a.box.width * a.box.height))
            .slice(0, this.maxFaces);

        let detectionsToProcess = sortedDetections;
        if (sortedDetections.length > this.arcFaceFacesPerCycle) {
            const startIndex = this.arcFaceScanCursor % sortedDetections.length;
            detectionsToProcess = [];
            for (let i = 0; i < this.arcFaceFacesPerCycle; i += 1) {
                detectionsToProcess.push(sortedDetections[(startIndex + i) % sortedDetections.length]);
            }
            this.arcFaceScanCursor = (startIndex + this.arcFaceFacesPerCycle) % sortedDetections.length;
        }

        for (const detection of detectionsToProcess) {
            if (detection.box.width < this.arcFaceMinFaceSize || detection.box.height < this.arcFaceMinFaceSize) {
                continue;
            }
            const embedding = await this.computeArcFaceEmbedding(this.videoEl, detection);
            if (!embedding) continue;
            const match = this.matchArcFaceEmbedding(embedding);
            const confidence = this.scoreToConfidence(match.score, this.arcFaceThreshold);
            faces.push({
                box: detection.box,
                label: match.label,
                score: match.score,
                confidence
            });
        }

        this.lastFaceDetections = faces;
    }

    runHandsDetection() {
        if (!this.hands || this.handInFlight || !this.videoEl) return;
        if (this.videoEl.readyState < 2) return;
        this.handInFlight = true;
        const sendResult = this.hands.send({ image: this.videoEl });
        if (sendResult && typeof sendResult.then === 'function') {
            sendResult.finally(() => {
                this.handInFlight = false;
            });
        } else {
            this.handInFlight = false;
        }
    }

    handleHandsResults(results) {
        const landmarks = results && results.multiHandLandmarks ? results.multiHandLandmarks : [];
        this.lastHandMatches = this.matchHandsToFaces(landmarks);
        this.renderOverlay();
    }

    matchHandsToFaces(handLandmarks) {
        const videoSize = this.getVideoSize();
        if (!videoSize) return [];
        const matches = [];

        handLandmarks.forEach((landmarks) => {
            const center = this.getHandCenter(landmarks, videoSize);
            const faceMatch = this.findClosestFace(center);
            if (!faceMatch) return;

            const isRaised = this.isHandRaised(center, faceMatch.box);
            const faceConfidence = typeof faceMatch.confidence === 'number' ? faceMatch.confidence : null;
            const voiceConfidence = faceMatch.label && faceMatch.label !== 'unknown'
                ? this.getVoiceConfidence(faceMatch.label)
                : null;
            matches.push({
                center,
                label: faceMatch.label,
                isRaised
            });

            if (isRaised && faceMatch.label !== 'unknown') {
                if (this.shouldTriggerHandRaise(faceMatch.label)) {
                    this.lastHandRaiseAt.set(faceMatch.label, Date.now());
                    this.handleHandRaise(faceMatch.label, {
                        manual: false,
                        faceConfidence,
                        voiceConfidence,
                        handRaise: true
                    });
                }
            }
        });

        return matches;
    }

    getHandCenter(landmarks, videoSize) {
        const points = landmarks.map((point) => ({
            x: point.x * videoSize.width,
            y: point.y * videoSize.height
        }));
        const sum = points.reduce((acc, point) => ({
            x: acc.x + point.x,
            y: acc.y + point.y
        }), { x: 0, y: 0 });
        return {
            x: sum.x / points.length,
            y: sum.y / points.length
        };
    }

    findClosestFace(point) {
        if (!this.lastFaceDetections.length) return null;
        let closest = null;
        let minDist = Infinity;

        this.lastFaceDetections.forEach((face) => {
            const center = {
                x: face.box.x + face.box.width / 2,
                y: face.box.y + face.box.height / 2
            };
            const dist = Math.hypot(point.x - center.x, point.y - center.y);
            const maxDist = Math.max(face.box.width, face.box.height) * 1.6;
            if (dist < minDist && dist <= maxDist) {
                minDist = dist;
                closest = face;
            }
        });

        return closest;
    }

    isHandRaised(handPoint, faceBox) {
        const thresholdY = faceBox.y - faceBox.height * this.handRaiseMargin;
        return handPoint.y < thresholdY;
    }

    shouldTriggerHandRaise(label) {
        const lastAt = this.lastHandRaiseAt.get(label) || 0;
        return Date.now() - lastAt > this.handRaiseCooldownMs;
    }

    getVideoSize() {
        if (!this.videoEl) return null;
        const width = this.videoEl.videoWidth || this.videoEl.width;
        const height = this.videoEl.videoHeight || this.videoEl.height;
        if (!width || !height) return null;
        return { width, height };
    }

    syncOverlayCanvas() {
        if (!this.videoEl || !this.overlayEl || !this.overlayCtx) return;
        const size = this.getVideoSize();
        if (!size) return;
        const ratio = window.devicePixelRatio || 1;
        this.overlayEl.width = size.width * ratio;
        this.overlayEl.height = size.height * ratio;
        this.overlayEl.style.width = `${size.width}px`;
        this.overlayEl.style.height = `${size.height}px`;
        this.overlayCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    renderOverlay() {
        if (!this.overlayCtx || !this.overlayEl) return;
        const size = this.getVideoSize();
        if (!size) return;
        const ctx = this.overlayCtx;
        ctx.clearRect(0, 0, size.width, size.height);

        this.lastFaceDetections.forEach((face) => {
            const isKnown = face.label && face.label !== 'unknown';
            ctx.strokeStyle = isKnown ? '#10b981' : '#9ca3af';
            ctx.lineWidth = 2.5;
            ctx.strokeRect(face.box.x, face.box.y, face.box.width, face.box.height);

            let label = isKnown ? face.label : 'Белгісіз';
            const confidence = typeof face.confidence === 'number' ? face.confidence : face.score;
            if (isKnown && typeof confidence === 'number' && Number.isFinite(confidence)) {
                label = `${label} ${Math.round(confidence * 100)}%`;
            }
            ctx.font = '600 15px Inter, sans-serif';
            const textWidth = ctx.measureText(label).width + 10;
            const labelY = Math.max(18, face.box.y);
            ctx.fillStyle = isKnown ? 'rgba(5, 150, 105, 0.88)' : 'rgba(51, 65, 85, 0.86)';
            ctx.fillRect(face.box.x, labelY - 18, textWidth, 18);
            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, face.box.x + 5, labelY - 5);
        });

        this.lastHandMatches.forEach((hand) => {
            ctx.beginPath();
            ctx.arc(hand.center.x, hand.center.y, 6, 0, Math.PI * 2);
            ctx.fillStyle = hand.isRaised ? '#f97316' : '#60a5fa';
            ctx.fill();
            if (hand.label && hand.label !== 'unknown') {
                ctx.fillStyle = '#ffffff';
                ctx.fillText(hand.label, hand.center.x + 8, hand.center.y - 8);
            }
        });
    }

    clearOverlay() {
        if (!this.overlayCtx || !this.overlayEl) return;
        const size = this.getVideoSize();
        if (!size) return;
        this.overlayCtx.clearRect(0, 0, size.width, size.height);
    }

    updateStatus(message) {
        const statusEl = document.getElementById('classroom-status');
        if (statusEl) {
            statusEl.textContent = message || '';
        }
    }
}

window.ClassroomLessonManager = ClassroomLessonManager;
