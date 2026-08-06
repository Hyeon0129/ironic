
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const API_BASE = `${location.protocol}//${location.hostname}:8000`;

class ThemeManager {
  constructor() {
    this.currentTheme = localStorage.getItem('theme') || 'dark';
    this.init();
  }
  
  init() {
    document.documentElement.setAttribute('data-theme', this.currentTheme);
    
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }
  }
  
  toggleTheme() {
    this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', this.currentTheme);
    localStorage.setItem('theme', this.currentTheme);
  }
}

class ToastManager {
  constructor() {
    this.container = document.getElementById('toastContainer');
    this.toasts = new Map();
    this.toastId = 0;
  }
  
  show(message, type = 'info', title = null, duration = 4000) {
    const id = ++this.toastId;
    
    const icons = { info: '', success: '', error: '', warning: '' };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-accent"></span>
      <div class="toast-icon" aria-hidden="true"></div>
      <div class="toast-content">
        ${title ? `<div class="toast-title">${title}</div>` : ''}
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close">×</button>
      <div class="toast-progress"></div>
    `;
    
    this.container.appendChild(toast);
    this.toasts.set(id, toast);
    
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
      this.hide(id);
    });
    
    setTimeout(() => {
      toast.classList.add('show');
    }, 10);
    
    const bar = toast.querySelector('.toast-progress');
    bar.style.transitionDuration = duration + 'ms';
    requestAnimationFrame(()=>{
      bar.style.transform = 'scaleX(1)';
    });

    if (duration > 0) {
      setTimeout(() => {
        this.hide(id);
      }, duration);
    }
    
    return id;
  }
  
  hide(id) {
    const toast = this.toasts.get(id);
    if (toast) {
      toast.classList.remove('show');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
        this.toasts.delete(id);
      }, 300);
    }
  }
  
  clear() {
    this.toasts.forEach((toast, id) => {
      this.hide(id);
    });
  }
}

const toastManager = new ToastManager();

window.customConfirm = function(message) {
  return new Promise((resolve) => {
    const modal = document.getElementById('customConfirmModal');
    const titleEl = document.getElementById('customConfirmTitle');
    const msgEl = document.getElementById('customConfirmMessage');
    const btnOk = document.getElementById('customConfirmOk');
    const btnCancel = document.getElementById('customConfirmCancel');

    if(!modal) {
      resolve(window.confirm(message));
      return;
    }

    let cleanMessage = message;
  cleanMessage = cleanMessage.replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}\s*내용:\s*/g, '').replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}\s*/g, '');
    
    titleEl.textContent = 'Confirm Action';
    msgEl.innerHTML = cleanMessage.replace(/\n/g, '<br>');
    btnCancel.style.display = 'block';
    const promptInput = document.getElementById('customPromptInput');
    if (promptInput) promptInput.style.display = 'none';
    
    modal.classList.add('show');

    const handleOk = () => {
      cleanup();
      resolve(true);
    };

    const handleCancel = () => {
      cleanup();
      resolve(false);
    };

    const cleanup = () => {
      modal.classList.remove('show');
      btnOk.removeEventListener('click', handleOk);
      btnCancel.removeEventListener('click', handleCancel);
    };

    btnOk.addEventListener('click', handleOk);
    btnCancel.addEventListener('click', handleCancel);
  });
};

window.alert = function(message) {
  // Hide the default toast-based alert and use the new Liquid Glass Alert
  const modal = document.getElementById('customConfirmModal');
  const titleEl = document.getElementById('customConfirmTitle');
  const msgEl = document.getElementById('customConfirmMessage');
  const btnOk = document.getElementById('customConfirmOk');
  const btnCancel = document.getElementById('customConfirmCancel');

  if(!modal) {
    console.log("Alert:", message);
    return;
  }

  let cleanMessage = message;
  cleanMessage = cleanMessage.replace(/192\.168\.222\.152:\d{1,5}\s*내용:\s*/g, '');

  let title = 'Ironic Dashboard';
  const lowerMsg = cleanMessage.toLowerCase();
  
  if (lowerMsg.includes('successfully') || lowerMsg.includes('success') || lowerMsg.includes('initiated')) {
    title = 'Action Success';
  } else if (lowerMsg.includes('failed') || lowerMsg.includes('error')) {
    title = 'Action Failed';
  } else if (lowerMsg.includes('please select')) {
    title = 'Selection Required';
  }

  titleEl.textContent = title;
  msgEl.innerHTML = cleanMessage.replace(/\n/g, '<br>');
  btnCancel.style.display = 'none';
  
  modal.classList.add('show');

  const handleOk = () => {
    modal.classList.remove('show');
    btnOk.removeEventListener('click', handleOk);
    btnCancel.style.display = 'block';
    const promptInput = document.getElementById('customPromptInput');
    if (promptInput) promptInput.style.display = 'none'; // Reset back to default
  };

  btnOk.addEventListener('click', handleOk);
};

let alarmState = {
  issues: [],
  isDropdownOpen: false
};

function toggleAlarmDropdown() {
  const dropdown = $("#alarmDropdown");
  if(!dropdown) return;
  alarmState.isDropdownOpen = !alarmState.isDropdownOpen;
  
  if (alarmState.isDropdownOpen) {
    dropdown.classList.add("show");
  } else {
    dropdown.classList.remove("show");
  }
}

document.addEventListener('click', (e) => {
  const alarmContainer = document.querySelector('.alarm-container');
  if (alarmContainer && !alarmContainer.contains(e.target) && alarmState.isDropdownOpen) {
    toggleAlarmDropdown();
  }
});

document.addEventListener("DOMContentLoaded", ()=>{
  const sb = document.querySelector('.sidebar');
  if (sb) sb.classList.remove('collapsed');
  localStorage.removeItem('sidebarCollapsed');
});

$("#alarmIcon")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleAlarmDropdown();
});

document.addEventListener('DOMContentLoaded', () => {
  window.themeManager = new ThemeManager();
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
  });
} else {
  window.themeManager = new ThemeManager();
}

function updateAlarmSystem() {
  if (typeof state === 'undefined' || !state.data) return;
  const issues = state.data.filter(row => row.health === 'error' || row.health === 'critical');
  
  alarmState.issues = issues;
  const alarmIcon = document.getElementById("alarmIcon");
  const badge = document.getElementById("alarmBadge");
  const list = document.getElementById("alarmList");
  
  if (issues.length > 0) {
    if (alarmIcon) alarmIcon.classList.add("active");
    if (badge) {
      badge.style.display = "flex";
      badge.textContent = issues.length;
    }
  } else {
    if (alarmIcon) alarmIcon.classList.remove("active");
    if (badge) badge.style.display = "none";
  }
  
  if (list) {
    if (issues.length === 0) {
      list.innerHTML = '<div style="text-align:center; color:rgba(184,194,210,.7); padding:20px;">No alerts</div>';
    } else {
      list.innerHTML = issues.map((issue, idx) => `
        <div class="alarm-item" data-idx="${idx}">
          <div class="alarm-item-icon"></div>
          <div class="alarm-item-content">
            <div class="alarm-item-title">${issue.name || issue.uuid} - Error</div>
          </div>
        </div>
      `).join('');
      
      list.querySelectorAll('.alarm-item').forEach((el, i) => {
        el.addEventListener('click', () => {
          const issue = alarmState.issues[i];
          if (issue) openAlarmDetail(issue);
        });
      });
    }
  }
}

function openAlarmDetail(issue) {
  const modal = document.getElementById('alarmModal');
  if (!modal) return;
  
  const elements = {
    m_name: issue.name || issue.uuid || '-',
    m_osip: issue.os_ip || '-',
    m_bmcip: issue.bmc_ip || '-',
    m_desc: issue.last_error || '-'
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

const modalClose = document.getElementById('modalClose');
if (modalClose) {
  modalClose.addEventListener('click', closeAlarmDetail);
}

document.getElementById('alarmModal')?.addEventListener('click', (e) => {
  if (e.target.id === 'alarmModal') closeAlarmDetail();
});

setInterval(updateAlarmSystem, 1000);

// Node Detail Modal — opened by clicking any row in the main table.
// Same modal-backdrop/modal-panel/modal-grid look as the alarm detail
// modal above, plus a small "Recent History" list (Ironic's Node History
// API, populated whenever last_error is set on the node).
// Ironic node history severities are ERROR/WARNING/INFO (python logging
// levels) — give each its own glyph + color instead of just a color swap,
// so the icon itself communicates status at a glance.
function getHistoryIcon(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'error' || s === 'critical') {
    return { glyph: '✕', bg: 'linear-gradient(135deg, rgba(220,53,69,.9), rgba(183,28,28,.8))' };
  }
  if (s === 'warning') {
    return { glyph: '!', bg: 'linear-gradient(135deg, rgba(245,158,11,.95), rgba(217,119,6,.9))' };
  }
  return { glyph: 'i', bg: 'linear-gradient(135deg, rgba(78,130,255,.9), rgba(58,100,220,.8))' };
}

async function openNodeDetail(uuid) {
  const modal = document.getElementById('nodeDetailModal');
  if (!modal || !uuid) return;
  modal.classList.add('show');

  const setVal = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (value === undefined || value === null || value === '') ? '-' : value;
  };

  // Show what we already have from the table's 1s poll instantly, then
  // fill in the rest (driver, image, inventory, history) from the detail call.
  const cached = (typeof state !== 'undefined' && state.data) ? state.data.find(r => r.uuid === uuid) : null;
  setVal('nd_name', cached ? (cached.name || cached.uuid) : uuid);
  setVal('nd_uuid', uuid);
  setVal('nd_power', cached?.power);
  setVal('nd_provision', cached?.provision_state);
  setVal('nd_maintenance', cached ? (cached.maintenance ? 'ON' : 'OFF') : '-');
  setVal('nd_osip', cached?.os_ip);
  setVal('nd_bmcip', cached?.bmc_ip);
  setVal('nd_lasterror', cached?.last_error);
  ['nd_driver', 'nd_image'].forEach(id => setVal(id, 'Loading...'));
  const invEl = document.getElementById('nd_inventory');
  if (invEl) invEl.innerHTML = '<div class="modal-label">Hardware</div><div class="modal-value">Loading...</div>';
  const histEl = document.getElementById('nd_history');
  if (histEl) histEl.innerHTML = '<div style="text-align:center; color:rgba(184,194,210,.7); padding:12px; font-size:12px;">Loading...</div>';

  try {
    const r = await fetch(`${window.API_BASE}/api/nodes/${uuid}/detail`);
    const data = await r.json();
    if (!data.ok) {
      if (invEl) invEl.innerHTML = `<div class="modal-label">Hardware</div><div class="modal-value">Failed to load: ${data.error || 'unknown'}</div>`;
      return;
    }
    const n = data.node;
    setVal('nd_name', n.name || n.uuid);
    setVal('nd_power', n.power_state);
    setVal('nd_provision', n.provision_state);
    setVal('nd_maintenance', n.maintenance ? `ON (${n.maintenance_reason || '-'})` : 'OFF');
    setVal('nd_osip', n.os_ip);
    setVal('nd_bmcip', n.bmc_ip);
    setVal('nd_driver', n.driver);
    setVal('nd_image', (n.instance_info || {}).image_source);
    setVal('nd_lasterror', n.last_error);
    renderInventory(data.inventory || {});

    const hist = data.history || [];
    if (!histEl) return;
    if (!hist.length) {
      histEl.innerHTML = '<div style="text-align:center; color:rgba(184,194,210,.7); padding:12px; font-size:12px;">No history recorded</div>';
    } else {
      histEl.innerHTML = hist.map(h => {
        const { glyph, bg } = getHistoryIcon(h.severity);
        return `
          <div class="alarm-item" style="cursor:default;">
            <div class="nd-history-icon" style="background:${bg};">${glyph}</div>
            <div class="alarm-item-content">
              <div class="alarm-item-title">${h.event || '-'}</div>
              <div class="alarm-item-desc">${h.created_at || ''}${h.event_type ? ' · ' + h.event_type : ''}</div>
            </div>
          </div>`;
      }).join('');
    }
  } catch (e) {
    console.error('Failed to load node detail', e);
    if (invEl) invEl.innerHTML = '<div class="modal-label">Hardware</div><div class="modal-value">Request failed</div>';
  }
}

// Builds the CPU/Memory/Disk/NIC rows below the main grid from Ironic's
// introspection inventory (GET /nodes/{uuid}/inventory — same data as
// `baremetal node inventory save`). Empty inventory just means the node
// hasn't been inspected yet (see the sidebar's Inspect action).
function renderInventory(inv) {
  const el = document.getElementById('nd_inventory');
  if (!el) return;
  const rows = [];

  if (inv.cpu_model) {
    rows.push(['CPU', inv.cpu_arch ? `${inv.cpu_model} (${inv.cpu_arch})` : inv.cpu_model]);
  }
  if (inv.memory_gb != null) {
    rows.push(['Memory', `${inv.memory_gb} GB`]);
  }
  const disks = inv.disks || [];
  disks.forEach((d, i) => {
    const bits = [];
    if (d.size_gb != null) bits.push(`${d.size_gb} GB`);
    if (d.vendor) bits.push(`vendor ${d.vendor}`);
    if (d.serial) bits.push(`serial ${d.serial}`);
    const label = disks.length > 1 ? `Disk ${i + 1}` : 'Disk';
    rows.push([label, `${d.name || '-'}${bits.length ? ' — ' + bits.join(', ') : ''}`]);
  });
  // ipv4_address here is deliberately left out: it's whatever the IPA
  // ramdisk had at inspection/cleaning time, not the node's current IP —
  // showing it next to the (correct, live) OS IP field above would just be
  // confusing. MAC is stable, so that's the only thing worth surfacing.
  const nics = inv.interfaces || [];
  nics.forEach((n, i) => {
    const label = nics.length > 1 ? `NIC ${i + 1}` : 'NIC';
    rows.push([label, `${n.name || '-'}${n.mac_address ? ' — ' + n.mac_address : ''}`]);
  });

  el.innerHTML = rows.length
    ? rows.map(([l, v]) => `<div class="modal-label">${l}</div><div class="modal-value">${v}</div>`).join('')
    : '<div class="modal-label">Hardware</div><div class="modal-value">Not inspected yet</div>';
}

function closeNodeDetail() {
  const modal = document.getElementById('nodeDetailModal');
  if (modal) modal.classList.remove('show');
}

document.getElementById('nodeDetailClose')?.addEventListener('click', closeNodeDetail);
document.getElementById('nodeDetailModal')?.addEventListener('click', (e) => {
  if (e.target.id === 'nodeDetailModal') closeNodeDetail();
});

window.openNodeDetail = openNodeDetail;

window.customPrompt = function(message) {
  return new Promise((resolve) => {
    const modal = document.getElementById('customConfirmModal');
    const titleEl = document.getElementById('customConfirmTitle');
    const msgEl = document.getElementById('customConfirmMessage');
    const btnOk = document.getElementById('customConfirmOk');
    const btnCancel = document.getElementById('customConfirmCancel');

    if(!modal) {
      resolve(prompt(message));
      return;
    }

    let cleanMessage = message;
  cleanMessage = cleanMessage.replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}\s*내용:\s*/g, '').replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}\s*/g, '');
    
    titleEl.textContent = 'Input Required';
    msgEl.innerHTML = cleanMessage.replace(/\n/g, '<br>');
    let inputEl = document.getElementById('customPromptInput');
    if (!inputEl) {
      inputEl = document.createElement('input');
      inputEl.type = 'text';
      inputEl.id = 'customPromptInput';
      inputEl.className = 'custom-dialog-input';
      inputEl.style = 'margin-top: 15px; width: 90%;';
      msgEl.appendChild(document.createElement('br'));
      msgEl.appendChild(inputEl);
    }
    inputEl.style.display = 'block';
    inputEl.value = '';
    btnCancel.style.display = 'block';

    modal.classList.add('show');    
    // Focus the input
    setTimeout(() => {
        const inputEl = document.getElementById('customPromptInput');
        if(inputEl) inputEl.focus();
    }, 50);

    const handleOk = () => {
      const inputEl = document.getElementById('customPromptInput');
      const val = inputEl ? inputEl.value : null;
      cleanup();
      resolve(val);
    };

    const handleCancel = () => {
      cleanup();
      resolve(null);
    };

    const cleanup = () => {
      modal.classList.remove('show');
      btnOk.removeEventListener('click', handleOk);
      btnCancel.removeEventListener('click', handleCancel);
    };

    btnOk.addEventListener('click', handleOk);
    btnCancel.addEventListener('click', handleCancel);
  });
};
