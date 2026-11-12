(() => {
  const button = document.getElementById('open-translator');
  button.addEventListener('click', async () => {
    document.getElementById('translator-page-status').textContent = '';
    button.disabled = true;
    const finish = window.OqyLoading ? window.OqyLoading.begin({button}) : () => {};
    try { await window.translatorAssistant.showTranslator(); }
    catch (_) { document.getElementById('translator-page-status').textContent = 'Аудармашыны ашу мүмкін болмады. Қайта көріңіз.'; }
    finally { finish(); button.disabled = false; }
  });
  document.addEventListener('keydown', event => {
    const modal = window.translatorAssistant.modal;
    if (!modal) return;
    if (event.key === 'Escape') window.translatorAssistant.closeModal();
    if (event.key === 'Tab') {
      const controls = [...modal.querySelectorAll('button, a[href], input')].filter(el => !el.disabled && el.offsetParent !== null);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('pagehide', () => window.translatorAssistant.closeModal());
})();
