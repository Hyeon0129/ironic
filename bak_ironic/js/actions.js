window.API_BASE = window.API_BASE || `${location?.protocol || 'http:'}//${location.hostname || '127.0.0.1'}:8000`;

function showActionMenu() {
  if (selectedServers.size === 0) return;
  const modal = document.getElementById('actionModal');
  if (modal) modal.classList.add('show');
}

function hideActionMenu() {
  const modal = document.getElementById('actionModal');
  if (modal) modal.classList.remove('show');
}

function executeAction(action) {
  const actionNames = {
    'power-on': {label:'Power On', api:'on'},
    'power-off': {label:'Power Off', api:'off'},
    'restart': {label:'Restart', api:'reset'},
    'power-cycle': {label:'Power Cycle', api:'cycle'},
    'uid-on': {label:'UID On'},
    'uid-off': {label:'UID Off'}
  };

  const selected = Array.from(selectedServers);
  if (selected.length === 0) { alert('Please select at least one server'); return; }

  const apimap = actionNames[action];
  if (!apimap) { alert('Unknown action'); return; }

  // Only power actions implemented in backend for now
  if (['power-on','power-off','restart','power-cycle'].includes(action)){
    fetch(`${API_BASE}/actions/power`, { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bmcip: selected, action: apimap.api })
    }).then(r=>r.json()).then(j=>{
      if (!j.ok) { alert(`Failed: ${j.error||'unknown'}`); return; }
      const okCount = Object.values(j.results||{}).filter(x=>x.ok).length;
      alert(`${apimap.label} queued for ${okCount}/${selected.length} servers`);
    }).catch(()=>alert('Request failed'))
    .finally(()=> hideActionMenu());
  } else {
    // UID actions
    fetch(`${API_BASE}/actions/uid`,   { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bmcip: selected, action: action === 'uid-on' ? 'on' : 'off' })
    }).then(r=>r.json()).then(j=>{
      if (!j.ok) { alert(`Failed: ${j.error||'unknown'}`); return; }
      const okCount = Object.values(j.results||{}).filter(x=>x.ok).length;
      alert(`${apimap.label} queued for ${okCount}/${selected.length} servers`);
    }).catch(()=>alert('Request failed'))
    .finally(()=> hideActionMenu());
  }
}

/* ---- action buttons ---- */
$("#btnQuery")?.addEventListener("click", async () => {
  const host = (location && location.hostname) ? location.hostname : "127.0.0.1";
  const startUrls = [ `${API_BASE}/query/start` ];
  let taskId = null;
  for (const url of startUrls){
    try{
      const r = await fetch(url, {method: 'POST'});
      if (!r.ok) continue;
      const j = await r.json();
      if (j.task_id){ taskId = j.task_id; break; }
    }catch(e){/* try next */}
  }
  if (!taskId){
    alert('Failed to start query.sh');
    return;
  }

  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  if (!modal || !titleEl || !barEl || !textEl) return;
  titleEl.textContent = 'Query Running';
  modal.classList.add('show');
  barEl.style.width = '0%';
  textEl.textContent = 'Starting query.sh...';

  
  const statusUrlsBase = [ `${API_BASE}/query/status/` ];
  let done = false;
  async function poll(){
    for (const base of statusUrlsBase){
      try{
        const r = await fetch(base + taskId);
        if (!r.ok) continue;
        const s = await r.json();
        if (s.error) continue;
        const lines = s.lines || [];
  
        const stage = s.stage || lines.slice(-1)[0] || (s.running ? 'Running...' : 'Finished');
        const pct = (typeof s.progress === 'number') ? s.progress : Math.min(95, Math.floor((s.elapsed % 30) / 30 * 95));
        textEl.textContent = stage;
        barEl.style.width = (s.running ? pct : 100) + '%';
        if (!s.running){
          done = true; break;
        }
      }catch(e){/* try next base */}
    }
    if (!done){
      setTimeout(poll, 1000);
    } else {
      setTimeout(()=>{
        modal.classList.remove('show');
        barEl.style.width = '0%';
      }, 1500);
      if (typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
    }
  }
  poll();
});


$("#btnRegister")?.addEventListener("click", async () => {
  const startUrls = [ `${API_BASE}/register/start` ];
  let taskId = null;
  for (const url of startUrls){
    try{
      const r = await fetch(url, {method: 'POST'});
      if (!r.ok) continue;
      const j = await r.json();
      if (j.task_id){ taskId = j.task_id; break; }
    }catch(e){/* try next */}
  }
  if (!taskId){
    alert('Failed to start register.sh');
    return;
  }

  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  if (!modal || !titleEl || !barEl || !textEl) return;
  titleEl.textContent = 'Register Running';
  modal.classList.add('show');
  barEl.style.width = '0%';
  textEl.textContent = 'Starting dashboard_register.sh...';

  
  const statusUrlsBase = [ `${API_BASE}/register/status/` ];
  let done = false;
  async function poll(){
    for (const base of statusUrlsBase){
      try{
        const r = await fetch(base + taskId);
        if (!r.ok) continue;
        const s = await r.json();
        if (s.error) continue;
        const lines = s.lines || [];
        const stage = s.stage || lines.slice(-1)[0] || (s.running ? 'Running...' : 'Finished');
        const pct = (typeof s.progress === 'number') ? s.progress : Math.min(95, Math.floor((s.elapsed % 30) / 30 * 95));
        textEl.textContent = stage;
        barEl.style.width = (s.running ? pct : 100) + '%';
        if (!s.running){
          done = true; break;
        }
      }catch(e){/* try next base */}
    }
    if (!done){
      setTimeout(poll, 1000);
    } else {
      setTimeout(()=>{
        modal.classList.remove('show');
        barEl.style.width = '0%';
      }, 1500);
      if (typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
    }
  }
  poll();
});


$("#btnOS")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const dropdown = document.getElementById('osDropdown');
  if (dropdown) dropdown.classList.toggle('show');
});


