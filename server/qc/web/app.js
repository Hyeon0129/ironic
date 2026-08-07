"use strict";

// ════════════════════════════════════════════════════════════════
// 아이콘 (인라인 SVG, 외부 아이콘 폰트/CDN 없이 자체 세트)
// ════════════════════════════════════════════════════════════════
const ICON_PATHS = {
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  layers: '<polygon points="12 3 3 8 12 13 21 8 12 3"/><polyline points="3 13 12 18 21 13"/><polyline points="3 18 12 22.5 21 18"/>',
  disc: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.6"/>',
  database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8v-13"/><path d="M4.5 12c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8"/>',
  tag: '<path d="M3 11.2V5.5A2.5 2.5 0 0 1 5.5 3h5.7c.66 0 1.3.26 1.77.73l8.3 8.3a2.5 2.5 0 0 1 0 3.54l-5.7 5.7a2.5 2.5 0 0 1-3.54 0l-8.3-8.3A2.5 2.5 0 0 1 3 11.2Z"/><circle cx="8" cy="8" r="1.4"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.2"/><path d="m10.6 12.4 7.9-7.9M16.8 5.2l2 2M19.7 2.3l2 2"/>',
  camera: '<path d="M22 18.5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.7a2 2 0 0 1 2-2h3.4l1.7-2.4h5.8l1.7 2.4H20a2 2 0 0 1 2 2Z"/><circle cx="12" cy="13" r="3.6"/>',
  edit: '<path d="M11.5 20.5H21"/><path d="M16 4.5a2.1 2.1 0 0 1 3 3L7.5 19 3 20l1-4.5Z"/>',
  hardDrive: '<line x1="21" y1="12" x2="3" y2="12"/><path d="M6 5.5 3 12v6a1.8 1.8 0 0 0 1.8 1.8h14.4A1.8 1.8 0 0 0 21 18v-6l-3-6.5A1.9 1.9 0 0 0 16.3 4.5H7.7A1.9 1.9 0 0 0 6 5.5Z"/><circle cx="6.5" cy="15.3" r=".4" fill="currentColor" stroke="none"/><circle cx="9.7" cy="15.3" r=".4" fill="currentColor" stroke="none"/>',
  barChart: '<line x1="5" y1="21" x2="5" y2="14"/><line x1="12" y1="21" x2="12" y2="8"/><line x1="19" y1="21" x2="19" y2="3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/>',
  hourglass: '<path d="M6 3h12M6 21h12M7 3c0 5 4 6.5 5 8-1 1.5-5 3-5 8M17 3c0 5-4 6.5-5 8 1 1.5 5 3 5 8"/>',
  refreshCw: '<polyline points="21 4 21 9 16 9"/><polyline points="3 20 3 15 8 15"/><path d="M4.6 9a8 8 0 0 1 13.2-3L21 9M3 15l3.2 3A8 8 0 0 0 19.4 15"/>',
  power: '<path d="M17.5 6.3a8 8 0 1 1-11 0"/><line x1="12" y1="3" x2="12" y2="11"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  copyPlus: '<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M4.5 15.5h-1a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/><line x1="14.5" y1="12" x2="14.5" y2="17"/><line x1="12" y1="14.5" x2="17" y2="14.5"/>',
  trash: '<polyline points="3.5 6 5.5 6 20.5 6"/><path d="M18.5 6v13a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2V6m3 0V3.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V6"/>',
  upload: '<path d="M20 16v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3"/><polyline points="16.5 8.5 12 4 7.5 8.5"/><line x1="12" y1="4" x2="12" y2="15.5"/>',
  checkSquare: '<polyline points="8.5 12.5 11 15 16.5 8"/><path d="M20 11v7.5a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2H15"/>',
  square: '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 13.5a1.65 1.65 0 0 0 .3 1.8l.05.06a2 2 0 1 1-2.8 2.8l-.07-.05a1.65 1.65 0 0 0-1.8-.3 1.65 1.65 0 0 0-1 1.5V19.5a2 2 0 0 1-4 0v-.1a1.65 1.65 0 0 0-1-1.5 1.65 1.65 0 0 0-1.8.3l-.06.05a2 2 0 1 1-2.8-2.8l.05-.07a1.65 1.65 0 0 0 .3-1.8 1.65 1.65 0 0 0-1.5-1H2.5a2 2 0 0 1 0-4h.1a1.65 1.65 0 0 0 1.5-1 1.65 1.65 0 0 0-.3-1.8l-.05-.06a2 2 0 1 1 2.8-2.8l.07.05a1.65 1.65 0 0 0 1.8.3H8.5a1.65 1.65 0 0 0 1-1.5V2.5a2 2 0 0 1 4 0v.1a1.65 1.65 0 0 0 1 1.5 1.65 1.65 0 0 0 1.8-.3l.06-.05a2 2 0 1 1 2.8 2.8l-.05.07a1.65 1.65 0 0 0-.3 1.8V8.5a1.65 1.65 0 0 0 1.5 1H21.5a2 2 0 0 1 0 4h-.1a1.65 1.65 0 0 0-1.5 1Z"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  monitor: '<rect x="2.5" y="4" width="19" height="13" rx="1.8"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
  globe: '<circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a13.5 13.5 0 0 1 3.5 9A13.5 13.5 0 0 1 12 21a13.5 13.5 0 0 1-3.5-9A13.5 13.5 0 0 1 12 3Z"/>',
  activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  plug: '<path d="M12 21.5v-4.7"/><path d="M9 8.3V2.8M15 8.3V2.8"/><path d="M17.7 8.3a1.9 1.9 0 0 1 1.9 1.9v1.6a7.6 7.6 0 0 1-15.2 0v-1.6a1.9 1.9 0 0 1 1.9-1.9Z"/>',
  memory: '<rect x="3" y="7" width="18" height="10" rx="1.5"/><line x1="7" y1="7" x2="7" y2="4.5"/><line x1="11" y1="7" x2="11" y2="4.5"/><line x1="15" y1="7" x2="15" y2="4.5"/><line x1="7" y1="19.5" x2="7" y2="17"/><line x1="11" y1="19.5" x2="11" y2="17"/><line x1="15" y1="19.5" x2="15" y2="17"/>',
  gpu: '<rect x="2.5" y="6" width="19" height="11" rx="1.8"/><circle cx="8" cy="11.5" r="2.2"/><polyline points="19.5 15 15 10.5 5.5 16.5"/>',
  network: '<circle cx="18" cy="5.5" r="2.6"/><circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="18.5" r="2.6"/><line x1="8.4" y1="13.2" x2="15.4" y2="17.1"/><line x1="15.4" y1="6.9" x2="8.4" y2="10.8"/>',
  shield: '<path d="M12 21.5s7.5-3.7 7.5-9.4V5.6L12 2.5l-7.5 3.1v6.5c0 5.7 7.5 9.4 7.5 9.4Z"/><polyline points="8.7 11.7 10.8 13.8 15.3 9.3"/>',
  boxes: '<path d="M21 8.2V6a1.8 1.8 0 0 0-.9-1.56l-6.3-3.6a1.8 1.8 0 0 0-1.8 0l-6.3 3.6A1.8 1.8 0 0 0 4.8 6v8.2a1.8 1.8 0 0 0 .9 1.56l6.3 3.6a1.8 1.8 0 0 0 1.8 0l1.2-.7"/><polyline points="4.95 6.05 12.6 10.4 20.25 6.05"/><line x1="12.6" y1="22.1" x2="12.6" y2="10.4"/><path d="M17.5 15.5v3.4M15.8 17.2h3.4"/>',
  list: '<line x1="9" y1="6.5" x2="21" y2="6.5"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="9" y1="17.5" x2="21" y2="17.5"/><line x1="4" y1="6.5" x2="4.01" y2="6.5"/><line x1="4" y1="12" x2="4.01" y2="12"/><line x1="4" y1="17.5" x2="4.01" y2="17.5"/>',
  eye: '<path d="M2 12s3.8-7 10-7 10 7 10 7-3.8 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  chevronDown: '<polyline points="6 9 12 15 18 9"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="1.8"/><polyline points="21 15.5 15.5 10 5 20.5"/>',
  folder: '<path d="M3 6.2A1.7 1.7 0 0 1 4.7 4.5h4.6l2 2.4h8A1.7 1.7 0 0 1 21 8.6v9.7A1.7 1.7 0 0 1 19.3 20H4.7A1.7 1.7 0 0 1 3 18.3Z"/>',
  filter: '<polygon points="4 4 20 4 14 12.5 14 19 10 21 10 12.5 4 4"/>',
  search: '<circle cx="11" cy="11" r="7.5"/><line x1="21" y1="21" x2="16.2" y2="16.2"/>',
  panelLeft: '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="9" y1="4" x2="9" y2="20"/>',
  clipboardCheck: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 3v1"/><polyline points="9 13 11 15 15.5 10"/>',
};

function icon(name, cls = "icon") {
  const p = ICON_PATHS[name];
  if (!p) return "";
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
}

// 정적 마크업의 data-icon 속성을 아이콘으로 치환 (버튼/헤더 등, 최초 1회)
function applyStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon));
  });
}
applyStaticIcons();

// ════════════════════════════════════════════════════════════════
// 상태
// ════════════════════════════════════════════════════════════════
const state = {
  config: {},
  servers: [],      // [{ip, serial}]
  status: {},       // ip -> {...}
  selected: new Set(),
  busy: {},         // ip -> {action -> {busy, progress}}
  searchQuery: "",
  pageSize: 10,
  currentPage: 1,
  tableColumns: [],  // 업체 프로필에 따라 추가되는 표 컬럼 — [{id, label, icon}], applyProfile() 참고
};

