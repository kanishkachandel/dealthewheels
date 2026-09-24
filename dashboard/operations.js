const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const TYPES = [{value:'NORMAL',label:'Normal'},{value:'ESCORT',label:'Escort / marshal'}];
const COLORS = ['#89aaff','#f6c56c','#66e2bd','#c0a5ff','#ff8798','#8ed1ee','#efaa79'];
const localDate = (date=new Date()) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
let token = '';
let zones = [];
let vendors = [];
let trips = [];
let editingVendor = null;

async function api(method, path, data) {
  const headers = {Authorization:`Bearer ${token}`};
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {method, headers, body:data === undefined ? undefined : JSON.stringify(data)});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.message || body.detail;
    const message = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body;
}

function setMessage(id, message, kind='') {
  const element = $(id);
  element.textContent = message;
  element.className = `message ${kind}`;
}

function showView(view) {
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.view === view));
  document.querySelectorAll('.view').forEach(section => section.classList.toggle('hidden', section.id !== `view-${view}`));
}

function poolTotal(zoneId, tripType) {
  return vendors.flatMap(v => v.shares || [])
    .filter(share => share.zone_id === zoneId && share.trip_type === tripType)
    .reduce((sum, share) => sum + Number(share.target_percent), 0);
}

function renderPoolChecks() {
  const combinations = zones.flatMap(zone => TYPES.map(type => ({zone,type,total:poolTotal(zone.id,type.value)})));
  $('pool-checks').innerHTML = combinations.map(pool => {
    const ready = Math.abs(pool.total - 100) <= 0.01;
    return `<article class="pool-check ${ready?'ready':'incomplete'}"><span>${escapeHtml(pool.zone.label)} · ${escapeHtml(pool.type.label)}</span><b>${pool.total.toFixed(2)}% ${ready?'✓':'· needs 100%'}</b></article>`;
  }).join('');
  const readyCount = combinations.filter(pool => Math.abs(pool.total - 100) <= 0.01).length;
  $('stat-pools').textContent = `${readyCount} / ${combinations.length}`;
  $('vendor-count').textContent = String(vendors.length);
  $('stat-vendors').textContent = String(vendors.filter(v => v.active).length);
}

function renderVendors() {
  if (!vendors.length) {
    $('vendor-list').innerHTML = '<div class="card empty">No vendors yet. Add your first vendor and set the target percentages for its zones and trip types.</div>';
    renderPoolChecks();
    return;
  }
  $('vendor-list').innerHTML = vendors.map((vendor,index) => {
    const color = COLORS[index % COLORS.length];
    const shares = (vendor.shares || []).map(share => `<span class="share-pill">${escapeHtml(share.zone_label)} · ${share.trip_type==='NORMAL'?'Normal':'Escort'} <b>${Number(share.target_percent).toFixed(2)}%</b></span>`).join('');
    return `<article class="vendor-card"><div class="vendor-head"><div><h3><i class="swatch" style="background:${color}"></i>${escapeHtml(vendor.name)}</h3><span class="vendor-sub">${vendor.active_cab_count} available cab${vendor.active_cab_count===1?'':'s'} · ${vendor.active?'Active':'Inactive'}</span></div><span class="badge ${vendor.active?'':'off'}">${vendor.active?'ACTIVE':'PAUSED'}</span></div><div class="share-pills">${shares || '<span class="vendor-sub">No share pools configured</span>'}</div><div class="vendor-foot"><span class="vendor-sub">Contract allocations are tracked per pool</span><button class="table-action" data-edit-vendor="${escapeHtml(vendor.id)}">Edit vendor</button></div></article>`;
  }).join('');
  $('vendor-list').querySelectorAll('[data-edit-vendor]').forEach(button => button.addEventListener('click', () => openVendor(vendors.find(v => v.id === button.dataset.editVendor))));
  renderPoolChecks();
}

function renderZones() {
  const previousZone = $('pool-zone').value;
  $('pool-zone').innerHTML = zones.map(z => `<option value="${escapeHtml(z.id)}">${escapeHtml(z.label)}</option>`).join('');
  if (zones.some(zone => zone.id === previousZone)) $('pool-zone').value = previousZone;
  $('report-form').elements.zone_id.innerHTML = zones.map(z => `<option value="${escapeHtml(z.id)}">${escapeHtml(z.label)}</option>`).join('');
}

