from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
from typing import List, Dict, Any, Optional
import socket
import subprocess
import threading
import uuid
import time
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import shlex

# -------------------------------
# Config
# -------------------------------
# Author: taehyeon kim
# Date: 2025-08-13

# DB Information #
MYSQL_HOST = "192.168.0.182"
MYSQL_USER = "root"
MYSQL_PASSWORD = "father!2023"
MYSQL_DB = "host"
AUTO_DB = "AUTOMATIC_OS_INSTALL"

# PATH Information #
IP_LIST_PATH = "/pxe_mac_sn/KTH/REDFISH/ip_list.txt"
HEALTH_LOG_DIR = "/pxe_mac_sn/KTH/REDFISH/health_check/log"
QUERY_SCRIPT = "/pxe_mac_sn/KTH/REDFISH/query.sh"
OS_SCRIPT_DIR = "/pxe_mac_sn/KTH/REDFISH/os"
OS_SCRIPT = "/pxe_mac_sn/KTH/REDFISH/os/check_os_options.sh"
REGISTER_DIR = "/pxe_mac_sn/KTH/ansible/dashboard"
REGISTER_SCRIPT = "/pxe_mac_sn/KTH/ansible/dashboard/dashboard_register.sh"
HEALTH_SCAN_INTERVAL_SEC = 60
BMC_RESET_WAIT_SECS = 183

# Extra task scripts (sidebar)
LOGO_DIR = "/pxe_mac_sn/KTH/REDFISH/logo"
LOGO_SCRIPT = "/pxe_mac_sn/KTH/REDFISH/logo/changelogo.sh"
ONLINE_DIR = "/pxe_mac_sn/KTH/ansible/1_ONLINE_CHECK"
ONLINE_SCRIPT = "/pxe_mac_sn/KTH/ansible/1_ONLINE_CHECK/1.sh"
LABEL_DIR = "/pxe_mac_sn/KTH/Label"
LABEL_SERIAL_TEMP = "serial_temp.txt"
LABEL_RESULT_FILE = "label.txt"
LABEL_ANSIBLE_SCRIPT = "/pxe_mac_sn/KTH/Label/ansible.sh"
ANSIBLE_INVENTORY = "/pxe_mac_sn/KTH/ansible/inventory.ini"
PLAY_FWCHECK = "/pxe_mac_sn/KTH/ansible/2_KAKAO_SCRIPT/yml/dashboard_fwcheck.yml"
PLAY_FRU = "/pxe_mac_sn/KTH/ansible/2_KAKAO_SCRIPT/yml/dashboard_fru.yml"
PLAY_IPMI = "/pxe_mac_sn/KTH/ansible/2_KAKAO_SCRIPT/yml/ipmi.yml"
PLAY_SETBIOS = "/pxe_mac_sn/KTH/ansible/2_KAKAO_SCRIPT/yml/dashboard_setbios.yml"
PLAY_SIMPLECHECK = "/pxe_mac_sn/KTH/ansible/3_SIMPLE_CHECK/yml/dashboard_simplecheck.yml"
PLAY_PING = "/pxe_mac_sn/KTH/ansible/4_PING/yml/dashboard_ping.yml"
PLAY_RECORD_SPEC = "/pxe_mac_sn/KTH/ansible/5_RECORD_SPEC/yml/dashboard_record_spec.yml"
DELETE_OS_LOG_DIR = "/pxe_mac_sn/KTH/ansible/6_DELETE_OS_LOG"
DELETE_OS_SCRIPT = "/pxe_mac_sn/KTH/ansible/6_DELETE_OS_LOG/delete_os.sh"
CLEARSEL_DIR = "/pxe_mac_sn/KTH/REDFISH/sellog"
CLEARSEL_SCRIPT = "/pxe_mac_sn/KTH/REDFISH/sellog/clearsel.sh"
SERVER_TYPE_DIR = "/pxe_mac_sn/KTH/REDFISH/server_type"
SERVER_TYPE_SCRIPT = "/pxe_mac_sn/KTH/REDFISH/server_type/server_type_check.sh"
SERVER_INFO_FILE = "/pxe_mac_sn/KTH/REDFISH/server_type/server_info.txt"


def get_mysql_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_mysql_connection_autoinstall():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=AUTO_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def is_ipv4(value: str) -> bool:
    try:
        parts = value.split('.')
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit():
                return False
            n = int(p)
            if n < 0 or n > 255:
                return False
        return True
    except Exception:
        return False