// 로컬 HTTP 서버(/api/<method>)를 pywebview.api 와 동일한 문법(api().method(...))으로 호출.
const api = () => new Proxy({}, {
  get: (_, method) => async (...args) => {
    const r = await fetch(`/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    return r.json();
  },
});

function ipRowId(ip) { return "row-" + ip.replace(/\./g, "-"); }

// 백엔드 실시간 이벤트(SSE) 구독 — 끊기면 브라우저가 자동 재연결한다.
function connectEvents() {
  const es = new EventSource("/events");
  es.onmessage = (e) => {
    try {
      const { event, payload } = JSON.parse(e.data);
      window.__push(event, payload);
    } catch (err) { /* keep-alive 핑 등은 무시 */ }
  };
}

// ════════════════════════════════════════════════════════════════
// 초기화
// ════════════════════════════════════════════════════════════════
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

const isLogOnly = new URLSearchParams(location.search).get("logonly") === "1";

async function init() {
  if (isLogOnly) document.documentElement.classList.add("log-only");
  connectEvents();
  const s = await api().get_state();
  state.config = s.config || {};
  state.servers = s.servers || [];
  state.status = s.status || {};
  // Was pre-selecting every server on load — with just 1-2 servers registered
  // this made every row look permanently "selected" (blue highlight + filled
  // checkbox) before the user ever clicked anything, which also threw off
  // every visual comparison against the main dashboard (rows there start
  // unselected). Nothing should be selected until the checkbox is clicked.
  state.selected = new Set();

  document.getElementById("cred-sales").value = state.config.sales_number || "";
  document.getElementById("cred-user").value = state.config.username || "";
  document.getElementById("cred-pass").value = state.config.password || "";

  await applyProfile();
  wireStaticEvents();
  wireLogResize();
  if (!isLogOnly) wireLogDetach();

  // 이전에 껐다 켜도 작업 로그가 이어지도록 저장된 기록을 그대로 재생
  for (const entry of s.log_history || []) appendLog(entry);
}

// ════════════════════════════════════════════════════════════════
// 백엔드 → 프론트 푸시
// ════════════════════════════════════════════════════════════════
window.__push = function (event, payload) {
  if (event === "log") appendLog(payload);
  else if (event === "status") onStatusPush(payload);
  else if (event === "busy") onBusyPush(payload);
  else if (event === "capture") onCapturePush(payload);
  else if (event === "log_window_closed") showLogPanel();
  else if (event === "batch_done") onBatchDone(payload);
  else if (event === "server_updated") onServerUpdated(payload);
};

function onServerUpdated({ ip, serial }) {
  const s = state.servers.find((x) => x.ip === ip);
  if (s) { s.serial = serial; renderRow(ip); }
}

function onStatusPush(payload) {
  const { ip, ...rest } = payload;
  const st = (state.status[ip] = state.status[ip] || {});
  Object.assign(st, rest);
  renderRow(ip);
  updateStatChip();
}

function onBusyPush(payload) {
  const { ip, action, busy, progress } = payload;
  const b = (state.busy[ip] = state.busy[ip] || {});
  if (busy) b[action] = { busy: true, progress: progress ?? null };
  else delete b[action];
  renderRowProgress(ip);
}

function onCapturePush(payload) {
  const label = CAPTURE_KIND_LABELS[payload.kind] || "캡처";
  toast(`[${payload.serial}] ${label} 캡처 완료`, "ok");
  // 배치로 여러 대를 한꺼번에 캡처하면 서버마다 완료 시점이 달라서, 캡처가 끝날 때마다
  // 바로 모달을 띄우면 먼저 끝난 서버 것부터 계속 덮어써져서 마지막 한 대 것만 남는 문제가
  // 있었다 — 개별 완료 시점에는 토스트만 띄우고, 뷰어는 배치 전체가 끝난 뒤(batch_done)
  // 시리얼 순서대로 넘겨볼 수 있게 한 번만 연다.
}

function onBatchDone({ name, ips }) {
  if (!name || !name.startsWith("capture_")) return;
  // "capture_all"(전체 캡처)은 5종을 순서대로 다 돌고 나서 한 번만 신호를 보낸다 — 첫 번째
  // 종류(장치관리자)부터 보여주고, 드롭다운으로 나머지 종류도 바로 돌려볼 수 있다.
  const kind = name === "capture_all" ? "devmgmt" : name.slice("capture_".length);
  openCaptureViewer(kind, ips);
}

// ════════════════════════════════════════════════════════════════
// 로그
// ════════════════════════════════════════════════════════════════
function appendLog({ ts, msg, level }) {
  const body = document.getElementById("log-body");
  const line = document.createElement("div");
  line.className = "log-line " + (level || "dim");
  line.innerHTML = `<span class="ts">${ts}</span><span class="msg"></span>`;
  line.querySelector(".msg").textContent = msg;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
  while (body.children.length > 2000) body.removeChild(body.firstChild);
}

function clearLog() { document.getElementById("log-body").innerHTML = ""; }

// "추출"(openLogExportModal)이 저장 위치/파일명을 직접 지정해서 파이썬이 로컬
// 디스크에 바로 써주는 방식 — pywebview 창에는 별도 다운로드 폴더 개념이 없어서 필요.
function openLogExportModal() {
  const ts = new Date().toISOString().replace(/[:T]/g, "-").slice(0, 15);
  openModal({
    title: "작업 로그 추출",
    bodyHtml: `
      <div class="form-row"><label>${icon("folder")}저장 폴더</label>
        <div class="browse-row">
          <input class="field" id="le-dir" value="${state.config.local_output_dir || ""}">
          <button class="btn" id="le-browse">${icon("folder", "icon-sm")}찾기</button>
        </div>
      </div>
      <div class="form-row"><label>${icon("tag")}파일명</label><input class="field" id="le-name" value="qc_log_${ts}.txt"></div>
    `,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      {
        label: "추출", cls: "btn-invert", onClick: async () => {
          const dir = document.getElementById("le-dir").value.trim();
          const name = document.getElementById("le-name").value.trim();
          if (!dir || !name) { toast("폴더와 파일명을 입력하세요.", "warn"); return; }
          const sep = dir.endsWith("\\") || dir.endsWith("/") ? "" : "\\";
          const res = await api().export_log(`${dir}${sep}${name}`);
          if (res.ok) { toast(`로그 추출 완료 → ${res.path}`, "ok"); closeModal(); }
          else toast(res.error || "추출 실패", "err");
        },
      },
    ],
    onMount: (backdrop) => {
      backdrop.querySelector("#le-browse").addEventListener("click", async () => {
        const res = await api().browse_folder();
        if (res.ok) backdrop.querySelector("#le-dir").value = res.path;
      });
    },
  });
}

// ── 작업 로그 패널 세로 크기 드래그 조절 ─────────────────
function wireLogResize() {
  // 로그 전용 분리 창은 항상 창 전체를 채워야 함 — 메인 창에서 저장된 고정 높이(px)를
  // 그대로 적용하면 그 값만큼만 차지하고 나머지는 빈 배경으로 남는 버그가 있었음.
  if (isLogOnly) return;
  const panel = document.getElementById("log-panel");
  const handle = document.getElementById("log-resize-handle");
  const saved = parseInt(localStorage.getItem("logPanelHeight") || "", 10);
  if (saved) panel.style.height = saved + "px";

  let startY = 0, startH = 0;
  const onMove = (e) => {
    const dy = e.clientY - startY;
    const h = Math.min(Math.max(startH - dy, 110), window.innerHeight * 0.75);
    panel.style.height = h + "px";
  };
  const onUp = () => {
    handle.classList.remove("dragging");
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    localStorage.setItem("logPanelHeight", parseInt(panel.style.height, 10));
  };
  handle.addEventListener("mousedown", (e) => {
    startY = e.clientY;
    startH = panel.getBoundingClientRect().height;
    handle.classList.add("dragging");
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    e.preventDefault();
  });
}

// ── 작업 로그 탭을 MobaXterm 처럼 드래그로 떼어내면 별도 창으로 분리 ──
// 서버가 10대 이상으로 늘어나면 하단 로그 패널이 테이블 표시 영역을 갉아먹는 문제를
// 피하려고, 로그를 완전히 별도 pywebview 창으로 분리해서 테이블에 전체 높이를 돌려준다.
const DETACH_THRESHOLD = 40;

function wireLogDetach() {
  const title = document.querySelector(".log-header .title");
  let startX = 0, startY = 0, dragging = false, detached = false;

  const onMove = (e) => {
    if (detached) return;
    const dist = Math.hypot(e.clientX - startX, e.clientY - startY);
    if (dist > DETACH_THRESHOLD) {
      detached = true;
      detachLogPanel();
      onUp();
    }
  };
  const onUp = () => {
    dragging = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };
  title.addEventListener("mousedown", (e) => {
    dragging = true;
    detached = false;
    startX = e.clientX;
    startY = e.clientY;
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// 원본은 백엔드(pywebview)에 새 네이티브 창을 띄워달라고 요청했다(open_log_window RPC) —
// 이 서버는 브라우저 컨텍스트라 그 RPC는 항상 실패만 반환한다(server/qc/backend.py 참고).
// 브라우저에서 "새 창 하나 더 띄우기"는 서버를 거칠 필요 없이 window.open()으로 그냥
// 되는 일이라, 이 함수는 순수 클라이언트 사이드로 재작성했다 — ?logonly=1 페이지가
// html.log-only 스타일(css/qc/web/style.css)로 로그만 꽉 채워서 보여준다.
function detachLogPanel() {
  const url = `${location.pathname}?logonly=1`;
  const win = window.open(url, "qcLogWindow", "width=560,height=760,menubar=no,toolbar=no,location=no,status=no");
  if (win) {
    hideLogPanel();
    win.focus();
  } else {
    toast("팝업이 차단됐습니다 — 브라우저 주소창의 팝업 차단 아이콘에서 허용해 주세요.", "err");
  }
}

function hideLogPanel() {
  document.getElementById("log-panel").style.display = "none";
}

function showLogPanel() {
  document.getElementById("log-panel").style.display = "";
}

// ════════════════════════════════════════════════════════════════
// 토스트
// ════════════════════════════════════════════════════════════════
function toast(msg, type = "info") {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  stack.appendChild(el);
  setTimeout(() => {
    el.classList.add("hide");
    setTimeout(() => el.remove(), 200);
  }, 3400);
}

// ════════════════════════════════════════════════════════════════
// 테이블 렌더링
// ════════════════════════════════════════════════════════════════
const CAPTURE_KIND_LABELS = {
  current: "현재화면", devmgmt: "장치관리자", about: "시스템정보", diskmgmt: "디스크관리",
  mypc: "내PC", activation: "인증정보",
};
const CAPTURE_KINDS = Object.keys(CAPTURE_KIND_LABELS);
// 완료 배지(예: "5/5")는 정기점검 5종만 센다 — 현재화면은 그때그때 바로 보는 용도라
// "전체 캡처"에도 포함 안 되고(server_app.py 의 CAPTURE_ALL_ORDER 참고) 완료 여부와 무관하다.
const CAPTURE_QC_KINDS = CAPTURE_KINDS.filter((k) => k !== "current");

const PILL_MAP = {
  boot: { A: ["A", "boot-a"], B: ["B", "boot-b"], UNKNOWN: ["?", "warn"] },
  vol: { OK: ["✓ 정상", "ok"], WARN: ["주의", "warn"], FAIL: ["실패", "fail"], PENDING: ["진행중", "pending"] },
  act: { LICENSED: ["인증됨", "ok"], UNLICENSED: ["미인증", "fail"], UNKNOWN: ["확인필요", "warn"], PENDING: ["진행중", "pending"] },
  qc: { RUNNING: ["실행중", "pending"], DONE: ["완료", "ok"], FAIL: ["실패", "fail"] },
  dev: { OK: ["정상", "ok"], WARN: ["이상감지", "warn"], FAIL: ["실패", "fail"], PENDING: ["조회중", "pending"] },
};

function pillHtml(kind, value) {
  if (!value) return `<span class="pill"><span class="dot"></span>–</span>`;
  const entry = (PILL_MAP[kind] || {})[value];
  if (!entry) return `<span class="pill"><span class="dot"></span>${value}</span>`;
  const [label, cls] = entry;
  // ok/fail now show only the Health-style icon badge, no text label — same
  // as the main dashboard's Health column (icon alone, nothing next to it).
  const text = cls === "ok" || cls === "fail" ? "" : label;
  return `<span class="pill ${cls}"><span class="dot"></span>${text}</span>`;
}

function dotHtml(value) {
  if (value === "OK") return `<span class="dot-ind ok"><span class="dot"></span></span>`;
  if (value === "FAIL") return `<span class="dot-ind fail"><span class="dot"></span></span>`;
  return `<span class="dot-ind"><span class="dot"></span>–</span>`;
}

function powerHtml(value) {
  return value === true
    ? `<span class="power-ind on">${icon("power", "icon-sm")}</span>`
    : `<span class="power-ind off">${icon("power", "icon-sm")}</span>`;
}

function checkSvg() {
  return icon("check", "icon-sm");
}

// 업체 프로필이 표에 추가로 요구하는 컬럼(state.tableColumns, applyProfile() 참고)의 <td>를
// NIC 다음/인증 앞자리에 끼워 넣는다. 지금은 boot/vol 뿐이라 하드코딩이지만, 항목이 늘어나면
// table_column_registry.py 쪽에 렌더 방식까지 등록하는 식으로 일반화하면 된다.
function extraColumnCellsHtml(st) {
  return state.tableColumns.map((col) => {
    if (col.id === "boot") return `<td class="cell-boot">${pillHtml("boot", st.boot)}</td>`;
    if (col.id === "vol") return `<td class="cell-vol">${pillHtml("vol", st.vol)}</td>`;
    return "";
  }).join("");
}

// ── 상태 셀 커스텀 툴팁 (네이티브 title 대신 다크테마 팝오버 — 구조화된 여러 줄 내용 지원) ──
let statusTooltipEl = null;

function tipHtml(title, lines) {
  const body = (lines || []).filter(Boolean).map((l) => `<div class="tip-line">${l}</div>`).join("");
  return `<div class="tip-title">${title}</div>${body}`;
}

function showStatusTooltip(target, html) {
  hideStatusTooltip();
  if (!html) return;
  statusTooltipEl = document.createElement("div");
  statusTooltipEl.className = "status-tooltip";
  statusTooltipEl.innerHTML = html;
  document.body.appendChild(statusTooltipEl);
  const r = target.getBoundingClientRect();
  const tw = statusTooltipEl.offsetWidth;
  const th = statusTooltipEl.offsetHeight;
  let left = Math.max(8, Math.min(r.left + r.width / 2 - tw / 2, window.innerWidth - tw - 8));
  let top = r.bottom + 8;
  if (top + th > window.innerHeight - 8) top = r.top - th - 8;
  statusTooltipEl.style.left = left + "px";
  statusTooltipEl.style.top = top + "px";
  requestAnimationFrame(() => statusTooltipEl && statusTooltipEl.classList.add("show"));
}

function hideStatusTooltip() {
  if (statusTooltipEl) { statusTooltipEl.remove(); statusTooltipEl = null; }
}

function wireTip(el, fn) {
  if (!el) return;
  el.addEventListener("mouseenter", () => showStatusTooltip(el, fn()));
  el.addEventListener("mouseleave", hideStatusTooltip);
}

// ── 액션 메뉴 (클릭하면 뜨는 작은 팝오버 — 전원 아이콘/캡처 버튼에서 사용) ──
let actionMenuEl = null;

function showActionMenu(target, items) {
  hideActionMenu();
  actionMenuEl = document.createElement("div");
  actionMenuEl.className = "action-menu";
  actionMenuEl.innerHTML = items.map((it, i) => it.sep
    ? `<div class="action-menu-sep"></div>`
    : `<button class="action-menu-item ${it.danger ? "danger" : ""}" data-i="${i}">${icon(it.icon, "icon icon-sm")}<span>${it.label}</span></button>`
  ).join("");
  document.body.appendChild(actionMenuEl);
  const r = target.getBoundingClientRect();
  const w = actionMenuEl.offsetWidth, h = actionMenuEl.offsetHeight;
  let left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
  let top = r.bottom + 6;
  if (top + h > window.innerHeight - 8) top = r.top - h - 6;
  actionMenuEl.style.left = left + "px";
  actionMenuEl.style.top = top + "px";
  actionMenuEl.querySelectorAll(".action-menu-item").forEach((btn) => {
    const it = items[Number(btn.dataset.i)];
    btn.addEventListener("click", (e) => { e.stopPropagation(); hideActionMenu(); it.onClick(); });
  });
  requestAnimationFrame(() => actionMenuEl && actionMenuEl.classList.add("show"));
  setTimeout(() => document.addEventListener("mousedown", actionMenuOutsideClick), 0);
}

function hideActionMenu() {
  if (actionMenuEl) { actionMenuEl.remove(); actionMenuEl = null; }
  document.removeEventListener("mousedown", actionMenuOutsideClick);
}

function actionMenuOutsideClick(e) {
  if (actionMenuEl && !actionMenuEl.contains(e.target)) hideActionMenu();
}

function pingTip(st) {
  if (st.ping == null) return tipHtml("Ping", ["아직 확인 안 함 — '연결확인' 실행 필요"]);
  return st.ping === "OK"
    ? tipHtml("Ping 성공", ["ICMP 응답 정상"])
    : tipHtml("Ping 실패", ["ICMP 응답 없음 — 방화벽에서 막혀 있을 수 있음"]);
}

function winrmTip(st) {
  if (st.winrm == null) return tipHtml("WinRM", ["아직 확인 안 함 — '연결확인' 실행 필요"]);
  return st.winrm === "OK"
    ? tipHtml("WinRM 연결 성공", ["원격 관리(5985 포트) 정상 응답"])
    : tipHtml("WinRM 연결 실패", ["5985 포트 응답 없음 — 서비스/방화벽 확인 필요"]);
}

function powerTip(st) {
  return st.power_on === true
    ? tipHtml("전원 ON", ["WinRM 응답 확인됨(연결확인 또는 재부팅 후 자동로그인까지 확인됨)"])
    : tipHtml("전원 OFF / 미확인", ["아직 연결확인을 안 했거나, WinRM 응답이 없거나, 재부팅 후 아직 확인 안 됨"]);
}

// 기린 프로필에서만 표에 추가되는 컬럼(부팅/볼륨) — WinRM_Dashboard 원본 그대로.
function bootTip(st) {
  if (!st.boot) return tipHtml("부팅 디스크", ["아직 확인 안 함 — '부팅디스크' 실행 필요"]);
  if (st.boot === "A") return tipHtml("A 디스크로 부팅", ["바탕화면에서 폴더 '1' 확인됨"]);
  if (st.boot === "B") return tipHtml("B 디스크로 부팅", ["바탕화면에서 폴더 '2' 확인됨"]);
  return tipHtml("부팅 디스크 판단 불가", ["바탕화면에 폴더 '1', '2' 가 모두 없어서 A/B 여부를 알 수 없음"]);
}

function volTip(st) {
  if (!st.vol) return tipHtml("볼륨", ["아직 확인 안 함 — '볼륨확인' 실행 필요"]);
  if (st.vol === "PENDING") return tipHtml("볼륨 확인 중…", []);
  if (st.vol === "FAIL") return tipHtml("볼륨 조회 실패", ["원격 통신 오류 — 다시 시도 필요"]);
  if (st.vol === "OK") return tipHtml("C, D, E, F 볼륨 모두 존재", []);
  return tipHtml("일부 볼륨 누락", [escapeHtml(st.vol_msg || "")]);
}

function actTip(st) {
  if (!st.act) return tipHtml("정품 인증", ["아직 확인 안 함 — '인증확인' 실행 필요"]);
  if (st.act === "PENDING") return tipHtml("정품 인증 진행 중…", []);
  if (st.act === "LICENSED") return tipHtml("정품 인증 완료", []);
  if (st.act === "UNLICENSED") return tipHtml("정품 인증 안 됨", ["'정품인증' 버튼으로 키 입력 필요"]);
  return tipHtml("인증 상태 확인 필요", []);
}

function qcTip(st) {
  if (!st.qc) return tipHtml("QC 스크립트", ["아직 실행 안 함"]);
  if (st.qc === "RUNNING") return tipHtml("QC 실행 중…", ["완료까지 최대 6분 소요"]);
  if (st.qc === "DONE") return tipHtml("QC 완료", ["결과가 로컬 결과 폴더에 저장됨"]);
  return tipHtml("QC 실패", ["작업 로그에서 실패 원인 확인 필요"]);
}

function devTip(st) {
  if (!st.dev) return tipHtml("장치 조회", ["아직 확인 안 함 — '장치조회' 실행 필요"]);
  if (st.dev === "PENDING") return tipHtml("장치 조회 중…", []);
  if (st.dev === "FAIL") return tipHtml("장치 조회 실패", []);
  const all = st.dev_all || [];
  if (!all.length) {
    // 구버전 캐시(재시작 전 캡처된 dev_issues만 있는 상태) 폴백 — 조회를 다시 하면 채워짐
    return st.dev === "OK"
      ? tipHtml(`장치 ${st.dev_count ?? "?"}개 모두 정상`, ["'장치조회'를 다시 실행하면 개별 목록이 보입니다"])
      : tipHtml(`이상 장치 ${st.dev_issue_count ?? "?"}개`, ["'장치조회'를 다시 실행하면 개별 목록이 보입니다"]);
  }
  const isBad = (d) => d.status && d.status.toUpperCase() !== "OK";
  const byCat = {};
  for (const d of all) (byCat[d.cat] = byCat[d.cat] || []).push(d);
  const lines = [];
  let shown = 0;
  for (const cat of Object.keys(byCat)) {
    lines.push(`<span class="tip-group">${escapeHtml(DEVICE_CAT_LABELS[cat] || cat)}</span>`);
    for (const d of byCat[cat]) {
      if (shown >= 20) continue;
      shown++;
      const bad = isBad(d);
      lines.push(`${escapeHtml(d.name)} <span class="${bad ? "tip-badge" : "tip-ok"}">${escapeHtml(d.status)}</span>`);
    }
  }
  if (all.length > shown) lines.push(`… 외 ${all.length - shown}개`);
  const badCount = all.filter(isBad).length;
  const title = badCount ? `이상 장치 ${badCount}개 / 전체 ${all.length}개` : `장치 ${all.length}개 모두 정상`;
  return tipHtml(title, lines);
}

function captureTip(st) {
  const caps = st.captures || {};
  const lines = CAPTURE_QC_KINDS.map((k) => `${caps[k] ? "✓" : "✗"} ${CAPTURE_KIND_LABELS[k]}`);
  const done = CAPTURE_QC_KINDS.filter((k) => caps[k]).length;
  return tipHtml(`캡처 ${done}/${CAPTURE_QC_KINDS.length}`, lines);
}

function captureCellHtml(captures) {
  const done = CAPTURE_QC_KINDS.filter((k) => captures && captures[k]).length;
  if (!done) return `<span class="pill"><span class="dot"></span>${done}/${CAPTURE_QC_KINDS.length}</span>`;
  const cls = done === CAPTURE_QC_KINDS.length ? "ok" : "warn";
  return `<span class="pill ${cls}"><span class="dot"></span>${done}/${CAPTURE_QC_KINDS.length}</span>`;
}

function matchesSearch(srv) {
  const q = state.searchQuery.trim().toLowerCase();
  if (!q) return true;
  const st = state.status[srv.ip] || {};
  return [srv.ip, srv.serial, st.cur_name].some((v) => (v || "").toLowerCase().includes(q));
}

// 시리얼 안의 숫자를 문자열이 아니라 값으로 비교("58676-6" < "58676-10")해서 자릿수 padding과
// 무관하게 항상 번호 순으로 뜨게 한다 — 추가한 순서(일괄추가 시작번호 등)와 무관하게 보여줌.
function compareSerial(a, b) {
  return (a.serial || "").localeCompare(b.serial || "", undefined, { numeric: true, sensitivity: "base" });
}

function renderTable() {
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  document.getElementById("empty-state").style.display = state.servers.length ? "none" : "flex";
  const visible = state.servers.filter(matchesSearch).sort(compareSerial);

  const totalPages = Math.max(1, Math.ceil(visible.length / state.pageSize));
  if (state.currentPage > totalPages) state.currentPage = totalPages;
  if (state.currentPage < 1) state.currentPage = 1;
  const start = (state.currentPage - 1) * state.pageSize;
  const pageItems = visible.slice(start, start + state.pageSize);

  for (const srv of pageItems) tbody.appendChild(buildRow(srv));
  updateStatChip();
  updateSelectAllCheckbox();
  renderPager(visible.length, start, pageItems.length, totalPages);
}

function renderPager(totalVisible, start, shownCount, totalPages) {
  const pager = document.getElementById("table-pager");
  if (totalPages <= 1) { pager.style.display = "none"; pager.innerHTML = ""; return; }
  pager.style.display = "flex";

  const cur = state.currentPage;
  const rangeText = shownCount
    ? `${start + 1}~${start + shownCount} / 총 ${totalVisible}대`
    : `총 ${totalVisible}대`;

  // 현재 페이지 주변만 숫자로 보여주고 나머지는 "…" 로 생략
  const pages = [];
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || Math.abs(p - cur) <= 1) pages.push(p);
    else if (pages[pages.length - 1] !== "…") pages.push("…");
  }

  const pageBtns = pages.map((p) =>
    p === "…"
      ? `<span class="pager-ellipsis">…</span>`
      : `<button class="pager-btn ${p === cur ? "active" : ""}" data-page="${p}">${p}</button>`
  ).join("");

  pager.innerHTML = `
    <span>${rangeText}</span>
    <div class="pager-pages">
      <button class="pager-btn" id="pager-prev" ${cur <= 1 ? "disabled" : ""}>${icon("chevronDown", "icon icon-xs")}</button>
      ${pageBtns}
      <button class="pager-btn" id="pager-next" ${cur >= totalPages ? "disabled" : ""}>${icon("chevronDown", "icon icon-xs")}</button>
    </div>`;
  pager.querySelector("#pager-prev").classList.add("pager-prev");
  pager.querySelector("#pager-next").classList.add("pager-next");

  pager.querySelectorAll(".pager-btn[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => { state.currentPage = Number(btn.dataset.page); renderTable(); });
  });
  pager.querySelector("#pager-prev").addEventListener("click", () => { state.currentPage--; renderTable(); });
  pager.querySelector("#pager-next").addEventListener("click", () => { state.currentPage++; renderTable(); });
}

function updateSelectAllCheckbox() {
  const allSelected = state.servers.length > 0 && state.servers.every((s) => state.selected.has(s.ip));
  document.getElementById("chk-select-all").classList.toggle("checked", allSelected);
}

function buildRow(srv) {
  const frag = document.createDocumentFragment();

  const tr = document.createElement("tr");
  tr.className = "srv-row";
  tr.id = ipRowId(srv.ip);
  tr.dataset.ip = srv.ip;
  // Selection is the checkbox's job alone now (its own listener is attached
  // in fillRow) — clicking elsewhere in the row used to also toggle
  // selection, which made every click in the row feel like it "randomly"
  // selected the server.
  tr.addEventListener("dblclick", () => openDetailModal(srv.ip));
  fillRow(tr, srv);
  frag.appendChild(tr);

  const progTr = document.createElement("tr");
  progTr.className = "srv-row-progress";
  progTr.id = ipRowId(srv.ip) + "-prog";
  // 컬럼 수는 업체 프로필(state.tableColumns)에 따라 달라지므로, 실제 헤더 칸 수를 그대로 센다.
  const colCount = document.querySelectorAll(".srv-table thead th").length;
  progTr.innerHTML = `<td colspan="${colCount}"><div class="row-progress"><div class="bar"></div></div></td>`;
  frag.appendChild(progTr);

  return frag;
}

function fillRow(tr, srv) {
  const st = state.status[srv.ip] || {};
  const checked = state.selected.has(srv.ip);
  tr.classList.toggle("selected", checked);
  tr.innerHTML = `
    <td><span class="chk-box ${checked ? "checked" : ""}">${checkSvg()}</span></td>
    <td class="cell-power">${powerHtml(st.power_on)}</td>
    <td class="col-host">
      <div class="host-row">
        <span class="host-name">${st.cur_name || "–"}</span>
        <button class="host-edit-btn" data-ip="${srv.ip}" title="시리얼번호 변경 (현재: ${srv.serial || "–"})">${icon("edit", "icon-xs")}</button>
      </div>
    </td>
    <td class="col-ip">${srv.ip}</td>
    <td class="cell-ping">${dotHtml(st.ping)}</td>
    <td class="cell-winrm">${dotHtml(st.winrm)}</td>
    <td class="spec-cell" title="${st.cpu || ""}">${st.cpu || "–"}</td>
    <td class="spec-cell">${st.ram || "–"}</td>
    <td class="spec-cell" title="${st.gpu || ""}">${st.gpu || "–"}</td>
    <td class="spec-cell" title="${st.nic || ""}">${st.nic || "–"}</td>
    ${extraColumnCellsHtml(st)}
    <td class="cell-act">${pillHtml("act", st.act)}</td>
    <td class="cell-qc">${pillHtml("qc", st.qc)}</td>
    <td class="cell-dev">${pillHtml("dev", st.dev)}</td>
    <td class="cell-cap">${captureCellHtml(st.captures)}</td>
  `;
  tr.querySelector(".chk-box").addEventListener("click", () => toggleSelect(srv.ip));
  tr.querySelector(".host-edit-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    openEditSerialModal(srv.ip);
  });
  wireTip(tr.querySelector(".cell-ping"), () => pingTip(st));
  wireTip(tr.querySelector(".cell-winrm"), () => winrmTip(st));
  wireTip(tr.querySelector(".cell-power"), () => powerTip(st));
  for (const col of state.tableColumns) {
    if (col.id === "boot") wireTip(tr.querySelector(".cell-boot"), () => bootTip(st));
    if (col.id === "vol") wireTip(tr.querySelector(".cell-vol"), () => volTip(st));
  }
  wireTip(tr.querySelector(".cell-act"), () => actTip(st));
  wireTip(tr.querySelector(".cell-qc"), () => qcTip(st));
  wireTip(tr.querySelector(".cell-dev"), () => devTip(st));
  wireTip(tr.querySelector(".cell-cap"), () => captureTip(st));
  renderRowProgress(srv.ip);
}

function renderRow(ip) {
  const tr = document.getElementById(ipRowId(ip));
  const srv = state.servers.find((s) => s.ip === ip);
  if (tr && srv) fillRow(tr, srv);
}

function renderRowProgress(ip) {
  const tr = document.getElementById(ipRowId(ip));
  const progTr = document.getElementById(ipRowId(ip) + "-prog");
  if (!tr || !progTr) return;
  const busyMap = state.busy[ip] || {};
  const actions = Object.values(busyMap);
  const bar = progTr.querySelector(".row-progress");
  if (!actions.length) {
    tr.classList.remove("busy");
    progTr.classList.remove("busy");
    bar.classList.remove("indeterminate");
    return;
  }
  tr.classList.add("busy");
  progTr.classList.add("busy");
  const withProgress = actions.find((a) => a.progress != null);
  const barInner = bar.querySelector(".bar");
  if (withProgress) {
    bar.classList.remove("indeterminate");
    barInner.classList.add("determinate");
    barInner.style.width = withProgress.progress + "%";
  } else {
    bar.classList.add("indeterminate");
    barInner.classList.remove("determinate");
  }
}

function toggleSelect(ip) {
  if (state.selected.has(ip)) state.selected.delete(ip);
  else state.selected.add(ip);
  renderRow(ip);
  updateStatChip();
  updateSelectAllCheckbox();
}

function updateStatChip() {
  const total = state.servers.length;
  const sel = state.selected.size;
  const online = state.servers.filter((s) => (state.status[s.ip] || {}).winrm === "OK").length;
  document.getElementById("stat-chip").innerHTML =
    `서버 <b>${total}</b>대 &nbsp;·&nbsp; 선택 <b>${sel}</b>대 &nbsp;·&nbsp; 온라인 <span class="stat-online">${online}</span>대`;
}

// ════════════════════════════════════════════════════════════════
// 배치 액션 실행
// ════════════════════════════════════════════════════════════════
function selectedIps() { return [...state.selected]; }

async function runBatch(actionName, extraArgs = []) {
  const ips = selectedIps();
  if (!ips.length) { toast("서버를 선택하세요.", "warn"); return null; }
  const res = await api()[actionName](ips, ...extraArgs);
  if (res && res.ok === false) toast(res.error || "실행 실패", "err");
  return res;
}

// 사이드바 항목 중 "batch"가 아니라 서버별 입력 폼/그리드 모달을 직접 띄워야 하는 소수만
// 여기 등록한다 — action_registry.py 의 kind="custom" / handler 이름과 매칭된다.
const SPECIAL_HANDLERS = {
  rename: confirmRename,
  activate: openActivationModal,
  all_devices: openMultiDeviceModal,
};

// 대시보드 상단의 "업체" 드롭다운에서 고르는 즉시(별도 저장/적용 버튼 없이) 반영한다 —
// 사이드바 항목과 표의 추가 컬럼(기린의 부팅/볼륨 등)을 전부 다시 그린다.
async function applyProfile(newProfileId) {
  if (newProfileId) {
    const res = await api().save_config({ client_profile: newProfileId });
    state.config = res.config;
  }
  const [sidebarRes, profilesRes] = await Promise.all([
    api().get_sidebar_config(),
    api().list_client_profiles(),
  ]);
  if (sidebarRes && sidebarRes.ok) {
    renderSidebarSections(sidebarRes.sections);
    applyProfileTableColumns(sidebarRes.table_columns || []);
  }
  if (profilesRes && profilesRes.ok) populateProfileSelect(profilesRes.profiles, profilesRes.current);
  renderTable();
}

// showActionMenu 팝오버에 넘길 목록 — 버튼 클릭 시점에 참조하므로 fetch 때마다 갱신해둔다.
let profileMenuOptions = [];

function populateProfileSelect(profiles, current) {
  profileMenuOptions = profiles;
  const found = profiles.find((p) => p.id === current);
  document.getElementById("profile-select-label").textContent = found ? found.display_name : (current || "–");
}

// 업체 프로필이 표에 추가로 요구하는 컬럼(예: 기린의 부팅/볼륨)의 <th>를 NIC 다음에 끼워
// 넣는다 — 매번 기존 걸 지우고 다시 그려서, 프로필을 여러 번 바꿔도 중복되지 않는다.
function applyProfileTableColumns(columns) {
  state.tableColumns = columns;
  document.querySelectorAll("th.col-extra").forEach((el) => el.remove());
  let insertAfter = document.getElementById("th-nic");
  for (const col of columns) {
    const th = document.createElement("th");
    th.className = "col-extra";
    th.dataset.label = col.label;
    th.innerHTML = `<span class="th-label">${icon(col.icon)}</span>`;
    wireTip(th.querySelector(".th-label"), () => tipHtml(col.label, []));
    insertAfter.insertAdjacentElement("afterend", th);
    insertAfter = th;
  }
}

// 사이드바는 서버의 get_sidebar_config()(레지스트리+업체 프로필을 합친 결과)로 그린다 —
// 업체마다 어떤 항목을 보여줄지가 client_profiles.py 목록 하나로 결정되고, 화면 쪽은
// 그 결과를 그대로 렌더링하기만 하면 된다.
function renderSidebarSections(sections) {
  const nav = document.querySelector(".sidebar-nav");
  nav.innerHTML = "";
  for (const section of sections) {
    const secEl = document.createElement("div");
    secEl.className = "nav-section";
    const labelBtn = document.createElement("button");
    labelBtn.className = "nav-section-label";
    labelBtn.innerHTML = `${icon("chevronDown")}<span>${escapeHtml(section.label)}</span>`;
    labelBtn.addEventListener("click", () => secEl.classList.toggle("collapsed"));
    const itemsEl = document.createElement("div");
    itemsEl.className = "nav-section-items";
    for (const item of section.items) {
      const btn = document.createElement("button");
      btn.className = "nav-item";
      btn.innerHTML = `${icon(item.icon)}<span>${escapeHtml(item.label)}</span>`;
      btn.addEventListener("click", () => runSidebarItem(item));
      itemsEl.appendChild(btn);
    }
    secEl.appendChild(labelBtn);
    secEl.appendChild(itemsEl);
    nav.appendChild(secEl);
  }
}

function runSidebarItem(item) {
  if (item.kind === "custom") {
    const fn = SPECIAL_HANDLERS[item.handler];
    if (fn) fn();
    else toast(`알 수 없는 항목: ${item.label}`, "err");
    return;
  }
  if (item.confirm) {
    confirmDanger(item.confirm.title, item.confirm.message, () => runBatch(item.action));
  } else {
    runBatch(item.action);
  }
}

function wireStaticEvents() {
  document.getElementById("srv-search").addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    state.currentPage = 1;
    renderTable();
  });

  document.getElementById("page-size-select").addEventListener("change", (e) => {
    state.pageSize = Number(e.target.value);
    state.currentPage = 1;
    renderTable();
  });

  document.querySelectorAll("th[data-label] .th-label").forEach((el) => {
    const label = el.closest("th").dataset.label;
    wireTip(el, () => tipHtml(label, []));
  });

  document.getElementById("btn-apply-cred").addEventListener("click", async () => {
    const cfg = {
      sales_number: document.getElementById("cred-sales").value.trim(),
      username: document.getElementById("cred-user").value.trim(),
      password: document.getElementById("cred-pass").value,
    };
    const res = await api().save_config(cfg);
    state.config = res.config;
    toast("설정 적용 완료", "ok");
  });

  // 업체 선택 — 전원 아이콘의 재부팅/종료 메뉴와 같은 팝오버로 띄운다. 골라도 즉시 반영되고
  // 별도 저장/적용 버튼은 없다(applyProfile 내부에서 save_config까지 처리).
  document.getElementById("profile-select-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    showActionMenu(e.currentTarget, profileMenuOptions.map((p) => ({
      label: p.display_name, icon: "boxes", onClick: () => applyProfile(p.id),
    })));
  });

  document.getElementById("btn-open-log").addEventListener("click", detachLogPanel);
  document.getElementById("btn-settings").addEventListener("click", openSettingsModal);
  document.getElementById("btn-del-server").addEventListener("click", deleteSelected);

  // 전원 헤더 아이콘 — 예전 사이드바의 재부팅/종료 버튼을 여기로 옮겼다(선택된 서버 대상은 동일).
  document.getElementById("th-power").addEventListener("click", (e) => {
    e.stopPropagation();
    showActionMenu(e.currentTarget, [
      { label: "재부팅", icon: "refreshCw", onClick: () =>
        confirmDanger("재부팅", "선택한 서버를 재부팅하시겠습니까?", () => runBatch("batch_restart")) },
      { label: "종료", icon: "power", danger: true, onClick: () =>
        confirmDanger("종료", "선택한 서버를 종료하시겠습니까?", () => runBatch("batch_shutdown")) },
    ]);
  });

  // 캡처 버튼 — 예전 사이드바의 캡처 종류별 버튼 8개를 메뉴 하나로 통합.
  document.getElementById("btn-capture").addEventListener("click", (e) => {
    e.stopPropagation();
    const items = CAPTURE_KINDS.map((k) => ({
      label: CAPTURE_KIND_LABELS[k], icon: "camera", onClick: () => runBatch(`batch_capture_${k}`),
    }));
    items.push({ label: "전체", icon: "layers", onClick: () => runBatch("batch_capture_all") });
    items.push({ label: "캡처 보기", icon: "eye", onClick: () => openCaptureViewer(pickCaptureKindWithData(), null) });
    showActionMenu(e.currentTarget, items);
  });

  // 테이블 헤더 전체선택 체크박스 — 예전 "전체선택"/"선택해제" 버튼 두 개를 체크박스 하나로 통합.
  document.getElementById("chk-select-all").addEventListener("click", () => {
    const allSelected = state.servers.length > 0 && state.servers.every((s) => state.selected.has(s.ip));
    state.selected = allSelected ? new Set() : new Set(state.servers.map((s) => s.ip));
    renderTable();
  });

  document.getElementById("btn-log-export").addEventListener("click", openLogExportModal);
  document.getElementById("btn-log-clear").addEventListener("click", clearLog);
}

async function deleteSelected() {
  const ips = selectedIps();
  if (!ips.length) { toast("삭제할 서버를 선택하세요.", "warn"); return; }
  confirmDanger("서버 삭제", `${ips.length}개 서버를 삭제하시겠습니까?`, async () => {
    const res = await api().delete_servers(ips);
    state.servers = res.servers;
    for (const ip of ips) { state.selected.delete(ip); delete state.status[ip]; }
    renderTable();
  });
}

// 이름변경 버튼을 누르는 "그 순간"의 매출번호로 실제 이름이 바뀐다 — 시리얼이 "...-숫자"
// 패턴이면 매출번호 부분만 지금 설정된 값으로 갈아끼우고, 패턴이 아니면(개별 등록) 그대로.
// 백엔드 _do_rename()의 계산과 반드시 동일한 로직이어야 확인창에 보여주는 미리보기가 맞다.
function computeRenameTarget(serial) {
  const sales = (state.config.sales_number || "").trim();
  const m = /^(.+)-(\d+)$/.exec(serial || "");
  return (sales && m) ? `${sales}-${m[2]}` : serial;
}

function confirmRename() {
  const srvs = state.servers.filter((s) => state.selected.has(s.ip));
  if (!srvs.length) { toast("서버를 선택하세요.", "warn"); return; }
  const list = srvs.map((s) => `<div>${s.ip}  →  ${computeRenameTarget(s.serial)}</div>`).join("");
  openModal({
    title: "이름 변경 확인",
    bodyHtml: `<p>다음 서버 이름을 아래로 변경합니다:</p><div class="confirm-list">${list}</div>
               <p class="form-hint">재부팅 후 반영됩니다.</p>`,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      { label: "변경", cls: "btn-invert", onClick: () => { closeModal(); runBatch("batch_rename"); } },
    ],
  });
}

// ── 서버 개별 시리얼번호 변경 ──────────────────────────
// 매출번호와 무관하게 등록된 서버(혹은 특수 케이스)는 이걸로 직접 하나씩 고친다.
function openEditSerialModal(ip) {
  const srv = state.servers.find((s) => s.ip === ip);
  if (!srv) return;
  openModal({
    title: "시리얼번호 변경",
    bodyHtml: `
      <div class="form-row"><label>${icon("tag")}시리얼번호</label><input class="field" id="es-serial" value="${srv.serial || ""}"></div>
      <div class="form-hint">IP: ${ip}</div>
    `,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      {
        label: "저장", cls: "btn-invert", onClick: async () => {
          const val = document.getElementById("es-serial").value.trim();
          if (!val) { toast("시리얼번호를 입력하세요.", "warn"); return; }
          const res = await api().update_server_serial(ip, val);
          if (!res.ok) { toast(res.error || "변경 실패", "err"); return; }
          state.servers = res.servers;
          renderTable();
          toast("시리얼번호 변경 완료", "ok");
          closeModal();
        },
      },
    ],
  });
}

function confirmDanger(title, message, onConfirm) {
  openModal({
    title,
    bodyHtml: `<p>${message}</p><p class="confirm-danger">${icon("zap", "icon-sm")}이 작업은 선택된 서버 전체에 즉시 적용됩니다.</p>`,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      { label: "확인", cls: "btn-danger-solid", onClick: () => { closeModal(); onConfirm(); } },
    ],
  });
}

// ════════════════════════════════════════════════════════════════
// 모달 시스템
// ════════════════════════════════════════════════════════════════
function openModal({ title, bodyHtml, bodyEl, footButtons = [], wide = false, xwide = false, onMount }) {
  closeModal();
  const root = document.getElementById("modal-root");
  root.style.pointerEvents = "auto";
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal-card ${wide ? "wide" : ""} ${xwide ? "xwide" : ""}">
      <div class="modal-head">
        <h3>${title}</h3>
        <button class="close-x" id="modal-close">${icon("x", "icon-sm")}</button>
      </div>
      <div class="modal-body" id="modal-body"></div>
      <div class="modal-foot" id="modal-foot"></div>
    </div>`;
  root.appendChild(backdrop);

  const body = backdrop.querySelector("#modal-body");
  if (bodyEl) body.appendChild(bodyEl);
  else body.innerHTML = bodyHtml || "";

  const foot = backdrop.querySelector("#modal-foot");
  if (!footButtons.length) foot.style.display = "none";
  for (const b of footButtons) {
    const btn = document.createElement("button");
    btn.className = "btn " + (b.cls || "");
    btn.textContent = b.label;
    btn.addEventListener("click", b.onClick);
    foot.appendChild(btn);
  }

  backdrop.querySelector("#modal-close").addEventListener("click", closeModal);
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) closeModal(); });
  document.addEventListener("keydown", escCloseHandler);

  requestAnimationFrame(() => backdrop.classList.add("show"));
  if (onMount) onMount(backdrop);
}

