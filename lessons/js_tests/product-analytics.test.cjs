const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const code = readFileSync(join(__dirname, '../../static/js/product-analytics.js'), 'utf8');

function simulate(respond) {
  const listeners = {}, timers = [], calls = [];
  const listen = (name, fn) => { listeners[name] = fn; };
  const document = {
    currentScript:{dataset:{csrf:'test',actor:'fixture',endpoint:'/analytics/events/'}},
    cookie:'csrftoken=initial', hidden:false, addEventListener:listen, querySelectorAll:() => [],
  };
  const window = {crypto:webcrypto,addEventListener:listen};
  vm.runInNewContext(code, {
    window,document,crypto:webcrypto,URLSearchParams,AbortController,location:{search:'',pathname:'/'},
    navigator:{userAgent:'Chrome'},matchMedia:()=>({matches:false}),
    fetch:async (url, options) => { calls.push(options); return {status:await respond(calls.length)}; },
    setTimeout:(fn,ms) => { if (ms < 8000) timers.push({fn,ms}); return fn; },
    clearTimeout:()=>{},
  });
  return {document,listeners,timers,calls};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('transient retries reuse one UUID and stop after four attempts with bounded jitter', async () => {
  const {calls,timers} = simulate(() => 503);
  for (let i=0; i<3; i++) {
    await tick();
    const timer = timers.shift();
    assert.ok(timer.ms >= 350*2**i && timer.ms <= 700*2**i);
    timer.fn();
  }
  await tick();
  assert.equal(calls.length,4);
  assert.equal(new Set(calls.map(c => c.body)).size,1);
  assert.equal(timers.length,0);
});

test('permanent errors stop and retries are dropped across navigation and account changes', async () => {
  for (const status of [400,403,413,429,500]) {
    const state = simulate(() => status);
    await tick();
    assert.equal(state.timers.length,0);
  }
  for (const change of [s=>s.listeners.pagehide(),s=>{s.document.cookie='csrftoken=next';}]) {
    const state = simulate(() => 503);
    await tick();
    change(state);
    state.timers.shift().fn();
    await tick();
    assert.equal(state.calls.length,1);
  }
});

test('a burst uses a single in-flight request and a bounded pending queue', async () => {
  let resolve;
  const state = simulate(n => n === 1 ? new Promise(r=>{resolve=r;}) : 204);
  const target = {closest:()=>({dataset:{analyticsAction:'subscription_cta_clicked'}})};
  for (let i=0; i<100; i++) state.listeners.click({target});
  assert.equal(state.calls.length,1);
  resolve(204);
  await tick();
  assert.equal(state.calls.length,25);
});

test('navigation flushes one queued CTA click with the original identity', async () => {
  let finish;
  const state = simulate(n => n === 1 ? new Promise(r=>{finish=r;}) : 204);
  state.listeners.click({target:{closest:()=>({dataset:{analyticsAction:'subscription_cta_clicked'}})}});
  state.listeners.pagehide();
  finish(204);
  await tick();
  assert.equal(state.calls.length,2);
  assert.equal(JSON.parse(state.calls[1].body).type,'subscription_cta_clicked');
  assert.equal(state.calls[1].headers['X-Analytics-Actor'],'fixture');
});
