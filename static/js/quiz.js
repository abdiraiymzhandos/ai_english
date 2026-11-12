(() => {
  'use strict';
  function mountQuiz() {
    const root = document.getElementById('quiz-container');
    if (!root || root.dataset.mounted) return;
    root.dataset.mounted = 'true';
    const byId = id => document.getElementById(id);
    const start = byId('start-quiz-btn'), content = byId('quiz-content');
    const summary = byId('quiz-summary'), retake = byId('retake-quiz-btn');
    const errorBox = byId('quiz-error'), retry = byId('quiz-retry-btn');
    const answers = byId('answer-buttons'), questionText = byId('question-text');
    let state, questions = [], current, timer, transition, busy = false, epoch = 0;
    let retryAction = null;
    const csrf = () => {
      const value = document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
      return value ? decodeURIComponent(value.slice(10)) : '';
    };
    const postOptions = body => ({method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'X-CSRFToken': csrf()}, body: new URLSearchParams(body)});
    function stop() { clearInterval(timer); clearTimeout(transition); }
    function hideError() { errorBox.hidden = true; retry.hidden = true; }
    function showError(error, action) {
      stop();
      errorBox.textContent = error.message || 'Қате орын алды. Қайта көріңіз.';
      errorBox.hidden = false;
      retryAction = action;
      retry.hidden = false;
      retry.focus({preventScroll: true});
    }
    function apply(data) {
      if (Number(data.lesson_id) !== Number(root.dataset.lessonId)) throw new Error('Сабақ деректері сәйкес келмейді. Бетті жаңартыңыз.');
      state = data;
      if (data.questions) questions = data.questions;
      byId('score').textContent = `🏆 Ұпай: ${Number(data.score || 0)}`;
      byId('attempts').textContent = `❌ Қателер: ${Number(data.attempts || 0)}/3`;
      const previous = byId('quiz-previous-score');
      if (data.previous_score !== null && data.previous_score !== undefined) {
        previous.hidden = false;
        previous.textContent = `Алдыңғы нәтиже: ${data.previous_score}${data.previous_total ? '/' + data.previous_total : ''}`;
      }
    }
    function showComplete() {
      stop();
      content.hidden = true;
      summary.hidden = false;
      start.hidden = true;
      byId('quiz-result').textContent = `✅ Тест аяқталды! Ұпай: ${state.score}`;
      const next = byId('next-lesson-link');
      next.hidden = !state.next_lesson;
      if (state.next_lesson) next.href = root.dataset.lessonUrl.replace('/0/', `/${state.next_lesson}/`);
      retake.focus({preventScroll: true});
    }
    function renderQuestion() {
      stop(); hideError();
      busy = false;
      summary.hidden = true; start.hidden = true; content.hidden = false;
      if (state.passed) { showComplete(); return; }
      current = questions.find(q => q.id === state.next_question_id);
      if (!current) {
        showError(new Error('Тест күйін қайта жүктеңіз.'), () => load());
        return;
      }
      questionText.textContent = current.english_word;
      byId('progress').style.width = `${(state.answered_count / state.total_questions) * 100}%`;
      answers.replaceChildren();
      current.choices.forEach(choice => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-outline-primary btn-lg';
        button.textContent = choice;
        button.addEventListener('click', () => submit({question_id: current.id, answer: choice,
          timed_out: 'false', attempt_token: state.attempt_token}, button));
        answers.appendChild(button);
      });
      questionText.focus({preventScroll: true});
      let timeLeft = 5;
      byId('timer').textContent = `⏳ ${timeLeft} секунд`;
      timer = setInterval(() => {
        timeLeft -= 1;
        byId('timer').textContent = `⏳ ${timeLeft} секунд`;
        if (timeLeft <= 0) {
          stop();
          submit({question_id: current.id, answer: '', timed_out: 'true', attempt_token: state.attempt_token});
        }
      }, 1000);
    }
    async function load(restart = false, initialRetake = false) {
      if (busy) return;
      busy = true; stop(); hideError();
      const requestEpoch = ++epoch;
      try {
        let data = await OqyLoading.json(restart ? root.dataset.restartUrl : root.dataset.startUrl,
          restart ? postOptions({attempt_token: state.attempt_token}) : {credentials: 'same-origin', cache: 'no-store'},
          {button: restart ? retake : start});
        if (requestEpoch !== epoch) return;
        apply(data);
        if (initialRetake && data.lesson_completed) {
          data = await OqyLoading.json(root.dataset.restartUrl, postOptions({attempt_token: data.attempt_token}), {button: start});
          if (requestEpoch !== epoch) return;
          apply(data);
        }
        renderQuestion();
      } catch (error) {
        if (requestEpoch === epoch) showError(error, () => load());
      } finally { if (requestEpoch === epoch) busy = false; }
    }
    async function submit(payload, button = null) {
      if (busy) return;
      busy = true; stop(); hideError();
      const requestEpoch = epoch;
      answers.querySelectorAll('button').forEach(item => { item.disabled = true; });
      try {
        const data = await OqyLoading.json(root.dataset.submitUrl, postOptions(payload), {button, progress: false, timeout: 15000});
        if (requestEpoch !== epoch) return;
        apply(data);
        if (data.restart_required) {
          content.hidden = true; start.hidden = false;
          start.textContent = '🔄 Қайта бастау';
          start.dataset.retake = 'false';
          showError(new Error('❌ 3 рет қателестіңіз. Тест басынан басталады.'), () => load());
          return;
        }
        if (button) button.classList.add(data.correct ? 'btn-success' : 'btn-danger');
        // Brief answer feedback; no network round trip or page reload to advance.
        const delay = matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 180;
        transition = setTimeout(() => data.passed ? showComplete() : renderQuestion(), delay);
      } catch (error) {
        if (requestEpoch !== epoch) return;
        // Retry the exact answer/token after ambiguous delivery. The server is idempotent.
        // A stale token must resume the server run; never replay into a new attempt.
        showError(error, error.status === 409 ? () => load() : () => submit(payload, button));
      } finally { if (requestEpoch === epoch) busy = false; }
    }
    start.addEventListener('click', async () => {
      if (busy) return;
      if (start.dataset.retake === 'true') { load(false, true); return; }
      const message = 'Әр сұраққа 5 секунд беріледі. 3 қате болса, тест басынан басталады.';
      if (window.Swal) {
        const result = await Swal.fire({title: 'Тест ережелері', text: message, icon: 'info',
          showCancelButton: true, confirmButtonText: 'Иә, бастаймыз', cancelButtonText: 'Жоқ'});
        if (result.isConfirmed) load();
      } else if (window.confirm(message)) load();
    });
    retake.addEventListener('click', () => load(true));
    retry.addEventListener('click', () => { if (!busy && retryAction) retryAction(); });
    window.addEventListener('pagehide', () => { stop(); epoch += 1; busy = false; });
    window.addEventListener('pageshow', event => { if (event.persisted && state) load(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountQuiz);
  else mountQuiz();
})();
