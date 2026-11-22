(() => {
  const clock = document.getElementById('countdown');
  if (!clock) return;
  const remaining = Number(clock.dataset.end) - Number(clock.dataset.now);
  const start = performance.now();
  if (!Number.isFinite(remaining)) return;
  function render() {
    const minutes = Math.ceil((remaining - (performance.now() - start)) / 60000);
    if (minutes <= 0) {
      clearInterval(timer);
      location.reload();
      return;
    }
    clock.textContent = Math.floor(minutes / 1440) + ' күн ' + Math.floor(minutes % 1440 / 60)
      + ' сағат ' + minutes % 60 + ' минут';
  }
  const timer = setInterval(render, 1000);
  render();
  document.addEventListener('visibilitychange', () => { if (!document.hidden) location.reload(); });
  window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
})();
