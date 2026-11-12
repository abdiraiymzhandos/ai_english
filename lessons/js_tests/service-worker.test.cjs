const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function worker() {
  const events = {}, deleted = [], stored = [];
  const cache = {match: async () => null, put: async request => stored.push(request.url)};
  const context = {
    URL, console, fetch: async () => ({ok: true, type: 'basic', headers: new Headers(), clone() { return this; }}),
    caches: {keys: async () => ['english-course-v2', 'unrelated-app'], delete: async name => deleted.push(name), open: async () => cache},
    self: {location: {origin: 'https://oqy.test'}, addEventListener: (name, fn) => { events[name] = fn; },
      skipWaiting: async () => {}, clients: {claim: async () => {}}},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../static/sw.js'), 'utf8'), context);
  return {events, deleted, stored};
}

test('quiz, personal pages, APIs, media, unversioned scripts and POSTs bypass the cache', () => {
  const {events} = worker();
  for (const url of ['/', '/lesson/1/', '/profile/', '/start-quiz/1/', '/submit-answer/1/',
    '/api/realtime/token/1/', '/media/audio.mp3', '/static/js/quiz.js']) {
    events.fetch({request: {url: 'https://oqy.test' + url, method: 'GET'},
      respondWith() { assert.fail('Must not intercept ' + url); }});
  }
  events.fetch({request: {url: 'https://oqy.test/static/file.abcdef123456.js', method: 'POST'},
    respondWith() { assert.fail('Must not intercept POST'); }});
});

test('activation removes only old OqyAI application caches', async () => {
  const {events, deleted} = worker();
  let completion;
  events.activate({waitUntil(promise) { completion = promise; }});
  await completion;
  assert.deepEqual(deleted, ['english-course-v2']);
});

test('only immutable same-origin public assets are stored', async () => {
  const {events, stored} = worker();
  let response;
  events.fetch({request: {url: 'https://oqy.test/static/file.abcdef123456.js', method: 'GET'},
    respondWith(promise) { response = promise; }});
  await response;
  assert.equal(stored.length, 1);
  events.fetch({request: {url: 'https://other.test/static/file.abcdef123456.js', method: 'GET'},
    respondWith() { assert.fail('Must not cache third-party resources'); }});
});