function escCloseHandler(e) { if (e.key === "Escape") closeModal(); }

function closeModal() {
  const root = document.getElementById("modal-root");
  root.innerHTML = "";
  root.style.pointerEvents = "none";
  document.removeEventListener("keydown", escCloseHandler);
}

// ── 서버 추가 ──────────────────────────────────────────
// ── 정품 인증 ──────────────────────────────────────────
function openActivationModal() {
  const srvs = state.servers.filter((s) => state.selected.has(s.ip));
  if (!srvs.length) { toast("서버를 선택하세요.", "warn"); return; }
  const rows = srvs.map((s) => `
    <div class="key-row">
      <span class="lbl">${s.serial} (${s.ip})</span>
      <input class="field" data-ip="${s.ip}">
    </div>`).join("");
  openModal({
    title: "Windows 정품 인증",
    wide: true,
    bodyHtml: `
      <div class="form-row">
        <label>${icon("key")}동일 키 일괄 적용</label>
        <div style="display:flex; gap:8px;">
          <input class="field" id="ak-global" placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX">
          <button class="btn btn-sm" id="ak-apply-all">${icon("copyPlus", "icon-sm")}전체 적용</button>
        </div>
      </div>
      <div style="max-height:280px; overflow-y:auto; margin-top:10px;">${rows}</div>
    `,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      {
        label: "인증 시작", cls: "btn-invert", onClick: () => {
          const keys = {};
          document.querySelectorAll("#modal-body input[data-ip]").forEach((inp) => {
            keys[inp.dataset.ip] = inp.value.trim();
          });
          closeModal();
          runBatch("batch_activate", [keys]);
        },
      },
    ],
    onMount: (backdrop) => {
      backdrop.querySelector("#ak-apply-all").addEventListener("click", () => {
        const v = backdrop.querySelector("#ak-global").value.trim();
        if (!v) return;
        backdrop.querySelectorAll("[data-ip]").forEach((inp) => (inp.value = v));
      });
    },
  });
}