function renderShareFields(vendor=null) {
  $('share-fields').innerHTML = zones.flatMap(zone => TYPES.map(type => {
    const current = vendor?.shares?.find(s => s.zone_id === zone.id && s.trip_type === type.value);
    const value = current ? Number(current.target_percent) : 0;
    const name = `${escapeHtml(zone.id)}|${type.value}`;
    return `<div class="share-input"><label for="share-${name}">${escapeHtml(zone.label)} · ${escapeHtml(type.label)}</label><input id="share-${name}" data-zone="${escapeHtml(zone.id)}" data-type="${type.value}" type="number" min="0" max="100" step="0.01" value="${value}" required></div>`;
  })).join('');
}

function openVendor(vendor=null) {
  editingVendor = vendor;
  const form = $('vendor-form');
  form.reset();
  form.elements.vendor_id.value = vendor?.id || '';
  form.elements.name.value = vendor?.name || '';
  form.elements.active_cab_count.value = vendor?.active_cab_count ?? 5;
  form.elements.active.checked = vendor?.active ?? true;
  $('dialog-title').textContent = vendor ? 'Edit vendor' : 'Add vendor';
  $('dialog-help').textContent = vendor ? 'Update current cab availability and contract targets.' : 'Add the vendor’s operating capacity and target share in each pool.';
  $('login-user-field').classList.toggle('hidden', Boolean(vendor));
  $('login-pass-field').classList.toggle('hidden', Boolean(vendor));
  form.elements.username.required = !vendor;
  form.elements.password.required = !vendor;
  renderShareFields(vendor);
  setMessage('vendor-form-message','');
  $('vendor-dialog').showModal();
}