document.querySelectorAll('.os-option').forEach(option => {
  option.addEventListener('click', (e) => {
    const osType = e.currentTarget.dataset.os;
    applyOsOption(osType);
  });
});


document.addEventListener('click', (e) => {
  if (!e.target.closest('.os-dropdown')) {
    const dropdown = document.getElementById('osDropdown');
    if (dropdown) dropdown.classList.remove('show');
  }
});


function showProgress(title, steps) {
  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  
  if (!modal || !titleEl || !barEl || !textEl) return;
  
  titleEl.textContent = title;
  modal.classList.add('show');
  
  let currentStep = 0;
  const totalSteps = steps.length;
  
  function updateProgress() {
    if (currentStep < totalSteps) {
      const progress = ((currentStep + 1) / totalSteps) * 100;
      barEl.style.width = progress + '%';
      textEl.textContent = steps[currentStep];
      currentStep++;
      
      setTimeout(updateProgress, 1000 + Math.random() * 500);
    } else {
      setTimeout(() => {
        modal.classList.remove('show');
        barEl.style.width = '0%';
      }, 1500);
    }
  }
  
  updateProgress();
}


function openTaskModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('show');
}

function closeTaskModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('show');
    modal.querySelectorAll('.type-option').forEach(option => {
      option.classList.remove('selected');
    });
  }
}

function executeScript() {
  const date = document.getElementById('scriptDate')?.value;
  const selectedType = document.querySelector('#scriptModal .type-option.selected');
  
  if (!date) {
    alert('Please select a date');
    return;
  }
  
  if (!selectedType) {
    alert('Please select a type');
    return;
  }
  
  const type = selectedType.dataset.type;
  closeTaskModal('scriptModal');
  
  toastManager.show(`Script started (date=${date}, type=${type})`, 'success', 'Script');
  (async () => {
    try{
      await fetch(`${API_BASE}/script/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date, type })
      });
    }catch{}
  })();
}

function executeSimpleCheck() {
  const selectedType = document.querySelector('#simpleCheckModal .type-option.selected');
  
  if (!selectedType) {
    alert('Please select a type');
    return;
  }
  
  const type = selectedType.dataset.type;
  closeTaskModal('simpleCheckModal');
  toastManager.show(`SimpleCheck started (type=${type})`, 'success', 'SimpleCheck');
  (async () => {
    try{
      await fetch(`${API_BASE}/simplecheck/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type })
      });
    }catch{}
  })();
}