// ── 설정 ───────────────────────────────────────────────
function openSettingsModal() {
  const c = state.config;
  openModal({
    title: "설정",
    wide: true,
    bodyHtml: `
      <div class="form-row"><label>${icon("folder")}QC 결과 저장 폴더</label>
        <div class="browse-row">
          <input class="field" id="st-local" value="${c.local_output_dir || ""}">
          <button class="btn" id="st-browse">${icon("folder", "icon-sm")}찾기</button>
        </div>
      </div>
      <div class="form-row"><label>${icon("folder")}로컬 QC 툴 폴더 (WindowsQC 원본)</label>
        <div class="browse-row">
          <input class="field" id="st-tooldir" value="${c.qc_tool_dir || ""}">
          <button class="btn" id="st-browse-tool">${icon("folder", "icon-sm")}찾기</button>
        </div>
      </div>
      <div class="form-row"><label>${icon("folder")}원격 QC 경로 (바탕화면)</label><input class="field" id="st-remote" value="${c.remote_qc_path || ""}"></div>
      <div class="form-grid-2">
        <div class="form-row"><label>${icon("key")}공유폴더 계정</label><input class="field" id="st-share-user" autocomplete="off" value="${c.qc_share_user || ""}"></div>
        <div class="form-row"><label>${icon("key")}공유폴더 비밀번호</label>
          <div class="browse-row">
            <input class="field" type="password" id="st-share-pass" autocomplete="new-password" value="${c.qc_share_pass || ""}">
            <button class="btn" id="st-toggle-pass" type="button">${icon("eye", "icon-sm")}</button>
          </div>
        </div>
      </div>
    `,
    footButtons: [
      { label: "취소", cls: "btn-ghost", onClick: closeModal },
      {
        label: "저장", cls: "btn-invert", onClick: async () => {
          const cfg = {
            local_output_dir: document.getElementById("st-local").value.trim(),
            qc_tool_dir: document.getElementById("st-tooldir").value.trim(),
            remote_qc_path: document.getElementById("st-remote").value.trim(),
            qc_share_user: document.getElementById("st-share-user").value.trim(),
            qc_share_pass: document.getElementById("st-share-pass").value,
          };
          const res = await api().save_config(cfg);
          state.config = res.config;
          toast("설정 저장 완료", "ok");
          closeModal();
        },
      },
    ],
    onMount: (backdrop) => {
      backdrop.querySelector("#st-browse").addEventListener("click", async () => {
        const res = await api().browse_folder("QC 결과를 저장할 폴더를 선택하세요");
        if (res.ok) backdrop.querySelector("#st-local").value = res.path;
      });
      backdrop.querySelector("#st-browse-tool").addEventListener("click", async () => {
        const res = await api().browse_folder("QC 툴(WindowsQC) 폴더가 들어있는 위치를 선택하세요");
        if (res.ok) backdrop.querySelector("#st-tooldir").value = res.path;
      });
      backdrop.querySelector("#st-toggle-pass").addEventListener("click", () => {
        const input = backdrop.querySelector("#st-share-pass");
        input.type = input.type === "password" ? "text" : "password";
      });
    },
  });
}

