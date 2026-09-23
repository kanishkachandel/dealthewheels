/* DEALTHEWHEELS interview studio — drives the real API and narrates every result. */

const VENDOR_COLOR = { 'Vendor One': 'var(--v1)', 'Vendor Two': 'var(--v2)', 'Vendor Three': 'var(--v3)' };
const ORDER = [...document.querySelectorAll('.step')].map(b => b.dataset.action);
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const color = name => VENDOR_COLOR[name] || 'var(--mint)';
const short = name => esc(String(name).replace('Vendor ', 'V'));
const sleep = ms => new Promise(r => setTimeout(r, ms));

let token = '';
let playing = false;

/* ---------------------------------------------------------------- plumbing */

function pill(id, text, state) {
  const node = $(id);
  node.className = `pill ${state || ''}`;
  node.innerHTML = `<i class="dot"></i> ${esc(text)}`;
}

function log(event, detail = '') {
  const stamp = new Date().toLocaleTimeString([], { hour12: false });
  $('log').insertAdjacentHTML('afterbegin',
    `<div><time>${stamp}</time><span class="ev">${esc(event)} <span style="color:var(--muted)">${esc(detail)}</span></span></div>`);
}

async function api(method, path) {
  const started = performance.now();
  const response = await fetch(path, { method, headers: { Authorization: `Bearer ${token}` } });
  const ms = Math.round(performance.now() - started);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.detail || `${response.status} ${response.statusText}`);
  return { body, ms, call: `${method} ${path}`, status: response.status };
}

async function signIn() {
  const response = await fetch('/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' }),
  });
  if (!response.ok) throw new Error('admin login failed');
  token = (await response.json()).access_token;
  pill('pill-auth', 'JWT: admin', 'ok');
}

/* ---------------------------------------------------------------- pieces */

function bars(standings) {
  if (!standings || !standings.rows.length) return;
  const total = standings.total_trips;
  $('bars').innerHTML = standings.rows.map(row => {
    const owed = row.running_shortfall;
    const owedClass = owed > 0.0001 ? 'owed-pos' : owed < -0.0001 ? 'owed-neg' : '';
    return `<div class="bar-row">
      <span class="bar-name"><i class="swatch" style="background:${color(row.vendor_name)}"></i>${esc(row.vendor_name)}</span>
      <span class="track">
        <span class="fill" style="width:${row.actual_percent}%;background:${color(row.vendor_name)}"></span>
        <span class="target" style="left:${row.target_percent}%" data-label="promised ${row.target_percent}%"></span>
      </span>
      <span class="bar-meta"><b>${row.allocated_trips}</b> trips · <b>${row.actual_percent}%</b><br>
        owed <span class="${owedClass}">${owed > 0 ? '+' : ''}${row.running_shortfall}</span> · ${row.free_cabs} cabs free</span>
    </div>`;
  }).join('') + `<p class="bar-meta" style="text-align:left;margin:2px 0 0">${total} trips allocated in this pool.</p>`;
  pill('pill-trips', `${total} trips allocated`, total ? 'ok' : '');
}

function traceTable(decision, caption) {
  if (!decision || !decision.length) return '';
  const rows = decision.map(row => {
    const cls = row.winner ? 'winner' : row.eligible ? '' : 'blocked';
    const status = row.winner ? '← picked' : row.eligible ? 'eligible' : `<span class="why">${esc(row.reason)}</span>`;
    return `<tr class="${cls}">
      <td>${esc(row.vendor_name)}</td>
      <td class="num">${row.target_percent}%</td>
      <td class="num">${row.expected_so_far}</td>
      <td class="num">${row.allocated}</td>
      <td class="num"><b>${row.shortfall}</b></td>
      <td>${status}</td></tr>`;
  }).join('');
  return `<h3>${esc(caption || 'Why this vendor won')}</h3>
    <div class="formula">shortfall = <b>target% × (trips so far + 1)</b> − <b>trips already allocated</b>
      &nbsp;·&nbsp; highest shortfall wins &nbsp;·&nbsp; ties break on vendor id, never on randomness</div>
    <table><thead><tr><th>Vendor</th><th class="num">Target</th><th class="num">Expected</th>
      <th class="num">Allocated</th><th class="num">Shortfall</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>`;
}

const chips = steps => `<div class="chips">${steps.map(step =>
  `<span class="chip" style="border-color:${color(step.vendor_name)};animation-delay:${step.trip_number * 45}ms">
    <i>#${step.trip_number}</i> ${short(step.vendor_name)}</span>`).join('')}</div>`;

