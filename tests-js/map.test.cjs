const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../static/cemetery/app.js'), 'utf8');
const data = (changes = {}) => ({
  spaces: [
    { id: 1, code: 'A-001', block: 'Bloque A', status: 'AVAILABLE', label: 'Disponible', x: 0, y: 0, url: '/sepultura/1/' },
    { id: 2, code: 'A-002', block: 'Bloque A', status: 'OCCUPIED', label: 'Ocupada', x: 110, y: 0, url: '/sepultura/2/' },
  ],
  people: [], truncated: false, people_truncated: false,
  ...changes,
});
const turn = () => new Promise(resolve => setImmediate(resolve));

function setup(t, query = '') {
  const dom = new JSDOM(`<!doctype html><html><body>
    <form id="map-filters"><input name="person"><button>Buscar</button></form>
    <div id="map-results"></div><p id="map-status"></p><span id="map-count"></span>
    <div id="map-canvas" data-url="/mapa/datos/" tabindex="0"><svg id="cemetery-map"></svg></div>
    </body></html>`, { url: `http://localhost/mapa/${query}`, runScripts: 'outside-only', pretendToBeVisual: true });
  t.after(() => dom.window.close());
  const { window } = dom;
  const requests = [], intervals = new Map();
  window.matchMedia = () => ({ matches: false });
  window.Element.prototype.scrollIntoView = function () {};
  window.setInterval = callback => { const id = intervals.size + 1; intervals.set(id, callback); return id; };
  window.clearInterval = id => intervals.delete(id);
  window.fetch = (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
  const document = window.document;
  window.eval(source);
  return {
    window, document, requests,
    async answer(index, payload = data(), contentType = 'application/json') {
      requests[index].resolve({ ok: true, headers: { get: () => contentType }, json: async () => payload });
      await turn();
    },
    search() { document.getElementById('map-filters').dispatchEvent(new window.Event('submit', { cancelable: true })); },
    refresh() { [...intervals.values()][0](); },
  };
}

test('renders linked states as text and never interprets record values as HTML', async t => {
  const page = setup(t);
  const payload = data();
  payload.spaces[0].code = '<img src=x onerror=alert(1)>';
  await page.answer(0, payload);
  assert.equal(page.document.querySelectorAll('.map-space').length, 2);
  assert.equal(page.document.getElementById('space-1').getAttribute('href'), '/sepultura/1/');
  assert.match(page.document.getElementById('space-1').textContent, /<img src=x/);
  assert.equal(page.document.querySelectorAll('img').length, 0);
  assert.match(page.document.getElementById('space-2').getAttribute('aria-label'), /Ocupada/);
});

test('an old request error cannot overwrite the newest successful search', async t => {
  const page = setup(t);
  page.search();
  await page.answer(1);
  page.requests[0].reject(new Error('Late network failure'));
  await turn();
  assert.match(page.document.getElementById('map-status').textContent, /Estados actualizados/);
  assert.equal(page.document.getElementById('map-status').classList.contains('error'), false);
});

test('periodic state updates preserve keyboard focus on the same space', async t => {
  const page = setup(t);
  await page.answer(0);
  page.document.getElementById('space-2').focus();
  page.refresh();
  await page.answer(1);
  assert.equal(page.document.activeElement.id, 'space-2');
});

test('periodic updates preserve focus on a person result', async t => {
  const page = setup(t);
  page.document.querySelector('[name="person"]').value = 'Persona';
  const payload = data({ people: [{ id: 7, name: 'Persona Ejemplo', space_id: 2, url: '/persona/7/' }] });
  await page.answer(0, payload);
  page.document.querySelector('#map-results button').focus();
  page.refresh();
  await page.answer(1, payload);
  assert.equal(page.document.activeElement.textContent, 'Persona Ejemplo · Localizar');
});

test('a later search keeps the selection chosen after the initial deep link', async t => {
  const page = setup(t, '?space=1');
  page.document.querySelector('[name="person"]').value = 'Persona';
  const payload = data({ people: [{ id: 7, name: 'Persona Ejemplo', space_id: 2, url: '/persona/7/' }] });
  await page.answer(0, payload);
  page.document.querySelector('#map-results button').click();
  assert.equal(page.document.querySelector('.selected').id, 'space-2');
  page.search();
  await page.answer(1, payload);
  assert.equal(page.document.querySelector('.selected').id, 'space-2');
});

test('session or network errors retain the previous map with an explicit warning', async t => {
  const page = setup(t);
  await page.answer(0);
  page.refresh();
  await page.answer(1, {}, 'text/html');
  assert.equal(page.document.querySelectorAll('.map-space').length, 2);
  assert.match(page.document.getElementById('map-status').textContent, /desactualizados/);
  assert.equal(page.document.getElementById('map-status').classList.contains('error'), true);
});

test('a stale success cannot replace the latest filtered results', async t => {
  const page = setup(t);
  page.search();
  await page.answer(1, data({ spaces: [] }));
  await page.answer(0);
  assert.equal(page.document.querySelectorAll('.map-space').length, 0);
  assert.match(page.document.getElementById('map-status').textContent, /No hay espacios/);
});

test('a removed focused result leaves focus on the map container', async t => {
  const page = setup(t);
  await page.answer(0);
  page.document.getElementById('space-2').focus();
  page.refresh();
  await page.answer(1, data({ spaces: [] }));
  assert.equal(page.document.activeElement.id, 'map-canvas');
});

test('background updates never take focus from the search field', async t => {
  const page = setup(t);
  await page.answer(0);
  const field = page.document.querySelector('[name="person"]');
  field.focus();
  page.refresh();
  await page.answer(1);
  assert.equal(page.document.activeElement, field);
});

test('hiding the page cancels pending work until it becomes visible again', async t => {
  const page = setup(t);
  let hidden = true;
  Object.defineProperty(page.document, 'hidden', { get: () => hidden });
  page.document.dispatchEvent(new page.window.Event('visibilitychange'));
  assert.equal(page.requests[0].options.signal.aborted, true);
  await page.answer(0);
  assert.equal(page.document.querySelectorAll('.map-space').length, 0);
  hidden = false;
  page.document.dispatchEvent(new page.window.Event('visibilitychange'));
  await page.answer(1);
  assert.equal(page.document.querySelectorAll('.map-space').length, 2);
});