// ── 전체 장치 현황 ─────────────────────────────────────
// 장치조회가 원격에서 4개 분류로만 수집한다(qc_dashboard.py 의 $cats 와 동일한 영문 키) —
// 시리얼별로 한 줄, 분류별로 한 칸씩 요약(정상/이상 개수)만 보여주고, 구체적인 장치 이름은
// hover 로만 보여줘서 50대가 넘어가도 표 전체를 한눈에 훑어볼 수 있게 한다.
const DEVICE_CATS = ["Network Adapters", "Display Adapters", "Disk Drives", "Security Devices"];
const DEVICE_CAT_LABELS = {
  "Network Adapters": "네트워크", "Display Adapters": "디스플레이",
  "Disk Drives": "디스크", "Security Devices": "보안장치",
};

async function openMultiDeviceModal() {
  const rows = await api().get_devices_all();
  if (!rows.length) { toast("'장치조회' 버튼을 먼저 실행하세요.", "warn"); return; }

  const bySerial = new Map();
  for (const r of rows) {
    if (!bySerial.has(r.serial)) bySerial.set(r.serial, { serial: r.serial, ip: r.ip, cats: {} });
    const g = bySerial.get(r.serial);
    (g.cats[r.cat] = g.cats[r.cat] || []).push(r);
  }
  const servers = [...bySerial.values()].sort((a, b) =>
    (a.serial || "").localeCompare(b.serial || "", undefined, { numeric: true }));
  const isBad = (d) => d.status && d.status.toUpperCase() !== "OK";
  const serverHasIssue = (g) => DEVICE_CATS.some((c) => (g.cats[c] || []).some(isBad));

  const render = (body) => {
    const stF = body.querySelector("#md-status").value;
    const filtered = servers.filter((g) => {
      if (stF === "이상만") return serverHasIssue(g);
      if (stF === "정상만") return !serverHasIssue(g);
      return true;
    });
    const totalIssue = servers.filter(serverHasIssue).length;
    body.querySelector("#md-count").textContent =
      `표시 ${filtered.length}대 · 이상 ${totalIssue}대 / 전체 ${servers.length}대`;

    body.querySelector("#md-tbody").innerHTML = filtered.map((g, i) => {
      const cells = DEVICE_CATS.map((c, ci) => {
        const devices = g.cats[c] || [];
        const bad = devices.filter(isBad);
        if (!devices.length) return `<td class="dg-cell dg-none" id="dg-${i}-${ci}">–</td>`;
        if (!bad.length) return `<td class="dg-cell dg-ok" id="dg-${i}-${ci}">${icon("check", "icon-sm")}</td>`;
        return `<td class="dg-cell dg-bad" id="dg-${i}-${ci}">${icon("zap", "icon-sm")} ${bad.length}</td>`;
      }).join("");
      return `<tr>
        <td class="dg-serial">${g.serial}</td>
        ${cells}
        <td class="dg-overall ${serverHasIssue(g) ? "warn" : "ok"}">${serverHasIssue(g) ? "이상" : "정상"}</td>
      </tr>`;
    }).join("");

    filtered.forEach((g, i) => {
      DEVICE_CATS.forEach((c, ci) => {
        const el = body.querySelector(`#dg-${i}-${ci}`);
        const devices = g.cats[c] || [];
        wireTip(el, () => {
          if (!devices.length) return tipHtml(`${g.serial} — ${DEVICE_CAT_LABELS[c]}`, ["조회된 장치 없음"]);
          const lines = devices.map((d) =>
            `${escapeHtml(d.name)}${isBad(d) ? ` <span class="tip-badge">${escapeHtml(d.status)}</span>` : ""}`);
          return tipHtml(`${g.serial} — ${DEVICE_CAT_LABELS[c]} (${devices.length}개)`, lines);
        });
      });
    });
  };

  openModal({
    title: "전체 장치 현황",
    xwide: true,
    bodyHtml: `
      <div class="filter-row">
        ${icon("filter", "icon-sm")}
        <select class="field" id="md-status"><option>전체</option><option>이상만</option><option>정상만</option></select>
        <span class="count-badge" id="md-count"></span>
      </div>
      <div style="max-height:56vh; overflow-y:auto;">
        <table class="mini-table device-grid">
          <thead><tr>
            <th>시리얼</th>
            ${DEVICE_CATS.map((c) => `<th>${DEVICE_CAT_LABELS[c]}</th>`).join("")}
            <th>종합</th>
          </tr></thead>
          <tbody id="md-tbody"></tbody>
        </table>
      </div>
      <div class="form-hint">칸에 마우스를 올리면 장치 이름을 확인할 수 있습니다.</div>
    `,
    onMount: (backdrop) => {
      backdrop.querySelector("#md-status").addEventListener("change", () => render(backdrop));
      render(backdrop);
    },
  });
}