def read_ip_list(path: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for idx, raw in enumerate(f):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 1:
                    continue
                bmcip = parts[0]
                osip = ""
                serial = ""
                if len(parts) >= 3:
                    # Standard format: bmcip osip serial
                    osip = parts[1] if is_ipv4(parts[1]) else ""
                    serial = parts[2]
                elif len(parts) == 2:
                    # The second token may be an OS IP or a serial number
                    token = parts[1]
                    if is_ipv4(token):
                        osip = token
                    else:
                        serial = token
                entries.append({
                    "order": idx,
                    "bmcip": bmcip,
                    "osip": osip,
                    "serial": serial,
                })
    except FileNotFoundError:
        # Return empty list if not present; frontend should handle gracefully
        return []
    return entries


def fetch_hardware_by_serial(conn, serial: str) -> Dict[str, Any]:
    sql = (
        "SELECT platform, manufact, model, bios_fw, bmc_fw, mbcpld, cpu, ram, "
        "raid, disk, nic, netmask, gw FROM hardware_inventory WHERE serial = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (serial,))
        row = cur.fetchone()
        return row or {}


class ServerRow(BaseModel):
    order: int = 0
    power: str = "off"
    osip: str = ""
    task: str = "N / A"
    status: str = "N / A"
    platform: str = ""
    serial: str = ""
    manufact: str = ""
    model: str = ""
    bios: str = ""
    bmc: str = ""
    mbcpld: str = ""
    cpu: str = ""
    ram: str = ""
    raid: str = ""
    disk: str = ""
    nic: str = ""
    bmcip: str = ""
    netmask: str = ""
    gw: str = ""
    health: str = ""
    uid: str = ""


class ServerRowsResponse(BaseModel):
    rows: List[ServerRow]


app = FastAPI(title="QC Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health scanner thread will be started after the function is defined below

# -------------------------------
# Background task store
# -------------------------------
TASKS: Dict[str, Dict[str, Any]] = {}
# In-memory UI status overrides keyed by serial
STATUS_OVERRIDES: Dict[str, Dict[str, Any]] = {}

# Health alarm memory to avoid UI flicker
ALARM_STATE: Dict[str, Any] = {
    "present": set(),   # set of bmcip that currently have log files
    "details": {},      # bmcip -> {filename, mtime, content}
    "last_scan": 0.0,   # epoch seconds of last successful scan
}

# Upload Logo workflow memory (stage-based progress)
UPLOAD_LOGO_STATE: Dict[str, Any] = {
    "job_id": None,
    "running": False,
    "started_at": 0.0,
    "updated_at": 0.0,
    "bmc_reset_started_at": 0.0,
    "stages": {
        "Upload Logo Start": False,
        "Upload Logo Complete": False,
        "BMC Reset": False,
        "BMC Reset Complete": False,
    },
    "counts": {
        "Upload Logo Start": 0,
        "Upload Logo Complete": 0,
        "BMC Reset": 0,
        "BMC Reset Complete": 0,
        "total": 0,
    },
}

def _scan_health_logs(limit_bytes: int = 4000) -> None:
    import os
    present: set[str] = set()
    details: Dict[str, Any] = {}
    if os.path.isdir(HEALTH_LOG_DIR):
        try:
            for name in os.listdir(HEALTH_LOG_DIR):
                if name in (".", ".."): continue
                file_path = os.path.join(HEALTH_LOG_DIR, name)
                if not os.path.isfile(file_path):
                    continue
                bmcip = os.path.splitext(name)[0]
                present.add(bmcip)
                try:
                    size = os.path.getsize(file_path)
                    with open(file_path, "rb") as f:
                        if size > limit_bytes:
                            f.seek(size - limit_bytes)
                        data = f.read().decode("utf-8", errors="ignore")
                    details[bmcip] = {
                        "filename": name,
                        "mtime": os.path.getmtime(file_path),
                        "content": data,
                    }
                except Exception:
                    details[bmcip] = {"filename": name, "error": "read_failed"}
        except Exception:
            pass
    ALARM_STATE["present"] = present
    ALARM_STATE["details"] = details
    ALARM_STATE["last_scan"] = time.time()


def _start_health_scanner_once() -> None:
    if ALARM_STATE.get("_scanner_started"):
        return
    ALARM_STATE["_scanner_started"] = True

    def _loop():
        while True:
            try:
                _scan_health_logs()
            except Exception:
                pass
            time.sleep(HEALTH_SCAN_INTERVAL_SEC)
    try:
        _scan_health_logs()
    except Exception:
        pass
    threading.Thread(target=_loop, daemon=True).start()

def _run_script_task(task_id: str, cmd: List[str]):
    env = os.environ.copy()
    # PATH expansion (ensure nmap, ipmitool, etc. are in PATH)
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd="/pxe_mac_sn/KTH/REDFISH",
        env=env,
    )
    TASKS[task_id] = {
        "id": task_id,
        "start": time.time(),
        "running": True,
        "returncode": None,
        "lines": [],
    }
    assert proc.stdout is not None
    for line in proc.stdout:
        TASKS[task_id]["lines"].append(line.rstrip())
    proc.wait()
    TASKS[task_id]["running"] = False
    TASKS[task_id]["returncode"] = proc.returncode


def _run_script_task_with_cwd(task_id: str, cmd: List[str], cwd: str):
    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
    )
    TASKS[task_id] = {
        "id": task_id,
        "start": time.time(),
        "running": True,
        "returncode": None,
        "lines": [],
    }
    assert proc.stdout is not None
    for line in proc.stdout:
        TASKS[task_id]["lines"].append(line.rstrip())
    proc.wait()
    TASKS[task_id]["running"] = False
    TASKS[task_id]["returncode"] = proc.returncode


@app.get("/servers", response_model=ServerRowsResponse)
def get_servers():
    ip_entries = read_ip_list(IP_LIST_PATH)
    if not ip_entries:
        return {"rows": []}

    try:
        conn = get_mysql_connection()
    except Exception:
        conn = None

    rows: List[ServerRow] = []
    try:
        for entry in ip_entries:
            hw: Dict[str, Any] = {}
            if conn is not None:
                try:
                    hw = fetch_hardware_by_serial(conn, entry["serial"]) or {}
                except Exception:
                    hw = {}
            try:
                power_state = probe_power_status(entry["bmcip"])  # "on" | "off" | None
            except Exception:
                power_state = None

            row = ServerRow(
                order=entry.get("order", 0),
                power=(power_state or "checking"),
                osip=str(entry.get("osip", "")),
                task="N / A",
                status="N / A",
                platform=str(hw.get("platform", "") or ""),
                serial=str(entry.get("serial", "")),
                manufact=str(hw.get("manufact", "") or ""),
                model=str(hw.get("model", "") or ""),
                bios=str(hw.get("bios_fw", "") or ""),
                bmc=str(hw.get("bmc_fw", "") or ""),
                mbcpld=str(hw.get("mbcpld", "") or ""),
                cpu=str(hw.get("cpu", "") or ""),
                ram=str(hw.get("ram", "") or ""),
                raid=str(hw.get("raid", "") or ""),
                disk=str(hw.get("disk", "") or ""),
                nic=str(hw.get("nic", "") or ""),
                bmcip=str(entry.get("bmcip", "")),
                netmask=str(hw.get("netmask", "") or ""),
                gw=str(hw.get("gw", "") or ""),
                health="",
                uid="",
            )
            rows.append(row)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return {"rows": rows}


@app.get("/health")
def healthcheck():
    return {"ok": True}


# -------------------------------
# Helpers: power probe
# -------------------------------
def udp_port_open(host: str, port: int = 623, timeout: float = 1.0) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(b"\x00", (host, port))
        sock.close()
        return True
    except Exception:
        return False


def run_ipmitool_power_status(host: str, user: str, password: str, timeout: int = 3) -> str | None:
    cmd = [
        "ipmitool", "-I", "lanplus",
        "-H", host,
        "-U", user,
        "-P", password,
        "power", "status",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        text = (out.stdout or "") + (out.stderr or "")
        text_low = text.lower()
        if "chassis power is on" in text_low or "power is on" in text_low:
            return "on"
        if "chassis power is off" in text_low or "power is off" in text_low:
            return "off"
        return None
    except Exception:
        return None


def probe_power_status(host: str) -> str | None:
    _ = udp_port_open(host)

    # Try 1: admin / admin
    r1 = run_ipmitool_power_status(host, "admin", "admin")
    if r1 in ("on", "off"):
        return r1

    # Try 2: ipmi / dkadmin1! (for kakao bmc account) 
    r2 = run_ipmitool_power_status(host, "ipmi", "dkadmin1!")
    if r2 in ("on", "off"):
        return r2

    return None


# -------------------------------
# Health logs & UID status endpoints
# -------------------------------
@app.get("/health/logs")
@app.get("/health/logs/")
def get_health_logs() -> Dict[str, bool]:
    _start_health_scanner_once()
    present = ALARM_STATE.get("present", set())
    if not present and time.time() - float(ALARM_STATE.get("last_scan", 0)) > HEALTH_SCAN_INTERVAL_SEC:
        try:
            _scan_health_logs()
            present = ALARM_STATE.get("present", set())
        except Exception:
            present = set()
    return {bmcip: True for bmcip in present}


@app.get("/health/logs/detail")
@app.get("/api/health/logs/detail")
def get_health_log_details(limit_bytes: int = 4000) -> Dict[str, Any]:
    _start_health_scanner_once()
    details = ALARM_STATE.get("details", {})
    if not details and time.time() - float(ALARM_STATE.get("last_scan", 0)) > HEALTH_SCAN_INTERVAL_SEC:
        try:
            _scan_health_logs(limit_bytes=limit_bytes)
            details = ALARM_STATE.get("details", {})
        except Exception:
            details = {}
    return details

def run_ipmitool_uid_raw(host: str, user: str, password: str, timeout: int = 3) -> str | None:
    cmd = [
        "ipmitool", "-I", "lanplus",
        "-H", host,
        "-U", user,
        "-P", password,
        "raw", "0x3c", "0x35", "0x00",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        text = (out.stdout or "") + (out.stderr or "")
        low = text.lower()
        if "ff" in low:
            return "ON"
        if "00" in low:
            return "OFF"
        return None
    except Exception:
        return None


@app.get("/uid/status")
@app.get("/uid/status/")
def get_uid_status() -> Dict[str, str]:
    """Return mapping of bmcip -> ON/OFF/ERROR for UID LED."""
    entries = read_ip_list(IP_LIST_PATH)
    statuses: Dict[str, str] = {}
    for e in entries:
        host = e["bmcip"]
        s = run_ipmitool_uid_raw(host, "admin", "admin")
        if s is None:
            s = run_ipmitool_uid_raw(host, "ipmi", "dkadmin1!")
        if s is None:
            s = "ERROR"
        statuses[host] = s
    return statuses

@app.get("/api/servers", response_model=ServerRowsResponse)
def get_servers_api_alias():
    return get_servers()

@app.get("/api/health/logs")
@app.get("/api/health/logs/")
def get_health_logs_api_alias():
    return get_health_logs()

@app.get("/api/uid/status")
@app.get("/api/uid/status/")
def get_uid_status_api_alias():
    return get_uid_status()


# -------------------------------
# Query script endpoints
# -------------------------------
@app.post("/query/start")
@app.post("/api/query/start")
def start_query() -> Dict[str, str]:
    """Start query.sh in background and return task id."""
    task_id = uuid.uuid4().hex[:12]
    cmd = ["/bin/bash", QUERY_SCRIPT]
    t = threading.Thread(target=_run_script_task, args=(task_id, cmd), daemon=True)
    t.start()
    return {"task_id": task_id}


@app.get("/query/status/{task_id}")
@app.get("/api/query/status/{task_id}")
def query_status(task_id: str) -> Dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return {"error": "task_not_found"}
    lines = task["lines"][-500:]
    running = task["running"]
    rc = task["returncode"]

    stage = "Initializing..."
    progress = 5

    addrs_count = 0
    iplist_count = 0
    iplist_triple = 0
    try:
        with open(os.path.join("/pxe_mac_sn/KTH/REDFISH", "addrs.txt"), "r", encoding="utf-8", errors="ignore") as f:
            addrs = [ln.strip() for ln in f if ln.strip()]
            addrs_count = len(addrs)
    except Exception:
        pass
    try:
        with open(os.path.join("/pxe_mac_sn/KTH/REDFISH", "ip_list.txt"), "r", encoding="utf-8", errors="ignore") as f:
            rows = [ln.strip() for ln in f if ln.strip()]
            iplist_count = len(rows)
            for r in rows:
                parts = r.split()
                if len(parts) >= 3:
                    iplist_triple += 1
    except Exception:
        pass

    if any("Looking for IPMI devices on network" in ln for ln in lines):
        stage = "Scanning IPMI devices..."; progress = 15
    if any("Cleaning up" in ln for ln in lines):
        stage = "Cleaning up targets..."; progress = 25
    if any("FINISHED SCANNING" in ln for ln in lines):
        stage = f"Scan complete (targets {addrs_count})"; progress = 30
        if running:
            stage = "Checking power and generating ip_list.txt..."; progress = 50
            if iplist_triple > 0:
                stage = "Running Redfish registration (set_host.sh)..."; progress = 65
    if not running:
        if rc == 0:
            stage = f"Query completed  {iplist_count} Servers Registered"; progress = 100
        else:
            stage = "Query failed"; progress = 100

    return {
        "id": task["id"],
        "running": running,
        "returncode": rc,
        "lines": lines[-200:],
        "elapsed": round(time.time() - task["start"], 1),
        "progress": progress,
        "stage": stage,
    }


# -------------------------------
# Register script endpoints (dashboard_register.sh)
# -------------------------------
@app.post("/register/start")
@app.post("/api/register/start")
def start_register() -> Dict[str, str]:
    """Start dashboard_register.sh in background and return task id."""
    task_id = uuid.uuid4().hex[:12]
    cmd = ["/bin/bash", REGISTER_SCRIPT]
    t = threading.Thread(target=_run_script_task_with_cwd, args=(task_id, cmd, REGISTER_DIR), daemon=True)
    t.start()
    return {"task_id": task_id}


@app.get("/register/status/{task_id}")
@app.get("/api/register/status/{task_id}")
def register_status(task_id: str) -> Dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return {"error": "task_not_found"}
    lines = task["lines"][-500:]
    running = task["running"]
    rc = task["returncode"]

    stage = "Initializing..."
    progress = 5

    text_all = "\n".join(lines)
    text_lower = text_all.lower()

    if "register" in text_lower or "dashboard_register" in text_lower:
        stage = "Preparing registration..."; progress = max(progress, 15)

    play_lines = [ln for ln in lines if "PLAY [" in ln]
    play_count = len(play_lines)
    task_lines = [ln for ln in lines if "TASK [" in ln]
    task_count = len(task_lines)
    recap_seen = any("PLAY RECAP" in ln for ln in lines)

    if play_count > 0 and task_count == 0:
        stage = "Starting Ansible playbooks..."; progress = max(progress, 30)

    last_task_name = None
    if task_count > 0:
        for ln in reversed(task_lines):
            m = re.search(r"TASK \[(.*?)\]", ln)
            if m:
                last_task_name = m.group(1)
                break
        stage = f"Running task: {last_task_name}" if last_task_name else "Running tasks..."
        progress = max(progress, min(85, 30 + task_count * 3))

    if recap_seen:
        stage = "Finalizing (Play recap)..."; progress = max(progress, 95)

    
    failed_total = 0
    unreachable_total = 0
    for ln in lines:
        if "failed=" in ln:
            try:
                failed_total += int(re.search(r"failed=(\d+)", ln).group(1))
            except Exception:
                pass
        if "unreachable=" in ln:
            try:
                unreachable_total += int(re.search(r"unreachable=(\d+)", ln).group(1))
            except Exception:
                pass
    if failed_total > 0 or unreachable_total > 0:
        stage = "Errors detected during play..."; progress = max(progress, 90)

    
    if not running:
        if rc == 0:
            stage = "Registration completed"; progress = 100
        else:
            stage = "Registration failed"; progress = 100

    return {
        "id": task["id"],
        "running": running,
        "returncode": rc,
        "lines": lines[-200:],
        "elapsed": round(time.time() - task["start"], 1),
        "progress": progress,
        "stage": stage,
    }


# -------------------------------
# OS option apply endpoint
# -------------------------------
@app.post("/os/apply")
@app.post("/api/os/apply")
def os_apply(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    
    os_type = None
    if payload and isinstance(payload, dict):
        os_type = payload.get("osType") or payload.get("os_type")
    
    try:
        from fastapi import Request
        
    except Exception:
        pass
    if not os_type:
        
        pass
    if not os_type:
        return {"ok": False, "error": "missing_osType"}
    os_type = str(os_type).upper().strip()
    allowed = {"NVME", "SSD", "CORE", "4K", "DEL"}
    if os_type not in allowed:
        return {"ok": False, "error": "invalid_osType", "allowed": sorted(list(allowed))}

    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
    try:
        out = subprocess.run([
            "/bin/bash", OS_SCRIPT, os_type
        ], cwd=OS_SCRIPT_DIR, env=env, capture_output=True, text=True, timeout=300)
        stdout = (out.stdout or "")
        stderr = (out.stderr or "")
        return {
            "ok": out.returncode == 0,
            "returncode": out.returncode,
            "osType": os_type,
            "stdout": stdout[-4000:],
            "stderr": stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "osType": os_type}


# -------------------------------
# Task/Status (boot workflow) endpoint
# -------------------------------
def _map_db_status_to_task_status(db_status: Optional[str], firmware_update: Optional[str]) -> Dict[str, str]:
    
    s = (db_status or "").strip()
    if not s:
        return {"task": "N / A", "status": "N / A"}
    return {"task": s, "status": "N / A"}


@app.get("/status/boot")
@app.get("/api/status/boot")
def get_boot_status() -> Dict[str, Any]:
    entries: List[Dict[str, str]] = read_ip_list(IP_LIST_PATH)

    items: List[Dict[str, Any]] = []
    for ent in entries:
        s = str(ent.get("serial", "") or "")
        b = str(ent.get("bmcip", "") or "")
        if s and s in STATUS_OVERRIDES:
            ov = STATUS_OVERRIDES[s]
            items.append({
                "serial": s,
                "bmcip": b,
                "task": ov.get("task", "N / A"),
                "status": ov.get("ui_status", "N / A"),
            })
        else:
            items.append({
                "serial": s,
                "bmcip": b,
                "task": "N / A",
                "status": "N / A",
            })

    return {"items": items}


@app.post("/status/boot/update")
@app.post("/api/status/boot/update")
def update_boot_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    mac = payload.get("mac") or payload.get("mac_address")
    serial = payload.get("serial")
    bmcip = payload.get("bmcip") or payload.get("bmc_ip") or payload.get("bmc")
    task = payload.get("task")  
    status = payload.get("status")
    ui_status = payload.get("ui_status") or payload.get("uiStatus") 
    fw = payload.get("firmware_update")
    persist = bool(payload.get("persist", False))

    if not mac and serial:
        
        try:
            with open("/pxe_mac_sn/KTH/REDFISH/mac_list.txt", "r", encoding="utf-8") as f:
                for raw in f:
                    parts = raw.strip().split()
                    if len(parts) >= 2 and parts[0] == str(serial):
                        mac = parts[1]
                        break
        except Exception:
            pass
    if serial is None and bmcip:
        
        try:
            with open("/pxe_mac_sn/KTH/REDFISH/ip_list.txt", "r", encoding="utf-8") as f:
                for raw in f:
                    parts = raw.strip().split()
                    if len(parts) >= 3 and parts[0] == str(bmcip):
                        serial = parts[2]
                        break
        except Exception:
            pass
    if not mac:
        return {"ok": False, "error": "missing_mac_or_serial"}

    
    if serial is None:
        
        try:
            with open("/pxe_mac_sn/KTH/REDFISH/mac_list.txt", "r", encoding="utf-8") as f:
                for raw in f:
                    parts = raw.strip().split()
                    if len(parts) >= 2 and parts[1].upper() == str(mac).upper():
                        serial = parts[0]
                        break
        except Exception:
            pass
    if serial is not None and (ui_status is not None or task is not None):
        STATUS_OVERRIDES[str(serial)] = {
            "task": task if task is not None else STATUS_OVERRIDES.get(str(serial), {}).get("task", "N / A"),
            "ui_status": ui_status if ui_status is not None else STATUS_OVERRIDES.get(str(serial), {}).get("ui_status", "N / A"),
            "updated_at": time.time(),
        }

    
    if persist and (status is not None or fw is not None):
        try:
            conn = get_mysql_connection_autoinstall()
            cols = ["mac_address"]
            vals = [mac]
            updates = []
            if status is not None:
                cols.append("status")
                vals.append(status)
                updates.append("status=VALUES(status)")
            if fw is not None:
                cols.append("firmware_update")
                vals.append(fw)
                updates.append("firmware_update=VALUES(firmware_update)")
            placeholders = ",".join(["%s"] * len(vals))
            colnames = ",".join(cols)
            upd = ",".join(updates) if updates else "status=status"
            sql = f"INSERT INTO server_boot_options ({colnames}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {upd}"
            with conn.cursor() as cur:
                cur.execute(sql, vals)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return {"ok": True}


@app.post("/status/boot/clear")
@app.post("/api/status/boot/clear")
def clear_boot_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    serial = payload.get("serial")
    if not serial:
        return {"ok": False, "error": "missing_serial"}
    STATUS_OVERRIDES.pop(str(serial), None)
    return {"ok": True}


# -------------------------------
# Bulk actions for selected BMC IPs (Power/UID via Redfish)
# -------------------------------
def _redfish_get_token(host: str, timeout: int = 6) -> Optional[str]:
    
    creds = [("admin", "admin"), ("ipmi", "dkadmin1!")]
    for user, pw in creds:
        try:
            out = subprocess.run(
                [
                    "curl", "-k", "-sS", "-X", "POST", f"https://{host}/redfish/v1/SessionService/Sessions",
                    "-d", json.dumps({"UserName": user, "Password": pw}),
                    "-H", "Content-Type: application/json",
                ],
                capture_output=True, text=True, timeout=timeout
            )
            txt = (out.stdout or out.stderr or '').strip()
            data = json.loads(txt or '{}')
            token = (
                data.get("Oem", {})
                    .get("Public", {})
                    .get("X-Auth-Token")
            )
            if token and token != "null":
                return token
        except Exception:
            continue
    return None


def _redfish_post(host: str, token: str, path: str, payload: Dict[str, Any], timeout: int = 6) -> Dict[str, Any]:
    try:
        out = subprocess.run(
            [
                "curl", "-k", "-sS", "-X", "POST", f"https://{host}{path}",
                "-d", json.dumps(payload),
                "-H", f"X-Auth-Token:{token}",
                "-H", "Content-Type: application/json",
            ],
            capture_output=True, text=True, timeout=timeout
        )
        txt = (out.stdout or out.stderr or '').strip()
        try:
            return json.loads(txt) if txt else {"ok": True}
        except Exception:
            return {"raw": txt, "returncode": out.returncode}
    except Exception as e:
        return {"error": str(e)}


@app.post("/actions/power")
@app.post("/api/actions/power")
def actions_power(payload: Dict[str, Any]) -> Dict[str, Any]:
    
    bmcips = payload.get("bmcip") or payload.get("bmcips") or []
    action = (payload.get("action") or "").lower().strip()
    if not isinstance(bmcips, list) or not bmcips:
        return {"ok": False, "error": "missing_bmcip_list"}
    action_map = {
        "on": {"ResetType": "On"},
        "off": {"ResetType": "ForceOff"},
        "reset": {"ResetType": "ForceRestart"},
        "cycle": {"ResetType": "PowerCycle"},
    }
    if action not in action_map:
        return {"ok": False, "error": "invalid_action", "allowed": list(action_map)}

    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(bmcips))) as ex:
        futures = {}
        for ip in bmcips:
            def task(host: str):
                token = _redfish_get_token(host)
                if not token:
                    return {"ok": False, "error": "auth_failed"}
                r = _redfish_post(host, token, "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", action_map[action])
                return {"ok": True, "response": r}
            futures[ex.submit(task, ip)] = ip
        for fut in as_completed(futures):
            host = futures[fut]
            try:
                results[host] = fut.result()
            except Exception as e:
                results[host] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results, "count": len(results)}


def _redfish_get_etag(host: str, token: str, timeout: int = 6) -> Optional[str]:
    try:
        out = subprocess.run(
            [
                "curl", "-i", "-k", "-sS", f"https://{host}/redfish/v1/Chassis/1",
                "-H", f"X-Auth-Token: {token}",
            ],
            capture_output=True, text=True, timeout=timeout
        )
        hdr = (out.stdout or out.stderr or '').splitlines()
        for ln in hdr:
            if ln.lower().startswith('etag:'):
                val = ln.split(':',1)[1].strip().strip('"')
                if val:
                    return val
    except Exception:
        pass
    return None


def _redfish_patch(host: str, token: str, path: str, payload: Dict[str, Any], etag: Optional[str], timeout: int = 6) -> Dict[str, Any]:
    try:
        cmd = [
            "curl", "-k", "-sS", "-X", "PATCH", f"https://{host}{path}",
            "-d", json.dumps(payload),
            "-H", f"X-Auth-Token: {token}",
            "-H", "Content-Type: application/json",
        ]
        if etag:
            cmd += ["-H", f"If-Match: \"{etag}\""]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        txt = (out.stdout or out.stderr or '').strip()
        try:
            return json.loads(txt) if txt else {"ok": True}
        except Exception:
            return {"raw": txt, "returncode": out.returncode}
    except Exception as e:
        return {"error": str(e)}


@app.post("/actions/uid")
@app.post("/api/actions/uid")
def actions_uid(payload: Dict[str, Any]) -> Dict[str, Any]:
    
    bmcips = payload.get("bmcip") or payload.get("bmcips") or []
    action = (payload.get("action") or "").lower().strip()
    if not isinstance(bmcips, list) or not bmcips:
        return {"ok": False, "error": "missing_bmcip_list"}
    if action not in ("on", "off"):
        return {"ok": False, "error": "invalid_action", "allowed": ["on","off"]}

    body = {"IndicatorLED": "Lit" if action == "on" else "Off"}
    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(bmcips))) as ex:
        futures = {}
        for ip in bmcips:
            def task(host: str):
                token = _redfish_get_token(host)
                if not token:
                    return {"ok": False, "error": "auth_failed"}
                etag = _redfish_get_etag(host, token)
                r = _redfish_patch(host, token, "/redfish/v1/Chassis/1", body, etag)
                return {"ok": True, "response": r}
            futures[ex.submit(task, ip)] = ip
        for fut in as_completed(futures):
            host = futures[fut]
            try:
                results[host] = fut.result()
            except Exception as e:
                results[host] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results, "count": len(results)}


