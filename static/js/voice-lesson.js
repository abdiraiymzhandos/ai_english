/**
 * Voice Lesson JavaScript for OpenAI Realtime API Integration
 * Handles audio streaming, WebSocket communication, and UI interactions
 */

class VoiceLessonManager {
    constructor(lessonId) {
        this.lessonId = lessonId;
        this.socket = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.microphone = null;
        this.isRecording = false;
        this.isConnected = false;
        this.audioQueue = [];
        this.isPlayingAudio = false;
        this.audioProcessor = null;
        this.volumeMeter = null;

        // Audio settings to prevent feedback
        this.audioConstraints = {
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
                sampleRate: 16000
            },
            video: false
        };

        this.initializeUI();
    }

    initializeUI() {
        // Create voice lesson UI elements
        this.createVoiceLessonUI();
        this.attachEventListeners();
    }

    createVoiceLessonUI() {
        const container = document.getElementById('voice-lesson-container');
        if (!container) return;

        container.innerHTML = `
            <div class="voice-lesson-card">
                <div class="voice-lesson-header">
                    <h3>🎙️ AI Дауыс Сабағы</h3>
                    <div class="connection-status" id="connection-status">
                        <span class="status-indicator offline"></span>
                        <span class="status-text">Байланыс жоқ</span>
                    </div>
                </div>

                <div class="voice-lesson-content">
                    <div class="audio-visualizer" id="audio-visualizer">
                        <div class="wave-container">
                            <div class="wave-bar"></div>
                            <div class="wave-bar"></div>
                            <div class="wave-bar"></div>
                            <div class="wave-bar"></div>
                            <div class="wave-bar"></div>
                        </div>
                    </div>

                    <div class="lesson-controls">
                        <button id="start-voice-lesson" class="btn-voice-primary">
                            <i class="fas fa-microphone"></i>
                            <span>Сабақты Бастау</span>
                        </button>
                        <button id="stop-voice-lesson" class="btn-voice-secondary" style="display: none;">
                            <i class="fas fa-stop"></i>
                            <span>Тоқтату</span>
                        </button>
                    </div>

                    <div class="audio-status" id="audio-status">
                        <div class="volume-meter">
                            <span>🎤 Микрофон деңгейі:</span>
                            <div class="volume-bar-container">
                                <div class="volume-bar" id="volume-bar"></div>
                            </div>
                            <span id="volume-percentage">0%</span>
                        </div>
                        <div class="connection-info">
                            <span id="audio-status-text">Күту режимі</span>
                        </div>
                    </div>

                    <div class="transcription-display" id="transcription-display">
                        <h4>Сіздің сөзіңіз:</h4>
                        <p id="user-transcript">...</p>
                    </div>

                    <div class="voice-instructions">
                        <p>💡 Микрофонға жақын сөйлеңіз және AI мұғалімнің жауабын күтіңіз</p>
                    </div>
                </div>
            </div>
        `;
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
        try {
            this.updateUI('connecting');

            // Request microphone permission
            await this.initializeAudio();

            // Connect to WebSocket
            await this.connectWebSocket();

            // Start recording and conversation
            await this.startRecording();
            await this.startConversation();

            this.updateUI('connected');

        } catch (error) {
            console.error('Error starting voice lesson:', error);
            this.updateUI('error', error.message);
        }
    }

    async stopVoiceLesson() {
        try {
            this.updateUI('disconnecting');

            // Stop recording
            await this.stopRecording();

            // Stop conversation
            await this.stopConversation();

            // Close WebSocket
            this.closeWebSocket();

            // Stop audio context
            this.cleanup();

            this.updateUI('disconnected');

        } catch (error) {
            console.error('Error stopping voice lesson:', error);
            this.updateUI('error', error.message);
        }
    }

    async initializeAudio() {
        try {
            console.log('Initializing audio...');

            // Create audio context - use 24000 Hz for OpenAI Realtime API
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 24000
            });
            console.log('Audio context created with 24kHz sample rate');

            // Request microphone access
            console.log('Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia(this.audioConstraints);
            this.microphone = stream;
            console.log('Microphone access granted');

            // Setup audio processing for real-time PCM16 streaming
            console.log('Setting up audio processor...');
            const source = this.audioContext.createMediaStreamSource(stream);
            this.audioProcessor = this.audioContext.createScriptProcessor(2048, 1, 1);

            // Create volume meter
            this.setupVolumeMeter(source);

            this.audioProcessor.onaudioprocess = (e) => {
                if (this.isRecording && !this.isPlayingAudio && this.socket && this.socket.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);

                    // Convert Float32 to PCM16
                    const pcm16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                    }

                    // Send PCM16 audio directly to WebSocket
                    this.socket.send(pcm16.buffer);

                    // Update status
                    this.updateAudioStatus('sending');
                }
            };

            source.connect(this.audioProcessor);
            this.audioProcessor.connect(this.audioContext.destination);

            // Setup MediaRecorder for fallback
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 16000
            });

            this.mediaRecorder.ondataavailable = (event) => {
                console.log('MediaRecorder data available:', event.data.size, 'bytes');
            };

            this.mediaRecorder.onerror = (error) => {
                console.error('MediaRecorder error:', error);
            };

            this.mediaRecorder.onstart = () => {
                console.log('MediaRecorder started');
            };

            this.mediaRecorder.onstop = () => {
                console.log('MediaRecorder stopped');
            };

            console.log('Audio initialization complete');

        } catch (error) {
            console.error('Audio initialization error:', error);
            throw new Error('Микрофонға қол жеткізу мүмкін емес: ' + error.message);
        }
    }

    setupVolumeMeter(source) {
        const analyser = this.audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const updateVolume = () => {
            if (!this.isRecording) return;

            analyser.getByteFrequencyData(dataArray);

            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
            }
            const average = sum / bufferLength;
            const volumePercentage = Math.round((average / 255) * 100);

            // Update UI
            const volumeBar = document.getElementById('volume-bar');
            const volumeText = document.getElementById('volume-percentage');
            if (volumeBar && volumeText) {
                volumeBar.style.width = volumePercentage + '%';
                volumeText.textContent = volumePercentage + '%';

                // Change color based on volume
                if (volumePercentage > 60) {
                    volumeBar.style.backgroundColor = '#4CAF50';
                } else if (volumePercentage > 20) {
                    volumeBar.style.backgroundColor = '#FFC107';
                } else {
                    volumeBar.style.backgroundColor = '#f44336';
                }
            }

            requestAnimationFrame(updateVolume);
        };

        this.volumeMeter = updateVolume;
    }

    convertToPCM16(audioBuffer) {
        const samples = audioBuffer.getChannelData(0);
        const pcm16 = new Int16Array(samples.length);

        for (let i = 0; i < samples.length; i++) {
            pcm16[i] = Math.max(-32768, Math.min(32767, samples[i] * 32768));
        }

        return pcm16.buffer;
    }

    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voice-lesson/${this.lessonId}/`;

            console.log('Connecting to WebSocket:', wsUrl);
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = () => {
                console.log('WebSocket connected successfully');
                this.isConnected = true;
                resolve();
            };

            this.socket.onmessage = (event) => {
                console.log('WebSocket message received:', event);
                this.handleWebSocketMessage(event);
            };

            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(new Error('Серверге байланысу мүмкін емес'));
            };

            this.socket.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                this.isConnected = false;
                this.updateUI('disconnected');
            };

            // Timeout for connection
            setTimeout(() => {
                if (!this.isConnected) {
                    console.error('WebSocket connection timeout');
                    reject(new Error('Байланыс орнату уақыты бітті'));
                }
            }, 10000);
        });
    }

    handleWebSocketMessage(event) {
        if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
            // Audio data from AI
            console.log('Received audio data:', event.data.constructor.name, 'size:', event.data.size || event.data.byteLength);
            this.playAudioResponse(event.data);
        } else {
            // Text message
            try {
                const data = JSON.parse(event.data);
                this.handleTextMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        }
    }

    handleTextMessage(data) {
        switch (data.type) {
            case 'transcription':
                this.updateTranscription(data.text);
                break;
            case 'user_speech_started':
                this.stopAIAudio();
                this.showSpeechIndicator(true);
                break;
            case 'user_speech_stopped':
                this.showSpeechIndicator(false);
                break;
            case 'audio_complete':
                this.isPlayingAudio = false;
                break;
            case 'error':
                console.error('Server error:', data.message);
                this.updateUI('error', data.message);
                break;
        }
    }

    async playAudioResponse(audioData) {
        try {
            // Prevent feedback by stopping user audio during AI speech
            if (this.isRecording) {
                this.pauseRecording();
            }

            this.isPlayingAudio = true;

            // Convert Blob to ArrayBuffer if needed
            let arrayBuffer;
            if (audioData instanceof Blob) {
                console.log('Converting Blob to ArrayBuffer...');
                arrayBuffer = await audioData.arrayBuffer();
            } else {
                arrayBuffer = audioData;
            }

            // Convert PCM16 to audio buffer
            const audioBuffer = await this.convertPCM16ToAudioBuffer(arrayBuffer);

            // Create audio source and play
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);

            source.onended = () => {
                this.isPlayingAudio = false;
                // Resume recording after AI finishes speaking
                if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
                    this.resumeRecording();
                }
            };

            source.start(0);
            console.log('Audio playback started');

        } catch (error) {
            console.error('Error playing audio response:', error);
            this.isPlayingAudio = false;
        }
    }

    async convertPCM16ToAudioBuffer(pcm16Data) {
        const samples = new Int16Array(pcm16Data);
        // OpenAI sends audio at 24kHz
        const audioBuffer = this.audioContext.createBuffer(1, samples.length, 24000);
        const channelData = audioBuffer.getChannelData(0);

        for (let i = 0; i < samples.length; i++) {
            channelData[i] = samples[i] / 32768.0;
        }

        return audioBuffer;
    }

    stopAIAudio() {
        // Stop any currently playing AI audio to prevent overlap
        this.audioContext.suspend().then(() => {
            this.audioContext.resume();
        });
    }

    async startRecording() {
        this.isRecording = true;
        this.animateVisualizer(true);

        // Start volume meter
        if (this.volumeMeter) {
            this.volumeMeter();
        }

        this.updateAudioStatus('recording');
        console.log('Recording started');
    }

    async stopRecording() {
        this.isRecording = false;
        this.animateVisualizer(false);
        this.updateAudioStatus('stopped');
        console.log('Recording stopped');
    }

    pauseRecording() {
        // Temporarily stop sending audio
        this.updateAudioStatus('paused');
    }

    resumeRecording() {
        // Resume sending audio
        this.updateAudioStatus('recording');
    }

    updateAudioStatus(status) {
        const statusText = document.getElementById('audio-status-text');
        if (statusText) {
            switch(status) {
                case 'recording':
                    statusText.textContent = '🔴 Жазылуда...';
                    statusText.style.color = '#4CAF50';
                    break;
                case 'sending':
                    statusText.textContent = '📤 Жіберілуде...';
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
                default:
                    statusText.textContent = 'Күту режимі';
                    statusText.style.color = '#757575';
            }
        }
    }

    async startConversation() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'start_recording'
            }));
        }
    }

    async stopConversation() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'stop_recording'
            }));
        }
    }

    closeWebSocket() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
            this.isConnected = false;
        }
    }

    cleanup() {
        // Stop all audio streams
        if (this.microphone) {
            this.microphone.getTracks().forEach(track => track.stop());
            this.microphone = null;
        }

        // Close audio context
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.mediaRecorder = null;
        this.isRecording = false;
        this.isPlayingAudio = false;
    }

    updateTranscription(text) {
        const transcriptElement = document.getElementById('user-transcript');
        if (transcriptElement) {
            transcriptElement.textContent = text || '...';
        }
    }

    showSpeechIndicator(speaking) {
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) {
            if (speaking) {
                visualizer.classList.add('user-speaking');
            } else {
                visualizer.classList.remove('user-speaking');
            }
        }
    }

    animateVisualizer(active) {
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) {
            if (active) {
                visualizer.classList.add('active');
            } else {
                visualizer.classList.remove('active');
            }
        }
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
}

// Export for use in templates
window.VoiceLessonManager = VoiceLessonManager;