document.querySelector(".task-item[data-task='ping']")?.addEventListener('click', async ()=>{
  toastManager.show('Ping started', 'success', 'Ping');
  try{ await fetch(`${API_BASE}/ping/run`, {method:'POST'}); }catch{}
});


document.querySelector(".task-item[data-task='record-spec']")?.addEventListener('click', ()=>{
  openRecordSpecModal();
});

function openRecordSpecModal(){
  if (document.getElementById('recordSpecModal')) return;
  const html = `
  <div class="modal-backdrop" id="recordSpecModal" style="display:flex;">
    <div class="modal-panel" style="max-width:520px;">
      <div class="modal-header">
        <div class="modal-title">Record Spec Execution</div>
        <button class="modal-close" id="rsClose">Close</button>
      </div>
      <div class="modal-body">
        <div class="task-field">
          <label class="task-label">FINID:</label>
          <input type="text" class="task-input" id="rsFin" placeholder="Enter FINID"/>
        </div>
        <div style="margin-top:12px;">
          <button class="task-btn task-btn-execute" id="rsExec">Execute</button>
        </div>
      </div>
    </div>
  </div>`;
  document.body.insertAdjacentHTML('beforeend', html);
  document.getElementById('rsClose')?.addEventListener('click', ()=> document.getElementById('recordSpecModal')?.remove());
  document.getElementById('recordSpecModal')?.addEventListener('click', (e)=>{ if (e.target.id==='recordSpecModal') e.currentTarget.remove(); });
  document.getElementById('rsExec')?.addEventListener('click', async ()=>{
    const finId = document.getElementById('rsFin')?.value.trim();
    if (!finId){ alert('Please enter FINID'); return; }
    toastManager.show(`Record Spec started (FINID=${finId})`, 'success', 'Record Spec');
    try{
      await fetch(`${API_BASE}/record-spec/run`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ finId }) });
    }catch{}
    document.getElementById('recordSpecModal')?.remove();
  });
}


document.querySelector(".task-item[data-task='delete-os-log']")?.addEventListener('click', async ()=>{
  toastManager.show('Delete OS & Log started', 'success', 'Delete OS & Log');
  try{ await fetch(`${API_BASE}/delete-os-log/run`, {method:'POST'}); }catch{}
});


document.getElementById('showActionsBtn')?.addEventListener('click', showActionMenu);


document.querySelectorAll('.action-item').forEach(item => {
  item.addEventListener('click', () => {
    const action = item.dataset.action;
    executeAction(action);
  });
});


document.getElementById('actionModal')?.addEventListener('click', (e) => {
  if (e.target.id === 'actionModal') {
    hideActionMenu();
  }
});


document.getElementById('scriptTask')?.addEventListener('click', () => {
  openTaskModal('scriptModal');
});

document.getElementById('simpleCheckTask')?.addEventListener('click', () => {
  openTaskModal('simpleCheckModal');
});

document.querySelectorAll('.type-option').forEach(option => {
  option.addEventListener('click', (e) => {
    const modal = e.target.closest('.task-modal');
    if (modal) {
      modal.querySelectorAll('.type-option').forEach(opt => opt.classList.remove('selected'));
      e.target.classList.add('selected');
    }
  });
});


document.querySelectorAll('.task-modal').forEach(modal => {
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeTaskModal(modal.id);
    }
  });
});


document.querySelectorAll('.task-item:not(#scriptTask):not(#simpleCheckTask)').forEach(item => {
  item.addEventListener('click', (e) => {
    const taskName = e.target.closest('.task-item').dataset.task;
    if (!taskName) return;
    if (taskName === 'upload-logo') return startUploadLogoTask();
    if (taskName === 'online') return startOnlineTask();
    alert(`Task: ${taskName.replace('-', ' ').toUpperCase()} clicked`);
  });
});


window.closeTaskModal = closeTaskModal;
window.executeScript = executeScript;
window.executeSimpleCheck = executeSimpleCheck;


