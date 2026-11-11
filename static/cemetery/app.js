'use strict';
document.querySelector('.menu-button')?.addEventListener('click', (event) => {
  const open = document.getElementById('navigation').classList.toggle('open');
  event.currentTarget.setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    document.getElementById('navigation')?.classList.remove('open');
    document.querySelector('.menu-button')?.setAttribute('aria-expanded', 'false');
  }
});
document.querySelectorAll('[data-password-toggle]').forEach(button => button.addEventListener('click', () => {
  const field = document.getElementById(button.dataset.passwordToggle);
  if (!field) return;
  field.type = field.type === 'password' ? 'text' : 'password';
  button.textContent = field.type === 'password' ? 'Mostrar contraseña' : 'Ocultar contraseña';
}));
document.querySelectorAll('[data-pending-form]').forEach(form => form.addEventListener('submit', () => {
  const button = form.querySelector('button[type="submit"]');
  if (button) { button.disabled = true; button.textContent = 'Guardando…'; }
}));
document.querySelector('[data-print]')?.addEventListener('click', () => window.print());
window.addEventListener('pageshow', () => document.querySelectorAll('[data-pending-form] button[type="submit"]').forEach(button => {
  if (button.disabled) window.location.reload();
}));

(() => {
  const container = document.getElementById('map-canvas');
  if (!container) return;
  const svg = document.getElementById('cemetery-map');
  const form = document.getElementById('map-filters');
  const status = document.getElementById('map-status');
  const count = document.getElementById('map-count');
  const results = document.getElementById('map-results');
  const editToggle = document.getElementById('map-edit-toggle');
  const ns = 'http://www.w3.org/2000/svg';
  const selected = new URLSearchParams(location.search).get('space');
  const fills = { AVAILABLE: ['#e2ecdc', '#9ab48e'], OCCUPIED: ['#eeded7', '#c49282'], RESERVED: ['#f1e8c5', '#c6ac61'], MAINTENANCE: ['#dfe8f1', '#90abc1'], OUT_OF_SERVICE: ['#e2e5df', '#a2aaa0'] };
  let zoom = 1, width = 900, height = 520, sequence = 0, timer, controller, highlightedId = selected, initialFocusPending = Boolean(selected), userHasZoomed = false, editMode = false;
  function node(name, attrs, text) {
    const element = document.createElementNS(ns, name);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (text != null) element.textContent = text;
    return element;
  }
  function setSize() { svg.setAttribute('width', String(width * zoom)); svg.setAttribute('height', String(height * zoom)); }
  function fitMap() {
    const style = getComputedStyle(container);
    const horizontalPadding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    const verticalPadding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
    const availableWidth = Math.max(180, (container.clientWidth || width) - horizontalPadding);
    const availableHeight = Math.max(180, (container.clientHeight || height) - verticalPadding);
    zoom = Math.min(1, availableWidth / width, availableHeight / height);
    setSize();
  }
  function focusSpace(id) {
    highlightedId = String(id);
    const element = document.getElementById(`space-${id}`);
    if (!element) { status.textContent = 'La ubicación no está entre los espacios mostrados. Limpia los filtros para localizarla.'; return; }
    svg.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');
    element.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center', inline: 'center' });
    element.focus({ preventScroll: true });
  }
  function attachDrag(anchor, space, plan) {
    if (!editMode || !plan || container.dataset.editable !== 'true') return;
    let origin = null, moved = false, pendingTransform = '';
    const pointInMap = event => {
      const point = svg.createSVGPoint();
      point.x = event.clientX; point.y = event.clientY;
      return point.matrixTransform(svg.getScreenCTM().inverse());
    };
    const reset = () => {
      if (pendingTransform) anchor.setAttribute('transform', pendingTransform);
      else anchor.removeAttribute('transform');
    };
    anchor.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      origin = pointInMap(event); moved = false;
      pendingTransform = anchor.getAttribute('transform') || '';
      anchor.setPointerCapture(event.pointerId);
    });
    anchor.addEventListener('pointermove', event => {
      if (!origin) return;
      event.preventDefault();
      const point = pointInMap(event);
      const x = Math.max(0, Math.min(Number(plan.width) - 58, Math.round(Number(space.x) + point.x - origin.x)));
      const y = Math.max(0, Math.min(Number(plan.height) - 50, Math.round(Number(space.y) + point.y - origin.y)));
      moved ||= Math.abs(x - Number(space.x)) + Math.abs(y - Number(space.y)) > 2;
      anchor.setAttribute('transform', `translate(${x - Number(space.x)} ${y - Number(space.y)})`);
      anchor.dataset.pendingX = String(x); anchor.dataset.pendingY = String(y);
    });
    anchor.addEventListener('pointerup', async event => {
      if (!origin) return;
      event.preventDefault(); event.stopPropagation();
      origin = null;
      const x = Number(anchor.dataset.pendingX ?? space.x), y = Number(anchor.dataset.pendingY ?? space.y);
      delete anchor.dataset.pendingX; delete anchor.dataset.pendingY;
      if (!moved || (x === Number(space.x) && y === Number(space.y))) { reset(); return; }
      const csrf = document.querySelector('#map-coordinate-csrf input[name="csrfmiddlewaretoken"]')?.value;
      const endpoint = container.dataset.editUrlTemplate.replace('/0/', `/${space.id}/`);
      status.textContent = `Guardando ubicación de ${space.code}…`;
      anchor.setAttribute('aria-busy', 'true');
      try {
        const response = await fetch(endpoint, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRFToken': csrf || '' },
          body: JSON.stringify({ x, y, revision: Number(space.revision), plan_version: plan.version }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'No se pudo guardar la ubicación.');
        space.x = result.x; space.y = result.y; space.revision = result.revision;
        anchor.removeAttribute('transform');
        pendingTransform = '';
        status.classList.remove('error');
        status.textContent = `Ubicación guardada: ${space.code}. Puedes seguir moviendo sepulturas.`;
      } catch (error) {
        reset();
        status.classList.add('error');
        status.textContent = error.message || 'No se pudo guardar la ubicación. Vuelve a intentarlo.';
      } finally {
        anchor.removeAttribute('aria-busy');
      }
    });
    anchor.addEventListener('pointercancel', () => { origin = null; reset(); });
    anchor.addEventListener('click', event => {
      if (editMode) { event.preventDefault(); event.stopPropagation(); }
    });
  }
  function draw(data) {
    const active = document.activeElement;
    const focusedId = (svg.contains(active) || results.contains(active)) ? active.id : null;
    const scrollLeft = container.scrollLeft, scrollTop = container.scrollTop;
    svg.replaceChildren(node('title', {}, 'Mapa de las sepulturas'));
    const positions = data.spaces.map(space => ({
      space, x: Number(space.x) + (data.plan ? 0 : 40), y: Number(space.y) + (data.plan ? 0 : 40),
    }));
    let maxX = data.plan ? Number(data.plan.width) : 850;
    let maxY = data.plan ? Number(data.plan.height) : 460;
    positions.forEach(({ x, y }) => {
      maxX = Math.max(maxX, x + (data.plan ? 58 : 300));
      maxY = Math.max(maxY, y + (data.plan ? 50 : 220));
    });
    width = maxX; height = maxY;
    const scenery = node('g', { class: 'lot-scenery', 'aria-hidden': 'true' });
    if (data.plan) {
      scenery.append(node('image', {
        x: 0, y: 0, width: data.plan.width, height: data.plan.height,
        href: data.plan.url, preserveAspectRatio: 'none',
      }));
    } else {
    scenery.append(node('rect', { x: 0, y: 0, width, height, rx: 38, fill: '#e8efe0' }));
    scenery.append(node('rect', { x: 18, y: 18, width: width - 36, height: height - 36, rx: 30, fill: '#dce8d2', stroke: '#91a987', 'stroke-width': 3, 'stroke-dasharray': '12 6' }));
    scenery.append(node('rect', { x: 30, y: 30, width: width - 60, height: height - 60, rx: 26, fill: 'none', stroke: '#b4c5a5', 'stroke-width': 1 }));

    const plots = new Map();
    positions.forEach(({ space, x, y }) => {
      if (!plots.has(space.block)) plots.set(space.block, []);
      plots.get(space.block).push({ x, y });
    });
    const bounds = [];
    for (const [label, points] of plots) {
      const minX = Math.min(...points.map(point => point.x)) - 28;
      const maxPlotX = Math.max(...points.map(point => point.x)) + 112;
      const minY = Math.min(...points.map(point => point.y)) - 30;
      const maxPlotY = Math.max(...points.map(point => point.y)) + 84;
      bounds.push({ label, left: minX, right: maxPlotX, top: minY, bottom: maxPlotY });
      scenery.append(node('rect', { x: minX, y: minY, width: maxPlotX - minX, height: maxPlotY - minY, rx: 20, fill: '#cbdcbe', stroke: '#a5bc98', 'stroke-width': 2 }));
      const rows = [...new Set(points.map(point => point.y))].sort((a, b) => a - b);
      for (let index = 0; index < rows.length - 1; index += 1) {
        const pathY = (rows[index] + rows[index + 1]) / 2 + 29;
        scenery.append(node('path', { d: `M ${minX + 12} ${pathY} H ${maxPlotX - 12}`, fill: 'none', stroke: '#eadfc9', 'stroke-width': 15, 'stroke-linecap': 'round' }));
        scenery.append(node('path', { d: `M ${minX + 12} ${pathY} H ${maxPlotX - 12}`, fill: 'none', stroke: '#d3c4a6', 'stroke-width': 1.5, 'stroke-dasharray': '10 6' }));
      }
      const shortLabel = label.split('/').at(-1).trim().toUpperCase();
      scenery.append(node('rect', { class: 'plot-label', x: minX + 8, y: minY - 13, width: Math.max(106, shortLabel.length * 8 + 24), height: 25, rx: 12, fill: '#3d6547' }));
      scenery.append(node('text', { x: minX + 20, y: minY + 4, fill: '#fff', 'font-size': 13, 'font-weight': 700, 'letter-spacing': 1 }, shortLabel));
    }
    for (const plot of bounds) {
      for (const other of bounds) {
        if (other === plot) continue;
        const overlapY = Math.min(plot.bottom, other.bottom) - Math.max(plot.top, other.top);
        if (overlapY > 0 && other.left >= plot.right && other.left - plot.right < 500) {
          const roadY = (Math.max(plot.top, other.top) + Math.min(plot.bottom, other.bottom)) / 2;
          scenery.append(node('path', { d: `M ${plot.right} ${roadY} H ${other.left}`, fill: 'none', stroke: '#f5f0e5', 'stroke-width': 28, 'stroke-linecap': 'round' }));
          scenery.append(node('path', { d: `M ${plot.right} ${roadY} H ${other.left}`, fill: 'none', stroke: '#d4c8ae', 'stroke-width': 1.5, 'stroke-dasharray': '8 8' }));
        }
        const overlapX = Math.min(plot.right, other.right) - Math.max(plot.left, other.left);
        if (overlapX > 0 && other.top >= plot.bottom && other.top - plot.bottom < 500) {
          const roadX = (Math.max(plot.left, other.left) + Math.min(plot.right, other.right)) / 2;
          scenery.append(node('path', { d: `M ${roadX} ${plot.bottom} V ${other.top}`, fill: 'none', stroke: '#f5f0e5', 'stroke-width': 28, 'stroke-linecap': 'round' }));
          scenery.append(node('path', { d: `M ${roadX} ${plot.bottom} V ${other.top}`, fill: 'none', stroke: '#d4c8ae', 'stroke-width': 1.5, 'stroke-dasharray': '8 8' }));
        }
      }
    }
    scenery.append(node('rect', { class: 'lot-access', x: 38, y: height - 74, width: 146, height: 40, rx: 8, fill: '#e7dfcc', stroke: '#aa9f84', 'stroke-width': 2 }));
    scenery.append(node('path', { d: `M 86 ${height - 34} V ${height - 13} M 136 ${height - 34} V ${height - 13}`, stroke: '#aa9f84', 'stroke-width': 4 }));
    scenery.append(node('text', { x: 110, y: height - 48, fill: '#62704f', 'font-size': 10, 'font-weight': 700, 'text-anchor': 'middle' }, 'ACCESO AL LOTE'));
    const trees = [[width - 92, 86], [width - 88, height - 110], [86, height - 95], [Math.round(width * .72), 70]]
      .filter(([x, y]) => bounds.every(plot => x < plot.left - 34 || x > plot.right + 34 || y < plot.top - 34 || y > plot.bottom + 34));
    trees.forEach(([x, y], index) => {
      scenery.append(node('circle', { cx: x, cy: y, r: index % 2 ? 23 : 28, fill: '#aac49b', opacity: '.68' }));
      scenery.append(node('circle', { cx: x, cy: y, r: 10, fill: '#77966b' }));
    });
    }
    svg.append(scenery);
    positions.forEach(({ space, x, y }) => {
      const colors = fills[space.status] || fills.OUT_OF_SERVICE;
      const stoneX = x + (data.plan ? 0 : 14);
      const stoneY = y + (data.plan ? 0 : 8);
      const anchor = node('a', { href: space.url, class: 'map-space', id: `space-${space.id}`, tabindex: '0', 'aria-label': `${space.code}, ${space.label}, ${space.block}` });
      if (String(space.id) === highlightedId) anchor.classList.add('selected');
      anchor.append(node('title', {}, `${space.code} · ${space.label} · ${space.block}`));
      anchor.append(node('ellipse', { cx: stoneX + 29, cy: stoneY + 55, rx: 30, ry: 5, fill: '#34402f', opacity: '.35' }));
      anchor.append(node('path', { d: `M ${stoneX} ${stoneY + 50} V ${stoneY + 16} Q ${stoneX} ${stoneY} ${stoneX + 15} ${stoneY} H ${stoneX + 43} Q ${stoneX + 58} ${stoneY} ${stoneX + 58} ${stoneY + 16} V ${stoneY + 50} Z`, fill: colors[0], stroke: colors[1], 'stroke-width': 2.5 }));
      anchor.append(node('rect', { x: stoneX + 6, y: stoneY + 32, width: 46, height: 15, rx: 3, fill: '#f5f4eb', stroke: colors[1], 'stroke-width': 1 }));
      anchor.append(node('text', { x: stoneX + 29, y: stoneY + 23, 'text-anchor': 'middle', 'font-size': 10, 'font-weight': 700, fill: '#344d35' }, space.code));
      anchor.append(node('text', { x: stoneX + 29, y: stoneY + 43, 'text-anchor': 'middle', 'font-size': 8, fill: '#344d35' }, space.label));
      svg.append(anchor);
      attachDrag(anchor, space, data.plan);
    });
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (userHasZoomed) setSize(); else fitMap();
    count.textContent = `${data.spaces.length} sepulturas mostradas${data.plan ? ` · Fondo: ${data.plan.original_name}` : ' · Plano ilustrativo, no corresponde a un cementerio real'}`;
    const caption = document.querySelector('.map-caption span:last-child');
    if (caption) caption.textContent = data.plan
      ? `Imagen ${data.plan.width} × ${data.plan.height} px · Las coordenadas CSV corresponden a píxeles desde la esquina superior izquierda`
      : 'Plano ilustrativo de un lote · No corresponde a un cementerio real';
    status.classList.remove('error');
    status.textContent = data.truncated ? 'Se muestran los primeros 1.000 espacios. Usa filtros para reducir la consulta.' : data.spaces.length ? 'Estados actualizados. Selecciona un espacio para abrir su ficha.' : 'No hay espacios que coincidan con la búsqueda.';
    results.replaceChildren();
    if (new FormData(form).get('person')) {
      if (!data.people.length) { const p = document.createElement('p'); p.textContent = 'No se encontraron personas con ese nombre.'; results.append(p); }
      if (data.people_truncated) { const p = document.createElement('p'); p.textContent = 'Se muestran las primeras 20 coincidencias. Añade más datos para afinar la búsqueda.'; results.append(p); }
      data.people.forEach(person => {
        const element = document.createElement(person.space_id ? 'button' : 'a');
        element.id = `person-result-${person.id}`;
        element.textContent = person.name + (person.space_id ? ' · Localizar' : ' · Sin ubicación vigente');
        if (person.space_id) { element.type = 'button'; element.addEventListener('click', () => focusSpace(person.space_id)); }
        else element.href = person.url;
        results.append(element);
      });
    }
    container.scrollLeft = scrollLeft; container.scrollTop = scrollTop;
    if (focusedId) (document.getElementById(focusedId) || container).focus({ preventScroll: true });
  }
  async function load(auto = false) {
    const current = ++sequence;
    controller?.abort(); controller = new AbortController();
    if (!auto) status.textContent = 'Consultando disponibilidad…';
    try {
      const response = await fetch(`${container.dataset.url}?${new URLSearchParams(new FormData(form))}`, { credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('No se pudo consultar el mapa. Comprueba tu sesión y vuelve a intentarlo.');
      const data = await response.json();
      if (current !== sequence) return;
      draw(data);
      if (initialFocusPending) { initialFocusPending = false; focusSpace(selected); }
    } catch (error) {
      if (current !== sequence || error.name === 'AbortError') return;
      status.classList.add('error');
      status.textContent = 'No fue posible actualizar el mapa. Los datos visibles pueden estar desactualizados. Vuelve a buscar para reintentar.';
      count.textContent = 'Actualización pendiente';
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); load(); });
  form.addEventListener('reset', () => setTimeout(() => load(), 0));
  editToggle?.addEventListener('click', () => {
    editMode = !editMode;
    editToggle.setAttribute('aria-pressed', String(editMode));
    editToggle.textContent = editMode ? 'Terminar edición' : 'Editar ubicaciones';
    container.classList.toggle('map-editing', editMode);
    clearInterval(timer);
    status.classList.remove('error');
    status.textContent = editMode
      ? 'Arrastra una sepultura hasta su posición real. Cada movimiento se guarda al soltar.'
      : 'Edición terminada. Actualizando el mapa…';
    load(true);
    if (!editMode) timer = setInterval(() => { if (!document.hidden) load(true); }, 15000);
  });
  document.querySelectorAll('[data-zoom]').forEach(button => button.addEventListener('click', () => {
    if (button.dataset.zoom === 'reset') { userHasZoomed = false; fitMap(); }
    else { userHasZoomed = true; zoom = Math.max(.12, Math.min(3, zoom + (button.dataset.zoom === 'in' ? .25 : -.25))); setSize(); }
  }));
  window.addEventListener('resize', () => { if (!userHasZoomed && width > 0 && height > 0) fitMap(); });
  document.addEventListener('visibilitychange', () => {
    clearInterval(timer);
    if (document.hidden) { ++sequence; controller?.abort(); }
    if (!document.hidden) { load(true); if (!editMode) timer = setInterval(() => load(true), 15000); }
  });
  load(); timer = setInterval(() => { if (!document.hidden) load(true); }, 15000);
})();