# -------------------------------
# Sidebar Tasks: Upload Logo & Online
# -------------------------------
def _simple_task_status(task_id: str, title: str) -> Dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return {"error": "task_not_found"}
    lines = task["lines"][-500:]
    running = task["running"]
    rc = task["returncode"]
    stage = f"{title}: Initializing..."
    progress = 5
    if running:
        stage = f"{title}: Running..."
        progress = max(progress, 50)
    else:
        stage = f"{title}: Completed" if rc == 0 else f"{title}: Failed"
        progress = 100
    return {
        "id": task_id,
        "running": running,
        "returncode": rc,
        "lines": lines[-200:],
        "elapsed": round(time.time() - task["start"], 1),
        "progress": progress,
        "stage": stage,
    }


@app.post("/task/upload-logo/start")
@app.post("/api/task/upload-logo/start")
def start_upload_logo() -> Dict[str, str]:
    # Reset workflow memory
    UPLOAD_LOGO_STATE["job_id"] = uuid.uuid4().hex[:12]
    UPLOAD_LOGO_STATE["running"] = True
    UPLOAD_LOGO_STATE["started_at"] = time.time()
    UPLOAD_LOGO_STATE["updated_at"] = time.time()
    UPLOAD_LOGO_STATE["stages"] = {
        "Upload Logo Start": False,
        "Upload Logo Complete": False,
        "BMC Reset": False,
        "BMC Reset Complete": False,
    }
    UPLOAD_LOGO_STATE["counts"] = {
        "Upload Logo Start": 0,
        "Upload Logo Complete": 0,
        "BMC Reset": 0,
        "BMC Reset Complete": 0,
        "total": 0,
    }
    UPLOAD_LOGO_STATE["bmc_reset_started_at"] = 0.0

    
    task_id = UPLOAD_LOGO_STATE["job_id"]
    cmd = ["/bin/bash", LOGO_SCRIPT]
    threading.Thread(target=_run_script_task_with_cwd, args=(task_id, cmd, LOGO_DIR), daemon=True).start()
    return {"task_id": task_id}