// ── 서버 상세 (더블클릭) ───────────────────────────────
async function openDetailModal(ip) {
  const d = await api().get_server_detail(ip);
  if (!d.ok) return;

  const devRows = (d.devices || []).slice().sort((a, b) =>
    (a.Category || "").localeCompare(b.Category || "")).map((x) => {
    const bad = x.Status && x.Status !== "OK";
    return `<tr><td>${x.Category || ""}</td><td>${x.Name || ""}</td>
      <td style="color:${bad ? "var(--red)" : "var(--green)"}">${x.Status || ""}</td></tr>`;
  }).join("") || `<tr><td colspan="3" class="muted-cell" style="text-align:center; padding:24px;">장치 정보 없음 — '장치조회'를 먼저 실행하세요</td></tr>`;

  const volRows = (d.volumes || []).slice().sort((a, b) =>
    (a.Letter || "").localeCompare(b.Letter || "")).map((v) => {
    const bad = v.Health && !["OK", "Healthy", ""].includes(v.Health);
    return `<tr><td>${v.Letter || ""}:</td><td>${v.DiskNum ?? ""}</td><td>${v.SizeGB ?? ""}</td>
      <td>${v.FreeGB ?? ""}</td><td>${v.FS || ""}</td><td>${v.Label || ""}</td>
      <td style="color:${bad ? "var(--red)" : "var(--green)"}">${v.Health || ""}</td></tr>`;
  }).join("") || `<tr><td colspan="7" class="muted-cell" style="text-align:center; padding:24px;">볼륨 정보 없음 — '볼륨확인'을 먼저 실행하세요</td></tr>`;

  const qcHtml = d.qc_text
    ? `<pre class="qc-report">${escapeHtml(d.qc_text)}</pre><div class="form-hint">${d.qc_path}</div>`
    : `<p class="muted-cell" style="text-align:center; padding:24px;">QC 리포트 없음 — QC 스크립트 실행 후 확인하세요</p>`;

  const caps = d.captures || {};
  const captureHtml = CAPTURE_KINDS.map((k) => {
    const label = CAPTURE_KIND_LABELS[k];
    const c = caps[k];
    if (!c || !c.data_url) {
      return `<div class="capture-block"><div class="capture-block-title">${label}</div>
        <p class="muted-cell" style="text-align:center; padding:16px;">캡처 없음 — '${label} 캡처'를 실행하세요</p></div>`;
    }
    return `<div class="capture-block"><div class="capture-block-title">${label}</div>
      <div class="capture-preview"><img src="${c.data_url}"></div>
      <div class="form-hint">${c.path || ""}</div></div>`;
  }).join("");

  openModal({
    title: `${d.serial} (${d.ip}) — 상세 정보`,
    xwide: true,
    bodyHtml: `
      <div class="tabs" style="margin:-18px -18px 14px; padding-left:18px;">
        <button class="tab-btn active" data-tab="dev">${icon("cpu", "icon icon-sm")}장치 관리자</button>
        <button class="tab-btn" data-tab="vol">${icon("database", "icon icon-sm")}디스크 볼륨</button>
        <button class="tab-btn" data-tab="qc">${icon("clipboardCheck", "icon icon-sm")}QC 리포트</button>
        <button class="tab-btn" data-tab="cap">${icon("camera", "icon icon-sm")}캡처 화면</button>
      </div>
      <div class="tab-panel active" data-panel="dev" style="max-height:50vh; overflow-y:auto;">
        <table class="mini-table"><thead><tr><th>분류</th><th>장치 이름</th><th>상태</th></tr></thead><tbody>${devRows}</tbody></table>
      </div>
      <div class="tab-panel" data-panel="vol" style="max-height:50vh; overflow-y:auto;">
        <table class="mini-table"><thead><tr><th>드라이브</th><th>디스크#</th><th>크기GB</th><th>여유GB</th><th>FS</th><th>레이블</th><th>상태</th></tr></thead><tbody>${volRows}</tbody></table>
      </div>
      <div class="tab-panel" data-panel="qc">${qcHtml}</div>
      <div class="tab-panel" data-panel="cap" style="max-height:60vh; overflow-y:auto;">${captureHtml}</div>
    `,
    onMount: (backdrop) => {
      backdrop.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          backdrop.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
          backdrop.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
          btn.classList.add("active");
          backdrop.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).classList.add("active");
        });
      });
    },
  });
}

