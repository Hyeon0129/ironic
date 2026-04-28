
let demoRows = [];


function getHealthStatus(index) {
  if (index < 20) return "checking";
  if (index < 45) return "ok";
  if (index < 52) return "warning";
  if (index < 57) return "error";
  return "critical";
}

function getStatusDisplay(status, index) {
  if (status === "loading") {
    return '<div class="status-spinner"><div class="spinner"></div></div>';
  } else if (status === "complete") {
    return '<div class="status-complete"></div>';
  } else if (status === "fail") {
    return '<div class="status-fail"></div>';
  } else if (status === "ok") {
    return '<span class="ic-ok"></span>';
  } else {
    return status;
  }
}

function getHealthDisplay(health) {
  switch(health) {
    case 'checking':
      return '<div class="status-spinner"><div class="health-spinner"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
    case 'ok':
      return '<div class="status-spinner"><div class="health-spinner"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
    case 'warning':
    case 'error':
    case 'critical':
    case 'not_healthy':
      return '<div class="health-critical"></div>';
    default:
      return '<div class="status-spinner"><div class="health-spinner"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
  }
}

function getPowerDisplay(row) {
  if (row.power === 'checking') {
    return '<div class="status-spinner"><div class="health-spinner"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
  }
  const src = row.power === 'on' ? 'icon/power_green_icon.png' : 'icon/power_red_icon.png';
  const alt = row.power === 'on' ? 'Power On' : 'Power Off';
  return `<img class="power-img" src="${src}" alt="${alt}"/>`;
}

function getUidDisplay(row) {
  if (row.uid === 'checking') {
    return '<div class="status-spinner"><div class="health-spinner"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
  }
  if (!row.useIconUid || !row.uid) return "";
  const cls = row.uid === 'on' ? 'on' : 'off';
  return `<i class="uid-sphere ${cls}" aria-label="UID ${row.uid}"></i>`;
}

/* ---- state ---- */
let state = {
  data: demoRows,
  filtered: demoRows.slice(),
  sortKey: "order",
  sortDir: "asc",
  page: 1,
  perPage: 10,
  query: ""
};

const healthPresenceCacheTable = new Map();
const TABLE_PRESENCE_TTL_MS = 120000;

/* ---- helpers ---- */
function compare(a,b,key,dir){
  const av = a[key];
  const bv = b[key];
  let r = 0;
  if (key === "order"){
    const an = Number(av ?? 0);
    const bn = Number(bv ?? 0);
    r = an - bn;
  } else {
    const as = (av ?? "").toString().toLowerCase();
    const bs = (bv ?? "").toString().toLowerCase();
    r = as>bs ? 1 : as<bs ? -1 : 0;
  }
  return dir === "asc" ? r : -r;
}

function applyFilter(){
  const q = state.query.trim().toLowerCase();
  state.filtered = q
    ? state.data.filter(row => Object.values(row).some(v => String(v).toLowerCase().includes(q)))
    : state.data.slice();
  state.page = 1;
  render();
}

function paginate(arr,page,per){
  const start = (page-1)*per;
  return [arr.slice(start, start+per), start, Math.min(start+per, arr.length)];
}

function renderHeader(){
  $$("#qcTable thead th.sortable").forEach(th=>{
    th.classList.remove("asc","desc");
    if (th.dataset.key===state.sortKey) th.classList.add(state.sortDir);
  });
}

function render(){
  // sort
  state.filtered.sort((a,b)=>compare(a,b,state.sortKey,state.sortDir));

  // page
  const [view,start,end] = paginate(state.filtered, state.page, state.perPage);

  const rows = view.map((r, index)=>`
    <tr data-index="${index}" data-bmc-ip="${r.bmcip}">
      <td>
        <input type="checkbox" class="custom-checkbox row-checkbox" data-row="${index}" />
      </td>
      <td>
        ${getPowerDisplay(r)}
      </td>
      <td>${r.osip}</td>
      <td>${r.task}</td>
      <td>${getStatusDisplay(r.status, state.data.indexOf(r))}</td>
      <td>${r.platform}</td>
      <td>${r.serial}</td>
      <td>${r.manufact}</td>
      <td>${r.model}</td>
      <td>${r.bios}</td>
      <td>${r.bmc}</td>
      <td>${r.mbcpld}</td>
      <td>${r.cpu}</td>
      <td>${r.ram}</td>
      <td>${r.raid}</td>
      <td>${r.disk}</td>
      <td>${r.nic}</td>
      <td>${r.bmcip}</td>
      <td>${r.netmask}</td>
      <td>${r.gw}</td>
      <td>${getHealthDisplay(r.health)}</td>
      <td>${getUidDisplay(r)}</td>
    </tr>`).join("");
  $("#qcTable tbody").innerHTML = rows || `<tr><td colspan="22" style="padding:24px; color:rgba(214,224,238,.7)">No data</td></tr>`;

  setupCheckboxEvents();

  
  $("#rangeInfo").textContent = `Showing ${state.filtered.length? start+1:0} to ${end} of ${state.filtered.length} entries`;

  const pages = Math.max(1, Math.ceil(state.filtered.length / state.perPage));
  const pager = [];
  for(let p=1;p<=pages;p++){
    pager.push(`<button class="qc-page" ${p===state.page?'aria-current="page"':''} data-page="${p}">${p}</button>`);
  }
  $("#pager").innerHTML = pager.join("");
  renderHeader();
}

