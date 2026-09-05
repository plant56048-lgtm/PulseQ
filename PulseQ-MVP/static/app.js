let state;
const $=id=>document.getElementById(id);
async function api(url, body){const r=await fetch(url,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await r.json();state=data.state||data;render();return data}
function esc(v){return String(v||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){if(!state)return;const p=state.patient, q=state.patient_info, serving=state.serving;
 $('pName').textContent=p.name;$('token').textContent=p.token;$('dept').textContent=p.department;$('apptTime').textContent=p.time;$('doctor').textContent=p.doctor;$('appointmentDoctor').textContent=p.doctor;$('appointmentDetail').textContent=`${p.department} · ${p.date} · ${p.time} · ${p.appointment_id}`;$('phaseText').textContent=q.phase==='Get ready'?'Your appointment is approaching. Please be ready.':q.phase==='In consultation'?'You are currently in consultation.':'Track your live position and estimated waiting time.';
 $('position').textContent=q.position||'—';$('ahead').textContent=q.ahead;$('estimate').textContent=q.estimate;$('doctorStatus').textContent=state.doctor_status;$('doctorStatus').className='badge '+state.doctor_status.toLowerCase().replace(' ','-');$('progress').style.width=q.position?Math.max(12,100-(q.position-1)*20)+'%':'0%';$('checkin').style.display=p.arrived?'none':'block';
 $('notifications').innerHTML=state.notifications.map(n=>`<div class="notice ${n.kind}"><b>${esc(n.title)}</b><span>${esc(n.message)}</span></div>`).join('');$('serving').textContent=serving?serving.token:'—';$('servingName').textContent=serving?serving.name:'No patient currently called';$('statusSelect').value=state.doctor_status;
 $('staffQueue').innerHTML=state.next_patients.map((x,i)=>`<div class="queue-row"><span>${i+1}</span><b>${x.token}</b><small>${esc(x.name)}</small></div>`).join('')||'<p>No waiting patients.</p>';$('displayServing').textContent=serving?serving.token:'—';$('displayNext').innerHTML=state.next_patients.map(x=>`<span>${x.token}</span>`).join('');$('displayWait').textContent=q.estimate;
 $('emergencyList').innerHTML=state.emergencies.length?state.emergencies.map(e=>`<div class="case"><div><b>${e.id}</b><span>${e.time} · ${esc(e.location)}</span><small>${esc(e.problem)} · ${esc(e.conscious)}</small></div><select onchange="emergencyStatus('${e.id}',this.value)">${['New','Reviewing','Accepted','Resolved'].map(s=>`<option ${s===e.status?'selected':''}>${s}</option>`).join('')}</select></div>`).join(''):'<p>No emergency cases today.</p>'}
function populate(dept,doctor){$(dept).innerHTML=Object.keys(DOCTORS).map(x=>`<option>${x}</option>`).join('');function update(){const list=DOCTORS[$(dept).value];$(doctor).innerHTML=list.map(x=>`<option>${x}</option>`).join('')} $(dept).onchange=update;update()}
async function askQueueAssistant(){
  try {
    const response = await fetch('/api/queue-assistant', {method: 'POST', headers: {'Content-Type': 'application/json'}});
    const data = await response.json();
    if (!state) state = {notifications: []};
    state.notifications.unshift({title: 'PulseQ assistant', message: data.message || 'No update available right now.', time: 'Just now', kind: 'info'});
    state.notifications = state.notifications.slice(0, 8);
    render();
  } catch (error) {
    alert('PulseQ assistant is unavailable right now.');
  }
}
function checkin(){api('/api/checkin',{})} function staff(action){api('/api/staff',{action})}function setStatus(){api('/api/staff',{action:'status',status:$('statusSelect').value})}function emergencyStatus(id,status){api('/api/emergency-status',{id,status})}function showEmergency(){$('emergencyDialog').showModal()} function resetDemo(){api('/api/reset',{})}
$('bookingForm').onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));await api('/api/book',data);$('bookingResult').innerHTML=`<p>APPOINTMENT CONFIRMED</p><strong>${state.patient.token}</strong><b>${esc(state.patient.doctor)}</b><span>${esc(state.patient.department)} · ${esc(state.patient.date)} · ${esc(state.patient.time)}</span>`;$('patient').scrollIntoView({behavior:'smooth'})};
$('walkinForm').onsubmit=async e=>{e.preventDefault();const d=await api('/api/walkin',Object.fromEntries(new FormData(e.target)));$('walkResult').innerHTML=`<div class="success-box">Token generated: <b>${d.token}</b></div>`;e.target.reset()};$('emergencyForm').onsubmit=async e=>{e.preventDefault();await api('/api/emergency',Object.fromEntries(new FormData(e.target)));$('emergencyDialog').close();document.querySelector('[data-page="staff"]').click()};
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));document.querySelectorAll('[data-page]').forEach(x=>x.classList.remove('active'));$(b.dataset.page).classList.add('active');b.classList.add('active')});populate('bookingDepartment','bookingDoctor');populate('walkDepartment','walkDoctor');api('/api/state');