// ── 캡처 뷰어 (전체화면, 시리얼 순서로 이전/다음 넘겨보기) ──────
// 캡처 버튼을 누르면 배치 전체가 끝난 뒤(onBatchDone) 자동으로 열리거나, "캡처 보기" 버튼으로
// 언제든 수동으로도 열 수 있다. 폴더에 직접 들어가서 하나씩 열어보는 대신, 프로그램 안에서
// 바로 큰 화면으로 확인하면서 QC 검증 속도를 높이는 게 목적.
let captureViewerState = null;

// 슬라이드 목록은 항상 "등록된 서버 전부"로 만든다 — 특정 종류의 캡처가 없는 서버도
// 목록엔 그대로 두고, 이미지가 없으면 슬라이드 안에서 "캡처 없음"으로 보여준다(기존 방식).
// 예전엔 여기서 "캡처가 있는 서버만" 걸러내다보니, 하필 고른 종류(예: 시스템정보)를 아무도
// 캡처 안 했으면 뷰어 자체가 아예 안 열리는 문제가 있었다.
function computeCaptureSlides(kind, restrictIps) {
  const ips = restrictIps || state.servers.map((s) => s.ip);
  return ips
    .map((ip) => state.servers.find((s) => s.ip === ip))
    .filter(Boolean)
    .sort((a, b) => (a.serial || "").localeCompare(b.serial || "", undefined, { numeric: true }))
    .map((s) => ({ ip: s.ip, serial: s.serial || s.ip }));
}

