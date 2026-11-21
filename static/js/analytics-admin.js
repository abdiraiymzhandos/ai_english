document.addEventListener('click', async event => {
  const button = event.target.closest('button[data-copy]');
  if (!button) return;
  const result = document.getElementById('copy-result');
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    result.textContent = 'Телефон нөмірі көшірілді.';
  } catch {
    result.textContent = 'Нөмірді белгілеп, қолмен көшіріңіз.';
  }
});
