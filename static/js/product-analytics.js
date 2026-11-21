(() => {
  'use strict';
  const script = document.currentScript;
  if (window.oqyAnalyticsMounted || !script || !window.crypto?.getRandomValues || navigator.doNotTrack === '1' || navigator.globalPrivacyControl) return;
  window.oqyAnalyticsMounted = true;
  const query = new URLSearchParams(location.search);
  const campaign = {};
  for (const key of ['utm_source','utm_medium','utm_campaign','utm_content']) {
    const value = query.get(key);
    if (value && /^[a-z][a-z0-9_-]{0,47}$/i.test(value)) campaign[key] = value;
  }
  const platform = matchMedia('(display-mode: standalone)').matches || navigator.standalone ? 'pwa'
    : /iPhone|iPad/.test(navigator.userAgent) && /OqyAIWebView/i.test(navigator.userAgent) ? 'ios_webview'
    : /; wv\)/.test(navigator.userAgent) ? 'android_webview' : /Safari|Firefox|Chrome/.test(navigator.userAgent) ? 'browser' : 'unknown';
  function eventId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
    return [hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  }
  const csrfCookie = () => document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
  const initialCsrf = csrfCookie();
  const queue = [];
  let busy = false, epoch = 0;
  const active = () => csrfCookie() === initialCsrf;
  async function pump() {
    if (busy) return;
    busy = true;
    try {
      while (queue.length && active()) {
        const item = queue.shift();
        for (let attempt = 0; attempt < 4 && item.epoch === epoch && active(); attempt++) {
          let status;
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 8000);
          try {
            status = (await fetch(script.dataset.endpoint, {...item.options, signal:controller.signal})).status;
          } catch { status = 0; } finally { clearTimeout(timeout); }
          if (![0,502,503,504].includes(status) || attempt === 3) break;
          await new Promise(resolve => setTimeout(resolve, (350 + Math.random()*350) * 2**attempt));
        }
      }
    } finally {
      busy = false;
      if (!active()) queue.length = 0;
    }
  }
  function send(type, context) {
    if (!active() || queue.length >= 24) return;
    const payload = {id:eventId(), type, path:location.pathname, platform,
      track: location.pathname === '/advertisement/' ? (query.get('track') === 'ru' ? 'ru' : 'kk') : ''};
    if (type === 'page_view') payload.campaign = campaign;
    if (context) payload.context = context;
    const options = {method:'POST', credentials:'same-origin', keepalive:true,
      headers:{'Content-Type':'application/json','X-CSRFToken':script.dataset.csrf,
               'X-Analytics-Actor':script.dataset.actor}, body:JSON.stringify(payload)};
    queue.push({options,epoch,type});
    pump();
  }
  let viewed = false;
  function recordView() {
    if (!viewed && !document.hidden) {
      viewed = true;
      send('page_view');
    }
  }
  recordView();
  document.addEventListener('visibilitychange', recordView);
  window.addEventListener('pageshow', e => { if (e.persisted) { viewed=false; recordView(); } });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-analytics-action]');
    if (button) send(button.dataset.analyticsAction);
  });
  const playback = new WeakSet(), failures = new Set();
  function mediaFailure(audio, source) {
    const phase = playback.has(audio) ? 'playback' : 'preload';
    const sectionId = audio.closest('.lesson-section')?.id.replace(/-section$/, '');
    const section = ['vocabulary','dialogue','grammar','content'].includes(sectionId) ? sectionId : 'unknown';
    // The lesson highlighter can replace a media node while keeping the same failed section.
    const key = section + '/' + phase;
    if (failures.has(key)) return;
    failures.add(key);
    const error = [null,'aborted','network','decode','unsupported'][audio.error?.code] || (source ? 'source' : 'unknown');
    send('audio_error', {section, phase, error});
  }
  document.addEventListener('play', e => {
    if (e.target.tagName !== 'AUDIO') return;
    playback.add(e.target);
    send('audio_play');
    if (e.target.error) mediaFailure(e.target, false);
  }, true);
  document.addEventListener('error', e => {
    const audio = e.target.closest?.('audio');
    if (audio) mediaFailure(audio, e.target.tagName === 'SOURCE');
  }, true);
  if (window.oqyEarlyMediaError) document.removeEventListener('error', window.oqyEarlyMediaError, true);
  document.querySelectorAll('audio').forEach(audio => {
    if (audio.error || audio.dataset.earlyMediaError || audio.networkState === audio.NETWORK_NO_SOURCE)
      mediaFailure(audio, Boolean(audio.querySelector('source')));
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.intersectionRatio >= 0.5 && document.visibilityState === 'visible') {
        send('subscription_cta_viewed'); observer.unobserve(entry.target);
      }
    }, {threshold:0.5});
    document.querySelectorAll('[data-analytics-action="subscription_cta_clicked"]').forEach(el => observer.observe(el));
  }
  let lastSent = Date.now(), lastInteraction = 0;
  function flush(minimumInterval) {
    const now = Date.now();
    if (lastInteraction > lastSent && now - lastInteraction <= 30000 && now - lastSent >= minimumInterval) {
      send('activity');
      lastSent = now;
    }
  }
  for (const event of ['pointerdown','keydown','scroll']) {
    document.addEventListener(event, () => { lastInteraction=Date.now(); flush(30000); }, {passive:true});
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) flush(5000); });
  window.addEventListener('pagehide', () => {
    flush(5000);
    // A fast navigation can overtake a queued CTA click. Allow one final identity-bound keepalive.
    const click = queue.reverse().find(item => item.type.endsWith('_clicked'));
    if (click && active()) fetch(script.dataset.endpoint, click.options).catch(() => {});
    epoch++;
    queue.length = 0;
  });
})();
