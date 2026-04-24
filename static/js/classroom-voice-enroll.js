class ClassroomVoiceEnrollment {
    constructor(config = {}) {
        this.recordSeconds = typeof config.recordSeconds === 'number' ? config.recordSeconds : 10;
        this.minRms = typeof config.minRms === 'number' ? config.minRms : 0.001;
        this.minSpectrum = typeof config.minSpectrum === 'number' ? config.minSpectrum : 2;
        this.embeddingSize = typeof config.embeddingSize === 'number' ? config.embeddingSize : 13;
        this.maxSamples = typeof config.maxSamples === 'number' ? config.maxSamples : 5;
        this.minFrames = typeof config.minFrames === 'number' ? config.minFrames : 20;
        this.minSpeechFrames = typeof config.minSpeechFrames === 'number'
            ? config.minSpeechFrames
            : Math.max(8, Math.floor(this.minFrames * 0.4));
        this.bufferSize = typeof config.bufferSize === 'number' ? config.bufferSize : 512;
        this.statusEl = config.statusEl || null;

        this.currentStudent = null;
        this.stream = null;
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.recordedBlob = null;
        this.recordedUrl = '';
        this.recordTimer = null;
        this.recordStartAt = null;
        this.isRecording = false;
        this.discardNextRecording = false;

        this.audioContext = null;
        this.voiceSource = null;
        this.silentGain = null;
        this.meydaAnalyzer = null;
        this.liveFrames = [];
        this.liveSpeechFrames = [];
        this.pendingEmbedding = null;
        this.analyser = null;
        this.spectrumFrames = [];
        this.spectrumSpeechFrames = [];
        this.spectrumInterval = null;
        this.spectrumSampleIntervalMs = 120;
        this.spectrumBuffer = null;

        this.modalEl = document.getElementById('voice-enroll-modal');
        this.modalTitleEl = document.getElementById('voice-enroll-modal-title');
        this.modalSubtitleEl = document.getElementById('voice-enroll-modal-subtitle');
        this.modalStatusEl = document.getElementById('voice-enroll-modal-status');
        this.timerEl = document.getElementById('voice-enroll-timer');
        this.progressEl = document.getElementById('voice-enroll-progress');
        this.previewEl = document.getElementById('voice-enroll-preview');
        this.startBtn = document.getElementById('voice-enroll-start');
        this.stopBtn = document.getElementById('voice-enroll-stop');
        this.rerecordBtn = document.getElementById('voice-enroll-rerecord');
        this.sendBtn = document.getElementById('voice-enroll-send');
        this.closeBtn = document.getElementById('voice-enroll-close');

        this.bindButtons();
        this.bindModalControls();
    }

    bindButtons() {
        const buttons = document.querySelectorAll('[data-voice-enroll]');
        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const studentId = btn.getAttribute('data-student-id');
                const studentName = btn.getAttribute('data-student-name');
                if (!studentId || !studentName) return;
                this.openModal({
                    id: Number(studentId),
                    name: studentName
                });
            });
        });
    }

    bindModalControls() {
        if (this.startBtn) {
            this.startBtn.addEventListener('click', () => this.startRecording());
        }
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stopRecording());
        }
        if (this.rerecordBtn) {
            this.rerecordBtn.addEventListener('click', () => this.resetRecordingUI());
        }
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.processAndSave());
        }
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.closeModal());
        }
    }

    openModal(student) {
        this.currentStudent = student;
        if (!this.modalEl) {
            this.updateStatus('Дауыс жазу модалы табылмады.');
            return;
        }
        this.resetRecordingUI();
        if (this.modalTitleEl) {
            this.modalTitleEl.textContent = 'Дауыс үлгісі';
        }
        this.refreshModalSubtitle();
        const count = this.getCurrentVoiceCount();
        if (count >= this.maxSamples) {
            this.setModalStatus('Үлгі саны толды. Жаңа жазба ең ескі үлгінің орнына сақталады.');
        } else if (count > 0) {
            this.setModalStatus('Бұл оқушыда дауыс үлгісі бар. Қаласаңыз, сапалырақ жаңасын жазыңыз.');
        } else {
            this.setModalStatus('Жазуды бастау үшін батырманы басыңыз.');
        }
        this.modalEl.style.display = 'flex';
    }

    closeModal() {
        this.stopRecording(true);
        this.cleanupStream();
        this.resetRecordingUI();
        if (this.modalEl) {
            this.modalEl.style.display = 'none';
        }
    }

    updateStatus(message) {
        if (this.statusEl) {
            this.statusEl.textContent = message || '';
        }
    }

    setModalStatus(message) {
        if (this.modalStatusEl) {
            this.modalStatusEl.textContent = message || '';
        }
        this.updateStatus(message);
    }

    resetRecordingUI() {
        this.stopRecording(true);
        this.cleanupStream();
        this.stopMeyda();
        this.recordedChunks = [];
        this.recordedBlob = null;
        this.pendingEmbedding = null;
        if (this.recordedUrl) {
            URL.revokeObjectURL(this.recordedUrl);
            this.recordedUrl = '';
        }
        if (this.previewEl) {
            this.previewEl.src = '';
            this.previewEl.style.display = 'none';
        }
        this.spectrumFrames = [];
        this.spectrumSpeechFrames = [];
        this.setButtons({
            start: true,
            stop: false,
            rerecord: false,
            send: false
        });
        this.updateTimer(0);
        this.updateProgress(0);
        if (this.modalEl && this.modalEl.style.display === 'flex') {
            this.setModalStatus('Жазуды бастау үшін батырманы басыңыз.');
        }
    }

    setButtons(state) {
        if (this.startBtn) this.startBtn.disabled = !state.start;
        if (this.stopBtn) this.stopBtn.disabled = !state.stop;
        if (this.rerecordBtn) this.rerecordBtn.disabled = !state.rerecord;
        if (this.sendBtn) this.sendBtn.disabled = !state.send;
    }

    updateTimer(elapsedMs) {
        if (!this.timerEl) return;
        const totalSeconds = Math.floor(elapsedMs / 1000);
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const seconds = String(totalSeconds % 60).padStart(2, '0');
        const target = String(this.recordSeconds).padStart(2, '0');
        this.timerEl.textContent = `${minutes}:${seconds} / 00:${target}`;
    }

    updateProgress(ratio) {
        if (!this.progressEl) return;
        const clamped = Math.max(0, Math.min(1, ratio));
        this.progressEl.style.width = `${Math.round(clamped * 100)}%`;
    }

    async startRecording() {
        if (this.isRecording) return;
        if (!window.MediaRecorder) {
            this.setModalStatus('Браузеріңіз дыбыс жазуды қолдамайды.');
            return;
        }
        const currentCount = this.getCurrentVoiceCount();
        if (Number.isFinite(currentCount) && currentCount >= this.maxSamples) {
            this.setModalStatus('Жаңа жазба ең ескі үлгінің орнына сақталады. Енді анық сөйлеп жазыңыз.');
        }

        this.recordedChunks = [];
        this.recordedBlob = null;
        if (this.recordedUrl) {
            URL.revokeObjectURL(this.recordedUrl);
            this.recordedUrl = '';
        }
        if (this.previewEl) {
            this.previewEl.src = '';
            this.previewEl.style.display = 'none';
        }
        this.updateTimer(0);
        this.updateProgress(0);

        this.liveFrames = [];
        this.liveSpeechFrames = [];
        this.spectrumFrames = [];
        this.spectrumSpeechFrames = [];

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        } catch (error) {
            this.setModalStatus('Микрофонға қол жеткізу мүмкін емес.');
            return;
        }

        await this.startMeyda(this.stream);

        const options = {};
        if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported('audio/webm')) {
            options.mimeType = 'audio/webm';
        }

        this.mediaRecorder = new MediaRecorder(this.stream, options);
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                this.recordedChunks.push(event.data);
            }
        };
        this.mediaRecorder.onstop = () => this.handleRecordingStop();

        this.mediaRecorder.start();
        this.isRecording = true;
        this.recordStartAt = Date.now();
        this.setButtons({
            start: false,
            stop: true,
            rerecord: false,
            send: false
        });
        this.setModalStatus('Сөйлеп тұрыңыз...');
        this.recordTimer = setInterval(() => {
            const elapsed = Date.now() - this.recordStartAt;
            const ratio = elapsed / (this.recordSeconds * 1000);
            this.updateTimer(elapsed);
            this.updateProgress(ratio);
            if (elapsed >= this.recordSeconds * 1000) {
                this.stopRecording();
            }
        }, 200);
    }

    stopRecording(discard = false) {
        if (!this.isRecording) return;
        this.isRecording = false;
        this.discardNextRecording = discard;
        if (this.recordTimer) {
            clearInterval(this.recordTimer);
            this.recordTimer = null;
        }
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        this.stopMeyda();
    }

    handleRecordingStop() {
        if (this.discardNextRecording) {
            this.discardNextRecording = false;
            this.recordedChunks = [];
            return;
        }
        if (!this.recordedChunks.length) {
            this.setModalStatus('Дауыс жазылмады. Қайта көріңіз.');
            this.setButtons({
                start: true,
                stop: false,
                rerecord: false,
                send: false
            });
            this.cleanupStream();
            return;
        }

        const mimeType = this.mediaRecorder && this.mediaRecorder.mimeType
            ? this.mediaRecorder.mimeType
            : 'audio/webm';
        this.recordedBlob = new Blob(this.recordedChunks, { type: mimeType });
        if (this.previewEl) {
            if (this.recordedUrl) {
                URL.revokeObjectURL(this.recordedUrl);
            }
            this.recordedUrl = URL.createObjectURL(this.recordedBlob);
            this.previewEl.src = this.recordedUrl;
            this.previewEl.style.display = 'block';
        }

        this.pendingEmbedding = this.computeEmbeddingFromLiveFrames();
        const canSave = true;
        this.setButtons({
            start: true,
            stop: false,
            rerecord: true,
            send: canSave
        });
        this.setModalStatus(
            this.pendingEmbedding
                ? 'Жазба дайын. Сақтау батырмасын басыңыз.'
                : 'Жазба дайын. Сақтау кезінде өңделеді.'
        );
        this.cleanupStream();
    }

    getCurrentVoiceCount() {
        if (!this.currentStudent) return 0;
        const countEl = document.querySelector(`[data-voice-count="${this.currentStudent.id}"]`);
        const currentCount = countEl ? Number.parseInt(countEl.textContent || '0', 10) : 0;
        return Number.isFinite(currentCount) ? currentCount : 0;
    }

    updateVoiceBadge(studentId, count) {
        const badgeEl = document.querySelector(`[data-voice-badge="${studentId}"]`);
        if (!badgeEl) return;
        if (count > 0) {
            badgeEl.textContent = 'Дауыс дайын';
            badgeEl.style.color = '#10b981';
        } else {
            badgeEl.textContent = 'Дауыс керек';
            badgeEl.style.color = '#b45309';
        }
    }

    refreshModalSubtitle() {
        if (!this.modalSubtitleEl || !this.currentStudent) return;
        const count = this.getCurrentVoiceCount();
        this.modalSubtitleEl.textContent = `${this.currentStudent.name} · ${this.recordSeconds} сек · Үлгі: ${count}/${this.maxSamples}`;
    }

    async startMeyda(stream) {
        const audioCtxClass = window.AudioContext || window.webkitAudioContext;
        if (!audioCtxClass) {
            this.setModalStatus('AudioContext қолжетімді емес.');
            return;
        }
        this.audioContext = new audioCtxClass();
        if (this.audioContext.state === 'suspended') {
            try {
                await this.audioContext.resume();
            } catch (error) {
                console.warn('AudioContext resume failed:', error);
            }
        }
        this.voiceSource = this.audioContext.createMediaStreamSource(stream);
        this.silentGain = this.audioContext.createGain();
        this.silentGain.gain.value = 0;
        this.voiceSource.connect(this.silentGain);
        this.silentGain.connect(this.audioContext.destination);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 1024;
        this.analyser.smoothingTimeConstant = 0.85;
        this.voiceSource.connect(this.analyser);
        this.startSpectrumSampling();
        if (!window.Meyda) {
            console.warn('Meyda not available; using spectrum fallback.');
            return;
        }
        this.meydaAnalyzer = window.Meyda.createMeydaAnalyzer({
            audioContext: this.audioContext,
            source: this.voiceSource,
            bufferSize: this.bufferSize,
            featureExtractors: ['mfcc', 'rms'],
            callback: (features) => this.handleLiveFeatures(features)
        });
        this.meydaAnalyzer.start();
    }

    stopMeyda() {
        if (this.meydaAnalyzer && this.meydaAnalyzer.stop) {
            this.meydaAnalyzer.stop();
        }
        this.meydaAnalyzer = null;
        if (this.spectrumInterval) {
            clearInterval(this.spectrumInterval);
            this.spectrumInterval = null;
        }
        if (this.analyser) {
            try {
                this.analyser.disconnect();
            } catch (error) {
                console.warn('Analyser disconnect error:', error);
            }
        }
        this.analyser = null;
        this.spectrumBuffer = null;
        if (this.voiceSource) {
            try {
                this.voiceSource.disconnect();
            } catch (error) {
                console.warn('Voice source disconnect error:', error);
            }
        }
        this.voiceSource = null;
        if (this.silentGain) {
            try {
                this.silentGain.disconnect();
            } catch (error) {
                console.warn('Gain node disconnect error:', error);
            }
        }
        this.silentGain = null;
        if (this.audioContext) {
            this.audioContext.close().catch(() => {});
        }
        this.audioContext = null;
    }

    handleLiveFeatures(features) {
        if (!features || !features.mfcc) return;
        const mfcc = features.mfcc.slice(0, this.embeddingSize);
        this.liveFrames.push(mfcc);
        const rms = typeof features.rms === 'number' ? features.rms : 0;
        if (rms >= this.minRms) {
            this.liveSpeechFrames.push(mfcc);
        }
    }

    startSpectrumSampling() {
        if (!this.analyser) return;
        if (this.spectrumInterval) {
            clearInterval(this.spectrumInterval);
        }
        this.spectrumInterval = setInterval(() => this.captureSpectrumFrame(), this.spectrumSampleIntervalMs);
    }

    captureSpectrumFrame() {
        if (!this.analyser) return;
        const binCount = this.analyser.frequencyBinCount;
        if (!binCount) return;
        if (!this.spectrumBuffer || this.spectrumBuffer.length !== binCount) {
            this.spectrumBuffer = new Uint8Array(binCount);
        }
        this.analyser.getByteFrequencyData(this.spectrumBuffer);
        const bandSize = Math.floor(binCount / this.embeddingSize);
        if (!bandSize) return;
        const frame = new Array(this.embeddingSize).fill(0);
        let total = 0;

        for (let i = 0; i < this.embeddingSize; i += 1) {
            const start = i * bandSize;
            const end = i === this.embeddingSize - 1 ? binCount : start + bandSize;
            let sum = 0;
            let count = 0;
            for (let j = start; j < end; j += 1) {
                sum += this.spectrumBuffer[j];
                count += 1;
            }
            const avg = count ? sum / count : 0;
            frame[i] = avg / 255;
            total += avg;
        }

        this.spectrumFrames.push(frame);
        const avgEnergy = total / this.embeddingSize;
        if (avgEnergy >= this.minSpectrum) {
            this.spectrumSpeechFrames.push(frame);
        }
    }

    async processAndSave() {
        if (!this.recordedBlob || !this.currentStudent) return;
        this.setButtons({
            start: false,
            stop: false,
            rerecord: false,
            send: false
        });
        this.setModalStatus('Дауыс өңделуде...');

        let embedding = this.pendingEmbedding;
        if (!embedding) {
            if (!window.Meyda) {
                this.setModalStatus('Сөйлеу анық естілмеді. Қайта жазыңыз.');
                this.setButtons({
                    start: true,
                    stop: false,
                    rerecord: true,
                    send: false
                });
                return;
            }
            const timeoutMs = 8000;
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('processing-timeout')), timeoutMs);
            });
            try {
                embedding = await Promise.race([
                    this.computeEmbeddingFromBlob(this.recordedBlob),
                    timeoutPromise
                ]);
            } catch (error) {
                console.warn('Voice processing failed:', error);
                this.setModalStatus('Дауыс өңдеу сәтсіз болды. Микрофонға жақынырақ сөйлеп қайта жазыңыз.');
                this.setButtons({
                    start: true,
                    stop: false,
                    rerecord: true,
                    send: false
                });
                return;
            }
        }

        if (!embedding) {
            this.setModalStatus('Сөйлеу анық естілмеді. Қайта жазыңыз.');
            this.setButtons({
                start: true,
                stop: false,
                rerecord: true,
                send: false
            });
            return;
        }

        const saved = await this.saveEmbedding(this.currentStudent.id, embedding);
        if (saved) {
            this.setModalStatus('Дауыс үлгісі сақталды.');
            this.refreshModalSubtitle();
            this.pendingEmbedding = null;
            this.setButtons({
                start: true,
                stop: false,
                rerecord: true,
                send: false
            });
        } else {
            this.setModalStatus('Дауыс үлгісін сақтау мүмкін болмады.');
            this.setButtons({
                start: true,
                stop: false,
                rerecord: true,
                send: true
            });
        }
    }

    computeEmbeddingFromLiveFrames() {
        if (this.liveSpeechFrames.length >= this.minFrames) {
            return this.computeEmbedding(this.liveSpeechFrames);
        }
        if (this.spectrumSpeechFrames.length >= this.minFrames) {
            return this.computeEmbedding(this.spectrumSpeechFrames);
        }
        if (this.liveSpeechFrames.length >= this.minSpeechFrames) {
            return this.computeEmbedding(this.liveSpeechFrames);
        }
        if (this.spectrumSpeechFrames.length >= this.minSpeechFrames) {
            return this.computeEmbedding(this.spectrumSpeechFrames);
        }
        if (this.liveFrames.length >= this.minFrames && this.liveSpeechFrames.length >= Math.max(4, Math.floor(this.minSpeechFrames / 2))) {
            return this.computeEmbedding(this.liveFrames);
        }
        if (this.spectrumFrames.length >= this.minFrames && this.spectrumSpeechFrames.length >= Math.max(4, Math.floor(this.minSpeechFrames / 2))) {
            return this.computeEmbedding(this.spectrumFrames);
        }
        return null;
    }

    async computeEmbeddingFromBlob(blob) {
        if (!window.Meyda) return null;
        const audioCtxClass = window.AudioContext || window.webkitAudioContext;
        if (!audioCtxClass) return null;

        let audioBuffer = null;
        const audioCtx = new audioCtxClass();
        if (audioCtx.state === 'suspended') {
            try {
                await audioCtx.resume();
            } catch (error) {
                console.warn('AudioContext resume failed:', error);
            }
        }
        try {
            const arrayBuffer = await blob.arrayBuffer();
            audioBuffer = await Promise.race([
                audioCtx.decodeAudioData(arrayBuffer),
                new Promise((_, reject) => setTimeout(() => reject(new Error('decode-timeout')), 4000))
            ]);
        } catch (error) {
            await audioCtx.close();
            return null;
        }

        const channelData = audioBuffer.getChannelData(0);
        const sampleRate = audioBuffer.sampleRate;
        const mfccFrames = this.extractMfccFrames(channelData, sampleRate, true);
        let frames = mfccFrames;
        if (frames.length < this.minFrames) {
            frames = this.extractMfccFrames(channelData, sampleRate, false);
        }

        await audioCtx.close();

        if (frames.length < this.minFrames && frames.length < this.minSpeechFrames) {
            return null;
        }
        return this.computeEmbedding(frames);
    }

    extractMfccFrames(channelData, sampleRate, filterByRms) {
        const frames = [];
        const bufferSize = this.bufferSize;
        const total = channelData.length;

        for (let i = 0; i + bufferSize <= total; i += bufferSize) {
            const slice = channelData.subarray(i, i + bufferSize);
            if (filterByRms) {
                const rms = this.computeRms(slice);
                if (rms < this.minRms) {
                    continue;
                }
            }
            try {
                const mfcc = window.Meyda.extract('mfcc', slice, {
                    sampleRate,
                    bufferSize,
                    numberOfMFCCCoefficients: this.embeddingSize
                });
                if (mfcc && mfcc.length) {
                    frames.push(mfcc.slice(0, this.embeddingSize));
                }
            } catch (error) {
                console.warn('MFCC extract error:', error);
            }
        }

        return frames;
    }

    computeRms(frame) {
        let sum = 0;
        for (let i = 0; i < frame.length; i += 1) {
            const value = frame[i];
            sum += value * value;
        }
        return Math.sqrt(sum / frame.length);
    }

    computeEmbedding(frames) {
        const size = this.embeddingSize;
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

    normalizeEmbedding(raw) {
        const data = raw instanceof Float32Array ? raw : new Float32Array(raw);
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

    async saveEmbedding(studentId, embedding) {
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
            const count = payload && typeof payload.count === 'number' ? payload.count : null;
            if (count !== null) {
                const countEl = document.querySelector(`[data-voice-count="${studentId}"]`);
                if (countEl) {
                    countEl.textContent = String(count);
                }
                this.updateVoiceBadge(studentId, count);
            }
            return true;
        } catch (error) {
            console.warn('Voice embedding save error:', error);
            return false;
        }
    }

    cleanupStream() {
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
        }
        this.stream = null;
        this.mediaRecorder = null;
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
}

window.ClassroomVoiceEnrollment = ClassroomVoiceEnrollment;