async function applyOsOption(osType){
  const dropdown = document.getElementById('osDropdown');
  if (dropdown) dropdown.classList.remove('show');
  const host = (location && location.hostname) ? location.hostname : '127.0.0.1';
  const urls = [ `${API_BASE}/os/apply` ];
  
  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  if (modal && titleEl && barEl && textEl){
    titleEl.textContent = `Apply OS Option: ${osType}`;
    modal.classList.add('show');
    barEl.style.width = '20%';
    textEl.textContent = 'Submitting...';
  }
  let result = null;
  for (const url of urls){
    try{
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ osType })
      });
      if (!r.ok) continue;
      result = await r.json();
      break;
    }catch(e){ /* try next */ }
  }
  if (modal && barEl && textEl){
    barEl.style.width = '100%';
    textEl.textContent = result && result.ok ? 'OS option applied' : `Failed (${result?.error || 'unknown'})`;
    setTimeout(()=>{ modal.classList.remove('show'); barEl.style.width='0%'; }, 1200);
  }
  
  if (typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
}


async function startUploadLogoTask(){
  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  if (!modal || !titleEl || !barEl || !textEl) return;
  titleEl.textContent = 'Upload Logo Running';
  modal.classList.add('show');
  barEl.style.width = '0%';
  textEl.textContent = 'Starting changelogo.sh...';

  let taskId = null;
  try{
    const r = await fetch(`${API_BASE}/task/upload-logo/start`, { method: 'POST' });
    if (r.ok){ const j = await r.json(); taskId = j.task_id; }
  }catch{}
  if (!taskId){
    textEl.textContent = 'Failed to start';
    setTimeout(()=>{ modal.classList.remove('show'); barEl.style.width='0%'; }, 1200);
    return;
  }
  const base = `${API_BASE}/task/upload-logo/status/`;
  const push = async (stage)=>{
    try{
      await fetch(`${API_BASE}/task/upload-logo/progress`, { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(stage) });
    }catch{}
  };
  
  let done = false;
  async function poll(){
    try{
      const r = await fetch(base + taskId);
      if (r.ok){
        const s = await r.json();
        const pct = (typeof s.progress === 'number') ? s.progress : 5;

        if (s.stage && s.stage.includes('BMC Reset') && typeof s.bmc_reset_remaining === 'number'){
          textEl.textContent = `${s.stage} (${s.bmc_reset_remaining}s remaining)`;
        } else {
          textEl.textContent = s.stage || 'Running...';
        }
        barEl.style.width = (s.running ? pct : 100) + '%';
        if (!s.running) done = true;
      }
    }catch{}
    if (!done) setTimeout(poll, 1000);
    else setTimeout(()=>{ modal.classList.remove('show'); barEl.style.width='0%'; }, 1200);
  }
  poll();
}


async function startOnlineTask(){
  const modal = document.getElementById('progressModal');
  const titleEl = document.getElementById('progressTitle');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  if (!modal || !titleEl || !barEl || !textEl) return;
  titleEl.textContent = 'Online Check Running';
  modal.classList.add('show');
  barEl.style.width = '0%';
  textEl.textContent = 'Starting 1.sh...';

  let taskId = null;
  try{
    const r = await fetch(`${API_BASE}/task/online/start`, { method: 'POST' });
    if (r.ok){ const j = await r.json(); taskId = j.task_id; }
  }catch{}
  if (!taskId){
    textEl.textContent = 'Failed to start';
    setTimeout(()=>{ modal.classList.remove('show'); barEl.style.width='0%'; }, 1200);
    return;
  }
  const base = `${API_BASE}/task/online/status/`;
  let done = false;
  async function poll(){
    try{
      const r = await fetch(base + taskId);
      if (r.ok){
        const s = await r.json();
        const pct = (typeof s.progress === 'number') ? s.progress : 50;
        textEl.textContent = s.stage || 'Running...';
        barEl.style.width = (s.running ? pct : 100) + '%';
        if (!s.running) done = true;
      }
    }catch{}
    if (!done) setTimeout(poll, 1000);
    else setTimeout(()=>{ modal.classList.remove('show'); barEl.style.width='0%'; }, 1200);
  }
  poll();
}