function kindHasAnyCapture(kind) {
  return state.servers.some((s) => ((state.status[s.ip] || {}).captures || {})[kind]);
}

// "캡처 보기" 수동 진입 시 기본으로 보여줄 종류 — 실제로 하나라도 캡처된 종류를 우선한다
// (전부 없으면 그냥 첫 번째 종류로, 뷰어는 어차피 항상 열리고 안에서 "캡처 없음"을 보여준다).
function pickCaptureKindWithData() {
  for (const k of CAPTURE_KINDS) {
    if (kindHasAnyCapture(k)) return k;
  }
  return CAPTURE_KINDS[0];
}

function openCaptureViewer(kind, restrictIps) {
  const slides = computeCaptureSlides(kind, restrictIps);
  if (!slides.length) { toast("등록된 서버가 없습니다.", "warn"); return; }
  captureViewerState = { kind, slides, idx: 0, cache: {} };
  renderCaptureViewer();
}

async function loadCaptureSlide(ip, kind) {
  const st = captureViewerState;
  const cacheKey = `${ip}|${kind}`;
  if (cacheKey in st.cache) return st.cache[cacheKey];
  const d = await api().get_server_detail(ip);
  const c = (d.captures || {})[kind] || null;
  st.cache[cacheKey] = c;
  return c;
}

function captureViewerNav(delta) {
  const st = captureViewerState;
  if (!st) return;
  st.idx = Math.min(Math.max(st.idx + delta, 0), st.slides.length - 1);
  renderCaptureViewer();
}

function captureViewerKeyHandler(e) {
  if (!captureViewerState) return;
  if (e.key === "ArrowLeft") captureViewerNav(-1);
  else if (e.key === "ArrowRight") captureViewerNav(1);
  else if (e.key === "Escape") closeCaptureViewer();
}

function closeCaptureViewer() {
  const root = document.getElementById("capture-viewer");
  if (root) root.remove();
  document.removeEventListener("keydown", captureViewerKeyHandler);
  captureViewerState = null;
}

async function renderCaptureViewer() {
  const st = captureViewerState;
  if (!st) return;
  let root = document.getElementById("capture-viewer");
  if (!root) {
    root = document.createElement("div");
    root.id = "capture-viewer";
    root.className = "capture-viewer";
    document.body.appendChild(root);
    document.addEventListener("keydown", captureViewerKeyHandler);
  }
  const slide = st.slides[st.idx];
  const kindOptions = CAPTURE_KINDS.map(
    (k) => `<option value="${k}" ${k === st.kind ? "selected" : ""}>${CAPTURE_KIND_LABELS[k]}</option>`
  ).join("");
  root.innerHTML = `
    <div class="cv-head">
      <select class="field" id="cv-kind">${kindOptions}</select>
      <span class="cv-title">${slide.serial} (${st.idx + 1} / ${st.slides.length})</span>
      <button class="close-x" id="cv-close">${icon("x", "icon-sm")}</button>
    </div>
    <div class="cv-body">
      <button class="cv-nav cv-prev" id="cv-prev" ${st.idx === 0 ? "disabled" : ""}>${icon("chevronDown", "icon icon-sm")}</button>
      <div class="cv-img-wrap" id="cv-img-wrap"><span class="cv-loading">불러오는 중…</span></div>
      <button class="cv-nav cv-next" id="cv-next" ${st.idx === st.slides.length - 1 ? "disabled" : ""}>${icon("chevronDown", "icon icon-sm")}</button>
    </div>
    <div class="cv-hint" id="cv-hint"></div>
  `;
  root.classList.add("show");
  root.querySelector("#cv-close").addEventListener("click", closeCaptureViewer);
  root.querySelector("#cv-prev").addEventListener("click", () => captureViewerNav(-1));
  root.querySelector("#cv-next").addEventListener("click", () => captureViewerNav(1));
  root.querySelector("#cv-kind").addEventListener("change", (e) => {
    st.kind = e.target.value;
    st.slides = computeCaptureSlides(st.kind, null);
    st.idx = 0;
    if (!st.slides.length) { toast(`${CAPTURE_KIND_LABELS[st.kind]} 캡처가 없습니다.`, "warn"); closeCaptureViewer(); return; }
    renderCaptureViewer();
  });

  const data = await loadCaptureSlide(slide.ip, st.kind);
  if (captureViewerState !== st || st.slides[st.idx] !== slide) return; // 그 사이 넘어갔으면 무시
  const wrap = document.getElementById("cv-img-wrap");
  const hint = document.getElementById("cv-hint");
  if (!wrap) return;
  if (data && data.data_url) {
    wrap.innerHTML = `<img src="${data.data_url}">`;
    hint.textContent = data.path || "";
  } else {
    wrap.innerHTML = `<span class="cv-empty">캡처 없음</span>`;
    hint.textContent = "";
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