let selectedServers = new Set();

function updateCheckboxActions() {
  const count = selectedServers.size;
  const checkboxActions = document.getElementById('checkboxActions');
  const selectedCount = document.getElementById('selectedCount');
  const actionCount = document.getElementById('actionCount');
  
  if (selectedCount) selectedCount.textContent = `${count} server${count !== 1 ? 's' : ''} selected`;
  if (actionCount) actionCount.textContent = count;
  
  if (count > 0) {
    checkboxActions?.classList.add('show');
  } else {
    checkboxActions?.classList.remove('show');
    hideActionMenu();
  }
}

function setupCheckboxEvents() {
  
  const selectAllCheckbox = $("#selectAll");
  const rowCheckboxes = $$(".row-checkbox");
  
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      selectedServers.clear();
      
      rowCheckboxes.forEach((checkbox, index) => {
        checkbox.checked = isChecked;
        const row = checkbox.closest("tr");
        const serverData = state.filtered[state.page * state.perPage - state.perPage + index];
        
        if (isChecked && serverData) {
          row.classList.add("selected");
          selectedServers.add(serverData.bmcip);
        } else {
          row.classList.remove("selected");
        }
      });
      
      updateCheckboxActions();
    });
  }
  
  
  rowCheckboxes.forEach((checkbox, index) => {
    checkbox.addEventListener("change", (e) => {
      const row = e.target.closest("tr");
      const serverData = state.filtered[state.page * state.perPage - state.perPage + index];
      
      if (e.target.checked && serverData) {
        row.classList.add("selected");
        selectedServers.add(serverData.bmcip);
      } else {
        row.classList.remove("selected");
        if (serverData) selectedServers.delete(serverData.bmcip);
      }
      
      
      const allChecked = Array.from(rowCheckboxes).every(cb => cb.checked);
      const someChecked = Array.from(rowCheckboxes).some(cb => cb.checked);
      
      if (selectAllCheckbox) {
        selectAllCheckbox.checked = allChecked;
        selectAllCheckbox.indeterminate = someChecked && !allChecked;
      }
      
      updateCheckboxActions();
    });
  });
}

function updateAlarmSystem() {
  const issues = state.filtered.filter(row => 
    row.health === 'warning' || row.health === 'error' || row.health === 'critical'
  );
  
  alarmState.issues = issues;
  const alarmIcon = $("#alarmIcon");
  const alarmBadge = $("#alarmBadge");
  const alarmList = $("#alarmList");
  
  
  if (issues.length > 0) {
    alarmIcon?.classList.add("active");
    if (alarmBadge) {
      alarmBadge.style.display = "flex";
      alarmBadge.textContent = issues.length;
    }
  } else {
    alarmIcon?.classList.remove("active");
    if (alarmBadge) alarmBadge.style.display = "none";
  }
  
  if (alarmList) {
    if (issues.length === 0) {
      alarmList.innerHTML = '<div style="text-align:center; color:rgba(184,194,210,.7); padding:20px;">No alerts</div>';
    } else {
      const alarmItems = issues.map((issue, idx) => {
        const severityText = {
          'warning': 'Warning',
          'error': 'Error', 
          'critical': 'Critical'
        }[issue.health];
        
        const severityDesc = {
          'warning': 'System performance degraded',
          'error': 'Service disruption detected',
          'critical': 'Critical system failure'
        }[issue.health];
        
        return `
          <div class="alarm-item" data-idx="${idx}">
            <div class="alarm-item-icon"></div>
            <div class="alarm-item-content">
              <div class="alarm-item-title">${issue.osip} - ${severityText}</div>
              <div class="alarm-item-desc">${severityDesc}</div>
            </div>
          </div>
        `;
      }).join('');
      
      alarmList.innerHTML = alarmItems;
      bindAlarmItemClicks();
    }
  }
}