@app.get("/task/upload-logo/status/{task_id}")
@app.get("/api/task/upload-logo/status/{task_id}")
def upload_logo_status(task_id: str) -> Dict[str, Any]:
    
    state = UPLOAD_LOGO_STATE
    if state.get("job_id") != task_id:
        return {"error": "task_not_found"}
    stages = state["stages"]
    ordered = ["Upload Logo Start", "Upload Logo Complete", "BMC Reset", "BMC Reset Complete"]
    
    last_idx = -1
    for i, name in enumerate(ordered):
        if stages.get(name):
            last_idx = i
        else:
            break
    progress = (last_idx + 1) * 25 if last_idx >= 0 else 0
    if last_idx >= 0 and last_idx < len(ordered):
        current = f"{ordered[last_idx]}..."
    else:
        current = "Upload Logo: Initializing..."
    if stages.get("BMC Reset Complete"):
        current = "Upload Logo: Completed"
    running = state.get("running", False) and not stages.get("BMC Reset Complete")
    bmc_remaining = None
    bmc_total = BMC_RESET_WAIT_SECS
    if stages.get("BMC Reset") and not stages.get("BMC Reset Complete"):
        start_ts = float(state.get("bmc_reset_started_at", 0.0) or 0.0)
        if start_ts > 0:
            elapsed = int(time.time() - start_ts)
            rem = max(0, bmc_total - elapsed)
            bmc_remaining = rem
    
    t = TASKS.get(task_id)
    lines = (t or {}).get("lines", [])[-100:]
    return {
        "id": task_id,
        "running": running,
        "returncode": (t or {}).get("returncode"),
        "lines": lines,
        "elapsed": round(time.time() - state.get("started_at", time.time()), 1),
        "progress": 100 if not running else max(progress, 5),
        "stage": current,
        "counts": state.get("counts", {}),
        "stages": stages,
        "bmc_reset_remaining": bmc_remaining,
        "bmc_reset_total": bmc_total,
    }


