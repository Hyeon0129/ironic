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

function executePowerAction(action) {
  closeTaskModal('powerManagerModal');
  executeIronicAction(action);
}
window.executePowerAction = executePowerAction;

function executeIronicAction(action) {
  const selected = Array.from(selectedServers);
  if (selected.length === 0) { 
    alert('Please select at least one server from the table.'); 
    return; 
  }

  if (action === 'power-manager') {
    openTaskModal('powerManagerModal');
    return;
  }

  if (action === 'redfish-manager') {
    openTaskModal('redfishManagerModal');
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

  if (!confirm(`Are you sure you want to execute '${action}' on ${selected.length} servers?`)) return;

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
  fetch(`${API_BASE}/api/deploy_files`)
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
    }
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}

window.executeDeploy = executeDeploy;

function executeRedfish() {
  const address = document.getElementById('redfishAddress').value;
  const username = document.getElementById('redfishUsername').value;
  const password = document.getElementById('redfishPassword').value;
  const selected = Array.from(selectedServers);
  
  if (!address || !username || !password) {
    alert('Please fill out Address, Username, and Password.');
    return;
  }
  
  closeTaskModal('redfishManagerModal');
  const processingId = toastManager.show('Updating Redfish info...', 'info', 'Redfish', 0);
  
  fetch(`${API_BASE}/api/redfish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      uuids: selected, 
      address: address, 
      username: username, 
      password: password 
    })
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
      alert(`Redfish update initiated for ${successCount}/${selected.length} servers.\nErrors:\n${errors.join('\n')}`);
    } else {
      alert(`Redfish info successfully updated for ${successCount}/${selected.length} servers.`);
      document.getElementById('redfishAddress').value = '';
      document.getElementById('redfishPassword').value = '';
    }
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}
window.executeRedfish = executeRedfish;

function executeRaid(type) {
  const selected = Array.from(selectedServers);
  if (selected.length === 0) { 
    alert('Please select at least one server.'); 
    return; 
  }
  
  if (!confirm(`Are you sure you want to execute RAID '${type}' on ${selected.length} servers?`)) return;

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
    }
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
}
window.executeRaid = executeRaid;

window.toggleMaintenance = function(uuid, targetState) {
  if (!confirm(`Are you sure you want to turn ${targetState ? 'ON' : 'OFF'} maintenance for this node?`)) return;
  
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
    if(typeof fetchRowsFromApi === 'function') fetchRowsFromApi();
  }).catch((e)=>{
    toastManager.hide(processingId);
    console.error(e);
    alert('Request failed');
  });
};

// Task Item click handler (direct action)
document.querySelectorAll('#ironicActions .task-item').forEach(item => {
  item.addEventListener('click', (e) => {
    const action = item.dataset.action;
    
    if (item.classList.contains('action-rename')) {
      const selected = Array.from(selectedServers);
      if (selected.length !== 1) { 
        alert('Please select exactly one server from the table to rename.'); 
        return; 
      }
      const uuid = selected[0];
      const newName = prompt('Enter new node name:');
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