function renderTrips() {
  $('trip-rows').innerHTML = trips.length ? trips.map(trip => {
    const date = new Date(trip.created_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const badge = trip.status === 'COMPLETED' ? 'badge' : 'badge warn';
    const action = trip.status === 'ASSIGNED' ? `<button class="table-action" data-complete-trip="${escapeHtml(trip.id)}">Complete</button> <button class="table-action" style="border-color:#70414a;color:#ffabb5" data-reject-trip="${escapeHtml(trip.id)}">Vendor rejected</button>` : '';
    return `<tr><td>${escapeHtml(date)}</td><td><code>${escapeHtml(trip.id.slice(0,8))}</code></td><td>${escapeHtml(trip.zone_label)}</td><td>${trip.trip_type==='ESCORT'?'Escort':'Normal'}</td><td><b>${escapeHtml(trip.vendor_name || 'Unassigned')}</b></td><td><span class="${badge}">${escapeHtml(trip.status)}</span> ${action}</td></tr>`;
  }).join('') : '<tr><td colspan="6" class="empty">No trips have been allocated yet.</td></tr>';
  $('trip-rows').querySelectorAll('[data-complete-trip]').forEach(button => button.addEventListener('click', () => finishTrip(button.dataset.completeTrip, button)));
  $('trip-rows').querySelectorAll('[data-reject-trip]').forEach(button => button.addEventListener('click', () => recordRejection(button.dataset.rejectTrip, button)));
  $('stat-trips').textContent = String(trips.length);
}

async function finishTrip(tripId, button) {
  button.disabled = true;
  try {
    await api('POST', `/api/trips/${encodeURIComponent(tripId)}/complete`);
    await refreshData();
    setMessage('trip-message','Trip completed. The assigned vendor’s cab is available again.','success');
  } catch (error) {
    button.disabled = false;
    setMessage('trip-message',error.message,'error');
  }
}

async function recordRejection(tripId, button) {
  if (!window.confirm('Record that the assigned vendor rejected this trip? The vendor will enter cool-off and the trip will be reallocated.')) return;
  button.disabled = true;
  try {
    const result = await api('POST', `/api/trips/${encodeURIComponent(tripId)}/reject-by-dispatch`);
    await refreshData();
    const reassigned = vendors.find(v => v.id === result.assigned_vendor_id)?.name || 'another eligible vendor';
    setMessage('trip-message',`Vendor rejection recorded. Trip reassigned to ${reassigned}; the rejecting vendor is in cool-off.`,'success');
  } catch (error) {
    button.disabled = false;
    setMessage('trip-message',error.message,'error');
  }
}

async function refreshPool() {
  const zoneId = $('pool-zone').value;
  const tripType = $('pool-type').value;
  const zone = zones.find(item => item.id === zoneId);
  if (!zone) return;
  const totalShare = poolTotal(zoneId, tripType);
  const ready = Math.abs(totalShare - 100) <= 0.01;
  $('pool-summary').innerHTML = `<span class="pool-state ${ready?'ready':'incomplete'}">${escapeHtml(zone.label)} · ${tripType==='NORMAL'?'Normal':'Escort'} contract: <b>${totalShare.toFixed(2)}%</b> ${ready?'· ready to allocate':'· configure shares to total 100%'}</span>`;
  try {
    const today = localDate();
    const report = await api('GET', `/api/reports/share?date=${today}&zone_id=${encodeURIComponent(zoneId)}&trip_type=${tripType}`);
    $('share-chart').innerHTML = report.rows.length ? report.rows.map((row,index) => {
      const width = Math.min(Math.max(Number(row.actual_percent),0),100);
      return `<div class="share-row"><span class="share-name"><i class="swatch" style="background:${COLORS[index%COLORS.length]}"></i>${escapeHtml(row.vendor_name)}</span><span class="share-track"><span class="share-fill" style="display:block;width:${width}%;background:${COLORS[index%COLORS.length]}"></span><i class="target-mark" style="left:${Math.min(Number(row.target_percent),100)}%" title="Target ${row.target_percent}%"></i></span><span class="share-values"><b>${row.actual_percent}%</b> actual<br>${row.target_percent}% target</span></div>`;
    }).join('') + `<div class="pool-summary">${report.total_trips} trips assigned in this pool today. Dashed marks show each contract target.</div>` : '<div class="empty">No vendors are configured for this pool yet.</div>';
  } catch (error) {
    $('share-chart').innerHTML = `<div class="empty">Could not load today’s share report: ${escapeHtml(error.message)}</div>`;
  }
}

async function refreshData() {
  const [zoneData, vendorData, tripData] = await Promise.all([
    api('GET','/api/zones'), api('GET','/api/vendors'), api('GET','/api/trips?limit=50')
  ]);
  zones = zoneData;
  vendors = vendorData;
  trips = tripData;
  renderZones();
  renderVendors();
  renderTrips();
  await refreshPool();
}

function reportDateControl() {
  const form = $('report-form');
  const period = form.elements.period.value;
  const input = form.elements.date;
  if (period === 'month') {
    input.type = 'month';
    input.value = localDate().slice(0,7);
  } else {
    input.type = 'date';
    input.value = localDate();
  }
}

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => showView(tab.dataset.view)));
$('pool-zone').addEventListener('change', refreshPool);
$('pool-type').addEventListener('change', refreshPool);
$('refresh-trips').addEventListener('click', async () => { try { trips = await api('GET','/api/trips?limit=50'); renderTrips(); } catch (error) { setMessage('trip-message',error.message,'error'); } });
$('logout').addEventListener('click', () => { token=''; vendors=[]; trips=[]; zones=[]; $('app-view').classList.add('hidden'); $('login-view').classList.remove('hidden'); $('logout').classList.add('hidden'); });
$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  setMessage('login-message','Signing in…');
  try {
    const response = await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:form.get('username'),password:form.get('password')})});
    const body = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(body.message || body.detail || 'Sign in failed');
    if (body.role !== 'ADMIN') throw new Error('This operations dashboard requires an administrator account.');
    token = body.access_token;
    await refreshData();
    $('login-view').classList.add('hidden');
    $('app-view').classList.remove('hidden');
    $('logout').classList.remove('hidden');
    setMessage('login-message','');
  } catch(error) { setMessage('login-message',error.message,'error'); }
});

$('add-vendor').addEventListener('click', () => openVendor());
$('close-dialog').addEventListener('click', () => $('vendor-dialog').close());
$('cancel-vendor').addEventListener('click', () => $('vendor-dialog').close());
$('vendor-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const vendorId = data.get('vendor_id');
  const shares = [...form.querySelectorAll('[data-zone][data-type]')].map(input => ({zone_id:input.dataset.zone,trip_type:input.dataset.type,target_percent:Number(input.value)}));
  const payload = {name:data.get('name').trim(),active_cab_count:Number(data.get('active_cab_count')),active:form.elements.active.checked,shares};
  if (!vendorId) { payload.username=data.get('username').trim(); payload.password=data.get('password'); }
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  setMessage('vendor-form-message','Saving vendor and share settings…');
  try {
    await api(vendorId?'PUT':'POST',vendorId?`/api/vendors/${encodeURIComponent(vendorId)}`:'/api/vendors',payload);
    await refreshData();
    $('vendor-dialog').close();
    showView('vendors');
  } catch(error) { setMessage('vendor-form-message',error.message,'error'); }
  finally { button.disabled = false; }
});