@app.post("/task/online/start")
@app.post("/api/task/online/start")
def start_online() -> Dict[str, str]:
    task_id = uuid.uuid4().hex[:12]
    cmd = ["/bin/bash", ONLINE_SCRIPT]
    t = threading.Thread(target=_run_script_task_with_cwd, args=(task_id, cmd, ONLINE_DIR), daemon=True)
    t.start()
    return {"task_id": task_id}


@app.get("/task/online/status/{task_id}")
@app.get("/api/task/online/status/{task_id}")
def online_status(task_id: str) -> Dict[str, Any]:
    return _simple_task_status(task_id, "Online Check")


# -------------------------------
# Upload Logo progress webhooks (called by shell scripts)
# -------------------------------
@app.post("/task/upload-logo/progress")
@app.post("/api/task/upload-logo/progress")
def upload_logo_progress(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Called by shell with { stage: 'upload'|'upload_complete'|'bmcreset'|'bmcreset_complete', count?, total? }"""
    stage_key = (payload.get("stage") or "").strip().lower()
    total = int(payload.get("total") or 0)
    count = int(payload.get("count") or 0)
    mapping = {
        "upload": "Upload Logo Start",
        "upload_complete": "Upload Logo Complete",
        "bmcreset": "BMC Reset",
        "bmcreset_complete": "BMC Reset Complete",
    }
    name = mapping.get(stage_key)
    if not name:
        return {"ok": False, "error": "invalid_stage"}
    UPLOAD_LOGO_STATE["stages"][name] = True
    UPLOAD_LOGO_STATE["updated_at"] = time.time()
    if stage_key == "bmcreset" and not UPLOAD_LOGO_STATE.get("bmc_reset_started_at"):
        UPLOAD_LOGO_STATE["bmc_reset_started_at"] = time.time()
        
        UPLOAD_LOGO_STATE["stages"]["BMC Reset"] = True
    if total:
        UPLOAD_LOGO_STATE["counts"]["total"] = max(UPLOAD_LOGO_STATE["counts"].get("total", 0), total)
    if count:
        UPLOAD_LOGO_STATE["counts"][name] = count
    
    if name == "BMC Reset Complete":
        UPLOAD_LOGO_STATE["running"] = False
    return {"ok": True, "stages": UPLOAD_LOGO_STATE["stages"], "counts": UPLOAD_LOGO_STATE["counts"]}


# -------------------------------
# Barcode Scan workflow (Label)
# -------------------------------

@app.post("/label/scan/start")
@app.post("/api/label/scan/start")
def label_scan_start() -> Dict[str, Any]:
    os.makedirs(LABEL_DIR, exist_ok=True)
    temp_path = os.path.join(LABEL_DIR, LABEL_SERIAL_TEMP)
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write("")
        return {"ok": True, "path": temp_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class LabelScanPayload(BaseModel):
    serial: str


@app.post("/label/scan/append")
@app.post("/api/label/scan/append")
def label_scan_append(payload: LabelScanPayload) -> Dict[str, Any]:
    serial = (payload.serial or '').strip()
    if not serial:
        return {"ok": False, "error": "missing_serial"}
    temp_path = os.path.join(LABEL_DIR, LABEL_SERIAL_TEMP)
    try:
        
        os.makedirs(LABEL_DIR, exist_ok=True)
        if not os.path.exists(temp_path):
            with open(temp_path, 'w', encoding='utf-8') as f0:
                f0.write("")
        
        with open(temp_path, 'r', encoding='utf-8') as fr:
            existing = set([ln.strip() for ln in fr if ln.strip()])
        if serial in existing:
            return {"ok": False, "error": "duplicate"}
        with open(temp_path, 'a', encoding='utf-8') as f:
            f.write(serial + "\n")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/label/scan/finish")
@app.post("/api/label/scan/finish")
def label_scan_finish() -> Dict[str, Any]:
    temp_path = os.path.join(LABEL_DIR, LABEL_SERIAL_TEMP)
    result_path = os.path.join(LABEL_DIR, LABEL_RESULT_FILE)
    try:
        
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                nonempty = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            nonempty = []
        if not nonempty:
            return {"ok": False, "error": "no_serials"}
        
        result_txt_in = os.path.join(LABEL_DIR, 'result.txt')
        try:
            with open(result_txt_in, 'w', encoding='utf-8') as fw:
                fw.write("\n".join(nonempty) + "\n")
        except Exception as e:
            return {"ok": False, "error": f"result.txt write failed: {str(e)}"}
        
        out = subprocess.run([
            "python3", os.path.join(LABEL_DIR, "reclean.py")
        ], cwd=LABEL_DIR, capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return {"ok": False, "error": out.stderr or "reclean.py failed"}
        content = out.stdout.strip()
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(content + ("\n" if content and not content.endswith("\n") else ""))
        
        try:
            with open(result_path, 'r', encoding='utf-8') as fsrc:
                data = fsrc.read()
            with open(IP_LIST_PATH, 'w', encoding='utf-8') as fdst:
                fdst.write(data)
        except Exception as e:
            return {"ok": False, "error": f"ip_list.txt update failed: {str(e)}"}
        
        def _run_ansible():
            try:
                subprocess.run(["/bin/bash", LABEL_ANSIBLE_SCRIPT], cwd=LABEL_DIR, capture_output=True, text=True, timeout=600)
            except Exception:
                pass
        threading.Thread(target=_run_ansible, daemon=True).start()
        
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return {"ok": True, "result": result_path, "async": True}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# -------------------------------
# Script modal: run ansible playbooks pipeline
# -------------------------------

def _run_ansible_pipeline(task_id: str, steps: List[Dict[str, Any]]):
    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
    TASKS[task_id] = {
        "id": task_id,
        "start": time.time(),
        "running": True,
        "returncode": None,
        "lines": [],
        "step_index": 0,
        "total_steps": len(steps),
        "stage": "Initializing...",
    }
    rc_last = 0
    for idx, step in enumerate(steps):
        name = step.get("name") or f"step_{idx+1}"
        cmd = step.get("cmd") or []
        TASKS[task_id]["step_index"] = idx
        TASKS[task_id]["stage"] = f"Running {name} ({idx+1}/{len(steps)})"
        TASKS[task_id]["lines"].append(f"== STEP start: {name} ==")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
            assert proc.stdout is not None
            for line in proc.stdout:
                TASKS[task_id]["lines"].append(line.rstrip())
            proc.wait()
            rc_last = proc.returncode or 0
        except Exception as e:
            rc_last = 1
            TASKS[task_id]["lines"].append(f"ERROR running {name}: {e}")
        TASKS[task_id]["lines"].append(f"== STEP done: {name} ==")
    TASKS[task_id]["running"] = False
    TASKS[task_id]["returncode"] = rc_last


class ScriptRunPayload(BaseModel):
    date: str
    type: str


@app.post("/script/run")
@app.post("/api/script/run")
def script_run(payload: ScriptRunPayload) -> Dict[str, str]:
    date = (payload.date or "").strip()
    typ = (payload.type or "").strip()
    task_id = uuid.uuid4().hex[:12]
    
    steps: List[Dict[str, Any]] = []
    steps.append({
        "name": "fwcheck",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_param={typ}", PLAY_FWCHECK,
        ]
    })
    steps.append({
        "name": "fru",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_date={date}", "-e", f"script_param={typ}", PLAY_FRU,
        ]
    })
    steps.append({
        "name": "fru_dup",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_date={date}", "-e", f"script_param={typ}", PLAY_FRU,
        ]
    })
    steps.append({
        "name": "ipmi",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80", PLAY_IPMI,
        ]
    })
    steps.append({
        "name": "ipmi_dup",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80", PLAY_IPMI,
        ]
    })
    steps.append({
        "name": "setbios",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_param={typ}", PLAY_SETBIOS,
        ]
    })
    steps.append({
        "name": "setbios_dup",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_param={typ}", PLAY_SETBIOS,
        ]
    })
    t = threading.Thread(target=_run_ansible_pipeline, args=(task_id, steps), daemon=True)
    t.start()
    return {"task_id": task_id}


@app.get("/script/status/{task_id}")
@app.get("/api/script/status/{task_id}")
def script_status(task_id: str) -> Dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return {"error": "task_not_found"}
    running = task.get("running", False)
    idx = int(task.get("step_index", 0))
    total = int(task.get("total_steps", 1))
    stage = task.get("stage", "Running...")
    base = int((idx / max(1, total)) * 100)
    progress = 100 if not running else max(5, min(95, base))
    return {
        "id": task_id,
        "running": running,
        "returncode": task.get("returncode"),
        "lines": task.get("lines", [])[-200:],
        "elapsed": round(time.time() - task.get("start", time.time()), 1),
        "progress": progress,
        "stage": stage,
    }


class SimpleCheckPayload(BaseModel):
    type: str


@app.post("/simplecheck/run")
@app.post("/api/simplecheck/run")
def simplecheck_run(payload: SimpleCheckPayload) -> Dict[str, str]:
    typ = (payload.type or "").strip()
    task_id = uuid.uuid4().hex[:12]
    steps = [{
        "name": "simplecheck",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"script_param={typ}", PLAY_SIMPLECHECK,
        ]
    }]
    threading.Thread(target=_run_ansible_pipeline, args=(task_id, steps), daemon=True).start()
    return {"task_id": task_id}


@app.get("/simplecheck/status/{task_id}")
@app.get("/api/simplecheck/status/{task_id}")
def simplecheck_status(task_id: str) -> Dict[str, Any]:
    return script_status(task_id)


# -------------------------------
# Quick tasks: Ping, Record Spec, Delete OS & Log
# -------------------------------

@app.post("/ping/run")
@app.post("/api/ping/run")
def ping_run() -> Dict[str, Any]:
    task_id = uuid.uuid4().hex[:12]
    steps = [{
        "name": "ping",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            PLAY_PING,
        ]
    }]
    threading.Thread(target=_run_ansible_pipeline, args=(task_id, steps), daemon=True).start()
    return {"task_id": task_id}


class RecordSpecPayload(BaseModel):
    finId: str


@app.post("/record-spec/run")
@app.post("/api/record-spec/run")
def record_spec_run(payload: RecordSpecPayload) -> Dict[str, Any]:
    fin = (payload.finId or "").strip()
    if not fin:
        return {"ok": False, "error": "missing_finId"}
    task_id = uuid.uuid4().hex[:12]
    steps = [{
        "name": "record_spec",
        "cmd": [
            "ansible-playbook", "-i", ANSIBLE_INVENTORY, "-f", "80",
            "-e", f"finid={fin}",
            PLAY_RECORD_SPEC,
        ]
    }]
    threading.Thread(target=_run_ansible_pipeline, args=(task_id, steps), daemon=True).start()
    return {"task_id": task_id}


@app.post("/delete-os-log/run")
@app.post("/api/delete-os-log/run")
def delete_os_log_run() -> Dict[str, Any]:
    def _runner():
        env = os.environ.copy()
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
        try:
            subprocess.run(["/bin/bash", CLEARSEL_SCRIPT], cwd=CLEARSEL_DIR, capture_output=True, text=True, timeout=600, env=env)
        except Exception:
            pass
        try:
            subprocess.run(["/bin/bash", DELETE_OS_SCRIPT], cwd=DELETE_OS_LOG_DIR, capture_output=True, text=True, timeout=1800, env=env)
        except Exception:
            pass
    threading.Thread(target=_runner, daemon=True).start()
    return {"ok": True}


@app.get("/dash/connected-hosts")
@app.get("/api/dash/connected-hosts")
def dash_connected_hosts() -> Dict[str, Any]:
    entries = read_ip_list(IP_LIST_PATH)
    hosts = [e.get("bmcip") for e in entries if e.get("bmcip")]
    connected = 0
    for h in hosts:
        try:
            # ping -c1 -W1 host
            out = subprocess.run(["ping", "-c", "1", "-W", "1", h], capture_output=True, text=True, timeout=2)
            if out.returncode == 0:
                connected += 1
        except Exception:
            pass
    return {"total": len(hosts), "connected": connected}


@app.post("/dash/server-type/check")
@app.post("/api/dash/server-type/check")
def dash_server_type_check() -> Dict[str, Any]:
    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")
    try:
        subprocess.run(["/bin/bash", SERVER_TYPE_SCRIPT], cwd=SERVER_TYPE_DIR, capture_output=True, text=True, timeout=600, env=env)
    except Exception:
        pass
    
    counts: Dict[str,int] = {}
    try:
        with open(SERVER_INFO_FILE, 'r', encoding='utf-8') as f:
            for ln in f:
                w = ln.strip()
                if not w: continue
                counts[w] = counts.get(w,0)+1
    except Exception:
        counts = {}
    total = sum(counts.values()) or 0
    majority = None
    pct = 0.0
    if total > 0:
        majority, cnt = max(counts.items(), key=lambda kv: kv[1])
        pct = cnt / total
    recommended = majority if pct >= 0.7 else None
    return {"total": total, "counts": counts, "recommended": recommended, "ratio": round(pct,2)}


@app.get("/dash/health/ok")
@app.get("/api/dash/health/ok")
def dash_health_ok() -> Dict[str, Any]:
    try:
        for name in os.listdir(HEALTH_LOG_DIR):
            if name in (".", ".."): continue
            path = os.path.join(HEALTH_LOG_DIR, name)
            if os.path.isfile(path):
                return {"ok": False}
    except Exception:
        pass
    return {"ok": True}


_SERV_STATUS_CACHE = {"updated": 0.0, "nginx": None, "httpd": None, "dnsmasq": None}

def _check_service_active(name: str) -> Optional[bool]:
    try:
        out = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=2)
        return out.stdout.strip() == "active"
    except Exception:
        return None


@app.get("/dash/services")
@app.get("/api/dash/services")
def dash_services() -> Dict[str, Any]:
    now = time.time()
    if now - _SERV_STATUS_CACHE["updated"] > 1800:  # 30 min
        _SERV_STATUS_CACHE["nginx"] = _check_service_active("nginx")
        _SERV_STATUS_CACHE["httpd"] = _check_service_active("httpd")
        _SERV_STATUS_CACHE["dnsmasq"] = _check_service_active("dnsmasq")
        _SERV_STATUS_CACHE["updated"] = now
    return {
        "nginx": _SERV_STATUS_CACHE["nginx"],
        "httpd": _SERV_STATUS_CACHE["httpd"],
        "dnsmasq": _SERV_STATUS_CACHE["dnsmasq"],
        "updated": _SERV_STATUS_CACHE["updated"],
    }
