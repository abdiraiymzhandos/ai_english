(() => {
  'use strict';
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const pending = status => status === 'queued' || status === 'running';
  function jobId() {
    // Older WebViews support getRandomValues before randomUUID.
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  document.querySelectorAll('[data-live-button]').forEach(button => {
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    const retry = panel.querySelector('[data-live-retry]');
    const root = button.closest('.explanation-container');
    const status = root.querySelector('[data-explanation-status]');
    const selector = panel.querySelector('select');
    const diagnostics = panel.querySelector('[data-diagnostics]');
    const comparison = panel.querySelector('input[type=checkbox]');
    const options = panel.querySelector('[data-live-options]');
    const initial = JSON.parse(panel.querySelector('script[type="application/json"]').textContent) || {};
    const key = 'oqy-explanation:' + panel.dataset.owner + ':' + panel.dataset.url;
    const takes = new Map();
    const publish = panel.querySelector('[data-publish]');
    const publicationState = panel.querySelector('[data-publication-state]');
    let publishedRevision = initial.published_revision || null;
    let active = '';
    let busy = false;
    let requestId;

    function preference(name, value) {
      try {
        if (value === undefined) return localStorage.getItem(key + name);
        if (value === null) localStorage.removeItem(key + name);
        else localStorage.setItem(key + name, value);
      } catch (_) { /* Playback also works when WebView storage is disabled. */ }
    }

    function addReview(take) {
      if (!take || takes.has(take.audio_url)) return;
      takes.set(take.audio_url, take);
      selector.add(new Option((take.revision ? 'Live · тексерілген' : 'Live · тексерілмеген') + (take.created_at ? ' · ' +
        new Date(take.created_at).toLocaleString('kk-KZ') : ''), take.audio_url));
    }

    function updateSelector() {
      for (const option of selector.options) {
        option.hidden = !!option.value && !takes.has(option.value);
        option.disabled = option.hidden || !option.value;
      }
      selector.value = active;
      selector.parentElement.hidden = takes.size < 2 && !(takes.size && !active);
    }

    function updatePublication() {
      const take = takes.get(active);
      if (!take) return;
      const current = active === 'realtime' ? !publishedRevision : !!take.revision && take.revision === publishedRevision;
      const verified = !!take.audio_url && (active === 'realtime' || !!take.revision);
      publish.hidden = !verified || current;
      publicationState.hidden = false;
      publicationState.textContent = current ? 'Оқушыларға жарияланған' : 'Жеке алдын ала тыңдау';
    }

    function select(kind, remember = true, alreadyShown = false) {
      const take = takes.get(kind);
      if (!take) return;
      if (!alreadyShown) showExplanation(root, take);
      active = kind;
      if (remember) {
        preference(':preview', kind);
        preference(':base', publishedRevision || takes.get('realtime')?.audio_url || '');
      }
      const isPrivate = kind !== 'realtime';
      diagnostics.open = false;
      diagnostics.hidden = !isPrivate;
      panel.querySelector('[data-live-warning]').hidden = !isPrivate || !!take.revision;
      if (isPrivate) {
        const fields = {...take, voice: [take.model, take.voice].join(' · '),
          mode: {comparison: 'Сақталған мәтін', retry: 'Соңғы Live мәтіні', fresh: 'Жаңа мәтін'}[take.mode],
          transcript: take.transcript || 'Транскрипт жоқ'};
        diagnostics.querySelectorAll('[data-field]').forEach(el => {
          const name = el.dataset.field;
          const unit = {coverage_percent: '%', audio_seconds: ' с', usage_seconds: ' с'}[name] || '';
          el.textContent = fields[name] == null ? '—' : fields[name] + unit;
        });
        const labels = {input_frames: 'Кіріс кадрлары', output_chunks: 'Шығыс бөліктері', pcm_peak: 'PCM шыңы',
          pcm_rms: 'PCM RMS', first_signal_seconds: 'Алғашқы дыбыс (с)', non_silent_seconds: 'Дыбысты бөлік (с)',
          instruction_state: 'Бастау нұсқауы'};
        const values = diagnostics.querySelector('[data-measurement-values]');
        values.textContent = Object.entries(take.measurements || {}).map(([key, value]) =>
          labels[key] + ' · ' + value).join('\n');
        diagnostics.querySelector('[data-measurements]').hidden = values.hidden = !values.textContent;
      }
      updatePublication();
      updateSelector();
    }

    function render(data) {
      panel.dataset.status = data.status || 'idle';
      retry.hidden = !data.can_retry;
      options.hidden = retry.hidden && comparison.parentElement.hidden && !data.review && !data.audio_url;
      if (data.audio_url) takes.set('live', data);
      if ('published_revision' in data) publishedRevision = data.published_revision;
      addReview(data.review);
      updatePublication();
      updateSelector();
      status.textContent = ({
        silent: 'Live сеансында дыбыс шықпады.',
        queued: 'Кезекте тұр…', running: 'Live аудио дайындалып жатыр…',
        review: 'Live аудио тыңдап тексеруге дайын.', failed: 'Live аудио дайындалмады.',
      })[data.status] || '';
    }

    const realtime = initial.realtime;
    if (realtime && (realtime.text || realtime.audio_url)) takes.set('realtime', realtime);
    render(initial);
    const saved = preference(':base') === (publishedRevision || realtime?.audio_url || '') && preference(':preview');
    function selectPublished() {
      const kind = publishedRevision
        ? Array.from(takes.keys()).find(k => takes.get(k).revision === publishedRevision)
        : 'realtime';
      if (takes.has(kind)) select(kind, false);
      else if (!publishedRevision && takes.has('live')) select('live', false);
    }
    if (takes.has(saved)) select(saved, false);
    else selectPublished();
    selector.addEventListener('change', () => select(selector.value));
    root.addEventListener('realtime-ready', event => {
      publishedRevision = null;
      preference(':preview', null);
      takes.set('realtime', event.detail);
      comparison.parentElement.hidden = !event.detail.text;
      options.hidden = false;
      select('realtime', false, true);
    });

    publish.addEventListener('click', async () => {
      const take = takes.get(active);
      publish.disabled = true;
      try {
        const data = await OqyLoading.json(panel.dataset.publishUrl, {
          method: 'POST', headers: {'X-CSRFToken': panel.querySelector('[name=csrfmiddlewaretoken]').value},
          body: new URLSearchParams({revision: take.revision || '', audio_url: take.audio_url}),
        });
        publishedRevision = data.published_revision;
        preference(':preview', null);
        updatePublication();
        status.textContent = 'Жазба оқушыларға жарияланды.';
      } catch (error) {
        status.textContent = error.message;
      } finally {
        publish.disabled = false;
      }
    });

    let historyLoaded = false;
    async function loadReviews() {
      if (historyLoaded) return;
      historyLoaded = true;
      try {
        const data = await OqyLoading.json(panel.dataset.url + '?reviews=1', {}, {progress: false});
        data.reviews.forEach(addReview);
        if (saved && preference(':preview') === saved && takes.has(saved)) select(saved, false);
        else if (!active) selectPublished();
        updateSelector();
      } catch (error) {
        historyLoaded = false;
        status.textContent = error.message;
      }
    }
    options.addEventListener('toggle', () => { if (options.open) loadReviews(); });
    if ((saved && !takes.has(saved)) || (publishedRevision && !active)) loadReviews();

    async function follow(mode) {
      if (busy) return;
      busy = true;
      button.disabled = retry.disabled = true;
      const finish = OqyLoading.begin({button, progress: false});
      try {
        let data;
        const deadline = Date.now() + 23 * 60 * 1000;
        if (mode) {
          requestId = requestId || jobId();
          data = await OqyLoading.json(panel.dataset.url, {
            method: 'POST', headers: {'X-CSRFToken': panel.querySelector('[name=csrfmiddlewaretoken]').value},
            body: new URLSearchParams({job: requestId, mode}),
          });
          render(data);
        }
        while (pending(panel.dataset.status)) {
          if (Date.now() >= deadline) throw new Error('Күйін тексеру үшін бетті жаңартыңыз.');
          await pause(2500);
          data = await OqyLoading.json(panel.dataset.url, {}, {progress: false, timeout: 12000});
          render(data);
        }
        requestId = null;
        if (data && data.status === 'ready') {
          preference(':preview', null);
          select('live', false);
        }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        finish();
        button.disabled = retry.disabled = false;
        busy = false;
      }
    }

    button.addEventListener('click', () => follow(comparison.checked ? 'comparison' : 'fresh'));
    retry.addEventListener('click', () => follow('retry'));
    if (pending(panel.dataset.status)) {
      follow(false);
    }
  });
})();
