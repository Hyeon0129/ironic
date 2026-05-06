window.API_BASE = `${location.protocol}//${location.hostname}:8000`;

function openTaskModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('show');
}

function closeTaskModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('show');
}

window.closeTaskModal = closeTaskModal;

window.toggleUnifiedBuilderFields = function() {
  const type = document.getElementById('unifiedBuildType')?.value;
  const osFields = document.getElementById('unifiedOsFields');
  const userdataFields = document.getElementById('unifiedUserdataFields');
  
  if (type === 'os') {
    if (osFields) osFields.style.display = 'flex';
    if (userdataFields) userdataFields.style.display = 'none';
  } else if (type === 'userdata') {
    if (osFields) osFields.style.display = 'none';
    if (userdataFields) userdataFields.style.display = 'flex';
  }
};

function initSidebarListeners() {
  // Task Item click handler (direct action)
  document.querySelectorAll('#ironicActions .task-item').forEach(item => {
    item.addEventListener('click', async (e) => {
      const action = item.dataset.action;
      
      if (item.classList.contains('action-rename')) {
        const selected = Array.from(selectedServers);
        if (selected.length !== 1) { 
          alert('Please select exactly one server from the table to rename.'); 
          return; 
        }
        const uuid = selected[0];
        const newName = await window.customPrompt('Enter new node name:');
        if (!newName) return;

        const processingId = toastManager.show('Renaming node...', 'info', 'Processing', 0);
        fetch(`${API_BASE}/api/nodes/rename`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uuid: uuid, new_name: newName })
        }).then(r=>r.json()).then(j=>{
          toastManager.hide(processingId);
          if (!j.ok) { alert(`Failed: ${j.error}`); return; }
          alert('Node renamed successfully');
          selectedServers.clear();
          if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
        }).catch(()=>{
          toastManager.hide(processingId);
          alert('Request failed');
        });
      } else if (action) {
        executeIronicAction(action);
      }
    });
  });

  document.getElementById('manageAssetsTask')?.addEventListener('click', () => {
    openTaskModal('assetManagerModal');
    refreshAssets();
  });

  document.getElementById('builderTask')?.addEventListener('click', () => {
    window.location.href = '/builder';
  });
}

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
  initSidebarListeners();
  
  if (window.location.pathname === '/builder') {
    if (document.getElementById('partitionList') && document.getElementById('partitionList').children.length === 0) {
      if (typeof addPartitionRow === 'function') {
        addPartitionRow('esp', 'EF00', '512MiB', 'vfat', '/boot/efi');
        addPartitionRow('bios', 'EF02', '8MiB', '', '');
        addPartitionRow('boot', '8300', '2GiB', 'ext4', '/boot');
        addPartitionRow('root', '8300', '100%', 'ext4', '/');
      }
    }
    checkActiveBuild();
  }
});

async function checkActiveBuild() {
  try {
    const r = await fetch(`${API_BASE}/api/assets/build/active`);
    const data = await r.json();
    if (data.task_id) {
      resumeBuildPolling(data.task_id);
    }
  } catch(e) {}
}

