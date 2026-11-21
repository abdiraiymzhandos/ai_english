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
    let state, questions = [], current, transition, busy = false, epoch = 0;
    const duration = 5000;
    const track = byId('timer'), fill = byId('timer-fill');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    const clockStorage = 'oqyai.quiz.clock.' + root.dataset.lessonId;
    let retryAction = null, frame = 0, armed = false, questionActive = false;
    let clockKey, deadline, wallDeadline;
    let scrollY = 0, bodyTop = '', returnFocus;
    const dialog = byId('quiz-dialog');
    const feedback = byId('quiz-feedback');
    function openQuiz() {
      if (dialog.open) return;
      returnFocus = start;
      scrollY = window.scrollY; bodyTop = document.body.style.top;
      document.body.style.top = `-${scrollY}px`;
      document.body.classList.add('quiz-page-locked');
      dialog.showModal();
    }
    function closeQuiz() {
      stop(); epoch += 1; busy = false;
      dialog.close();
      document.body.classList.remove('quiz-page-locked');
      document.body.style.top = bodyTop;
      window.scrollTo(0, scrollY);
      if (returnFocus) returnFocus.focus({preventScroll: true});
    }
    byId('close-quiz-btn').addEventListener('click', closeQuiz);
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeQuiz(); });
    function prepareClock() {
      const key = state.attempt_token + '/' + current.id;
      if (clockKey === key) return;
      clockKey = key;
      deadline = null;
      // A backgrounded WebView can reload the same question in this tab.
      try {
        const saved = JSON.parse(sessionStorage.getItem(clockStorage));
        if (saved && saved.key === key && Number.isFinite(saved.until)) {
          wallDeadline = saved.until;
          deadline = performance.now() + Math.min(duration, wallDeadline - Date.now());
        }
      } catch { /* Storage is optional. */ }
    }
    function beginClock() {
      if (deadline !== null) return;
      deadline = performance.now() + duration;
      wallDeadline = Date.now() + duration;
      try {
        sessionStorage.setItem(clockStorage, JSON.stringify({key: clockKey, until: wallDeadline}));
      } catch { /* Keep using this document's deadline when storage is unavailable. */ }
    }
    function timeLeft() {
      return Math.max(0, Math.min(deadline - performance.now(), wallDeadline - Date.now()));
    }
    function displayTime(ms) {
      const seconds = Math.ceil(ms / 1000);
      const fraction = reducedMotion.matches ? seconds / (duration / 1000) : ms / duration;
      fill.style.transform = `scaleX(${fraction})`;
      if (track.getAttribute('aria-valuenow') !== String(seconds)) {
        track.setAttribute('aria-valuenow', seconds);
        track.setAttribute('aria-valuetext', seconds + ' секунд');
      }
      track.classList.toggle('urgent', ms > 0 && ms <= 1500);
    }
    function tick() {
      const left = timeLeft();
      displayTime(left);
      if (left > 0) frame = requestAnimationFrame(tick);
      else submit({question_id: current.id, answer: '', timed_out: 'true', attempt_token: state.attempt_token});
    }
    function armTimer() {
      questionActive = true;
      if (document.hidden) return;
      // Allow one paint with the new choices before enabling them and starting the clock.
      frame = requestAnimationFrame(() => { frame = requestAnimationFrame(() => {
        frame = 0;
        if (document.hidden) return;
        answers.querySelectorAll('button').forEach(button => { button.disabled = false; });
        armed = true;
        beginClock();
        tick();
      }); });
    }
    document.addEventListener('visibilitychange', () => {
      if (!questionActive) return;
      cancelAnimationFrame(frame);
      if (document.hidden) {
        armed = false;
        answers.querySelectorAll('button').forEach(button => { button.disabled = true; });
      } else armTimer();
    });
    const csrf = () => {
      const value = document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
      return value ? decodeURIComponent(value.slice(10)) : '';
    };
    const postOptions = body => ({method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'X-CSRFToken': csrf()}, body: new URLSearchParams(body)});
    function stop() { clearTimeout(transition); cancelAnimationFrame(frame); frame = 0; armed = false; questionActive = false; }
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
      byId('score').textContent = `✓ Ұпай: ${Number(data.finished_score ?? data.score ?? 0)}`;
      const lives = data.restart_required ? 0 : Math.max(0, 3 - data.attempts);
      const hearts = byId('attempts');
      hearts.setAttribute('aria-label', lives + ' мүмкіндік қалды');
      Array.from(hearts.children).forEach((heart, index) => heart.classList.toggle('spent', index >= lives));
      const previous = byId('quiz-previous-score');
      if (data.previous_score !== null && data.previous_score !== undefined) {
        previous.hidden = false;
        byId('quiz-previous-value').textContent = data.previous_total == null
          ? String(data.previous_score) : `${data.previous_score} / ${data.previous_total}`;
      }
    }
    function showComplete() {
      stop();
      content.hidden = true;
      summary.hidden = false;
      start.hidden = false;
      dialog.dataset.result = 'pass';
      track.hidden = true;
      byId('quiz-result').textContent = `Жарайсыз!`;
      byId('quiz-result-detail').textContent = `${state.total_questions} сұрақтың ${state.score} жауабы дұрыс`;
      start.dataset.retake = 'true'; start.textContent = 'Тестті қайта тапсыру';
      feedback.textContent = '';
      const offer = state.subscription_offer;
      const subscribe = byId('subscription-result');
      subscribe.hidden = !offer;
      if (offer) {
        byId('quiz-result').textContent = offer.title;
        byId('quiz-result-detail').textContent = offer.detail;
        subscribe.href = offer.url;
        subscribe.textContent = offer.cta;
      }
      const next = byId('next-lesson-link');
      next.hidden = !state.can_continue;
      if (state.can_continue) next.href = root.dataset.lessonUrl.replace('/0/', `/${state.next_lesson}/`);
      (offer ? subscribe : retake).focus({preventScroll: true});
    }
    function showFailure(score) {
      byId('subscription-result').hidden = true;
      dialog.dataset.result = 'fail';
      track.hidden = true;
      content.hidden = true;
      summary.hidden = false;
      byId('quiz-result').textContent = 'Тағы байқап көріңіз';
      byId('quiz-result-detail').textContent = 'Жиналған ұпай: ' + score;
      byId('next-lesson-link').hidden = true;
      retake.textContent = 'Қайта бастау';
      start.dataset.retake = 'false';
      start.textContent = state.lesson_completed ? 'Тестті қайта тапсыру' : 'Тестті бастау';
      retake.focus({preventScroll: true});
    }
    function renderQuestion() {
      stop(); hideError();
      busy = false;
      summary.hidden = true; content.hidden = false; byId('quiz-loading').hidden = true;
      feedback.textContent = '';
      if (state.passed) { showComplete(); return; }
      current = questions.find(q => q.id === state.next_question_id);
      if (!current) {
        showError(new Error('Тест күйін қайта жүктеңіз.'), () => load());
        return;
      }
      track.hidden = false;
      questionText.textContent = current.english_word;
      byId('question-count').textContent = `${Math.min(state.answered_count + 1, state.total_questions)} / ${state.total_questions} сұрақ`;
      answers.replaceChildren();
      current.choices.forEach((choice, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'quiz-answer';
        button.disabled = true;
        button.dataset.marker = String.fromCharCode(65 + index);
        button.textContent = choice;
        button.addEventListener('click', () => submit({question_id: current.id, answer: choice,
          timed_out: 'false', attempt_token: state.attempt_token}, button));
        answers.appendChild(button);
      });
      questionText.focus({preventScroll: true});
      answers.scrollTop = 0;
      prepareClock();
      displayTime(deadline === null ? duration : timeLeft());
      armTimer();
    }
    async function load(restart = false, initialRetake = false) {
      if (busy) return;
      openQuiz();
      delete dialog.dataset.result;
      track.hidden = true;
      busy = true; stop(); hideError();
      content.hidden = true; summary.hidden = true;
      byId('quiz-loading').hidden = false; feedback.textContent = '';
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
      } finally { if (requestEpoch === epoch) { busy = false; byId('quiz-loading').hidden = true; } }
    }
    async function submit(payload, button = null, replay = false) {
      if (busy || !dialog.open || (!armed && !replay)) return;
      if (!replay) {
        const left = timeLeft();
        displayTime(left);
        if (left === 0) {
          payload = {...payload, answer: '', timed_out: 'true'};
          button = null;
        }
      }
      busy = true; stop(); hideError();
      const requestEpoch = epoch;
      if (button) button.classList.add('selected');
      feedback.textContent = 'Жауап сақталуда…';

      answers.querySelectorAll('button').forEach(item => { item.disabled = true; });
      try {
        const data = await OqyLoading.json(root.dataset.submitUrl, postOptions(payload), {button, progress: false, timeout: 15000});
        if (requestEpoch !== epoch) return;
        apply(data);
        if (data.already_passed) { showComplete(); return; }
        const selected = data.already_answered ? data.selected_answer : payload.answer;
        for (const option of answers.children) {
          option.classList.remove('selected');
          if (option.textContent === data.correct_answer) option.classList.add('btn-success');
          else if (option.textContent === selected) option.classList.add('btn-danger');
        }
        feedback.textContent = data.correct ? 'Дұрыс' : 'Дұрыс жауап: ' + data.correct_answer;
        transition = setTimeout(() => {
          if (data.restart_required) showFailure(data.finished_score);
          else if (data.passed) showComplete();
          else renderQuestion();
        }, data.correct ? 500 : 1250);
      } catch (error) {
        if (requestEpoch !== epoch) return;
        // Retry the exact answer/token after ambiguous delivery. The server is idempotent.
        // A stale token must resume the server run; never replay into a new attempt.
        showError(error, error.status === 409 ? () => load() : () => submit(payload, button, true));
      } finally { if (requestEpoch === epoch) busy = false; }
    }
    start.addEventListener('click', () => load(false, start.dataset.retake === 'true'));
    retake.addEventListener('click', () => { retake.textContent = 'Тестті қайта тапсыру'; load(!state.restart_required); });
    retry.addEventListener('click', () => { if (!busy && retryAction) retryAction(); });
    let restoreQuiz = false;
    window.addEventListener('pagehide', () => { restoreQuiz = dialog.open; if (dialog.open) closeQuiz(); });
    window.addEventListener('pageshow', event => { if (event.persisted && restoreQuiz) { restoreQuiz = false; load(); } });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountQuiz);
  else mountQuiz();
})();
