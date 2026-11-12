/* Shared navigation and request feedback. No history interception or global fetch patch. */
(() => {
  'use strict';
  if (window.OqyLoading) return;
  const pending = new Set();
  const buttonStates = new WeakMap();
  let bar, status, navigation;
  function mount() {
    if (bar) return;
    bar = document.createElement('div');
    bar.id = 'oqy-loading-bar';
    bar.setAttribute('aria-hidden', 'true');
    status = document.createElement('div');
    status.id = 'oqy-loading-status';
    status.className = 'oqy-visually-hidden';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    document.body.append(bar, status);
  }
  function announce(message) { mount(); status.textContent = message; }
  function update() {
    mount();
    bar.classList.toggle('is-loading', [...pending].some(item => item.visible && item.progress));
  }
  function begin({button = null, progress = true, delay = 150, disable = true} = {}) {
    mount();
    const item = {visible: false, progress};
    pending.add(item);
    let buttonState;
    if (button) {
      buttonState = buttonStates.get(button);
      if (!buttonState) {
        buttonState = {disabled: button.disabled, busy: button.getAttribute('aria-busy'), count: 0, disabling: 0, visible: 0};
        buttonStates.set(button, buttonState);
      }
      buttonState.count += 1;
      if (disable) buttonState.disabling += 1;
      button.setAttribute('aria-busy', 'true');
      button.disabled = buttonState.disabled || buttonState.disabling > 0;
    }
    const show = () => {
      item.visible = true;
      if (button) { buttonState.visible += 1; button.classList.add('oqy-busy'); }
      announce('Жүктелуде…');
      update();
    };
    const timer = delay ? setTimeout(show, delay) : null;
    if (!delay) show();
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      pending.delete(item);
      if (button) {
        buttonState.count -= 1;
        if (disable) buttonState.disabling -= 1;
        if (item.visible) buttonState.visible -= 1;
        button.disabled = buttonState.disabled || buttonState.disabling > 0;
        button.classList.toggle('oqy-busy', buttonState.visible > 0);
        if (!buttonState.count) {
          if (buttonState.busy === null) button.removeAttribute('aria-busy');
          else button.setAttribute('aria-busy', buttonState.busy);
          buttonStates.delete(button);
        }
      }
      if (!pending.size) status.textContent = '';
      update();
    };
    item.finish = finish;
    return finish;
  }
  async function request(url, options = {}, ui = {}, asJson = false) {
    const finish = begin(ui);
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    const externalSignal = options.signal;
    const abort = () => controller && controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) abort();
      else externalSignal.addEventListener('abort', abort, {once: true});
    }
    let deadline;
    try {
      // The deadline covers body parsing too. AbortController is optional in older WebViews.
      return await Promise.race([
        (async () => {
          const response = await fetch(url, {...options, signal: controller ? controller.signal : externalSignal});
          if (!asJson) return response;
          let data;
          try { data = await response.json(); }
          catch (_) { throw new Error('Сервер жауабын оқу мүмкін болмады. Қайта көріңіз.'); }
          if (!response.ok || data.error) {
            const error = new Error(data.error || 'Сұрау орындалмады. Қайта көріңіз.');
            error.status = response.status;
            error.code = data.code;
            throw error;
          }
          return data;
        })(),
        new Promise((_, reject) => {
          deadline = setTimeout(() => {
            const error = new Error('Жауап күту уақыты аяқталды. Интернетті тексеріп, қайта көріңіз.');
            error.name = 'TimeoutError';
            reject(error);
            abort();
          }, ui.timeout || 30000);
        }),
      ]);
    } finally {
      clearTimeout(deadline);
      if (externalSignal) externalSignal.removeEventListener('abort', abort);
      finish();
    }
  }
  function reset() {
    if (navigation) navigation();
    [...pending].forEach(item => item.finish());
  }
  function navigate(button = null, onFinish = () => {}) {
    if (navigation) navigation();
    const finish = begin({button, delay: 0, disable: false});
    const release = () => {
      clearTimeout(timer);
      finish();
      if (navigation === release) navigation = null;
      onFinish();
    };
    const timer = setTimeout(() => {
      release();
      announce('Жүктеу ұзаққа созылды. Интернет байланысын тексеріңіз.');
    }, 30000);
    navigation = release;
  }
  function internalDestination(raw) {
    try {
      const url = new URL(raw, location.href);
      return /^https?:$/.test(url.protocol) && url.origin === location.origin ? url : null;
    } catch (_) { return null; }
  }
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest && event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || link.hasAttribute('data-no-loading') ||
        (link.target && link.target !== '_self') || link.relList.contains('external')) return;
    const url = internalDestination(link.href);
    if (!url || /\/(media|static)\/|\.(pdf|zip|mp3|mp4|csv|xlsx?)$/i.test(url.pathname)) return;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    navigate(link);
  });
  const forms = new WeakMap();
  document.addEventListener('submit', event => {
    const form = event.target;
    const target = (event.submitter && event.submitter.getAttribute('formtarget')) || form.target;
    const action = (event.submitter && event.submitter.getAttribute('formaction')) || form.action;
    if (event.defaultPrevented || form.method === 'dialog' || form.hasAttribute('data-no-loading') ||
        (target && target !== '_self') || !internalDestination(action)) return;
    if (forms.has(form)) { event.preventDefault(); return; }
    // Do not disable the submitter: its name/value must reach the server.
    navigate(event.submitter || form.querySelector('[type="submit"]'), () => forms.delete(form));
    forms.set(form, true);
  });
  window.addEventListener('pageshow', reset);
  window.addEventListener('pagehide', reset);
  window.OqyLoading = {
    begin, reset, navigate, announce,
    fetch: (url, options, ui) => request(url, options, ui, false),
    json: (url, options, ui) => request(url, options, ui, true),
  };
})();
