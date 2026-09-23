const date = document.querySelector('#date');
date.value = new Date().toISOString().slice(0, 10);
const message = document.querySelector('#message');
const cards = document.querySelector('#cards');

document.querySelector('#refresh').onclick = async () => {
  const token = document.querySelector('#token').value;
  if (!token) return message.textContent = 'An admin bearer token is required.';
  message.textContent = 'Loading share report…'; cards.replaceChildren();
  const response = await fetch(`/api/reports/share?date=${date.value}`, {headers: {Authorization: `Bearer ${token}`}});
  if (!response.ok) return message.textContent = `Could not load report (${response.status}).`;
  const report = await response.json();
  message.textContent = `${report.total_trips} assigned trips on ${report.date}.`;
  report.rows.forEach(row => {
    const card = document.createElement('article'); card.className = 'card';
    card.innerHTML = `<strong>${row.vendor_name}</strong><div class="bar"><i style="width:${Math.min(row.actual_percent,100)}%"></i></div><div class="numbers"><span>Actual ${row.actual_percent}%</span><span>Target ${row.target_percent}%</span></div><small>Shortfall ${row.running_shortfall}</small>`;
    cards.append(card);
  });
};
