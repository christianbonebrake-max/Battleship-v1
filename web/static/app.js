const ROWS = Array.from({ length: 10 }, (_, i) => String.fromCharCode(65 + i));
const COLS = Array.from({ length: 10 }, (_, i) => (i + 1).toString());

const el = (sel) => document.querySelector(sel);
const logEl = () => el('#log');

function cellLabel(r, c) {
  return `${ROWS[r]}${COLS[c]}`;
}

function log(msg) {
  const l = logEl();
  l.textContent = (msg + '\n' + l.textContent).slice(0, 4000);
}

function buildBoard(container, clickable) {
  container.innerHTML = '';
  // Header row
  container.appendChild(labelCell(''));
  for (const col of COLS) container.appendChild(labelCell(col));
  // Rows
  for (let r = 0; r < 10; r++) {
    container.appendChild(labelCell(ROWS[r]));
    const rowWrap = document.createElement('div');
    rowWrap.className = 'cells';
    for (let c = 0; c < 10; c++) {
      const cell = document.createElement('div');
      cell.className = 'cell' + (clickable ? ' clickable' : '');
      cell.dataset.r = r;
      cell.dataset.c = c;
      cell.title = cellLabel(r, c);
      rowWrap.appendChild(cell);
    }
    container.appendChild(rowWrap);
  }
}

function labelCell(text) {
  const d = document.createElement('div');
  d.className = 'label';
  d.textContent = text;
  return d;
}

function applyBoardState(container, data, revealShips) {
  const cells = container.querySelectorAll('.cell');
  const key = (r, c) => `${r},${c}`;
  const hits = new Set(data.hits.map((p) => key(p[0], p[1])));
  const misses = new Set(data.misses.map((p) => key(p[0], p[1])));

  const sunkCoords = new Set();
  if (revealShips) {
    for (const s of data.ships || []) {
      if (s.sunk) for (const p of s.coords) sunkCoords.add(key(p[0], p[1]));
    }
  }

  const shipCoords = new Set();
  if (revealShips) {
    for (const s of data.ships || []) for (const p of s.coords) shipCoords.add(key(p[0], p[1]));
  }

  cells.forEach((cell) => {
    const r = parseInt(cell.dataset.r);
    const c = parseInt(cell.dataset.c);
    const k = key(r, c);
    cell.classList.remove('hit', 'miss', 'ship', 'sunk');
    if (hits.has(k)) cell.classList.add('hit');
    else if (misses.has(k)) cell.classList.add('miss');
    else if (revealShips && shipCoords.has(k)) cell.classList.add('ship');
    if (sunkCoords.has(k)) cell.classList.add('sunk');
  });
}

async function fetchState() {
  const res = await fetch('/api/state');
  if (!res.ok) throw new Error('Failed to fetch state');
  return await res.json();
}

async function newGame(autoPlace, manual) {
  const res = await fetch('/api/new-game', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_place: manual ? false : !!autoPlace }),
  });
  if (!res.ok) throw new Error('Failed to start new game');
  log('New game started.' + (manual ? ' Manual placement enabled.' : ''));
}

async function fireAt(label) {
  const res = await fetch('/api/fire', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cell: label }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Shot failed');
  return data;
}

async function placeShip(startLabel, orient) {
  const res = await fetch('/api/place', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start: startLabel, orient }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Placement failed');
  return data;
}

function updateSunkSummaries(state) {
  el('#humanSunk').textContent = `AI sunk: ${state.ai_sunk?.join(', ') || 'None'}`;
  el('#aiSunk').textContent = `You sunk: ${state.human_sunk?.join(', ') || 'None'}`;
}

async function refresh() {
  const state = await fetchState();
  const hb = state.human;
  const ab = state.ai;
  applyBoardState(el('#humanBoard'), hb, true);
  applyBoardState(el('#aiBoard'), ab, false);
  updateSunkSummaries(state);
  // Placement UI
  const placing = !!state.placing;
  const panel = el('#placementPanel');
  panel.hidden = !placing;
  if (placing) {
    const next = state.next_ship;
    el('#placementPrompt').textContent = `Next ship: ${next?.name} (size ${next?.size}). Choose start cell and orientation.`;
    el('#aiBoard').classList.add('disabled');
  } else {
    el('#aiBoard').classList.remove('disabled');
  }
  if (state.over) {
    log(state.winner === 'human' ? 'You win! 🎉' : 'General Bones wins. 💀');
  }
}

function setup() {
  buildBoard(el('#humanBoard'), false);
  buildBoard(el('#aiBoard'), true);

  el('#newGameBtn').addEventListener('click', async () => {
    const auto = el('#autoPlace').checked;
    const manual = el('#manualPlace').checked;
    await newGame(auto, manual);
    await refresh();
  });

  el('#aiBoard').addEventListener('click', async (e) => {
    if (el('#aiBoard').classList.contains('disabled')) {
      log('Finish placing your ships before firing.');
      return;
    }
    const target = e.target.closest('.cell');
    if (!target) return;
    const r = parseInt(target.dataset.r);
    const c = parseInt(target.dataset.c);
    const label = cellLabel(r, c);
    try {
      const data = await fireAt(label);
      const h = data.human;
      const a = data.ai;
      log(`You fired ${h.label}: ${h.result}${h.sunk ? ` (${h.sunk} sunk)` : ''}`);
      if (a) log(`AI fired ${a.label}: ${a.result}${a.sunk ? ` (${a.sunk} sunk)` : ''}`);
      await refresh();
    } catch (err) {
      log(`Error: ${err.message || err}`);
    }
  });

  // Prefill placement start by clicking on your board
  el('#humanBoard').addEventListener('click', (e) => {
    const target = e.target.closest('.cell');
    if (!target) return;
    const r = parseInt(target.dataset.r);
    const c = parseInt(target.dataset.c);
    el('#placeStart').value = cellLabel(r, c);
  });

  el('#placeBtn').addEventListener('click', async () => {
    const start = el('#placeStart').value.trim().toUpperCase();
    const orient = el('#placeOrient').value;
    if (!start) { log('Enter a start cell like A1.'); return; }
    try {
      const res = await placeShip(start, orient);
      log(`Placed ship${res.done ? '. All ships placed! Game begins.' : ''}`);
      await refresh();
    } catch (err) {
      log(`Placement error: ${err.message || err}`);
    }
  });

  // Start initial game automatically
  newGame(true, false).then(refresh).catch((e) => log(`Startup error: ${e.message || e}`));
}

document.addEventListener('DOMContentLoaded', setup);
