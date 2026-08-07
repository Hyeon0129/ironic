#!/usr/bin/env python3
"""WinRM QC 대시보드 백엔드 (Ironic 대시보드에 서버사이드로 통합, 2026-08-06).

원본(sangsang/server_app.py)은 Python 표준 라이브러리 HTTP 서버 + pywebview
"창 껍데기"로 데스크톱 앱을 띄우는 진입점이었다. 이 파일은 그 원본에서 순수
비즈니스 로직인 Backend 클래스와, 그게 필요로 하는 헬퍼(sales_no, IP_RE,
_get_lan_ip 등)만 남기고, HTTP서버(Handler/do_GET/do_POST)·창 관리(main,
_apply_native_window_style, pywebview)는 뺐다 — 그 자리를 이 프로젝트의
FastAPI 앱(server/qc/routes.py)이 대신한다. 원본과 마찬가지로 Backend의
공개 메서드가 그대로 `/api/<method명>` RPC 엔드포인트로 노출되고, 기존
web/app.js는 그 계약을 그대로 기대하므로 프론트는 한 줄도 안 고쳤다.
"""

import base64
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent  # server/qc/ — web/ 은 여기, git에 커밋됨
WEB_DIR = BASE_DIR / "web"

# 런타임 상태(WinRM 계정정보, 서버 목록, 상태, 로그, 캡처 이미지)는 소스 트리
# 밖에 둔다 — redfish_creds.json/mac_list.txt와 같은 이유로 git에 커밋되면 안 됨
# (CLAUDE.md "시크릿 관리" 참고). .gitignore에도 이 경로를 추가해둠.
DATA_DIR = Path(os.environ.get("QC_DATA_DIR", "/data/ironic/qc_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE   = DATA_DIR / "config.json"
SERVERS_FILE  = DATA_DIR / "servers.json"
STATUS_FILE   = DATA_DIR / "status.json"
ACTIVITY_FILE = DATA_DIR / "activity_log.json"
CAPTURE_DIR   = DATA_DIR / "capture"

ACTIVITY_MAX = 500
# 상태 중 이 항목들만 재시작해도 남긴다 — 장치/볼륨 상세 목록이나 캡처 이미지(base64, 용량 큼)는
# 매번 상태가 바뀔 때마다 전체 파일에 다시 쓰기엔 너무 무거워서 제외 (다시 조회/캡처하면 채워짐).
STATUS_PERSIST_KEYS = {
    "ping", "winrm", "cur_name", "cpu", "ram", "gpu", "nic",
    "boot", "vol", "vol_msg", "act", "qc", "dev", "dev_count", "dev_issue_count",
    "dev_all", "captures", "power_on",
}

from .dashboard import WinRMClient, Server, DEFAULT_CONFIG, QC_TOOL_DIR
from .action_registry import ACTION_REGISTRY
from .client_profiles import CLIENT_PROFILES, DEFAULT_CLIENT_PROFILE
from .table_column_registry import TABLE_COLUMN_REGISTRY

IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

# QC 툴은 외부 공유서버(다운되거나 랜선이 빠질 수 있음) 대신 이 노트북 자신을 SMB 공유
# 호스트로 쓴다 — 공유 이름은 고정, 노트북 IP는 와이파이라 바뀔 수 있으므로 QC 실행마다
# _get_lan_ip()로 그때그때 새로 알아내서 원격 서버에 전달한다.
QC_SHARE_NAME = "QcShare"

# 캡처 종류 — 파일명/로그에 쓰이는 한글 라벨. "current"(현재화면)는 특정 창을 열지 않고 지금
# 떠 있는 화면을 그대로 찍는 것이라, 5종 정기점검 캡처와 달리 "전체 캡처" 순차 진행 및
# 완료 개수 집계(CAPTURE_ALL_ORDER)에는 포함하지 않는다(서버실에 안 들어가고 지금 뭘 하고
# 있는지만 빠르게 확인하는 용도).
CAPTURE_KIND_LABELS = {
    "devmgmt": "장치관리자",
    "mypc": "내PC",
    "diskmgmt": "디스크관리",
    "about": "시스템정보",
    "activation": "인증정보",
    "current": "현재화면",
}


def sales_no(serial):
    """시리얼번호(예: 58844-001)에서 매출번호(58844) 부분만 추출 — 캡처 폴더 분류용."""
    serial = serial or ""
    return serial.split("-", 1)[0] if "-" in serial else serial


class Backend:
    """비즈니스 로직 전부 (qc_dashboard.py 의 WinRMClient 를 그대로 감싸는 계층).
    HTTP 서버가 이 클래스의 공개 메서드를 /api/<method> 로 그대로 노출한다."""

    def __init__(self):
        self.cfg = self._load_config()
        self.servers: list[Server] = []
        self.status: dict[str, dict] = self._load_status()
        self.client = WinRMClient(
            self.cfg.get("username", "super"), self.cfg.get("password", "1"))
        self._subscribers: list[queue.Queue] = []
        self._sub_lock = threading.Lock()
        self._activity = self._load_activity()
        self._load_servers()
        self._log_window = None

    # ── 영속화 ────────────────────────────────────────────────────
    def _load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        cfg.setdefault("qc_share_user", "")
        cfg.setdefault("qc_share_pass", "")
        # 이 노트북에서 QC 툴(WindowsQC 폴더) 원본이 있는 위치 — 사람마다 저장 위치가 다를 수
        # 있어서 설정에서 직접 고를 수 있어야 한다. 기본값은 기존에 코드에 고정돼 있던 경로.
        cfg.setdefault("qc_tool_dir", str(QC_TOOL_DIR))
        if CONFIG_FILE.exists():
            try:
                cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass
        return cfg

    def _save_config(self):
        CONFIG_FILE.write_text(
            json.dumps(self.cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_servers(self):
        if SERVERS_FILE.exists():
            try:
                for d in json.loads(SERVERS_FILE.read_text(encoding="utf-8")):
                    s = Server.from_dict(d)
                    if s.ip:
                        self.servers.append(s)
            except Exception:
                pass

    def _save_servers(self):
        SERVERS_FILE.write_text(
            json.dumps([s.to_dict() for s in self.servers], ensure_ascii=False, indent=2),
            encoding="utf-8")

    def _load_status(self):
        if STATUS_FILE.exists():
            try:
                return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_status(self):
        try:
            filtered = {
                ip: {k: v for k, v in st.items() if k in STATUS_PERSIST_KEYS}
                for ip, st in self.status.items()
            }
            STATUS_FILE.write_text(json.dumps(filtered, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_activity(self):
        if ACTIVITY_FILE.exists():
            try:
                return json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_activity(self):
        try:
            ACTIVITY_FILE.write_text(
                json.dumps(self._activity[-ACTIVITY_MAX:], ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # ── 프론트엔드 푸시 (SSE 구독자 전원에게 브로드캐스트) ─────────
    def subscribe(self):
        q = queue.Queue()
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _push(self, event, payload):
        msg = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(msg)

    def log(self, msg, level="dim"):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"ts": ts, "msg": msg, "level": level}
        self._activity.append(entry)
        if len(self._activity) > ACTIVITY_MAX:
            self._activity = self._activity[-ACTIVITY_MAX:]
        self._save_activity()
        self._push("log", entry)

    # cur_name 자리에 "지금 이 서버 상태가 어떤지" 보여주려고 잠깐 넣어두는 문구들 — 실제
    # 컴퓨터명이 아니므로 로그 식별자로 쓰면 "[재부팅중…] 연결 확인 중…"처럼 어느 서버 얘기인지
    # 알 수 없는 로그가 찍힌다(재부팅 자동감지 중 실제로 발생했던 문제).
    _CUR_NAME_PLACEHOLDERS = {"재부팅중…", "응답없음", "종료됨"}

    def _label(self, srv):
        """로그에 서버를 가리킬 때 쓰는 식별자 — 목표 시리얼(srv.serial, "이름변경"을 누르기
        전까지는 아직 실제 이름이 아님)이 아니라, 실제로 조회된 현재 컴퓨터명(cur_name)을
        우선 사용한다. 한 번도 조회 안 된 신규 서버는 조회할 값이 없으므로 시리얼로 대체.
        cur_name이 상태 placeholder인 동안에도 시리얼로 대체한다."""
        cur_name = (self.status.get(srv.ip, {}) or {}).get("cur_name")
        if not cur_name or cur_name in self._CUR_NAME_PLACEHOLDERS:
            return srv.serial
        return cur_name

    def set_status(self, ip, **kw):
        self.status.setdefault(ip, {}).update(kw)
        self._save_status()
        self._push("status", {"ip": ip, **kw})

    def set_busy(self, ip, action, busy, progress=None):
        payload = {"ip": ip, "action": action, "busy": busy}
        if progress is not None:
            payload["progress"] = progress
        self._push("busy", payload)

    @contextmanager
    def busy(self, ip, action):
        # progress=None → 실제 진행률 신호가 없는 동안은 불확정(shimmer) 표시.
        # 실제 통신 결과로 확인된 마일스톤이 있을 때만 개별 set_busy(..., progress=N) 호출로 갱신.
        self.set_busy(ip, action, True, progress=None)
        try:
            yield
        finally:
            self.set_busy(ip, action, False)

    # ══════════════════════════════════════════════════════════════
    # HTTP 로 노출되는 공개 API (프론트엔드는 fetch('/api/xxx')로 호출)
    # ══════════════════════════════════════════════════════════════
    def get_state(self):
        return {
            "config": self.cfg,
            "servers": [s.to_dict() for s in self.servers],
            "status": self.status,
            "log_history": self._activity,
        }

    def list_client_profiles(self):
        """대시보드 상단의 업체 선택 드롭다운 채우는 용도 — 지금 적용 중인 게 어떤 프로필인지도
        같이 내려줘서, "이 exe가 지금 어느 업체로 동작 중인지"를 화면에서 바로 알 수 있게 한다."""
        current = self.cfg.get("client_profile") or DEFAULT_CLIENT_PROFILE
        if current not in CLIENT_PROFILES:
            current = DEFAULT_CLIENT_PROFILE
        return {
            "ok": True,
            "current": current,
            "profiles": [{"id": k, "display_name": v.get("display_name", k)} for k, v in CLIENT_PROFILES.items()],
        }

    def get_sidebar_config(self):
        """현재 client_profile 설정에 맞는 사이드바 섹션/항목 + 대시보드 표에 추가로 필요한
        컬럼 목록을 조립해서 돌려준다 — 레지스트리(항목/컬럼 정의)와 프로필(업체별 목록)을
        여기서 합친다. 프로필에 없는 업체거나 목록에 없는 id는 조용히 건너뛴다(오타로 화면이
        깨지는 대신 그 항목만 빠짐)."""
        name = self.cfg.get("client_profile") or DEFAULT_CLIENT_PROFILE
        profile = CLIENT_PROFILES.get(name) or CLIENT_PROFILES[DEFAULT_CLIENT_PROFILE]
        sections = []
        for sec in profile["sections"]:
            items = [{"id": mid, **ACTION_REGISTRY[mid]} for mid in sec["items"] if mid in ACTION_REGISTRY]
            if items:
                sections.append({"label": sec["label"], "items": items})
        table_columns = [{"id": cid, **TABLE_COLUMN_REGISTRY[cid]}
                          for cid in profile.get("table_columns", []) if cid in TABLE_COLUMN_REGISTRY]
        return {"ok": True, "profile": name, "sections": sections, "table_columns": table_columns}

    def export_log(self, dest_path):
        """작업 로그 전체를 사용자가 지정한 경로/파일명으로 저장 (브라우저 다운로드와 달리
        pywebview 창에는 다운로드 폴더 개념이 없어 파이썬이 직접 파일을 쓴다)."""
        try:
            lines = [f"[{e.get('ts', '')}] {e.get('msg', '')}" for e in self._activity]
            p = Path(dest_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(lines), encoding="utf-8")
            return {"ok": True, "path": str(p)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_config(self, cfg):
        # 매출번호 적용은 여기서 서버 목록을 건드리지 않는다 — "이 서버를 이 이름으로 바꿀 것"이라는
        # 목표는 "이름변경" 버튼을 눌러 실제로 Windows 컴퓨터명을 바꾸는 그 순간에만 반영된다
        # (_do_rename 참고, 그때 self.cfg의 현재 매출번호를 읽어서 계산). 그래서 매출번호를
        # 잘못 등록해서 12345 → 55555 로 바꿔도, "이름변경"을 누르기 전까지는 아무 것도 안 바뀌고,
        # 누르는 순간 그때의 매출번호로 실제 이름이 바뀐다.
        old_share_user = self.cfg.get("qc_share_user", "")
        old_share_pass = self.cfg.get("qc_share_pass", "")
        self.cfg.update(cfg)
        self._save_config()
        self.client = WinRMClient(
            self.cfg.get("username", "super"), self.cfg.get("password", "1"))
        self.log("설정 저장 완료", "ok")

        new_share_user = self.cfg.get("qc_share_user", "")
        new_share_pass = self.cfg.get("qc_share_pass", "")
        if new_share_user and new_share_pass and (
                new_share_user != old_share_user or new_share_pass != old_share_pass):
            # 여기서 저장한 비밀번호는 config.json에만 반영될 뿐, 실제 Windows 로컬 계정
            # 비밀번호는 별개로 관리되고 있었다 — 둘이 어긋나면 QC 공유폴더 인증이 조용히
            # 실패하게 된다. 그래서 설정에서 바꾸는 즉시 실제 계정에도 반영을 시도한다.
            # 계정 비밀번호 변경은 관리자 권한이 필요해서 UAC 승인 창이 뜬다(앱 자체는 평소
            # 비관리자 권한으로 돌기 때문 — 이 한 동작만 별도로 승격시킨다).
            threading.Thread(
                target=self._apply_share_password,
                args=(new_share_user, new_share_pass), daemon=True).start()
        return {"ok": True, "config": self.cfg}

    def _apply_share_password(self, username, password):
        u = username.replace("'", "''")
        p = password.replace("'", "''")
        self.log(f"공유폴더 계정({username}) 비밀번호를 실제 Windows 계정에도 적용 중… "
                  f"(관리자 권한 승인 창이 뜹니다)", "run")
        inner = f"""
try {{
    if (Get-LocalUser -Name '{u}' -ErrorAction SilentlyContinue) {{
        $sec = ConvertTo-SecureString '{p}' -AsPlainText -Force
        Set-LocalUser -Name '{u}' -Password $sec -ErrorAction Stop
        "PWSET_OK" | Out-File '__STATUS__' -Encoding UTF8 -Force
    }} else {{
        "PWSET_NOUSER" | Out-File '__STATUS__' -Encoding UTF8 -Force
    }}
}} catch {{
    "PWSET_ERR: $($_.Exception.Message)" | Out-File '__STATUS__' -Encoding UTF8 -Force
}}
"""
        ts = int(time.time())
        status_file = str(Path(os.environ.get("TEMP", ".")) / f"qcshare_pwset_{ts}.txt")
        tmp_script = str(Path(os.environ.get("TEMP", ".")) / f"qcshare_pwset_{ts}.ps1")
        inner = inner.replace("__STATUS__", status_file.replace("'", "''"))
        b64 = base64.b64encode(b"\xef\xbb\xbf" + inner.encode("utf-8")).decode("ascii")
        outer = f"""
Remove-Item '{status_file}' -EA SilentlyContinue
$bytes = [System.Convert]::FromBase64String('{b64}')
[System.IO.File]::WriteAllBytes('{tmp_script}', $bytes)
try {{
    Start-Process powershell -Verb RunAs -Wait -ErrorAction Stop `
        -ArgumentList '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{tmp_script}"'
}} catch {{
    "PWSET_CANCELLED" | Out-File '{status_file}' -Encoding UTF8 -Force
}}
Start-Sleep -Milliseconds 300
if (Test-Path '{status_file}') {{ Get-Content '{status_file}' -Raw }} else {{ "PWSET_UNKNOWN" }}
Remove-Item '{tmp_script}' -EA SilentlyContinue
Remove-Item '{status_file}' -EA SilentlyContinue
"""
        _, out, err = self.client.run_local(outer, timeout=120)
        out = (out or "").strip()
        if "PWSET_OK" in out:
            self.log(f"공유폴더 계정({username}) 비밀번호가 실제 Windows 계정에 정상 적용됐습니다.", "ok")
        elif "PWSET_NOUSER" in out:
            self.log(f"공유폴더 계정({username})이 아직 이 노트북에 없습니다 — "
                      f"setup_qc_share.ps1을 먼저 관리자 권한으로 실행하세요.", "warn")
        elif "PWSET_CANCELLED" in out:
            self.log(f"공유폴더 계정 비밀번호 적용 취소됨 (관리자 권한 승인 안 함) — "
                      f"config.json에만 저장되고 실제 계정은 그대로입니다.", "warn")
        else:
            detail = " / ".join(p for p in (out, err) if p)[:300]
            self.log(f"공유폴더 계정 비밀번호 적용 실패: {detail}", "err")

    def update_server_serial(self, ip, serial):
        """서버 하나만 개별로 시리얼번호 변경 — 매출번호 스킴을 따르지 않는 서버도 등록할 수
        있으므로, 일괄 매출번호 변경과 별개로 서버 하나만 직접 고칠 수 있어야 한다."""
        serial = (serial or "").strip()
        if not serial:
            return {"ok": False, "error": "시리얼번호를 입력하세요."}
        srv = next((s for s in self.servers if s.ip == ip), None)
        if not srv:
            return {"ok": False, "error": "서버를 찾을 수 없습니다."}
        old = srv.serial
        srv.serial = serial
        self._save_servers()
        self.log(f"[{old}] 시리얼번호 변경 → {serial}", "ok")
        return {"ok": True, "servers": [s.to_dict() for s in self.servers]}

    def browse_folder(self, description=None):
        """원본은 이 프로세스를 돌리는 로컬 Windows 데스크톱에 네이티브 폴더 선택창을 띄웠다.
        여기선 이 프로세스가 서버이고 화면은 사용자의 브라우저 안에 있어서, 서버가 대신 로컬
        폴더 선택창을 띄울 방법이 없다(띄워도 이 서버 화면 앞에 아무도 없음) — 웹 컨텍스트에서는
        지원 불가능한 기능이라 항상 실패를 반환한다. app.js가 이 응답을 받으면 텍스트 입력으로
        경로를 직접 타이핑하도록 유도해야 함."""
        return {"ok": False, "error": "웹 버전에서는 폴더 선택창을 지원하지 않습니다. 경로를 직접 입력해 주세요."}

    def open_log_window(self):
        """원본은 로그 패널을 pywebview 네이티브 창으로 분리했다. 브라우저 탭 안에서 서버가
        새 OS 창을 띄울 방법은 없으므로 지원하지 않음 — app.js 쪽에서 이 실패를 받으면 로그
        패널을 별도 브라우저 탭(window.open)으로 여는 식으로 대체해야 한다면 프론트 쪽 변경이
        필요함(지금은 백엔드만 통합 범위)."""
        return {"ok": False, "error": "웹 버전에서는 로그 창 분리를 지원하지 않습니다."}

    # ── 서버 관리 ─────────────────────────────────────────────────
    def add_server(self, ip, serial):
        ip = (ip or "").strip()
        serial = (serial or "").strip()
        if not IP_RE.match(ip):
            return {"ok": False, "error": "올바른 IP를 입력하세요."}
        if any(s.ip == ip for s in self.servers):
            return {"ok": False, "error": f"{ip} 는 이미 등록되어 있습니다."}
        self.servers.append(Server(ip, serial))
        self._save_servers()
        self.log(f"[{serial}] 서버 추가됨", "ok")
        return {"ok": True, "servers": [s.to_dict() for s in self.servers]}

    def bulk_add_servers(self, sales, ip_text):
        sales = (sales or "").strip()
        if not sales:
            return {"ok": False, "error": "시작번호를 입력하세요."}
        # "58676-010" 처럼 시작 시리얼을 통째로 받는다 — 접두어(매출번호)와 시작 인덱스를
        # 분리해서, IP 목록 순서대로 그 번호부터 이어서 매긴다. "-숫자" 패턴이 아니면(예전처럼
        # 매출번호만 입력) 1번부터 3자리로 시작하는 기존 동작을 그대로 유지한다.
        m = re.match(r"^(.+)-(\d+)$", sales)
        if m:
            prefix, start_idx, width = m.group(1), int(m.group(2)), len(m.group(2))
        else:
            prefix, start_idx, width = sales, 1, 3
        lines = [l.strip() for l in (ip_text or "").splitlines() if l.strip()]
        valid = [ip for ip in lines if IP_RE.match(ip)]
        if not valid:
            return {"ok": False, "error": "올바른 IP를 입력하세요."}
        added = 0
        idx = start_idx
        duplicates = []
        for ip in valid:
            if any(s.ip == ip for s in self.servers):
                duplicates.append(ip)
                continue
            self.servers.append(Server(ip, f"{prefix}-{idx:0{width}d}"))
            idx += 1
            added += 1
        if added:
            self._save_servers()
            self.log(f"서버 {added}대 일괄 추가 완료", "ok")
        if duplicates:
            self.log(f"이미 등록된 IP {len(duplicates)}개 건너뜀: {', '.join(duplicates)}", "warn")
        return {
            "ok": True, "added": added, "duplicates": duplicates,
            "servers": [s.to_dict() for s in self.servers],
        }

    def add_servers_from_text(self, text):
        added = 0
        for ln in (text or "").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split()
            if len(parts) >= 2:
                ip, serial = (parts[0], parts[1]) if IP_RE.match(parts[0]) else (parts[1], parts[0])
            elif len(parts) == 1:
                ip, serial = parts[0], ""
            else:
                continue
            if IP_RE.match(ip) and not any(s.ip == ip for s in self.servers):
                self.servers.append(Server(ip, serial))
                added += 1
        if added:
            self._save_servers()
            self.log(f"파일에서 {added}개 서버 로드 완료", "ok")
        return {"ok": True, "added": added, "servers": [s.to_dict() for s in self.servers]}

    def delete_servers(self, ips):
        ips = set(ips or [])
        self.servers = [s for s in self.servers if s.ip not in ips]
        for ip in ips:
            self.status.pop(ip, None)
        self._save_servers()
        return {"ok": True, "servers": [s.to_dict() for s in self.servers]}

    # ── 조회/상세 ─────────────────────────────────────────────────
    def get_devices_all(self):
        rows = []
        for s in self.servers:
            devices = self.status.get(s.ip, {}).get("_devices", [])
            for d in devices:
                rows.append({
                    "serial": s.serial, "ip": s.ip,
                    "cat": d.get("Category", ""), "name": d.get("Name", ""),
                    "status": d.get("Status", ""),
                })
        return rows

    def get_server_detail(self, ip):
        srv = next((s for s in self.servers if s.ip == ip), None)
        if not srv:
            return {"ok": False}
        st = self.status.get(ip, {})
        local_out = Path(self.cfg.get(
            "local_output_dir", str(Path.home() / "Desktop" / "QC_Results")))
        qc_text = None
        qc_path = None
        try:
            txts = sorted(local_out.glob("*hardwareQC.txt"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if txts:
                qc_path = str(txts[0])
                qc_text = txts[0].read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        captures = self._live_captures(ip, st)
        return {
            "ok": True, "serial": srv.serial, "ip": ip,
            "devices": st.get("_devices", []),
            "volumes": st.get("_volumes", []),
            "qc_path": qc_path, "qc_text": qc_text,
            "captures": captures,
        }

    def _live_captures(self, ip, st=None):
        """캡처 이미지는 메모리(_captures)에 base64로 캐시돼 있어서, 사용자가 capture\\ 폴더의
        PNG 파일을 직접 지워도 캐시는 그대로 남아 "캡처 보기"에 계속 나오는 것처럼 보일 수 있다.
        조회 시점에 실제 파일이 아직 존재하는지 확인해서, 지워진 파일은 캐시에서도 같이
        제거하고 테이블의 n/5 배지도 실제 상태로 다시 반영한다."""
        st = st if st is not None else self.status.get(ip, {})
        raw = st.get("_captures", {})
        live = {k: v for k, v in raw.items() if v.get("path") and Path(v["path"]).exists()}
        if len(live) != len(raw):
            st["_captures"] = live
            self.set_status(ip, captures={k: v["path"] for k, v in live.items()})
        return live

    # ── 일괄 실행 헬퍼 ────────────────────────────────────────────
    def _selected(self, ips):
        want = set(ips or [])
        return [s for s in self.servers if s.ip in want]

    def _run_batch(self, name, ips, fn):
        srvs = self._selected(ips)
        if not srvs:
            return {"ok": False, "error": "서버를 선택하세요."}
        self.log(f"일괄 시작 ({len(srvs)}대) [{name}]", "run")

        def run():
            threads = [threading.Thread(target=fn, args=(s,), daemon=True) for s in srvs]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.log(f"일괄 완료 [{name}]", "ok")
            # 캡처 계열 배치는 "전부 다 찍힐 때까지 기다렸다가 시리얼 순서대로 넘겨보기" 뷰어를
            # 프론트에서 자동으로 띄우기 위한 신호 — 개별 캡처 완료 이벤트만으로는 언제 배치
            # 전체가 끝났는지 알 수 없어서 별도로 필요하다.
            self._push("batch_done", {"name": name, "ips": [s.ip for s in srvs]})

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "count": len(srvs)}

    # ── 배치 액션 ─────────────────────────────────────────────────
    def batch_connect(self, ips):
        return self._run_batch("connect", ips, self._do_connect)

    def batch_devices(self, ips):
        return self._run_batch("devices", ips, self._do_devices)

    def batch_boot_folder(self, ips):
        return self._run_batch("boot_folder", ips, self._do_boot_folder)

    def batch_volumes_check(self, ips):
        return self._run_batch("volumes_check", ips, self._do_volumes_check)

    def batch_name_check(self, ips):
        return self._run_batch("name_check", ips, self._do_name_check)

    def batch_activation_check(self, ips):
        return self._run_batch("activation_check", ips, self._do_activation_check)

    def batch_capture_devmgmt(self, ips):
        return self._run_batch("capture_devmgmt", ips, lambda s: self._do_capture(s, "devmgmt"))

    def batch_capture_mypc(self, ips):
        return self._run_batch("capture_mypc", ips, lambda s: self._do_capture(s, "mypc"))

    def batch_capture_diskmgmt(self, ips):
        return self._run_batch("capture_diskmgmt", ips, lambda s: self._do_capture(s, "diskmgmt"))

    def batch_capture_about(self, ips):
        return self._run_batch("capture_about", ips, lambda s: self._do_capture(s, "about"))

    def batch_capture_activation(self, ips):
        return self._run_batch("capture_activation", ips, lambda s: self._do_capture(s, "activation"))

    def batch_capture_current(self, ips):
        return self._run_batch("capture_current", ips, lambda s: self._do_capture(s, "current"))

    CAPTURE_ALL_ORDER = ["devmgmt", "about", "diskmgmt", "mypc", "activation"]

    def batch_capture_all(self, ips):
        """5종 캡처를 순서대로 한 단계씩 진행: 한 종류를 선택된 서버 전부에서 병렬로 캡처하고,
        전부 끝난 것을 확인(스레드 join)한 뒤 5초 쉬고 다음 종류로 넘어간다. 장치관리자 창이
        아직 안 닫혔는데 다음 종류(예: 시스템정보)가 열리기 시작해서 화면이 꼬이는 걸 막기 위해
        같은 서버에서 두 종류가 동시에 진행되는 일이 없도록 종류별로 완전히 순차 실행한다."""
        srvs = self._selected(ips)
        if not srvs:
            return {"ok": False, "error": "서버를 선택하세요."}

        def run():
            for kind in self.CAPTURE_ALL_ORDER:
                label = CAPTURE_KIND_LABELS[kind]
                self.log(f"전체 캡처 — {label} 시작 ({len(srvs)}대)", "run")
                threads = [threading.Thread(target=self._do_capture, args=(s, kind), daemon=True)
                           for s in srvs]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                self.log(f"전체 캡처 — {label} 완료", "ok")
                time.sleep(5)
            self.log("전체 캡처 완료", "ok")
            self._push("batch_done", {"name": "capture_all", "ips": [s.ip for s in srvs]})

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "count": len(srvs)}

    def batch_volumes(self, ips):
        return self._run_batch("volumes", ips, self._do_volumes)

    def batch_qc(self, ips):
        return self._run_batch("qc", ips, self._do_qc)

    def batch_time_sync(self, ips):
        return self._run_batch("time_sync", ips, self._do_time_sync)

    def batch_power_high(self, ips):
        return self._run_batch("power_high", ips, self._do_power_high)

    def batch_cloudbase_init(self, ips):
        return self._run_batch("cloudbase_init", ips, self._do_cloudbase_init)

    def batch_install_rst(self, ips):
        return self._run_batch("install_rst", ips, self._do_install_rst)

    def batch_open_rst(self, ips):
        return self._run_batch("open_rst", ips, self._do_open_rst)

    def batch_raid1(self, ips):
        return self._run_batch("raid1", ips, self._do_raid1)

    def batch_temp_cleanup(self, ips):
        return self._run_batch("temp_cleanup", ips, self._do_temp_cleanup)

    def batch_stop_winrm(self, ips):
        return self._run_batch("stop_winrm", ips, self._do_stop_winrm)

    def batch_restart(self, ips):
        return self._run_batch("restart", ips, self._do_restart)

    def batch_shutdown(self, ips):
        return self._run_batch("shutdown", ips, self._do_shutdown)

    def batch_rename(self, ips):
        return self._run_batch("rename", ips, self._do_rename)

    def batch_activate(self, ips, keys):
        srvs = self._selected(ips)
        if not srvs:
            return {"ok": False, "error": "서버를 선택하세요."}
        keys = keys or {}

        def activate_one(s):
            with self.busy(s.ip, "activate"):
                key = (keys.get(s.ip) or "").strip()
                if not key:
                    self.log(f"[{self._label(s)}] 키 없음 — 건너뜀", "warn")
                    return
                self.log(f"[{self._label(s)}] 정품 인증 중…", "run")
                self.set_status(s.ip, act="PENDING")
                code, out, err = self.client.activate_windows(s.ip, key)
                for p in out.split("|||"):
                    if p.strip():
                        self.log(f"[{self._label(s)}] {p.strip()}")
                if "successfully" in out.lower() or "성공" in out:
                    self.log(f"[{self._label(s)}] 인증 성공", "ok")
                    self.set_status(s.ip, act="LICENSED")
                else:
                    self.log(f"[{self._label(s)}] 인증 결과 확인 필요", "warn")
                    self.set_status(s.ip, act="UNKNOWN")

        def run():
            threads = [threading.Thread(target=activate_one, args=(s,), daemon=True) for s in srvs]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.log(f"정품 인증 완료 ({len(srvs)}대)", "ok")

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True}

    # ══════════════════════════════════════════════════════════════
    # 개별 작업 (원격 1대 대상)
    # ══════════════════════════════════════════════════════════════
    def _do_connect(self, srv: Server):
        with self.busy(srv.ip, "connect"):
            self.log(f"[{self._label(srv)}] 연결 확인 중…")
            self.set_status(srv.ip, ping=None, winrm=None, cur_name="…")
            # Ping(ICMP)과 WinRM(5985 포트)은 서로 다른 통신이라 방화벽 설정에 따라 결과가
            # 갈릴 수 있음 (예: ICMP는 막혀있어도 WinRM은 열려있는 경우) — 하나가 실패해도
            # 넘겨짚지 않고 각각 실제로 통신해서 얻은 결과로만 OK/FAIL을 표시한다.
            ok = self.client.ping(srv.ip)
            self.set_status(srv.ip, ping="OK" if ok else "FAIL")
            if not ok:
                self.log(f"[{self._label(srv)}] Ping 실패", "err")

            ok2 = self.client.test_winrm(srv.ip)
            self.set_status(srv.ip, winrm="OK" if ok2 else "FAIL")
            if not ok2:
                self.log(f"[{self._label(srv)}] WinRM 실패", "err")
                self.set_status(srv.ip, cur_name=None, power_on=False)
                return
            _, out, _ = self.client.get_computer_name(srv.ip)
            name = out.strip() or None
            self.set_status(srv.ip, cur_name=name)
            # 전원 표시(power_on): 예전엔 has_active_session(그 계정으로 RDP Active 세션인지)으로
            # 판정했는데, 그러면 계정/WinRM 다 정상인데 지금 아무도 RDP로 접속 중이 아니면(세션이
            # Disc거나 로그오프 상태) 실제로는 멀쩡히 켜져 있는데도 계속 꺼짐(빨강)으로 나오는
            # 문제가 있었다(실사용 중 확인됨). 여기까지 왔다는 건 이미 WinRM(ok2)이 응답했다는
            # 뜻이므로 그걸로 충분히 "켜져 있다"고 판단한다 — Active 세션 여부는 재부팅 완료
            # 감지(_wait_for_reboot, 자동로그인+바탕화면 진입까지 확인하는 별개 용도)에서만 쓴다.
            self.set_status(srv.ip, power_on=True)
            self.log(f"[{self._label(srv)}] 연결 OK — 컴퓨터명: {name}", "ok")

    def _do_devices(self, srv: Server):
        with self.busy(srv.ip, "devices"):
            self.log(f"[{self._label(srv)}] 장치·스펙 조회 중…")
            self.set_status(srv.ip, dev="PENDING")
            code, out, err = self.client.get_pnp_devices(srv.ip)
            if code != 0 or not out or "REMOTE_ERROR" in err:
                self.log(f"[{self._label(srv)}] 장치 조회 실패: {err[:80]}", "err")
                self.set_status(srv.ip, dev="FAIL", cpu=None, ram=None, gpu=None, nic=None)
                return
            try:
                data = json.loads(out)
                specs = data.get("specs", {}) if isinstance(data, dict) else {}
                cpu_n = (specs.get("cpu", "") or "")[:22]
                cnt = specs.get("cpu_count", 1) or 1
                cpu_s = f"{cpu_n} ×{cnt}" if cnt > 1 else cpu_n
                ram_s = f"{specs.get('ram_gb', '?')}GB"
                gpu_s = (specs.get("gpu", "") or "")[:20]
                nic_s = (specs.get("nic", "") or "")[:24]
                raw = data.get("devices", []) if isinstance(data, dict) else \
                    (data if isinstance(data, list) else [])
                if not isinstance(raw, list):
                    raw = [raw] if raw else []
                self.status.setdefault(srv.ip, {})["_devices"] = raw
                issues = [d for d in raw if d.get("Status", "").upper() != "OK"]
                if issues:
                    self.log(f"[{self._label(srv)}] 이상 장치 {len(issues)}개", "warn")
                else:
                    self.log(f"[{self._label(srv)}] 장치 정상 ({len(raw)}개) | {cpu_s} | {ram_s}", "ok")
                # dev_all: 장치 전체 목록을 요약(분류/이름/상태)만 추려서 status 에 함께 실어
                # 보낸다 — 테이블의 "장치" 칸에 마우스를 올렸을 때 추가 조회 없이 바로 "어떤
                # 장치가 정상이고 어떤 장치가 왜 이상인지"까지 전부 hover 로 보여주기 위함
                # (개수만 보여주면 실제로 뭐가 문제인지 알 수 없다는 피드백 반영).
                self.set_status(srv.ip, cpu=cpu_s, ram=ram_s, gpu=gpu_s, nic=nic_s,
                                 dev="WARN" if issues else "OK", dev_count=len(raw),
                                 dev_issue_count=len(issues),
                                 dev_all=[{"cat": d.get("Category", ""), "name": d.get("Name", ""),
                                           "status": d.get("Status", "")} for d in raw])
            except json.JSONDecodeError:
                self.set_status(srv.ip, dev="FAIL", cpu=None, ram=None, gpu=None, nic=None)

    def _do_volumes(self, srv: Server):
        with self.busy(srv.ip, "volumes"):
            self.log(f"[{self._label(srv)}] HDD 볼륨 E,F 생성 중…")
            self.set_status(srv.ip, vol="PENDING")
            code, out, err = self.client.create_hdd_volumes(srv.ip)
            if not out:
                self.log(f"[{self._label(srv)}] 볼륨 생성 실패: {err[:80]}", "err")
                self.set_status(srv.ip, vol="FAIL")
                return
            for p in out.split("|||"):
                p = p.strip()
                if not p:
                    continue
                if "OK:" in p or "EXISTS:" in p:
                    lvl = "ok"
                elif "ERR:" in p or "NO_TARGET:" in p:
                    lvl = "err"
                else:
                    lvl = "dim"
                self.log(f"[{self._label(srv)}] {p}", lvl)
            # E,F 생성 성공 여부와 C/D 등 다른 드라이브가 실제로 있는지는 서로 다른 질문이라
            # "볼륨" 칸을 이 작업의 성공/실패만으로 채우면 안 됨 — 생성 시도 후 실제 디스크
            # 상태를 다시 조회해서 CDEF 전체 존재 여부로 반영한다 (볼륨확인과 동일한 판단 로직).
            self._refresh_volume_status(srv)

    def _do_restart(self, srv: Server):
        with self.busy(srv.ip, "restart"):
            # 재부팅 감지에 쓸 "재부팅 전" 부팅시각을 미리 받아둔다 — 재부팅 명령을 보낸
            # 이 노트북 시각과 원격 서버의 LastBootUpTime을 직접 비교하는 방식은 두 기기의
            # 시계가 어긋나 있으면(특히 새로 설치한 VM은 시간/시간대가 안 맞는 경우가 흔함)
            # 절대 "신선하다"고 판정되지 않아 무한 대기하는 문제가 실사용 중 확인됐다. 그래서
            # 절대시각 비교 대신, 재부팅 전/후 같은 기기에서 받은 부팅시각 문자열이 "달라졌는지"
            # 만 보는 방식으로 바꿔서 시계 어긋남과 무관하게 정확히 판정한다.
            old_boot_iso = self.client.get_boot_time(srv.ip)
            self.log(f"[{self._label(srv)}] 재부팅 명령 전송…")
            self.client.restart(srv.ip)
            self.set_status(srv.ip, ping=None, winrm=None, cur_name="재부팅중…", power_on=False)
            self.log(f"[{self._label(srv)}] 재부팅 명령 전송 완료", "ok")
            self._wait_for_reboot(srv, old_boot_iso)

    def _wait_for_reboot(self, srv: Server, old_boot_iso, max_sec=600, interval=5):
        """재부팅 명령을 보낸 뒤 "진짜 다시 켜져서 바탕화면까지 뜬 시점"을 감지해서 대시보드의
        전원 표시(power_on)를 갱신하고, 이름확인 한 번만 자동으로 실행한다(장치조회 등 나머지는
        여전히 기술자가 직접 — 이유는 기존 주석 참고).

        매 10초 폴링마다 아래 3가지를 한 번에 확인하는 단일 루프 — 서버가 꺼져있거나 로딩
        중이면 이 중 하나는 항상 거짓이므로, 셋 다 참인 순간은 사실상 "진짜 바탕화면까지
        뜬 시점"뿐이다:
        1) WinRM 응답 — 안 되면 그냥 계속 대기(로그 없음). 실사용 확인 결과 재부팅 자체는
           수십 초면 끝나도 WinRM 서비스가 기동되는 데 그보다 훨씬 오래 걸리는 경우가 흔함 —
           이건 Windows 자체의 한계라 판정 로직으로 더 빠르게 할 수 없다.
        2) 부팅시각(LastBootUpTime)이 재부팅 "전"에 받아둔 값(old_boot_iso)과 달라졌는지 —
           이전 세션의 잔여 응답을 걸러낸다. `Restart-Computer`를 보내도 실제로 내려가기까지
           수 초~수십 초 걸리는데, 그 사이엔 이전 세션이 여전히 활성 상태로 남아있어서 이
           대조 없이 "WinRM+활성세션"만 보면 재부팅 시작 직후 오판할 수 있다(실사용 중 확인된
           최초 버그). 노트북과 원격 서버의 시계가 어긋나 있어도 정확하도록 절대시각이 아니라
           "같은 기기에서 재부팅 전/후 값이 달라졌는지"만 비교한다.
        3) 그 계정 세션이 실제로 Active 상태인지 — WinRM(서비스)이 응답한다고 사람이 로그인해서
           바탕화면까지 뜬 건 아니다(has_active_session, query user 기반 — 대상이 전부 영문
           Windows라 언어 문제 없음)."""
        hard_deadline = time.time() + max_sec
        username = self.cfg.get("username", "super")
        boot_confirmed = False

        while time.time() < hard_deadline:
            time.sleep(interval)
            if not self.client.test_winrm(srv.ip):
                continue
            boot_iso = self.client.get_boot_time(srv.ip)
            # old_boot_iso 를 못 받아온 경우(재부팅 전 이미 통신 불가 등)엔 비교 기준이
            # 없으므로 지금 받은 값을 그냥 신뢰한다.
            fresh = (not old_boot_iso) or (boot_iso and boot_iso != old_boot_iso)
            if not fresh:
                self.log(f"[{self._label(srv)}] 아직 이전 세션 응답으로 보임(부팅시각 미확인) — 계속 대기", "dim")
                continue
            if not boot_confirmed:
                boot_confirmed = True
                self.log(f"[{self._label(srv)}] WinRM 응답 재개 — 바탕화면 진입 대기 중…", "dim")
            if not self.client.has_active_session(srv.ip, username):
                continue

            self.log(f"[{self._label(srv)}] 재부팅 완료 — 바탕화면 진입 확인됨", "ok")
            self.set_status(srv.ip, power_on=True)
            self._do_name_check(srv)
            return
        self.log(f"[{self._label(srv)}] 재부팅 후 통신 재개 대기 타임아웃(10분)", "warn")
        self.set_status(srv.ip, cur_name="응답없음", power_on=False)

    def _do_shutdown(self, srv: Server):
        with self.busy(srv.ip, "shutdown"):
            self.log(f"[{self._label(srv)}] 종료 명령 전송…")
            self.client.shutdown(srv.ip)
            self.set_status(srv.ip, ping=None, winrm=None, cur_name="종료됨", power_on=False)
            self.log(f"[{self._label(srv)}] 종료 명령 전송 완료", "ok")

    def _do_boot_folder(self, srv: Server):
        with self.busy(srv.ip, "boot_folder"):
            self.log(f"[{self._label(srv)}] 부팅 디스크 확인 중…")
            code, out, err = self.client.check_boot_folder(srv.ip)
            out = out.strip()
            if out == "DISK_A":
                self.log(f"[{self._label(srv)}] A 디스크 부팅", "ok")
                self.set_status(srv.ip, boot="A")
            elif out == "DISK_B":
                self.log(f"[{self._label(srv)}] B 디스크 부팅")
                self.set_status(srv.ip, boot="B")
            else:
                self.log(f"[{self._label(srv)}] 부팅 디스크 불확실 — 바탕화면에 폴더1/2 필요", "warn")
                self.set_status(srv.ip, boot="UNKNOWN")

    def _refresh_volume_status(self, srv: Server):
        """실제 디스크를 다시 조회해서 C/D/E/F 전체 존재 여부로 '볼륨' 상태를 갱신.
        볼륨확인 버튼과 HDD볼륨생성 버튼이 공통으로 사용 — 어느 쪽에서 왔든 '볼륨' 칸은
        항상 실제 드라이브 존재 여부를 반영해야 하고, E,F 생성 성공 여부 같은 다른 의미로
        덮어써지면 안 된다 (예: D가 실제로 없는데도 E,F 생성만 성공해서 '정상'으로 잘못 표시되던 버그)."""
        code, out, err = self.client.get_disk_volumes(srv.ip)
        if code != 0 or not out:
            self.set_status(srv.ip, vol="FAIL")
            return
        try:
            items = json.loads(out)
            if not isinstance(items, list):
                items = [items]
            self.status.setdefault(srv.ip, {})["_volumes"] = items
            letters = {d.get("Letter", "") for d in items}
            missing = {"C", "D", "E", "F"} - letters
            if missing:
                self.log(f"[{self._label(srv)}] 누락 볼륨: {','.join(sorted(missing))}", "warn")
                self.set_status(srv.ip, vol="WARN", vol_msg=f"누락:{','.join(sorted(missing))}")
            else:
                self.log(f"[{self._label(srv)}] CDEF 모두 존재", "ok")
                self.set_status(srv.ip, vol="OK", vol_msg="CDEF")
        except Exception:
            self.set_status(srv.ip, vol="FAIL")

    def _do_volumes_check(self, srv: Server):
        with self.busy(srv.ip, "volumes_check"):
            self.log(f"[{self._label(srv)}] 볼륨 확인 중…")
            self._refresh_volume_status(srv)

    def _do_name_check(self, srv: Server):
        with self.busy(srv.ip, "name_check"):
            self.log(f"[{self._label(srv)}] 이름 확인 중…")
            _, out, _ = self.client.get_computer_name(srv.ip)
            name = out.strip()
            self.set_status(srv.ip, cur_name=name or None)
            if name.upper() == srv.serial.upper():
                self.log(f"[{self._label(srv)}] 이름 일치: {name}", "ok")
            else:
                self.log(f"[{self._label(srv)}] 이름 불일치: 현재={name} / 예상={srv.serial}", "warn")

    def _do_activation_check(self, srv: Server):
        with self.busy(srv.ip, "activation_check"):
            self.log(f"[{self._label(srv)}] 인증 상태 확인 중…")
            _, out, _ = self.client.check_activation(srv.ip)
            if "Licensed" in out:
                self.log(f"[{self._label(srv)}] 정품 인증 완료", "ok")
                self.set_status(srv.ip, act="LICENSED")
            else:
                self.log(f"[{self._label(srv)}] 미인증: {out[:50]}", "warn")
                self.set_status(srv.ip, act="UNLICENSED")

    def _do_rename(self, srv: Server):
        with self.busy(srv.ip, "rename"):
            # "이름변경"을 누르는 이 순간의 매출번호를 기준으로 목표 이름을 계산한다 — 매출번호를
            # 바꿔서 적용해도 이 버튼을 누르기 전까지는 등록된 서버가 전혀 안 바뀌고, 누르는
            # 순간에만 실제 Windows 컴퓨터명이 "그때의" 매출번호로 바뀐다. 시리얼이 "...-숫자"
            # 패턴이 아니면(개별 등록한 서버) 매출번호와 무관하게 기존 시리얼을 그대로 쓴다.
            sales = (self.cfg.get("sales_number") or "").strip()
            m = re.match(r"^(.+)-(\d+)$", srv.serial or "")
            target = f"{sales}-{m.group(2)}" if (sales and m) else srv.serial
            self.log(f"[{self._label(srv)}] 이름 변경 중… (목표: {target})")
            code, out, err = self.client.rename_computer(srv.ip, target)
            if "RENAMED" in out or code == 0:
                if target != srv.serial:
                    srv.serial = target
                    self._save_servers()
                    self._push("server_updated", {"ip": srv.ip, "serial": target})
                self.log(f"[{self._label(srv)}] 이름 변경 완료 (재부팅 후 적용)", "ok")
            else:
                self.log(f"[{self._label(srv)}] 이름 변경 실패: {err[:60]}", "err")

    def _do_time_sync(self, srv: Server):
        with self.busy(srv.ip, "time_sync"):
            self.log(f"[{self._label(srv)}] 한국 시간 동기화 중…", "run")
            now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            script = f"""
Set-TimeZone -Id 'Korea Standard Time' -EA SilentlyContinue
Set-Date -Date '{now_str}' -EA SilentlyContinue | Out-Null
try {{
    w32tm /config /syncfromflags:manual /manualpeerlist:'time.windows.com' /update 2>$null | Out-Null
    w32tm /resync /nowait 2>$null | Out-Null
}} catch {{}}
$tz = (Get-TimeZone).Id
$dt = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"SYNC_OK: $tz $dt" """
            code, out, err = self.client.run_remote(srv.ip, script, timeout=30)
            if "SYNC_OK" in out:
                self.log(f"[{self._label(srv)}] 시간 동기화 완료: {out.strip()}", "ok")
            else:
                self.log(f"[{self._label(srv)}] 시간 동기화 실패: {(err or out)[:60]}", "err")

    def _do_power_high(self, srv: Server):
        with self.busy(srv.ip, "power_high"):
            self.log(f"[{self._label(srv)}] 전원 고성능 변경 중…", "run")
            script = """
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
powercfg /change disk-timeout-ac 0
powercfg /change disk-timeout-dc 0
powercfg /change monitor-timeout-ac 0
"POWER_HIGH_OK" """
            code, out, err = self.client.run_remote(srv.ip, script, timeout=30)
            if "POWER_HIGH_OK" in out:
                self.log(f"[{self._label(srv)}] 전원 고성능 변경 완료", "ok")
            else:
                self.log(f"[{self._label(srv)}] 전원 고성능 변경 실패: {(err or out)[:60]}", "err")

    def _do_cloudbase_init(self, srv: Server):
        with self.busy(srv.ip, "cloudbase_init"):
            self.log(f"[{self._label(srv)}] CloudBase 초기화 중…", "run")
            # Win32_Product 조회는 설치된 모든 MSI를 재구성 검사하기 때문에 느린데, 매칭되는
            # 항목이 여러 개(실사용 중 2개인 경우 확인됨)면 각각 순서대로 Uninstall까지 걸려서
            # 90초로는 부족해 실제로는 다 지워졌는데도 "Timeout"으로 잘못 뜨는 문제가 있었다 —
            # 여유있게 5분으로 늘린다. 또한 -InputObject 에 배열을 통째로 넘기면 항목별로
            # 확실히 개별 처리된다는 보장이 약해서, 각 항목을 명시적으로 순회하며 결과를 모은다.
            script = """
$p = @(Get-CimInstance Win32_Product | Where-Object Name -like "*Cloudbase*")
if ($p.Count -gt 0) {
    $results = foreach ($item in $p) {
        $r = Invoke-CimMethod -InputObject $item -MethodName Uninstall
        "$($item.Name)=$($r.ReturnValue)"
    }
    "CLOUDBASE_UNINSTALLED: " + ($results -join ', ')
} else {
    "CLOUDBASE_NOT_FOUND"
}"""
            code, out, err = self.client.run_remote(srv.ip, script, timeout=300)
            if "CLOUDBASE_UNINSTALLED" in out:
                self.log(f"[{self._label(srv)}] CloudBase 제거 완료: {out.strip()}", "ok")
            elif "CLOUDBASE_NOT_FOUND" in out:
                self.log(f"[{self._label(srv)}] CloudBase 없음(이미 정리됨)", "ok")
            else:
                self.log(f"[{self._label(srv)}] CloudBase 초기화 실패: {(err or out)[:60]}", "err")

    def _do_temp_cleanup(self, srv: Server):
        with self.busy(srv.ip, "temp_cleanup"):
            self.log(f"[{self._label(srv)}] Temp 초기화 중…", "run")
            script = """
Remove-Item -Path "C:\\DriverTemp" -Recurse -Force -ErrorAction SilentlyContinue
"DriverTemp Removed. Exists: $(Test-Path 'C:\\DriverTemp')" """
            code, out, err = self.client.run_remote(srv.ip, script, timeout=30)
            if "Exists: False" in out:
                self.log(f"[{self._label(srv)}] Temp 초기화 완료: {out.strip()}", "ok")
            elif "DriverTemp Removed" in out:
                self.log(f"[{self._label(srv)}] Temp 초기화 후에도 폴더 남아있음: {out.strip()}", "warn")
            else:
                self.log(f"[{self._label(srv)}] Temp 초기화 실패: {(err or out)[:60]}", "err")

    def _do_install_rst(self, srv: Server):
        with self.busy(srv.ip, "install_rst"):
            self.log(f"[{self._label(srv)}] RST 설치 중…", "run")
            # -Wait 로 설치가 끝날 때까지 블록한 뒤, 드라이버/서비스가 완전히 자리잡을 시간을
            # 10초 더 주고 나서야 완료 신호를 돌려보낸다.
            script = r"""
Get-Process -Name SetupRST -ErrorAction SilentlyContinue | Stop-Process -Force
$setupPath = "C:\DriverTemp\Intel_Rapid_Storage_Technology_Driver_software_V20.2.6.1025\RAID\Intel\Install\SetupRST.exe"
$proc = Start-Process -FilePath $setupPath -ArgumentList "-s -accepteula" -Wait -PassThru
$exitCode = $proc.ExitCode
Start-Sleep -Seconds 10
"RST_INSTALL_DONE ExitCode: $exitCode"
"""
            code, out, err = self.client.run_remote(srv.ip, script, timeout=180)
            if "RST_INSTALL_DONE" in out:
                self.log(f"[{self._label(srv)}] RST 설치 완료: {out.strip()}", "ok")
            else:
                self.log(f"[{self._label(srv)}] RST 설치 실패: {(err or out)[:120]}", "err")

    def _do_open_rst(self, srv: Server):
        with self.busy(srv.ip, "open_rst"):
            self.log(f"[{self._label(srv)}] RST 창 여는 중…", "run")
            username = self.cfg.get("username", "super")
            # UWP 앱은 일반 exe처럼 경로 실행이 안 되고 shell:AppsFolder\<PackageFamilyName>!<AppId>
            # 형태로만 열 수 있어서, devmgmt/RAID 구성과 동일하게 Interactive 예약작업으로 연다.
            script = rf"""
$packageFamilyName = "AppUp.IntelOptaneMemoryandStorageManagement_8j3eq9eme6ctt"
$appId = "App"
$action = New-ScheduledTaskAction -Execute "explorer.exe" -Argument "shell:AppsFolder\$packageFamilyName!$appId"
$principal = New-ScheduledTaskPrincipal -UserId "{username}" -LogonType Interactive -RunLevel Highest
$task = New-ScheduledTask -Action $action -Principal $principal
Register-ScheduledTask -TaskName "OpenIntelRST" -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName "OpenIntelRST"
Start-Sleep -Seconds 3
Unregister-ScheduledTask -TaskName "OpenIntelRST" -Confirm:$false
echo "Intel RST App Opened."
"""
            code, out, err = self.client.run_remote(srv.ip, script, timeout=30)
            if "Intel RST App Opened" in out:
                self.log(f"[{self._label(srv)}] RST 창 열기 완료", "ok")
            else:
                self.log(f"[{self._label(srv)}] RST 창 열기 실패: {(err or out)[:120]}", "err")

    def _do_raid1(self, srv: Server):
        with self.busy(srv.ip, "raid1"):
            self.log(f"[{self._label(srv)}] RAID 1 구성 중…", "run")
            username = self.cfg.get("username", "super")
            # rstcli64 를 Invoke-Command 세션에서 직접 실행하면 실패하는 경우가 있어, devmgmt
            # 캡처와 같은 방식으로 Interactive 예약작업(실제 로그인 세션)을 통해 실행한다.
            script = rf"""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"& 'C:\DriverTemp\rstcli64.exe' --disableVersionCheck --create --level 1 --create-from-existing 0-2-1-0 --name volume_0000 0-2-2-0 | Out-File 'C:\DriverTemp\raid_create_result.txt' -Encoding UTF8`""
$principal = New-ScheduledTaskPrincipal -UserId "{username}" -LogonType Interactive -RunLevel Highest
$task = New-ScheduledTask -Action $action -Principal $principal
Register-ScheduledTask -TaskName "RunRaidCreate" -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName "RunRaidCreate"
Start-Sleep -Seconds 5
Unregister-ScheduledTask -TaskName "RunRaidCreate" -Confirm:$false
Start-Sleep -Seconds 2
Get-Content "C:\DriverTemp\raid_create_result.txt" -ErrorAction SilentlyContinue
Remove-Item "C:\DriverTemp\raid_create_result.txt" -Force -ErrorAction SilentlyContinue
echo "RAID Create via Interactive Task Done."
"""
            code, out, err = self.client.run_remote(srv.ip, script, timeout=60)
            if "RAID Create via Interactive Task Done" in out:
                self.log(f"[{self._label(srv)}] RAID 1 구성 완료: {out.strip()}", "ok")
            else:
                self.log(f"[{self._label(srv)}] RAID 1 구성 실패: {(err or out)[:200]}", "err")

    _STOP_WINRM_LABELS = {
        "ServiceStatus": "서비스", "ServiceStartType": "시작유형", "TrustedHosts": "TrustedHosts",
        "TokenFilterPolicy": "토큰필터정책", "FirewallCustom": "방화벽(전용규칙)",
        "FirewallGroup": "방화벽(내장그룹)", "Listener": "리스너",
    }

    def _do_stop_winrm(self, srv: Server):
        with self.busy(srv.ip, "stop_winrm"):
            self.log(f"[{self._label(srv)}] WinRM 및 관련 설정(레지스트리/방화벽/TrustedHosts/"
                     f"리스너) 원복 중…", "run")
            username = self.cfg.get("username", "super")
            code, out, err = self.client.stop_winrm(srv.ip, username)
            if "REVERT_SCHEDULED" in out:
                before_part = ""
                if "###BEFORE###" in out:
                    _, _, rest = out.partition("###BEFORE###")
                    before_part, _, diag_part = rest.partition("###DIAG###")
                    before_part = before_part.strip()
                    if diag_part:
                        print(f"[{self._label(srv)}] WinRM 종료 진단: {diag_part.strip()}")
                if before_part:
                    pretty = []
                    for kv in before_part.split("|"):
                        k, _, v = kv.strip().partition("=")
                        if k:
                            pretty.append(f"{self._STOP_WINRM_LABELS.get(k.strip(), k.strip())}={v.strip()}")
                    self.log(f"[{self._label(srv)}] 변경 전 상태: {', '.join(pretty)}", "dim")
                self.log(f"[{self._label(srv)}] 원복 예약 완료 — 10초 후 WinRM 서비스 실제로 꺼짐 "
                         f"(이후 원격 명령 불가). 서버 화면에 13초 후 전/후 비교 표가 자동으로 뜨니 "
                         f"서버실에서 화면만 확인하면 됨", "ok")
            else:
                self.log(f"[{self._label(srv)}] 원복/WinRM 종료 실패: {(err or out)[:80]}", "err")

    def _do_capture(self, srv: Server, kind: str):
        """캡처 공용 처리. devmgmt 는 트리 펼치기가 있는 capture_device_manager, current(현재화면)는
        여닫는 창 없이 그대로 찍는 capture_current_screen, 나머지는 capture_window 를 호출한다.

        장치관리자/내 PC 2종만 Windows 10/11 에서 동작 방식이 달라(Windows 11용으로 고친 뒤
        Windows 10에서는 오히려 원하는 대로 캡처가 안 되는 문제가 확인됨), 이 둘을 캡처하기
        직전에만 대상 서버의 OS 빌드번호를 조회해서 그 버전에 맞는 스크립트를 보낸다. 나머지
        4종(디스크관리/시스템정보/인증정보/현재화면)은 두 OS에서 이미 동일하게 잘 동작해서
        매번 조회할 필요 없다."""
        label = CAPTURE_KIND_LABELS[kind]
        with self.busy(srv.ip, f"capture_{kind}"):
            self.log(f"[{self._label(srv)}] {label} 캡처 중…", "run")
            username = self.cfg.get("username", "super")
            if kind in ("devmgmt", "mypc"):
                build = self.client.get_os_build(srv.ip)
                is_win11 = bool(build and build >= 22000)
                self.log(f"[{self._label(srv)}] OS 빌드 {build or '확인불가(Windows 11로 간주)'} → "
                         f"{'Windows 11' if is_win11 else 'Windows 10'} 방식으로 캡처", "dim")
            if kind == "devmgmt":
                _, out, err = self.client.capture_device_manager(srv.ip, username, is_win11)
            elif kind == "current":
                _, out, err = self.client.capture_current_screen(srv.ip, username)
            elif kind == "mypc":
                _, out, err = self.client.capture_window(srv.ip, username, kind, is_win11)
            else:
                _, out, err = self.client.capture_window(srv.ip, username, kind)
            # ###DIAG### 블록(예약작업 실행 여부/결과코드, 원격 세션 목록, 창 열기 로그)은 사용자
            # 화면(작업 로그 패널)에는 노출하지 않고 server.log 에만 남긴다 — 사용자는 성공/실패만
            # 보면 되고, 필요시 문제 조사할 때만 server.log 를 열어 상세 내용을 확인한다.
            status_part = out or ""
            if "###DIAG###" in status_part:
                status_part, _, diag = status_part.partition("###DIAG###")
                print(f"[{self._label(srv)}] {label} {diag.strip()}")
            if "CAPTURE_OK" not in status_part:
                self.log(f"[{self._label(srv)}] {label} 캡처 실패: {(status_part or err or '')[:200]}", "err")
                return

            # 캡처 파일은 capture/<매출번호>/<컴퓨터명>_<종류>.png 로 정리해서 저장한다.
            # 여기서 "컴퓨터명"은 srv.serial(우리가 매긴 목표 라벨 — "이름변경" 버튼을 누르는
            # 순간 실제 원격 이름변경+재부팅이 끝나기도 전에 이미 이 값으로 바뀜)이 아니라,
            # 캡처하는 이 순간 실제 Windows가 응답하는 살아있는 컴퓨터명이어야 한다. 캐시된
            # cur_name(마지막으로 연결확인/이름확인을 눌렀을 때 값)을 그대로 믿으면, 이름변경을
            # 누른 뒤 아직 재부팅/재확인을 안 한 상태에서 캡처하면 "바뀔 예정인 이름"으로 파일이
            # 저장되는 문제가 있었다 — 그래서 캡처 시점에 매번 실제 컴퓨터명을 새로 조회한다
            # ($env:COMPUTERNAME 하나만 물어보는 아주 가벼운 호출이라 왕복 비용은 무시할 만하다).
            _, live_name_out, _ = self.client.get_computer_name(srv.ip)
            live_name_out = (live_name_out or "").strip()
            if live_name_out:
                self.set_status(srv.ip, cur_name=live_name_out)
            live_name = live_name_out \
                or (self.status.get(srv.ip, {}).get("cur_name") or "").strip() \
                or srv.serial or srv.ip
            dest_dir = CAPTURE_DIR / sales_no(live_name)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dst = dest_dir / f"{live_name}_{label}.png"
            work_dir = self.client.devmgmt_work_dir(username)
            remote_filename = "devmgmt_capture.png" if kind == "devmgmt" else f"capture_{kind}.png"
            # 배치 캡처는 서버마다 별도 스레드로 동시 실행되는데, copy_from_remote 가 원격
            # 파일명을 그대로 써서 내려받기 때문에, 모든 서버가 같은 로컬 파일명을 공유하면
            # 서로 덮어쓰는 경쟁 상태가 생긴다 — 서버+종류별 고유 임시 폴더에 받은 뒤 최종
            # 이름으로 옮겨서 경쟁을 원천 차단한다.
            tmp_dir = CAPTURE_DIR / f"_tmp_{srv.serial}_{kind}"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            try:
                _, co, ce = self.client.copy_from_remote(
                    srv.ip, f"{work_dir}\\{remote_filename}", str(tmp_dir))
                if "COPY_OK" not in (co or ""):
                    self.log(f"[{self._label(srv)}] 이미지 수거 실패: {(ce or '')[:80]}", "err")
                    return

                src = tmp_dir / remote_filename
                if src.exists():
                    if dst.exists():
                        dst.unlink()
                    src.rename(dst)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

            wd_esc = work_dir.replace("'", "''")
            self.client.run_remote(
                srv.ip,
                f"Remove-Item -Path '{wd_esc}' -Recurse -Force -EA SilentlyContinue; 'CLEANUP_OK'",
                timeout=30)

            data_url = None
            try:
                b64 = base64.b64encode(dst.read_bytes()).decode("ascii")
                data_url = f"data:image/png;base64,{b64}"
            except Exception:
                pass

            # _captures(밑줄 접두어)에는 data_url 포함 전체를 메모리에만 유지(재시작시 소실돼도
            # 다시 캡처하면 채워짐 — _devices/_volumes 와 동일한 관례), captures 는 경로만 담아
            # 재시작 후에도 "몇 개 캡처됐는지" 표시용으로 영속화한다.
            capmap = self.status.setdefault(srv.ip, {})
            priv = capmap.setdefault("_captures", {})
            priv[kind] = {"path": str(dst), "data_url": data_url}
            pub = dict(capmap.get("captures") or {})
            pub[kind] = str(dst)
            self.set_status(srv.ip, captures=pub)
            self.log(f"[{self._label(srv)}] {label} 캡처 완료 → {dst}", "ok")
            self._push("capture", {"ip": srv.ip, "serial": srv.serial, "kind": kind,
                                    "path": str(dst), "data_url": data_url})

    # ── QC 스크립트 실행 (Python 폴링 → 실시간 진행률) ────────────
    def _start_qc_task(self, ip, remote_qc_path, username, task_name):
        rp = remote_qc_path.replace("'", "\\'")
        u = username.replace("'", "\\'")
        script = f"""
$taskName = '{task_name}'
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -EA SilentlyContinue
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "{rp}\\5-hardwareQC.ps1"' `
    -WorkingDirectory '{rp}'
$principal = New-ScheduledTaskPrincipal -UserId '{u}' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $taskName `
    -InputObject (New-ScheduledTask -Action $action -Principal $principal) -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
"STARTED" """
        _, out, err = self.client.run_remote(ip, script, timeout=30)
        return "STARTED" in out

    def _cleanup_qc_task(self, ip, task_name):
        self.client.run_remote(
            ip,
            f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false -EA SilentlyContinue",
            timeout=15)

    def _do_qc(self, srv: Server):
        with self.busy(srv.ip, "qc"):
            self.log(f"[{self._label(srv)}] QC 스크립트 시작 (약 4분 소요)…", "run")
            self.set_status(srv.ip, qc="RUNNING")

            username = self.cfg.get("username", "super")
            rp_raw = self.cfg.get("remote_qc_path", "").strip()
            if not rp_raw or rp_raw.upper().startswith("C:\\TEMP"):
                rp_raw = f"C:\\Users\\{username}\\Desktop\\WindowsQC"
            remote_path = rp_raw
            local_out = Path(self.cfg.get(
                "local_output_dir", str(Path.home() / "Desktop" / "QC_Results")))
            local_out.mkdir(parents=True, exist_ok=True)

            # 공유 경로를 설정에 고정으로 저장해두지 않고, 서버별로 QC 실행할 때마다 이 노트북의
            # 현재 IP를 새로 알아내서 그때그때 만든다 — 와이파이라 IP가 바뀌어도 항상 최신 IP로
            # 접속하게 됨. 반드시 "이 서버(srv.ip)로 나갈 때 쓰는 IP"를 기준으로 계산한다 —
            # 노트북에 NIC가 여러 개 잡혀 있으면(인터넷용 와이파이 + QC 서버 전용 어댑터 등)
            # 그냥 "인터넷 나가는 IP"를 쓰면 정작 이 서버에서는 접근 불가능한 IP가 나올 수 있다.
            share_path = f"\\\\{_get_local_ip_for(srv.ip)}\\{QC_SHARE_NAME}"
            share_user = self.cfg.get("qc_share_user", "")
            share_pass = self.cfg.get("qc_share_pass", "")

            self.log(f"[{self._label(srv)}] 1/3 QC 도구 수신 중 ({share_path} → 서버 바탕화면)…")
            self.set_busy(srv.ip, "qc", True, progress=5)
            if share_user:
                _, out, err = self.client.pull_qc_from_share(
                    srv.ip, share_path, share_user, share_pass, remote_path)
                if "PULL_OK" not in out:
                    # out/err 둘 다 보여주고(둘 중 하나가 비어있는 경우가 흔함) 넉넉하게 잘라서
                    # 진짜 원인이 잘려서 안 보이는 일이 없게 한다 (예: "네트워크 이름을 찾을 수
                    # 없음" 같은 실제 net use 실패 사유가 100자 제한에 잘려서 안 보이던 버그).
                    detail = " / ".join(p for p in (out, err) if p)[:400]
                    self.log(f"[{self._label(srv)}] 공유폴더 수신 실패: {detail}", "err")
                    self.set_status(srv.ip, qc="FAIL")
                    return
            else:
                self.log(f"[{self._label(srv)}] 공유폴더 계정 미설정 — 노트북에서 직접 전송…", "warn")
                tool_dir = self.cfg.get("qc_tool_dir") or str(QC_TOOL_DIR)
                _, out, err = self.client.copy_to_remote(srv.ip, tool_dir, remote_path)
                if "COPY_ERR" in out or "COPY_OK" not in out:
                    detail = " / ".join(p for p in (out, err) if p)[:400]
                    self.log(f"[{self._label(srv)}] 파일 전송 실패: {detail}", "err")
                    self.set_status(srv.ip, qc="FAIL")
                    return

            self.log(f"[{self._label(srv)}] 2/3 QC 실행 중 (완료 자동감지, 최대 6분)…", "run")
            self.set_busy(srv.ip, "qc", True, progress=15)
            task_name = f"QCRun_{int(time.time())}"
            if not self._start_qc_task(srv.ip, remote_path, username, task_name):
                self.log(f"[{self._label(srv)}] QC 작업 시작 실패", "err")
                self.set_status(srv.ip, qc="FAIL")
                return

            # 원격 스크립트 내부 진행률은 알 수 없으므로(실제 신호 없음) 시간 추정으로 %를 만들지 않고
            # 완료 여부만 실제로 폴링해서 확인 — 대기 중엔 불확정(shimmer) 표시로 둔다.
            # find_qc_output 은 ZIP 파일 존재만을 완료 신호로 본다 (결과 폴더는 스크립트 시작
            # 직후부터 존재하므로 폴더 존재만으로는 절대 완료로 오판하면 안 됨).
            self.set_busy(srv.ip, "qc", True, progress=None)
            max_wait = 360
            deadline = time.time() + max_wait
            remote_result = ""
            while time.time() < deadline:
                time.sleep(5)
                _, out3, _ = self.client.find_qc_output(srv.ip, remote_path)
                out3 = (out3 or "").strip()
                if out3 and "NOT_FOUND" not in out3:
                    remote_result = out3
                    break

            if not remote_result:
                self.log(f"[{self._label(srv)}] QC 타임아웃 — 결과 수거 시도", "warn")
                _, out3, _ = self.client.find_qc_output(srv.ip, remote_path)
                remote_result = (out3 or "").strip()
                if "NOT_FOUND" in remote_result or not remote_result:
                    self.log(f"[{self._label(srv)}] 결과 없음 — QC 스크립트 미완료 가능성", "warn")
                    self.set_status(srv.ip, qc="FAIL")
                    # 스크립트가 아직 실행 중일 수 있으므로 원격 폴더는 건드리지 않는다.
                    self._cleanup_qc_task(srv.ip, task_name)
                    return

            # 예약작업 등록 정보 정리 (이미 완료됐으므로 등록만 해제 — 실행 자체엔 영향 없음)
            self._cleanup_qc_task(srv.ip, task_name)

            self.set_busy(srv.ip, "qc", True, progress=95)
            self.log(f"[{self._label(srv)}] 3/3 결과 수집 중…")

            if remote_result.endswith(".zip"):
                zip_path = remote_result
                folder_path = remote_result[:-4]
            else:
                folder_path = remote_result
                zip_path = remote_result + ".zip"

            local_dest = str(local_out)
            copied = False

            _, o1, e1 = self.client.copy_from_remote(srv.ip, folder_path, local_dest)
            if "COPY_OK" in o1:
                self.log(f"[{self._label(srv)}] 결과 폴더 복사 완료", "ok")
                copied = True
            else:
                self.log(f"[{self._label(srv)}] 폴더 복사 실패: {e1[:80]}", "warn")

            _, o2, e2 = self.client.copy_from_remote(srv.ip, zip_path, local_dest)
            if "COPY_OK" in o2:
                self.log(f"[{self._label(srv)}] ZIP 복사 완료 → {local_dest}", "ok")
                copied = True
            else:
                self.log(f"[{self._label(srv)}] ZIP 복사 실패: {e2[:80]}", "warn")

            if copied:
                self.log(f"[{self._label(srv)}] 원격 QC 폴더 삭제 중…")
                rp_esc = remote_path.replace("'", "''")
                self.client.run_remote(
                    srv.ip,
                    f"Remove-Item -Path '{rp_esc}' -Recurse -Force -EA SilentlyContinue; 'CLEANUP_OK'",
                    timeout=30)
                self.set_busy(srv.ip, "qc", True, progress=100)
                self.log(f"[{self._label(srv)}] QC 완료 → {local_dest}", "ok")
                self.set_status(srv.ip, qc="DONE")
            else:
                self.log(f"[{self._label(srv)}] 결과 복사 전부 실패", "err")
                self.set_status(srv.ip, qc="FAIL")


# ══════════════════════════════════════════════════════════════════
# HTTP 서버 (표준 라이브러리만 사용 — 정적 파일 + /api/* RPC + /events SSE)
# ══════════════════════════════════════════════════════════════════
backend = Backend()


# ── 이 노트북(=지금은 이 서버) 자신을 SMB 공유 호스트로 쓸 때 필요한 LAN IP 계산 ──
# 순수 소켓/라우팅 로직이라 원본 그대로(수정 없이) 가져옴. batch_qc의 SMB 경로에서만 쓰임 —
# copy_to_remote(zip+base64) 경로를 쓴다면 이 값은 안 쓰인다.
def _get_lan_ip():
    """실제 트래픽이 나가는 인터페이스의 사설 IP를 알아낸다 (패킷은 전송하지 않음)."""
    return _get_local_ip_for("8.8.8.8")


def _get_local_ip_for(target_ip):
    """이 PC에서 target_ip로 나갈 때 실제로 쓰이는 인터페이스의 IP를 알아낸다(패킷 전송 없음 —
    UDP는 connect() 해도 라우팅 테이블만 확인하고 실제로 보내지 않음). 노트북에 NIC가 여러 개
    잡혀 있으면(예: 와이파이로 인터넷 접속 + 별도 어댑터로 QC 서버 네트워크 접속) "인터넷으로
    나가는 IP"와 "그 서버로 나가는 IP"가 다를 수 있어서, 반드시 대상 서버 IP 기준으로 계산해야
    QC 공유 경로가 실제로 그 서버에서 접근 가능한 IP가 된다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
