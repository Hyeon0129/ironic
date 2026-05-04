
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