function bindAlarmItemClicks() {
  const container = document.getElementById('alarmList');
  if (container) {
    container.querySelectorAll('.alarm-item').forEach((el, i) => {
      el.addEventListener('click', () => {
        const issue = alarmState.issues[i];
        if (issue) openAlarmDetail(issue);
      });
    });
  }
}

function openAlarmDetail(issue) {
  const modal = document.getElementById('alarmModal');
  if (!modal) return;
  
  const elements = {
    m_ip: issue.osip,
    m_sev: issue.health.toUpperCase(),
    m_status: issue.status || 'N/A',
    m_platform: issue.platform || 'N/A',
    m_model: issue.model || 'N/A',
    m_desc: issue.health === 'critical' ? 'Critical system failure' : 
            issue.health === 'error' ? 'Service disruption detected' : 
            'System performance degraded'
  };
  
  Object.entries(elements).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  });
  
  modal.classList.add('show');
}

function closeAlarmDetail() {
  const modal = document.getElementById('alarmModal');
  if (modal) modal.classList.remove('show');
}

/* ---- events ---- */
$$("#qcTable thead th.sortable").forEach(th=>{
  th.addEventListener("click", ()=>{
    const key = th.dataset.key;
    if (state.sortKey===key){
      state.sortDir = state.sortDir==="asc" ? "desc" : "asc";
    }else{
      state.sortKey = key; state.sortDir = "asc";
    }
    render();
  });
});

$("#searchBox")?.addEventListener("input", e=>{
  state.query = e.target.value;
  applyFilter();
});

$("#rowsPerPage")?.addEventListener("change", e=>{
  state.perPage = parseInt(e.target.value,10);
  state.page = 1;
  render();
});

$("#pager")?.addEventListener("click", e=>{
  const btn = e.target.closest("[data-page]");
  if (!btn) return;
  state.page = parseInt(btn.dataset.page,10);
  render();
});

$("#modalClose")?.addEventListener('click', closeAlarmDetail);

document.getElementById('alarmModal')?.addEventListener('click', (e) => {
  if (e.target.id === 'alarmModal') closeAlarmDetail();
});

async function fetchRowsFromApi() {
  const host = (location && location.hostname) ? location.hostname : "127.0.0.1";
  const scheme = location?.protocol || 'http:';
  const endpoints = [
    `${scheme}//${host}:8000/servers`,
    `${scheme}//127.0.0.1:8000/servers`
  ];
  for (const url of endpoints) {
    try {
      const res = await fetch(url, { credentials: "omit" });
      if (!res.ok) continue;
      const data = await res.json();
      if (data && Array.isArray(data.rows)) {
        const prevByBmcip = new Map(state.data.map(x=>[x.bmcip, x]));
        const rowsSorted = [...data.rows].sort((a,b)=> (a.order??0) - (b.order??0));
        demoRows = rowsSorted.map((r, i) => {
          const prev = prevByBmcip.get(r.bmcip);
          const prevHealth = prev?.health;
          const prevUid = prev?.uid;
          const prevTask = prev?.task;
          const prevStatus = prev?.status;
          const serverTask = r.task;
          const serverStatus = r.status;
          const mergedTask = (serverTask && serverTask !== 'N / A') ? serverTask : (prevTask ?? 'N / A');
          const mergedStatus = (serverStatus && serverStatus !== 'N / A') ? serverStatus : (prevStatus ?? 'N / A');
          return {
            power: r.power || "off",
            osip: r.osip || "",
            task: mergedTask,
            status: mergedStatus,
            platform: r.platform || "",
            serial: r.serial || "",
            manufact: r.manufact || "",
            model: r.model || "",
            bios: r.bios || "",
            bmc: r.bmc || "",
            mbcpld: r.mbcpld || "",
            cpu: r.cpu || "",
            ram: r.ram || "",
            raid: r.raid || "",
            disk: r.disk || "",
            nic: r.nic || "",
            bmcip: r.bmcip || "",
            netmask: r.netmask || "",
            gw: r.gw || "",
            health: (r.health === undefined || r.health === null || r.health === "")
                      ? (prevHealth ?? "checking")
                      : r.health,
            uid: (r.uid === undefined || r.uid === null || r.uid === "")
                      ? (prevUid ?? "")
                      : r.uid,
            order: r.order ?? i,
            useIconPower: true,
            useIconUid: Boolean((r.uid === undefined || r.uid === null || r.uid === "") ? prevUid : r.uid),
          }
        });
        state.data = demoRows;
        state.filtered = demoRows.slice();
        render();
        return;
      }
    } catch (e) {
      console.debug("fetchRowsFromApi failed for", url, e);
    }
  }
  state.data = [];
  state.filtered = [];
  render();
}

