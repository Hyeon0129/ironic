let demoRows = [];

function getPowerDisplay(powerState) {
  if (!powerState) return '-';
  const state = powerState.toLowerCase();
  const src = state === 'power on' ? 'icon/power_green_icon.png' : 'icon/power_red_icon.png';
  const alt = state === 'power on' ? 'Power On' : 'Power Off';
  return `<div style="text-align: center; margin-top: -3px;"><img class="power-img" src="${src}" alt="${alt}" style="width:20px;height:20px; display: inline-block;"/></div>`;
}

function getHealthDisplay(health) {
  if (health === 'ok') {
    return `<div style="text-align: center;"><div class="status-complete"></div></div>`;
  } else if (health === 'error' || health === 'critical') {
    return `<div style="text-align: center;"><div class="health-critical"></div></div>`;
  } else {
    return `<div style="text-align: center;">-</div>`;
  }
}

function getMaintenanceDisplay(r) {
  const isMaint = r.maintenance;
  const color = isMaint ? '#e34d42' : '#94A3B8';
  const text = isMaint ? 'True' : 'False';
  const action = isMaint ? 'false' : 'true';
  return `<div style="display:flex; align-items:center; justify-content:center; gap:8px;">
            <span style="color:${color}; font-weight:bold; min-width: 35px; text-align: left;">${text}</span>
            <button style="appearance:none; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.06); color:#fff; padding:2px 6px; border-radius:4px; font-size:11px; cursor:pointer;" onclick="toggleMaintenance('${r.uuid}', ${action})">Toggle</button>
          </div>`;
}

let state = {
  data: demoRows,
  filtered: demoRows.slice(),
  sortKey: "name",
  sortDir: "asc",
  page: 1,
  perPage: 10,
  query: ""
};

function compare(a,b,key,dir){
  const av = a[key] || "";
  const bv = b[key] || "";
  const as = av.toString().toLowerCase();
  const bs = bv.toString().toLowerCase();
  const r = as>bs ? 1 : as<bs ? -1 : 0;
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
  document.querySelectorAll("#qcTable thead th.sortable").forEach(th=>{
    th.classList.remove("asc","desc");
    if (th.dataset.key===state.sortKey) th.classList.add(state.sortDir);
  });
}

function render(){
  state.filtered.sort((a,b)=>compare(a,b,state.sortKey,state.sortDir));
  const [view,start,end] = paginate(state.filtered, state.page, state.perPage);

  const rows = view.map((r, index)=>{
    const isChecked = selectedServers.has(r.uuid) ? 'checked' : '';
    const selectedClass = selectedServers.has(r.uuid) ? 'selected' : '';
    return `
    <tr data-index="${index}" data-uuid="${r.uuid}" class="${selectedClass}">
      <td>
        <input type="checkbox" class="custom-checkbox row-checkbox" data-uuid="${r.uuid}" ${isChecked} />
      </td>
      <td>${getPowerDisplay(r.power)}</td>
      <td>${r.name || '-'}</td>
      <td>${r.os_ip || '-'}</td>
      <td>${r.bmc_ip || '-'}</td>
      <td>${r.provision_state || '-'}</td>
      <td>${r.uuid || '-'}</td>
      <td>${getMaintenanceDisplay(r)}</td>
      <td>${getHealthDisplay(r.health)}</td>
    </tr>`;
  }).join("");
  
  const tbody = document.querySelector("#qcTable tbody");
  if(tbody) tbody.innerHTML = rows || `<tr><td colspan="9" style="padding:24px; text-align:center; color:rgba(214,224,238,.7)">No data</td></tr>`;

  setupCheckboxEvents();

  const rangeInfo = document.querySelector("#rangeInfo");
  if(rangeInfo) rangeInfo.textContent = `Showing ${state.filtered.length? start+1:0} to ${end} of ${state.filtered.length} entries`;

  const pages = Math.max(1, Math.ceil(state.filtered.length / state.perPage));
  const pager = [];
  for(let p=1;p<=pages;p++){
    pager.push(`<button class="qc-page" ${p===state.page?'aria-current="page"':''} data-page="${p}">${p}</button>`);
  }
  const pagerEl = document.querySelector("#pager");
  if(pagerEl) pagerEl.innerHTML = pager.join("");
  
  renderHeader();
}