function resumeBuildPolling(taskId) {
  const statusEl = document.getElementById('buildProgressStatus');
  const pctEl = document.getElementById('buildProgressPct');
  const barEl = document.getElementById('buildProgressBar');
  const terminalEl = document.getElementById('buildLogTerminal');
  const terminalContainer = document.getElementById('buildTerminalContainer');
  const btnStart = document.getElementById('btnStartBuild');
  const btnStop = document.getElementById('btnStopBuild');

  if (terminalContainer) terminalContainer.style.display = 'flex';
  if (btnStart) btnStart.style.display = 'none';
  if (btnStop) btnStop.style.display = 'inline-block';

  if (buildTaskPollingId) clearInterval(buildTaskPollingId);
  buildTaskPollingId = setInterval(async () => {
    try {
      const st = await fetch(`${API_BASE}/api/assets/build/status/${taskId}`);
      const s = await st.json();
      if (s.error) return;

      if (statusEl) statusEl.textContent = s.status;
      if (pctEl) pctEl.textContent = s.progress + '%';
      if (barEl) barEl.style.width = s.progress + '%';

      try {
        const logRes = await fetch(`${API_BASE}/api/assets/build/log?t=${Date.now()}`);
        const logData = await logRes.json();
        if (terminalEl && logData.log !== undefined) {
          terminalEl.textContent = logData.log || "Build started, waiting for output...";
          terminalEl.scrollTop = terminalEl.scrollHeight;
        }
      } catch(e){}

      if (!s.running) {
        clearInterval(buildTaskPollingId);
        if (btnStart) btnStart.style.display = 'inline-block';
        if (btnStop) btnStop.style.display = 'none';

        if (s.error) {
          if (s.error === "Stopped") {
             toastManager.show('Build stopped by user.', 'warning');
          } else {
             alert("Build failed: " + s.error);
             if (statusEl) statusEl.textContent = "Failed";
          }
        } else {
          toastManager.show('Build completed successfully!', 'success');
          if (typeof refreshAssets === 'function') refreshAssets();
        }
      }
    } catch(e) {}
  }, 2000);
}

window.stopBuildImage = async function() {
  if (!confirm("Are you sure you want to stop the current build?")) return;
  try {
    const r = await fetch(`${API_BASE}/api/assets/build/stop`, { method: 'POST' });
    const res = await r.json();
    if (res.ok) {
      toastManager.show('Build stop requested.', 'info');
    }
  } catch(e) {
    alert("Failed to stop build.");
  }
}
function executePowerAction(action) {
  closeTaskModal('powerManagerModal');
  executeIronicAction(action);
}
window.executePowerAction = executePowerAction;

async function executeIronicAction(action) {
  const selected = Array.from(selectedServers);
  if (selected.length === 0) { 
    alert('Please select at least one server from the table.'); 
    return; 
  }

  if (action === 'power-manager') {
    openTaskModal('powerManagerModal');
    return;
  }

  if (action === 'raid-manager') {
    openTaskModal('raidManagerModal');
    return;
  }

  if (action === 'deploy') {
    loadDeployFiles();
    openTaskModal('deployModal');
    return;
  }

  const confirmed = await window.customConfirm(`Are you sure you want to execute '${action}' on ${selected.length} servers?`);
  if (!confirmed) return;

  const processingId = toastManager.show(`Executing '${action}'...`, 'info', 'Processing', 0);

  fetch(`${API_BASE}/api/actions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uuids: selected, action: action })
  }).then(r=>r.json()).then(j=>{
    toastManager.hide(processingId);
    if (!j.ok) { 
      alert(`Failed: ${j.error||'unknown'}`); 
      return; 
    }
    
    let successCount = 0;
    let errors = [];
    for(let uuid in j.results) {
      if(j.results[uuid].ok) {
        successCount++;
      } else {
        errors.push(`[${uuid}] ${j.results[uuid].error}`);
      }
    }
    
    if (errors.length > 0) {
      alert(`Action '${action}' completed with mixed results.\nSuccess: ${successCount}/${selected.length}\nErrors:\n${errors.join('\n')}`);
    } else {
      alert(`Action '${action}' successfully initiated for ${successCount}/${selected.length} servers.`);
      selectedServers.clear();
    }
    
    if(typeof fetchRowsFromApi === 'function') {
      fetchRowsFromApi();
    }
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}

function loadDeployFiles() {
  fetch(`${API_BASE}/api/deploy_files?t=${Date.now()}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        console.error("Deploy files API error:", data.error);
        alert("Error loading files: " + data.error);
      }
      const imgSelect = document.getElementById('deployImageSelect');
      const userSelect = document.getElementById('deployUserDataSelect');
      
      imgSelect.innerHTML = '<option value="">Select an image</option>' + (data.images || []).map(i => `<option value="${i}">${i}</option>`).join('');
      userSelect.innerHTML = '<option value="">Select user data</option>' + (data.user_datas || []).map(i => `<option value="${i}">${i}</option>`).join('');
    })
    .catch(e => console.error("Failed to load deploy files", e));
}