$('trip-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const distance = Number(form.elements.distance_km.value);
  const tripType = form.elements.trip_type.value;
  const zone = zones.find(item => distance >= item.min_km && (item.max_km == null || distance < item.max_km));
  if (!zone) { setMessage('trip-message','No configured distance zone covers that trip distance.','error'); return; }
  const total = poolTotal(zone.id,tripType);
  if (Math.abs(total-100)>0.01) { setMessage('trip-message',`${zone.label} / ${tripType} shares currently total ${total.toFixed(2)}%. Set them to exactly 100% in Vendors & shares before allocating.`,'error'); showView('vendors'); return; }
  const button=form.querySelector('button[type="submit"]'); button.disabled=true;
  $('allocation-result').classList.add('hidden');
  setMessage('trip-message','Checking eligibility and allocating…');
  try {
    const result = await api('POST','/api/trips',{distance_km:distance,trip_type:tripType,idempotency_key:`dispatch-${crypto.randomUUID()}`});
    const assigned = vendors.find(v => v.id === result.assigned_vendor_id);
    const name = assigned?.name || 'Assigned vendor';
    $('allocation-result').innerHTML = `<span class="result-label">Vendor assigned · ${escapeHtml(zone.label)} · ${tripType==='NORMAL'?'Normal':'Escort'}</span><strong>${escapeHtml(name)}</strong><small>Trip ${escapeHtml(result.id.slice(0,8))} saved · ${result.status} · Record this trip as complete when service ends to return the cab to availability.</small>`;
    $('allocation-result').classList.remove('hidden');
    setMessage('trip-message','Allocation saved successfully.','success');
    form.elements.distance_km.value='';
    trips = await api('GET','/api/trips?limit=50'); renderTrips();
    vendors = await api('GET','/api/vendors'); renderVendors();
    await refreshPool();
  } catch(error) { setMessage('trip-message',error.message,'error'); }
  finally { button.disabled=false; }
});

$('report-form').elements.period.addEventListener('change',reportDateControl);
$('report-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const param = data.get('period')==='month'?'month':'date';
  const query = new URLSearchParams({[param]:data.get('date'),zone_id:data.get('zone_id'),trip_type:data.get('trip_type')});
  setMessage('report-message','Loading contract performance…');
  try {
    const report = await api('GET',`/api/reports/share?${query}`);
    $('report-results').innerHTML = `<p class="pool-summary">${escapeHtml(report.date)} · ${escapeHtml(zones.find(z=>z.id===report.zone_id)?.label || '')} · ${report.trip_type==='NORMAL'?'Normal trips':'Escort trips'} · ${report.total_trips} trips</p><table><thead><tr><th>Vendor</th><th>Promised share</th><th>Actual share</th><th>Trips allocated</th><th>Expected trips</th><th>Running shortfall</th></tr></thead><tbody>${report.rows.map(row=>`<tr><td><b>${escapeHtml(row.vendor_name)}</b></td><td>${row.target_percent}%</td><td>${row.actual_percent}%</td><td>${row.allocated_trips}</td><td>${row.expected_trips}</td><td>${row.running_shortfall>0?'+':''}${row.running_shortfall}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">No share configuration found for this pool.</td></tr>'}</tbody></table>`;
    setMessage('report-message','Report loaded.','success');
  } catch(error) { setMessage('report-message',error.message,'error'); $('report-results').innerHTML=''; }
});

(async function boot(){
  $('today-label').textContent = new Date().toLocaleDateString([], {weekday:'short',month:'short',day:'numeric',year:'numeric'});
  reportDateControl();
  const status=$('system-status');
  try { const response=await fetch('/actuator/health'); const health=await response.json(); if(!response.ok)throw new Error(); status.innerHTML=`<i></i> ${escapeHtml(health.status)} service`; status.classList.add('ok'); }
  catch { status.innerHTML='<i></i> Service unavailable'; }
})();
