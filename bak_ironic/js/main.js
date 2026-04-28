
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const API_BASE = `${location?.protocol || 'http:'}//${(location && location.hostname) ? location.hostname : '127.0.0.1'}:8000`;

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

window.alert = function(message) {
  let title = 'QC Core';
  let type = 'info';
  
  if (message.includes('Task:')) {
    title = 'Task Executed';
    type = 'success';
  } else if (message.includes('Executing')) {
    title = 'Execution';
    type = 'success';
  } else if (message.includes('Selected OS:')) {
    title = 'OS Selected';
    type = 'success';
  } else if (message.includes('Please select')) {
    title = 'Selection Required';
    type = 'warning';
  }
  
  toastManager.show(message, type, title);
};


let alarmState = {
  issues: [],
  isDropdownOpen: false
};

const healthAlarmCache = new Map();
const HEALTH_STALE_MS = 60000;
const healthPresenceCache = new Map();
const PRESENCE_STALE_MS = 120000;

function toggleAlarmDropdown() {
  const dropdown = $("#alarmDropdown");
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
  startAlarmPolling();
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
  });
} else {
  window.themeManager = new ThemeManager();
}


async function startAlarmPolling(){
  async function poll(){
    try{
      const [mapRes, detRes] = await Promise.all([
        fetch(`${API_BASE}/health/logs`),
        fetch(`${API_BASE}/health/logs/detail`)
      ]);
      let present = null;
      if (mapRes.ok) present = await mapRes.json();
      let details = {};
      if (detRes.ok) details = await detRes.json();

      const now = Date.now();
      if (present){
        Object.keys(present || {}).forEach(ip => {
          healthPresenceCache.set(ip, { lastSeen: now });
        });
      }
      const keepIPs = [];
      for (const [ip, rec] of healthPresenceCache.entries()){
        if (now - (rec.lastSeen || 0) <= PRESENCE_STALE_MS){
          keepIPs.push(ip);
        } else {
          healthPresenceCache.delete(ip);
        }
      }
      keepIPs.forEach(ip => {
        const info = details[ip] || {};
        const prev = healthAlarmCache.get(ip);
        if (info && (info.content || info.filename)){
          const content = info.content || '';
          const filename = info.filename || '';
          healthAlarmCache.set(ip, { content, filename, lastSeen: now });
        } else if (prev && (now - (prev.lastSeen || 0) <= HEALTH_STALE_MS)) {
          healthAlarmCache.set(ip, { ...prev });
        }
      });
      alarmState.issues = keepIPs.map(ip=>{
        const rec = healthAlarmCache.get(ip) || { content: '', filename: '' };
        return { bmcip: ip, content: rec.content, filename: rec.filename };
      });
      renderAlarmBell(alarmState.issues.length);
      renderAlarmList(alarmState.issues);
    }catch{}
    setTimeout(poll, 5000);
  }
  poll();
}

function renderAlarmBell(count){
  const icon = document.getElementById('alarmIcon');
  const badge = document.getElementById('alarmBadge');
  if (!icon || !badge) return;
  if (count > 0){
    icon.classList.add('active');
    badge.style.display = 'flex';
    badge.textContent = String(count);
  } else {
    icon.classList.remove('active');
    badge.style.display = 'none';
  }
}

function renderAlarmList(issues){
  const list = document.getElementById('alarmList');
  if (!list) return;
  if (!issues || issues.length === 0){
    list.innerHTML = '<div style="text-align:center; color:rgba(184,194,210,.7); padding:20px;">No alerts</div>';
    return;
  }
  const items = issues.map((it, idx)=>{
    const rec = parseHealthLog(it.bmcip, it.content || '');
    const title = rec ? `${rec.bmcip} - ${rec.severity.toUpperCase()}` : it.bmcip;
    const desc = rec ? rec.description : 'Health anomaly detected';
    return `
      <div class="alarm-item" data-idx="${idx}">
        <div class="alarm-item-icon"></div>
        <div class="alarm-item-content">
          <div class="alarm-item-title">${title}</div>
          <div class="alarm-item-desc">${desc}</div>
        </div>
      </div>`;
  }).join('');
  list.innerHTML = items;
  const container = document.getElementById('alarmList');
  if (container){
    container.querySelectorAll('.alarm-item').forEach((el,i)=>{
      el.addEventListener('click', ()=>{
        const issue = alarmState.issues[i];
        if (!issue) return;
        const rec = parseHealthLog(issue.bmcip, issue.content || '');
        openHealthDetail(rec || { bmcip: issue.bmcip, timestamp: '-', severity: 'unknown', sensor: '-', type: '-', description: 'See raw log' });
      });
    });
  }
}

function openHealthDetail(rec){
  const modal = document.getElementById('alarmModal');
  if (!modal) return;
  const elements = {
    m_bmcip: rec.bmcip || '-',
    m_ts: rec.timestamp || '-',
    m_sev: (rec.severity || '-').toUpperCase(),
    m_sensor: rec.sensor || '-',
    m_type: rec.type || '-',
    m_desc: rec.description || '-'
  };
  Object.entries(elements).forEach(([id,val])=>{ const el=document.getElementById(id); if (el) el.textContent = val; });
  modal.classList.add('show');
}


function parseHealthLog(bmcip, content){
  try{
    const parts = (content||'').split('|').map(s=>s.trim()).filter(Boolean);
    const events = [];
    for (let i=0; i<parts.length; i++){
      const p = parts[i];
      if (/^\d{4}-\d{2}-\d{2}T/.test(p)){
        const timestamp = parts[i];
        const sensor = parts[i+1] || '';
        const _assert = parts[i+2] || '';
        const severity = (parts[i+3] || '').toLowerCase();
        const code = parts[i+4] || '';
        const description = (parts[i+5] || '').replace(/^"`/, '').trim();
        const type = sensor === 'PSU' ? 'Power Supply' : sensor;
        events.push({ timestamp, sensor, type, severity, code, description });
      }
    }
    if (events.length === 0) return null;
    const rank = { critical: 3, warning: 2, ok: 1 };
    events.sort((a,b)=> (rank[b.severity]||0) - (rank[a.severity]||0));
    return { bmcip, ...events[0] };
  }catch{ return null; }
}