fetchRowsFromApi();
setInterval(fetchRowsFromApi, 5000);



async function refreshHealthAndUid() {
  const host = (location && location.hostname) ? location.hostname : "127.0.0.1";
  const scheme = location?.protocol || 'http:';  
  let changed = false;
  
  {
    const eps = [
      `${scheme}//${host}:8000/health/logs`,
      `${scheme}//127.0.0.1:8000/health/logs`,
    ];
    for (const url of eps) {
      try {
        const resH = await fetch(url);
        if (!resH.ok) throw new Error('not ok');
        const logs = await resH.json();
        const now = Date.now();
        if (logs && typeof logs === 'object'){
          Object.keys(logs).forEach(ip => {
            if (logs[ip]) healthPresenceCacheTable.set(ip, { lastSeen: now });
          });
        }
        state.data.forEach(r => {
          const rec = healthPresenceCacheTable.get(r.bmcip);
          const seenRecently = rec && (now - (rec.lastSeen || 0) <= TABLE_PRESENCE_TTL_MS);
          const hasLog = (logs && logs[r.bmcip]) || seenRecently;
          const newHealth = hasLog ? 'not_healthy' : 'checking';
          if (newHealth !== r.health) { r.health = newHealth; changed = true; }
        });
        break;
      } catch (e) {
        console.debug('health fetch failed', url, e);
      }
    }
  }

  {
    const eps = [
      `${scheme}//${host}:8000/uid/status`,
      `${scheme}//127.0.0.1:8000/uid/status`
    ];
    for (const url of eps) {
      try {
        const resU = await fetch(url);
        if (!resU.ok) throw new Error('not ok');
        const uidMap = await resU.json();
        state.data.forEach(r => {
          const u = uidMap[r.bmcip];
          let newUid = r.uid;
          let newUse = r.useIconUid;
          if (u === 'ON') { newUid = 'on'; newUse = true; }
          else if (u === 'OFF') { newUid = 'off'; newUse = true; }
          else { newUid = 'checking'; newUse = false; }
          if (newUid !== r.uid || newUse !== r.useIconUid) { r.uid = newUid; r.useIconUid = newUse; changed = true; }
        });
        break;
      } catch (e) {
        console.debug('uid fetch failed', url, e);
      }
    }
  }

  if (changed) applyFilter();
}

setInterval(refreshHealthAndUid, 20000);
refreshHealthAndUid();

async function refreshTaskStatus(){
  try{
    const host = (location && location.hostname) ? location.hostname : '127.0.0.1';
    const scheme = location?.protocol || 'http:';
    const eps = [
      `${scheme}//${host}:8000/status/boot`,
      `${scheme}//127.0.0.1:8000/status/boot`
    ];
    let res = null;
    for (const url of eps){
      try{
        const r = await fetch(url);
        if (r.ok){ res = r; break; }
      }catch(e){ /* try next */ }
    }
    if (!res) return;
    const data = await res.json();
    if (!data || !Array.isArray(data.items)) return;
    const mapBySerial = new Map(data.items.map(it=>[String(it.serial || ''), it]));
    const mapByBmcip = new Map(data.items.map(it=>[String(it.bmcip || ''), it]));
    let changed = false;
    state.data.forEach(r=>{
      const it = mapBySerial.get(String(r.serial || '')) || mapByBmcip.get(String(r.bmcip || ''));
      if (it){
        const newTask = (it.task !== undefined && it.task !== null) ? it.task : r.task;
        const ui = (it.ui_status !== undefined && it.ui_status !== null) ? it.ui_status : it.status;
        const newStatus = ui || r.status;
        if (newTask !== r.task || newStatus !== r.status){
          r.task = newTask;
          r.status = newStatus;
          changed = true;
        }
      }
    });
    if (changed) applyFilter();
  }catch{}
}

setInterval(refreshTaskStatus, 3000);
refreshTaskStatus();