let selectedServers = new Set();

function setupCheckboxEvents() {
  const selectAllCheckbox = document.querySelector("#selectAll");
  const rowCheckboxes = document.querySelectorAll(".row-checkbox");
  
  if (selectAllCheckbox) {
    const newSelectAll = selectAllCheckbox.cloneNode(true);
    selectAllCheckbox.parentNode.replaceChild(newSelectAll, selectAllCheckbox);
    
    newSelectAll.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      
      document.querySelectorAll(".row-checkbox").forEach((checkbox) => {
        checkbox.checked = isChecked;
        const row = checkbox.closest("tr");
        const uuid = checkbox.dataset.uuid;
        
        if (isChecked && uuid) {
          row.classList.add("selected");
          selectedServers.add(uuid);
        } else {
          row.classList.remove("selected");
          if (uuid) selectedServers.delete(uuid);
        }
      });
      console.log("Selected Node IDs for action:", Array.from(selectedServers));
    });
  }
  
  rowCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", (e) => {
      const row = e.target.closest("tr");
      const uuid = e.target.dataset.uuid;
      
      if (e.target.checked && uuid) {
        row.classList.add("selected");
        selectedServers.add(uuid);
      } else {
        row.classList.remove("selected");
        if (uuid) selectedServers.delete(uuid);
      }
      
      updateSelectAllState();
      console.log("Selected Node IDs for action:", Array.from(selectedServers));
    });
  });
  
  updateSelectAllState();
}

function updateSelectAllState() {
  const currentSelectAll = document.querySelector("#selectAll");
  if (!currentSelectAll) return;
  const rowCheckboxes = Array.from(document.querySelectorAll(".row-checkbox"));
  if (rowCheckboxes.length === 0) {
      currentSelectAll.checked = false;
      currentSelectAll.indeterminate = false;
      return;
  }
  const allChecked = rowCheckboxes.every(cb => cb.checked);
  const someChecked = rowCheckboxes.some(cb => cb.checked);
  currentSelectAll.checked = allChecked;
  currentSelectAll.indeterminate = someChecked && !allChecked;
}

document.querySelectorAll("#qcTable thead th.sortable").forEach(th=>{
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

const searchBox = document.querySelector("#searchBox");
if(searchBox) searchBox.addEventListener("input", e=>{
  state.query = e.target.value;
  applyFilter();
});

const rowsPerPage = document.querySelector("#rowsPerPage");
if(rowsPerPage) rowsPerPage.addEventListener("change", e=>{
  state.perPage = parseInt(e.target.value,10);
  state.page = 1;
  render();
});

const pagerEl = document.querySelector("#pager");
if(pagerEl) pagerEl.addEventListener("click", e=>{
  const btn = e.target.closest("[data-page]");
  if (!btn) return;
  state.page = parseInt(btn.dataset.page,10);
  render();
});

// Click a row (but not its checkbox or the maintenance toggle button) to
// open the Node Detail modal. Delegated on the (stable) tbody element since
// render() replaces the rows' innerHTML every poll.
const qcTableBody = document.querySelector("#qcTable tbody");
if (qcTableBody) qcTableBody.addEventListener("click", e => {
  if (e.target.closest(".row-checkbox") || e.target.closest("button")) return;
  const tr = e.target.closest("tr[data-uuid]");
  if (tr && typeof window.openNodeDetail === "function") window.openNodeDetail(tr.dataset.uuid);
});

async function fetchRowsFromApi() {
  try {
    const res = await fetch('/api/servers');
    if (!res.ok) return;
    const data = await res.json();
    if (data && Array.isArray(data.rows)) {
      state.data = data.rows;
      applyFilter(); 
    }
  } catch (e) {
    console.error("fetchRowsFromApi failed", e);
  }
}

fetchRowsFromApi();
setInterval(fetchRowsFromApi, 1000);