function executeDeploy() {
  const image = document.getElementById('deployImageSelect').value;
  const userData = document.getElementById('deployUserDataSelect').value;
  const selected = Array.from(selectedServers);
  
  if (!image || !userData) {
    alert('Please select both Image and User Data');
    return;
  }
  
  closeTaskModal('deployModal');
  const processingId = toastManager.show('Initiating deployment...', 'info', 'Deploy', 0);
  
  fetch(`${API_BASE}/api/deploy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uuids: selected, image: image, user_data: userData })
  }).then(r=>r.json()).then(j=>{
    toastManager.hide(processingId);
    if (!j.ok) { 
      alert(`Deploy Failed: ${j.error||'unknown'}`); 
      return; 
    }
    let successCount = 0;
    let errors = [];
    for(let uuid in j.results) {
      if(j.results[uuid].ok) {
        successCount++;
      } else {
        errors.push(`[${uuid}] ${j.results[uuid].error}`);
      }
    }
    if (errors.length > 0) {
      alert(`Deploy initiated for ${successCount}/${selected.length} servers.\nErrors:\n${errors.join('\n')}`);
    } else {
      alert(`Deploy successfully initiated for ${successCount}/${selected.length} servers.`);
      selectedServers.clear();
    }
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}

window.executeDeploy = executeDeploy;

async function executeRaid(type) {
  const selected = Array.from(selectedServers);
  if (selected.length === 0) { 
    alert('Please select at least one server.'); 
    return; 
  }
  
  const confirmed = await window.customConfirm(`Are you sure you want to execute RAID '${type}' on ${selected.length} servers?`);
  if (!confirmed) return;

  closeTaskModal('raidManagerModal');
  const processingId = toastManager.show(`Executing RAID ${type}...`, 'info', 'RAID', 0);
  
  fetch(`${API_BASE}/api/raid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uuids: selected, action: type })
  }).then(r=>r.json()).then(j=>{
    toastManager.hide(processingId);
    if (!j.ok) { 
      alert(`Failed: ${j.error||'unknown'}`); 
      return; 
    }
    let successCount = 0;
    let errors = [];
    for(let uuid in j.results) {
      if(j.results[uuid].ok) {
        successCount++;
      } else {
        errors.push(`[${uuid}] ${j.results[uuid].error}`);
      }
    }
    if (errors.length > 0) {
      alert(`RAID '${type}' completed with mixed results.\nSuccess: ${successCount}/${selected.length}\nErrors:\n${errors.join('\n')}`);
    } else {
      alert(`RAID '${type}' successfully initiated for ${successCount}/${selected.length} servers.`);
      selectedServers.clear();
    }
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}
window.executeRaid = executeRaid;

window.executeQuery = function() {
  const username = document.getElementById('queryUsername').value;
  const password = document.getElementById('queryPassword').value;
  
  if (!username || !password) {
    alert('Please fill out Username and Password.');
    return;
  }
  
  closeTaskModal('queryModal');
  const processingId = toastManager.show('Querying nodes...', 'info', 'Query', 0);
  
  fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: username, password: password })
  }).then(r=>r.json()).then(j=>{
    toastManager.hide(processingId);
    if (!j.ok) { 
      alert(`Query Failed: ${j.error||'unknown'}`); 
      return; 
    }
    alert(`Query completed successfully. ${j.matched_count} nodes matched and configured.`);
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
};

window.toggleMaintenance = async function(uuid, targetState) {
  const confirmed = await window.customConfirm(`Are you sure you want to turn ${targetState ? 'ON' : 'OFF'} maintenance for this node?`);
  if (!confirmed) return;
  
  const processingId = toastManager.show(`Setting maintenance to ${targetState}...`, 'info', 'Maintenance', 0);
  
  fetch(`${API_BASE}/api/maintenance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uuid: uuid, maintenance: targetState, reason: 'Toggled via Dashboard' })
  }).then(r=>r.json()).then(j=>{
    toastManager.hide(processingId);
    if (!j.ok) { 
      alert(`Failed: ${j.error||'unknown'}`); 
      return; 
    }
    alert(`Maintenance successfully set to ${targetState}`);
    selectedServers.clear();
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
};

// Initialization moved to DOMContentLoaded
async function uploadAsset(type) {
  const inputId = type === 'image' ? 'imageUploadFile' : 'userDataUploadFile';
  const fileInput = document.getElementById(inputId);
  if (!fileInput.files.length) {
    alert('Please select a file to upload');
    return;
  }
  
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('type', type);
  
  const processingId = toastManager.show(`Uploading ${fileInput.files[0].name}...`, 'info', 'Upload', 0);
  try {
    const r = await fetch(`${API_BASE}/api/assets/upload`, {
      method: 'POST',
      body: formData
    });
    const res = await r.json();
    toastManager.hide(processingId);
    if (res.ok) {
      toastManager.show('Upload successful', 'success', 'Upload');
      fileInput.value = '';
      refreshAssets();
    } else {
      alert('Upload failed: ' + res.error);
    }
  } catch(e) {
    toastManager.hide(processingId);
    alert('Upload error: ' + e);
  }
}

async function deleteAsset(type, filename) {
  const confirmed = await window.customConfirm(`Delete ${filename}?`);
  if (!confirmed) return;
  try {
    const r = await fetch(`${API_BASE}/api/assets/${type}/${filename}`, { method: 'DELETE' });
    const res = await r.json();
    if (res.ok) {
      toastManager.show('Deleted', 'success');
      refreshAssets();
    } else {
      alert('Delete failed: ' + res.error);
    }
  } catch(e) {
    alert('Delete error: ' + e);
  }
}

// OS Family dynamic dropdown
window.updateOsReleases = function() {
  const family = document.getElementById('buildOsFamily').value;
  const relSelect = document.getElementById('buildRelease');
  relSelect.innerHTML = '';
  const options = {
    ubuntu: [
      {val: 'noble', text: '24.04 (Noble)'},
      {val: 'jammy', text: '22.04 (Jammy)'},
      {val: 'focal', text: '20.04 (Focal)'}
    ],
    centos: [
      {val: '9-stream', text: 'CentOS Stream 9'},
      {val: '8-stream', text: 'CentOS Stream 8'},
      {val: '7', text: 'CentOS 7'}
    ],
    rocky: [
      {val: '9', text: 'Rocky Linux 9'},
      {val: '8', text: 'Rocky Linux 8'}
    ],
    almalinux: [
      {val: '9', text: 'AlmaLinux 9'},
      {val: '8', text: 'AlmaLinux 8'}
    ],
    debian: [
      {val: 'bookworm', text: 'Debian 12 (Bookworm)'},
      {val: 'bullseye', text: 'Debian 11 (Bullseye)'}
    ]
  };
  (options[family] || []).forEach(o => {
    relSelect.innerHTML += `<option value="${o.val}">${o.text}</option>`;
  });
};

async function loadSshKeys() {
  try {
    const r = await fetch(`${API_BASE}/api/ssh-keys`);
    const j = await r.json();
    const sel = document.getElementById('buildSsh');
    if (sel) {
      sel.innerHTML = j.keys.map(k => `<option value="${k}">${k}</option>`).join('');
    }
  } catch(e) {
    console.error("Failed to load SSH keys", e);
  }
}

// Asset Management Logic
async function refreshAssets() {
  // Target refresh icons and ensure they can rotate
  const icons = document.querySelectorAll('.bi-arrow-clockwise');
  icons.forEach(icon => {
    icon.style.display = 'inline-block';
    icon.style.transition = 'transform 1s cubic-bezier(0.4, 0, 0.2, 1)';
    const currentRot = parseInt(icon.dataset.rot || '0', 10);
    const newRot = currentRot + 360;
    icon.style.transform = `rotate(${newRot}deg)`;
    icon.dataset.rot = newRot;
  });

  try {
    const r = await fetch(`${API_BASE}/api/assets`);
    const data = await r.json();

    const imgList = document.getElementById('imageList');
    if (imgList) {
      const images = (data.images || []).filter(f => f.endsWith('.qcow2') || f.endsWith('.raw'));
      imgList.innerHTML = images.map(f => `
        <li style="display:flex; justify-content:space-between; align-items: center; margin-bottom:8px; padding-bottom:4px; border-bottom:1px solid rgba(255,255,255,0.05);">
          <span>${f}</span>
          <button onclick="deleteAsset('image', '${f}')" style="background:transparent; border:none; color:#ef4444; cursor:pointer;"><i class="bi bi-trash"></i></button>
        </li>
      `).join('') || '<li>No images found</li>';
    }

    const udList = document.getElementById('userDataList');
    if (udList) {
      const userDatas = (data.user_datas || []).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'));
      udList.innerHTML = userDatas.map(f => `
        <li style="display:flex; justify-content:space-between; align-items: center; margin-bottom:8px; padding-bottom:4px; border-bottom:1px solid rgba(255,255,255,0.05);">
          <span>${f}</span>
          <button onclick="deleteAsset('user-data', '${f}')" style="background:transparent; border:none; color:#ef4444; cursor:pointer;"><i class="bi bi-trash"></i></button>
        </li>
      `).join('') || '<li>No user data files found</li>';
    }
  } catch (e) {
    console.error("Refresh assets failed", e);
  }
}

// Dynamic Partition UI
function addPartitionRow(name='', type='8300', size='', mkfs='', mount='') {
  const container = document.getElementById('partitionList');
  const id = 'part_' + Date.now() + Math.floor(Math.random()*1000);
  const html = `
    <div id="${id}" style="display:flex; gap:8px; align-items:center; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
      <div style="flex:1;"><input type="text" class="qc-input-header part-name" placeholder="Name (e.g. root)" value="${name}" style="width:100%; height:28px; font-size:11px;" /></div>
      <div style="flex:1;"><input type="text" class="qc-input-header part-type" placeholder="Type (e.g. 8300)" value="${type}" style="width:100%; height:28px; font-size:11px;" /></div>
      <div style="flex:1;"><input type="text" class="qc-input-header part-size" placeholder="Size (e.g. 100%)" value="${size}" style="width:100%; height:28px; font-size:11px;" /></div>
      <div style="flex:1;"><input type="text" class="qc-input-header part-mkfs" placeholder="FS (e.g. ext4)" value="${mkfs}" style="width:100%; height:28px; font-size:11px;" /></div>
      <div style="flex:1.5;"><input type="text" class="qc-input-header part-mount" placeholder="Mount Point (e.g. /)" value="${mount}" style="width:100%; height:28px; font-size:11px;" /></div>
      <div><button class="qc-btn" style="padding: 2px 6px; color:#ef4444;" onclick="document.getElementById('${id}').remove()">X</button></div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', html);
}
window.addPartitionRow = addPartitionRow;

function getPartitionsArray() {
  const rows = document.querySelectorAll('#partitionList > div');
  const partitions = [];
  rows.forEach(row => {
    const name = row.querySelector('.part-name').value.trim();
    const type = row.querySelector('.part-type').value.trim();
    const size = row.querySelector('.part-size').value.trim();
    const mkfs = row.querySelector('.part-mkfs').value.trim();
    const mount = row.querySelector('.part-mount').value.trim();
    if (name && size) {
      partitions.push({ name, type, size, mkfs_type: mkfs, mount_point: mount });
    }
  });
  return partitions;
}

let buildTaskPollingId = null;

async function startBuildImage() {
  const type = 'os';
  const osFamily = document.getElementById('buildOsFamily').value;
  const release = document.getElementById('buildRelease').value;
  const sizeGb = document.getElementById('buildSize').value;
  const filename = document.getElementById('buildFilename').value;

  if (!filename) {
    alert("Please fill out the Output Filename.");
    return;
  }

  const partitions = getPartitionsArray();
  const pkgCheckboxes = document.querySelectorAll('.pkg-checkbox:checked');
  const packages = Array.from(pkgCheckboxes).map(cb => cb.value);

  const customPkgInput = document.getElementById('customPackages');
  if (customPkgInput && customPkgInput.value) {
     const extras = customPkgInput.value.split(',').map(x => x.trim()).filter(Boolean);
     packages.push(...extras);
  }

  const payload = {
    build_type: type,
    os_family: osFamily,
    release: release,
    size_gb: sizeGb,
    partitions: partitions,
    packages: packages,
    filename: filename
  };

  const statusEl = document.getElementById('buildProgressStatus');
  const pctEl = document.getElementById('buildProgressPct');
  const barEl = document.getElementById('buildProgressBar');
  const terminalEl = document.getElementById('buildLogTerminal');
  const terminalContainer = document.getElementById('buildTerminalContainer');
  const btnStart = document.getElementById('btnStartBuild');
  const btnStop = document.getElementById('btnStopBuild');

  if (terminalContainer) terminalContainer.style.display = 'flex';
  if (btnStart) btnStart.style.display = 'none';
  if (btnStop) btnStop.style.display = 'inline-block';

  if (statusEl) statusEl.textContent = 'Starting build...';
  if (pctEl) pctEl.textContent = '0%';
  if (barEl) barEl.style.width = '0%';
  if (terminalEl) terminalEl.textContent = 'Initializing...';
  try {
    const r = await fetch(`${API_BASE}/api/assets/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await r.json();
    if (res.ok) {
      toastManager.show(`Build process started!`, 'success', 'Build');
      resumeBuildPolling(res.task_id);
    } else {
      alert('Build start failed: ' + res.error);
      if (btnStart) btnStart.style.display = 'inline-block';
      if (btnStop) btnStop.style.display = 'none';
    }
  } catch(e) {
    alert('Build request error: ' + e);
    if (btnStart) btnStart.style.display = 'inline-block';
    if (btnStop) btnStop.style.display = 'none';
  }
}

async function createUserData() {
  const filename = document.getElementById('udFilename').value;
  const hostname = document.getElementById('udHostname').value;
  const username = document.getElementById('udUser').value;
  const password = document.getElementById('udPass').value;

  if (!filename || !hostname || !username || !password) {
    alert("All User-Data fields are required.");
    return;
  }

  const processingId = toastManager.show(`Saving user-data...`, 'info', 'User-Data', 0);
  try {
    const r = await fetch(`${API_BASE}/api/assets/userdata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, hostname, username, password })
    });
    const res = await r.json();
    toastManager.hide(processingId);
    if (res.ok) {
      toastManager.show('User-Data saved successfully', 'success', 'Saved');
      refreshAssets();
    } else {
      alert('Save failed: ' + res.error);
    }
  } catch(e) {
    toastManager.hide(processingId);
    alert('Save error: ' + e);
  }
}

window.handleUploadAsset = async function() {
  const fileInput = document.getElementById('uploadAssetFile');
  if (!fileInput.files.length) return;
  const file = fileInput.files[0];
  const type = file.name.endsWith('.yaml') ? 'user-data' : 'image';
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  
  const processingId = toastManager.show(`Uploading ${file.name}...`, 'info', 'Upload', 0);
  try {
    const r = await fetch(`${API_BASE}/api/assets/upload`, {
      method: 'POST',
      body: formData
    });
    const res = await r.json();
    toastManager.hide(processingId);
    if (res.ok) {
      toastManager.show('Upload successful', 'success', 'Upload');
      fileInput.value = '';
      refreshAssets();
    } else {
      alert('Upload failed: ' + res.error);
    }
  } catch(e) {
    toastManager.hide(processingId);
    alert('Upload error: ' + e);
  }
};