const kpi = (label, value, good) =>
  `<div class="kpi ${good ? 'good' : ''}"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;

function standingsTable(standings, caption) {
  const rows = standings.rows.map(row => `<tr>
    <td>${esc(row.vendor_name)}</td><td class="num">${row.target_percent}%</td>
    <td class="num">${row.actual_percent}%</td><td class="num">${row.allocated_trips}</td>
    <td class="num">${row.expected_trips}</td><td class="num">${row.running_shortfall}</td></tr>`).join('');
  return `<h3>${esc(caption)} — ${standings.total_trips} trips</h3>
    <table><thead><tr><th>Vendor</th><th class="num">Promised</th><th class="num">Actual</th>
      <th class="num">Trips</th><th class="num">Expected</th><th class="num">Running shortfall</th></tr>
    </thead><tbody>${rows}</tbody></table>`;
}

/* ---------------------------------------------------------------- renderers */

const RENDER = {
  setup: d => `<h3>Contract configuration</h3><div class="kpis">
      ${d.setup.vendors.map(v => kpi(v.name, `${v.target_percent}%`)).join('')}
      ${kpi('Isolated zone', d.setup.zone)}</div>
    <p class="bar-meta" style="text-align:left">Each vendor also gets its own login, and a share row for
    <b>both</b> the normal and the escort stream.</p>`,

  'allocate-one': d => traceTable(d.decision, `Decision for trip #${d.trip_number}`),

  'run-ten': d => `${chips(d.steps)}${traceTable(d.steps[d.steps.length - 1].decision, 'The arithmetic on the 10th trip')}`,

  'escort-stream': d => `${chips(d.steps)}
    ${standingsTable(d.standings, 'Escort pool')}
    ${standingsTable(d.normal_standings, 'Normal pool (untouched by the escort run)')}`,

  'capacity-guard': d => `<div class="kpis">
      ${kpi('Blocked vendor', d.blocked_vendor)}
      ${kpi('Its free cabs', '0')}
      ${kpi('Its shortfall (still the largest)', d.blocked_row ? d.blocked_row.shortfall : '—')}</div>
    ${traceTable(d.decision, 'The most-owed vendor was skipped on purpose')}`,

  rejection: d => `<div class="kpis">
      ${kpi('Rejected by', d.rejected_vendor)}${kpi('Re-offered to', d.reassigned_vendor, true)}
      ${kpi('Cool-off until', new Date(d.cooloff_until).toLocaleTimeString())}</div>
    <h3>Audit trail for this trip</h3><div class="chips">
      ${d.audit_trail.map(e => `<span class="chip">${esc(e)}</span>`).join('<span class="chip" style="border:0">→</span>')}</div>
    ${traceTable(d.decision, 'The original offer')}`,

  report: d => `${standingsTable(d.standings, 'Normal trips today')}
    ${standingsTable(d.escort_standings, 'Escort trips today')}
    <p class="bar-meta" style="text-align:left">The same endpoint answers a whole month with
    <code>GET /api/reports/share?month=${esc(d.month)}</code>.</p>`,

  'carry-forward': d => `<h3>Day 1 — Vendor Two has no cabs at all</h3>${chips(d.day_one.steps)}
    ${standingsTable(d.day_one.standings, 'End of day 1')}
    <h3>Day 2 — Vendor Two is back online</h3>${chips(d.day_two.steps)}
    <p class="bar-meta" style="text-align:left">Yesterday's debt is still inside today's arithmetic, so
    Vendor Two is repaid first. No nightly reset job exists — that is the point.</p>`,

  determinism: d => `<div class="kpis">
      ${kpi('Run 1 vs run 2', d.identical ? 'IDENTICAL' : 'DIFFERENT', d.identical)}
      ${kpi('Trips replayed', d.run_one.length)}</div>
    <h3>Allocation sequence</h3>
    <div class="chips">${d.run_one.map((n, i) => `<span class="chip" style="border-color:${color(n)}"><i>#${i + 1}</i> ${short(n)}</span>`).join('')}</div>
    <div class="chips" style="margin-top:8px">${d.run_two.map((n, i) => `<span class="chip" style="border-color:${color(n)}"><i>#${i + 1}</i> ${short(n)}</span>`).join('')}</div>
    <h3>SHA-256 of each run</h3><div class="hashes">
      <div class="mono">run 1 · ${esc(d.hash_one)}</div><div class="mono">run 2 · ${esc(d.hash_two)}</div></div>`,

  race: d => `<div class="kpis">
      ${kpi('Concurrent requests', d.workers)}${kpi('Free cabs', d.free_cabs_before)}
      ${kpi('Assigned', d.assigned, d.safe)}${kpi('Cleanly refused', d.refused)}
      ${kpi('No vendor oversold', d.no_vendor_oversold ? 'CONFIRMED' : 'FAILED', d.no_vendor_oversold)}
      ${kpi('Wall time', d.elapsed_ms + ' ms')}</div>
    <h3>Cabs left per vendor</h3><div class="chips">
      ${Object.entries(d.remaining_cabs).map(([name, count]) => `<span class="chip" style="border-color:${color(name)}">${short(name)} · ${count}</span>`).join('')}</div>
    <p class="bar-meta" style="text-align:left">Losers received a clean <code>NO_ELIGIBLE_VENDOR</code>
    domain error — never a half-written allocation.</p>`,

  convergence: d => `<div class="kpis">
      ${kpi('Trips simulated', d.total_trips.toLocaleString())}${kpi('Days', d.days)}
      ${kpi('Worst drift', d.worst_drift_percent + '%', true)}${kpi('Compute time', d.elapsed_ms + ' ms')}</div>
    <h3>After ${d.days} days of uneven volume</h3>
    <table><thead><tr><th>Vendor</th><th class="num">Promised</th><th class="num">Actual</th>
      <th class="num">Trips</th><th class="num">Drift</th><th class="num">Residue owed</th></tr></thead><tbody>
      ${d.rows.map(r => `<tr><td>${esc(r.vendor_name)}</td><td class="num">${r.target_percent}%</td>
        <td class="num">${r.actual_percent}%</td><td class="num">${r.allocated.toLocaleString()}</td>
        <td class="num">${r.drift_percent}%</td><td class="num">${r.residue}</td></tr>`).join('')}</tbody></table>
    <h3>Daily volume was deliberately lumpy</h3><div class="chips">
      ${d.timeline.map(t => `<span class="chip"><i>day ${t.day}</i> +${t.trips_today} → ${t.actual_percent.join(' / ')}</span>`).join('')}</div>`,
};

/* ---------------------------------------------------------------- driver */

const ENDPOINT = { snapshot: ['GET', '/api/demo/snapshot'] };
const endpointFor = action => ENDPOINT[action] || ['POST', `/api/demo/${action}`];

async function runStep(action) {
  const button = document.querySelector(`.step[data-action="${action}"]`);
  document.querySelectorAll('.step').forEach(step => step.classList.remove('active'));
  button.classList.add('active');
  $('result').innerHTML = `<p class="empty">Calling the API…</p>`;
  const [method, path] = endpointFor(action);
  try {
    const { body, ms, call, status } = await api(method, path);
    const good = body.identical === false || body.safe === false ? 'bad' : 'good';
    $('result').innerHTML = `
      <p class="headline ${good}">${esc(body.headline)}</p>
      <div class="say"><b>SAY THIS</b>${esc(body.narration)}</div>
      ${(RENDER[action] || (() => ''))(body)}
      <div class="callbar"><span class="verb">${esc(method)}</span>
        <code>${esc(path)}</code> · ${status} · ${ms} ms · bearer token ·
        <code>curl -X ${esc(method)} localhost:8000${esc(path)} -H "Authorization: Bearer $TOKEN"</code></div>`;
    bars(body.standings);
    button.classList.add('done');
    log(button.querySelector('.t').textContent, `${ms} ms`);
  } catch (error) {
    $('result').innerHTML = `<p class="headline bad">${esc(error.message)}</p>
      <p class="empty">Is the API still running? Check <code>/actuator/health</code>.</p>`;
    log('failed', error.message);
    throw error;
  } finally {
    button.classList.remove('active');
  }
}

$('rail').addEventListener('click', async event => {
  const button = event.target.closest('.step');
  if (!button || playing) return;
  await runStep(button.dataset.action).catch(() => {});
});

async function playAll() {
  playing = true;
  $('play').disabled = true;
  $('stop').disabled = false;
  document.querySelectorAll('.step').forEach(step => step.classList.remove('done'));
  for (const action of ORDER) {
    if (!playing) break;
    try { await runStep(action); } catch { break; }
    await sleep(2600);
  }
  playing = false;
  $('play').disabled = false;
  $('stop').disabled = true;
}

$('play').onclick = playAll;
$('stop').onclick = () => { playing = false; log('demo paused by presenter'); };

/* Right arrow / space advances one step — handy while narrating. */
document.addEventListener('keydown', event => {
  if (playing || !['ArrowRight', ' '].includes(event.key)) return;
  const done = [...document.querySelectorAll('.step.done')].length;
  if (done < ORDER.length) { event.preventDefault(); runStep(ORDER[done]).catch(() => {}); }
});

(async function boot() {
  try {
    const health = await (await fetch('/actuator/health')).json();
    pill('pill-api', `API ${health.status}`, 'ok');
  } catch { pill('pill-api', 'API unreachable', 'bad'); }
  try {
    await signIn();
    const { body } = await api('GET', '/api/demo/snapshot');
    bars(body.standings);
    log('signed in as admin', 'JWT stored in memory only');
  } catch (error) { pill('pill-auth', 'auth failed', 'bad'); log('auth failed', error.message); }
})();
