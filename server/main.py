from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import subprocess
import json
import os
import requests
import sys

app = FastAPI(title="Ironic Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ironic API Endpoint
IRONIC_BASE_URL = "http://192.168.222.152:6385/v1"
IRONIC_HEADERS = {
    "X-OpenStack-Ironic-API-Version": "1.80",
    "Content-Type": "application/json"
}

# Image Server Configuration (From User CLI Example)
CONTROLLER_IP = "192.168.240.1"
IMAGE_PORT = "8080"
HTTPBOOT_DIR = "/var/lib/ironic/httpboot/"
REDFISH_CREDS_FILE = "/data/ironic/redfish_creds.json"

def get_redfish_creds():
    try:
        with open(REDFISH_CREDS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_redfish_creds(creds):
    try:
        with open(REDFISH_CREDS_FILE, "w") as f:
            json.dump(creds, f)
    except:
        pass

def get_file_checksum(file_name):
    """Get checksum and algo from local .sha256 or .md5 files."""
    file_path = os.path.join(HTTPBOOT_DIR, file_name)
    
    # Try sha256 first (preferred in CLI example)
    sha_path = file_path + ".sha256"
    if os.path.exists(sha_path):
        try:
            with open(sha_path, 'r') as f:
                return f.read().split()[0], "sha256"
        except: pass

    # Try md5
    md5_path = file_path + ".md5"
    if os.path.exists(md5_path):
        try:
            with open(md5_path, 'r') as f:
                return f.read().split()[0], "md5"
        except: pass
        
    # Manual calculate as fallback
    if os.path.exists(file_path):
        try:
            out = subprocess.run(["sha256sum", file_path], capture_output=True, text=True)
            if out.returncode == 0:
                return out.stdout.split()[0], "sha256"
        except: pass
        
    return "unknown", "sha256"

def log_request(method, url, data=None):
    print(f"DEBUG: Ironic API Request -> {method} {url}", file=sys.stderr)
    if data:
        display_data = json.loads(json.dumps(data))
        for item in display_data:
            if isinstance(item, dict) and item.get("path") == "/instance_info/configdrive":
                item["value"] = "... (configdrive JSON content)"
        print(f"DEBUG: Payload -> {json.dumps(display_data)}", file=sys.stderr)

def handle_ironic_response(r):
    try:
        r.raise_for_status()
        return {"ok": True}
    except requests.exceptions.HTTPError:
        error_msg = r.text
        try:
            error_msg = r.json().get("error_message", {}).get("faultstring", r.text)
        except: pass
        print(f"ERROR: Ironic API Failed -> {r.status_code}: {error_msg}", file=sys.stderr)
        return {"ok": False, "error": error_msg}

def get_os_ip_batch_api(nodes):
    node_to_ips = {}
    try:
        # Get all ports from Ironic API
        r = requests.get(f"{IRONIC_BASE_URL}/ports?detail=True", headers=IRONIC_HEADERS)
        if not r.ok:
            return {}
        ports = r.json().get("ports", [])
        
        node_macs = {}
        for p in ports:
            nu = p.get("node_uuid")
            mac = p.get("address")
            if nu and mac:
                node_macs.setdefault(nu, []).append(mac.lower())
                
        # Parse dnsmasq.leases file
        lease_mapping = {}
        try:
            with open('/var/lib/misc/dnsmasq.leases', 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            epoch = int(parts[0])
                        except ValueError:
                            epoch = 0
                        mac = parts[1].lower()
                        ip = parts[2]
                        # Keep the IP with the most recent (largest) lease expiry
                        existing = lease_mapping.get(mac)
                        if not existing or epoch > existing[1]:
                            lease_mapping[mac] = (ip, epoch)
        except Exception:
            pass

        for nu, macs in node_macs.items():
            active_ip = "N / A"
            for mac in macs:
                if mac in lease_mapping:
                    active_ip = lease_mapping[mac][0]
                    break
            node_to_ips[nu] = active_ip
            
    except Exception as e:
        pass
    return node_to_ips

def get_bmc_ip(node):
    driver = node.get("driver", "")
    if driver == "manual-management":
        return "N / A"
    
    driver_info = node.get("driver_info", {})
    redfish_address = driver_info.get("redfish_address", "")
    if redfish_address:
        return redfish_address.replace("https://", "").replace("http://", "").strip()
    return "N / A"

@app.get("/api/servers")
def get_servers():
    try:
        # Use detail=True to get driver_info directly in the nodes list
        r = requests.get(f"{IRONIC_BASE_URL}/nodes?detail=True", headers=IRONIC_HEADERS)
        r.raise_for_status()
        nodes = r.json().get("nodes", [])
        
        node_to_ips = get_os_ip_batch_api(nodes)
        creds = get_redfish_creds()
        
        rows = []
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        for i, n in enumerate(nodes):
            uuid = n.get("uuid") or ""
            prov = n.get("provision_state") or ""
            
            power_state = n.get("power_state")
            bmc_ip = get_bmc_ip(n)
            
            if not power_state and bmc_ip and bmc_ip != "N / A":
                cred = creds.get(bmc_ip)
                if cred:
                    try:
                        pr = requests.get(f"https://{bmc_ip}/redfish/v1/Systems/1", auth=(cred["username"], cred["password"]), verify=False, timeout=2)
                        if pr.ok:
                            rf_power = pr.json().get("PowerState")
                            if rf_power:
                                power_state = "power " + rf_power.lower()
                    except:
                        pass
                        
            if not power_state:
                power_state = ""
            
            is_error = "error" in prov.lower() or "failed" in prov.lower()
            err_msg = ""
            
            if is_error:
                err_msg = n.get("last_error") or n.get("fault") or ""
                if not err_msg:
                    try:
                        node_r = requests.get(f"{IRONIC_BASE_URL}/nodes/{uuid}", headers=IRONIC_HEADERS)
                        if node_r.ok:
                            err_msg = node_r.json().get("last_error") or ""
                    except:
                        pass
                if not err_msg:
                    err_msg = f"Node is in {prov} state"
            
            rows.append({
                "order": i,
                "name": n.get("name") or "",
                "power": power_state,
                "os_ip": node_to_ips.get(uuid, "N / A"),
                "bmc_ip": bmc_ip,
                "provision_state": prov,
                "uuid": uuid,
                "maintenance": bool(n.get("maintenance")),
                "health": "error" if is_error else "ok",
                "last_error": err_msg
            })
        return {"rows": rows}
    except Exception as e:
        return {"rows": [], "error": str(e)}

class QueryPayload(BaseModel):
    username: str
    password: str

@app.post("/api/query")
def perform_query(payload: QueryPayload):
    import concurrent.futures
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        out = subprocess.run(["nmap", "-p", "623", "--open", "192.168.222.0/24"], capture_output=True, text=True)
        ips = []
        for line in out.stdout.splitlines():
            if "Nmap scan report for" in line:
                ip = line.split()[-1].strip("()")
                ips.append(ip)
        
        results = []
        def check_ip(ip):
            try:
                r = requests.get(f"https://{ip}/redfish/v1/Systems/1", auth=(payload.username, payload.password), verify=False, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    serial = data.get("SerialNumber")
                    if serial:
                        eth_r = requests.get(f"https://{ip}/redfish/v1/Systems/1/EthernetInterfaces", auth=(payload.username, payload.password), verify=False, timeout=5)
                        if eth_r.status_code == 200:
                            eth_data = eth_r.json()
                            members = eth_data.get("Members", [])
                            if members:
                                eth_url = members[0].get("@odata.id")
                                if eth_url:
                                    mac_r = requests.get(f"https://{ip}{eth_url}", auth=(payload.username, payload.password), verify=False, timeout=5)
                                    if mac_r.status_code == 200:
                                        mac = mac_r.json().get("MACAddress")
                                        if mac:
                                            return {"ip": ip, "serial": serial.strip(), "mac": mac.strip()}
            except:
                pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_ip, ip) for ip in ips]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    results.append(res)
                    
        mac_list_path = "/data/ironic/mac_list.txt"
        with open(mac_list_path, "r") as f:
            lines = f.read().splitlines()
            
        if not lines or not (lines[0].startswith("[") and lines[0].endswith("]")):
            return {"ok": False, "error": "Invalid mac_list.txt format"}
            
        prefix = lines[0]
        prefix_val = prefix.strip("[]")
        
        serial_to_info = {item["serial"]: item for item in results}
        
        new_lines = [prefix]
        matched_count = 0
        creds = get_redfish_creds()
        
        for i, line in enumerate(lines[1:]):
            parts = line.split()
            if not parts:
                continue
            serial = parts[0]
            info = serial_to_info.get(serial)
            
            if info:
                new_line = f"{serial} {info['ip']} {info['mac']}"
                new_lines.append(new_line)
                matched_count += 1
                
                mac = info['mac'].lower()
                dnsmasq_file = f"/etc/dnsmasq.d/ironic-hosts.d/{mac}"
                subprocess.run(f"sudo mkdir -p /etc/dnsmasq.d/ironic-hosts.d && echo '{mac},set:allow_me' | sudo tee {dnsmasq_file}", shell=True)
                
                node_name = f"{prefix_val}-{i+1:03d}"
                node_payload = {
                    "name": node_name,
                    "driver": "redfish",
                    "driver_info": {
                      "redfish_address": f"https://{info['ip']}",
                      "redfish_username": payload.username,
                      "redfish_password": payload.password,
                      "redfish_system_id": "/redfish/v1/Systems/1",
                      "redfish_verify_ca": False
                    },
                    "bios_interface": "redfish",
                    "boot_interface": "ipxe",
                    "deploy_interface": "direct",
                    "inspect_interface": "agent",
                    "management_interface": "redfish",
                    "power_interface": "redfish",
                    "raid_interface": "agent",
                    "vendor_interface": "no-vendor"
                }
                
                try:
                    nr = requests.post(f"{IRONIC_BASE_URL}/nodes", headers=IRONIC_HEADERS, json=node_payload)
                    if nr.ok or nr.status_code == 409:
                        port_payload = {
                            "node_ident": node_name,
                            "address": mac,
                            "pxe_enabled": True
                        }
                        port_headers = IRONIC_HEADERS.copy()
                        port_headers["X-OpenStack-Ironic-API-Version"] = "1.94"
                        requests.post(f"{IRONIC_BASE_URL}/ports", headers=port_headers, json=port_payload)
                        
                        creds[info['ip']] = {
                            "username": payload.username,
                            "password": payload.password
                        }
                except:
                    pass
            else:
                new_lines.append(line)
                
        with open(mac_list_path, "w") as f:
            f.write("\n".join(new_lines) + "\n")
            
        save_redfish_creds(creds)
        return {"ok": True, "matched_count": matched_count}
    except Exception as e:
        return {"ok": False, "error": str(e)}

class MaintenancePayload(BaseModel):
    uuid: str
    maintenance: bool
    reason: str = ""

@app.post("/api/maintenance")
def toggle_maintenance(payload: MaintenancePayload):
    try:
        if payload.maintenance:
            r = requests.put(f"{IRONIC_BASE_URL}/nodes/{payload.uuid}/maintenance", headers=IRONIC_HEADERS, json={"reason": payload.reason})
        else:
            r = requests.delete(f"{IRONIC_BASE_URL}/nodes/{payload.uuid}/maintenance", headers=IRONIC_HEADERS)
        return handle_ironic_response(r)
    except Exception as e:
        return {"ok": False, "error": str(e)}

import threading
import uuid
import shutil
import time
import crypt
from glob import glob

IMAGE_DIR = "/var/lib/ironic/httpboot/images"
USER_DATA_DIR = "/var/lib/ironic/httpboot/user-data"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

BUILD_TASKS: Dict[str, Dict[str, Any]] = {}

@app.get("/api/ssh-keys")
def get_ssh_keys():
    """Find public ssh keys in common directories."""
    keys = []
    search_paths = [
        "/root/.ssh/*.pub",
        "/home/*/.ssh/*.pub",
        "/etc/ssh/*.pub"
    ]
    for path in search_paths:
        keys.extend(glob(path))
    if not keys:
        keys = ["/root/.ssh/id_rsa.pub"]
    return {"keys": sorted(list(set(keys)))}

class PartitionConfig(BaseModel):
    name: str
    type: str
    size: str
    mkfs_type: Optional[str] = None
    mount_point: Optional[str] = None

class BuildImagePayload(BaseModel):
    build_type: str
    os_family: str
    release: str
    size_gb: str
    partitions: List[PartitionConfig] = []
    packages: List[str] = []
    filename: str

@app.get("/api/assets/build/active")
def get_active_build():
    for tid, t in BUILD_TASKS.items():
        if t.get("running"):
            return {"task_id": tid, **t}
    return {"task_id": None}

@app.post("/api/assets/build")
def build_asset(payload: BuildImagePayload):
    # Only allow one build at a time for simplicity in this test version
    for tid, t in BUILD_TASKS.items():
        if t.get("running"):
            return {"ok": False, "error": "A build is already in progress."}

    task_id = uuid.uuid4().hex[:12]
    
    BUILD_TASKS[task_id] = {
        "status": "Initializing",
        "progress": 0,
        "running": True,
        "error": None,
        "filename": payload.filename
    }
    
    def _bg_build():
        out_path = os.path.join(IMAGE_DIR, payload.filename)
        # Log to the images directory as requested
        log_file_path = os.path.join(IMAGE_DIR, "build.log")
        env = os.environ.copy()
        
        try:
            BUILD_TASKS[task_id]["status"] = "Preparing environment..."
            BUILD_TASKS[task_id]["progress"] = 5
            
            env["DIB_RELEASE"] = payload.release
            env["TMPDIR"] = "/tmp"
            
            if payload.build_type == "os":
                import yaml
                env["DIB_DEV_USER_USERNAME"] = "sysadmin"
                env["DIB_DEV_USER_PWDLESS_SUDO"] = "yes"

                os_dist = payload.os_family.lower()
                os_element = f"{os_dist}-minimal"

                if os_dist == "ubuntu":
                    env["DIB_DISTRIBUTION_MIRROR"] = "http://mirror.kakao.com/ubuntu"

                env["DIB_IMAGE_SIZE"] = str(payload.size_gb)

                # Use NESTED YAML structure exactly like the CLI example
                block_config = [
                    {"local_loop": {"name": "image0"}},
                    {"partitioning": {
                        "base": "image0",
                        "label": "gpt",
                        "partitions": []
                    }}
                ]

                for part in payload.partitions:
                    p = {
                        "name": part.name,
                        "type": str(part.type),
                        "size": part.size
                    }
                    if part.mkfs_type:
                        p["mkfs"] = {"type": part.mkfs_type}
                        # Labels are critical for user's patch scripts
                        if part.mount_point == "/boot":
                            p["mkfs"]["label"] = "mkfs_boot"
                        elif part.mount_point == "/":
                            p["mkfs"]["label"] = "cloudimg-rootfs"
                        
                        if part.mount_point:
                            passno = 1 if part.mount_point == '/' or part.mkfs_type == 'vfat' else 2
                            opts = 'umask=0077' if part.mkfs_type == 'vfat' else 'defaults'
                            p["mkfs"]["mount"] = {
                                "mount_point": part.mount_point,
                                "fstab": {
                                    "options": opts,
                                    "fsck-passno": passno
                                }
                            }
                    block_config[1]["partitioning"]["partitions"].append(p)

                config_content = yaml.dump(block_config, default_flow_style=False)
                # In CLI example, DIB_BLOCK_DEVICE_CONFIG holds the STRING content
                env["DIB_BLOCK_DEVICE_CONFIG"] = config_content

                mandatory_pkgs = ["grub-efi-amd64", "grub-efi-amd64-signed", "shim-signed", "plymouth", "plymouth-themes", "libc6", "libkmod2", "libudev1"]
                all_pkgs = list(set(mandatory_pkgs + payload.packages))
                pkg_str = ",".join(all_pkgs)

                cmd = [
                    "disk-image-create",
                    "-p", pkg_str,
                    "-t", "qcow2", "-o", out_path,
                    os_element, "bootloader", "grub2", "block-device-efi", "cloud-init", "growroot", "devuser"
                ]
            else:
                return

            BUILD_TASKS[task_id]["status"] = "Running disk-image-create..."
            BUILD_TASKS[task_id]["progress"] = 10

            with open(log_file_path, "w") as log_file:
                proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid)
                BUILD_TASKS[task_id]["proc"] = proc
                import sys
                last_progress_time = time.time()
                for line in iter(proc.stdout.readline, ''):
                    log_file.write(line)
                    log_file.flush()
                    # Slow progress update (simulated)
                    if time.time() - last_progress_time > 15:
                        if BUILD_TASKS[task_id]["progress"] < 85:
                            BUILD_TASKS[task_id]["progress"] += 1
                        last_progress_time = time.time()
                proc.wait()
                if proc.returncode != 0:
                    if BUILD_TASKS[task_id].get("stopped"):
                        BUILD_TASKS[task_id]["status"] = "Build stopped by user"
                        BUILD_TASKS[task_id]["error"] = "Stopped"
                    else:
                        BUILD_TASKS[task_id]["error"] = f"Build failed. Check {log_file_path}"
                    return
            BUILD_TASKS[task_id]["status"] = "Post-processing..."
            BUILD_TASKS[task_id]["progress"] = 90
            
            if payload.build_type == "os":
                qcow2_path = f"{out_path}.qcow2"
                gf_mounts.sort(key=lambda x: len(x[1]))
                gf_mount_cmds = "\n".join([f"mount {dev} {mp}" for dev, mp in gf_mounts])
                
                efi_patch = ""
                if os_dist == "ubuntu":
                    efi_patch = f"""
mkdir-p /boot/efi/EFI/ubuntu
cp /usr/lib/shim/shimx64.efi /boot/efi/EFI/BOOT/BOOTX64.EFI || true
cp /usr/lib/shim/shimx64.efi /boot/efi/EFI/ubuntu/shimx64.efi || true
cp /usr/lib/shim/fbx64.efi /boot/efi/EFI/ubuntu/fbx64.efi || true
cp /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed /boot/efi/EFI/ubuntu/grubx64.efi || true
cp /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed /boot/efi/EFI/BOOT/grubx64.efi || true
write /boot/efi/EFI/ubuntu/grub.cfg "search --no-floppy --label --set=root mkfs_boot\\nset prefix=($root)/grub\\nconfigfile $prefix/grub.cfg\\n"
write /boot/efi/EFI/BOOT/grub.cfg "search --no-floppy --label --set=root mkfs_boot\\nset prefix=($root)/grub\\nconfigfile $prefix/grub.cfg\\n"
sh "sed -i 's|search --no-floppy --fs-uuid --set=root.*|search --no-floppy --label --set=root mkfs_boot|g' /boot/grub/grub.cfg || true"
sh "sed -i 's|search --no-floppy --label --set=root cloudimg-rootfs|search --no-floppy --label --set=root mkfs_boot|g' /boot/grub/grub.cfg || true"
"""
                gf_cmd = f"guestfish -a {qcow2_path} <<'EOF'\nrun\n{gf_mount_cmds}\n{efi_patch}\nEOF\n"
                subprocess.run(gf_cmd, shell=True, executable='/bin/bash')
                subprocess.run(f"virt-customize -a {qcow2_path} --run-command \"sed -i 's| boot=LABEL=mkfs_boot||g' /etc/default/grub\" --run-command \"update-grub\" || true", shell=True)
                
                BUILD_TASKS[task_id]["status"] = "Generating checksum..."
                BUILD_TASKS[task_id]["progress"] = 98
                subprocess.run(f"sha256sum {os.path.basename(qcow2_path)} > {os.path.basename(qcow2_path)}.sha256", shell=True, cwd=IMAGE_DIR)

            BUILD_TASKS[task_id]["status"] = "Completed successfully!"
            BUILD_TASKS[task_id]["progress"] = 100
            
        except Exception as e:
            BUILD_TASKS[task_id]["status"] = "Failed"
            BUILD_TASKS[task_id]["error"] = str(e)
        finally:
            BUILD_TASKS[task_id]["running"] = False
            try:
                if payload.build_type == "os":
                    os.remove(f"/tmp/dib_block_config_{task_id}.yaml")
            except: pass

    threading.Thread(target=_bg_build, daemon=True).start()
    return {"ok": True, "task_id": task_id}

@app.post("/api/assets/build/stop")
def stop_active_build():
    import signal
    stopped = False
    for tid, t in BUILD_TASKS.items():
        if t.get("running"):
            proc = t.get("proc")
            if proc:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    pass
            t["stopped"] = True
            t["running"] = False
            t["status"] = "Stopped"
            t["error"] = "Build stopped by user"
            stopped = True
    return {"ok": stopped}
@app.get("/api/assets/build/status/{task_id}")
def get_build_status(task_id: str):
    if task_id not in BUILD_TASKS:
        return {"error": "Not found"}
    return BUILD_TASKS[task_id]

@app.get("/api/assets/build/log")
def get_build_log(lines: int = 200):
    log_file_path = os.path.join(IMAGE_DIR, "build.log")
    if not os.path.exists(log_file_path):
        return {"log": ""}
    try:
        # read last N lines
        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return {"log": "".join(all_lines[-lines:])}
    except Exception as e:
        return {"log": f"Error reading log: {e}"}

class UserDataPayload(BaseModel):
    filename: str
    hostname: str
    username: str
    password: str

@app.post("/api/assets/userdata")
def create_userdata(payload: UserDataPayload):
    try:
        hashed_pw = crypt.crypt(payload.password, crypt.mksalt(crypt.METHOD_SHA512))
        yaml_content = f"""#cloud-config
hostname: {payload.hostname}
ssh_pwauth: true
users:
  - name: {payload.username}
    passwd: "{hashed_pw}"
    lock_passwd: false
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
"""
        path = os.path.join(USER_DATA_DIR, payload.filename)
        with open(path, "w") as f:
            f.write(yaml_content)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

from fastapi import UploadFile, File, Form
@app.get("/api/deploy_files")
def get_deploy_files() -> Dict[str, List[str]]:
    try:
        images = []
        user_datas = []
        if os.path.exists(IMAGE_DIR):
            images = [f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f)) and f.endswith(('.qcow2', '.raw'))]
        if os.path.exists(USER_DATA_DIR):
            user_datas = [f for f in os.listdir(USER_DATA_DIR) if os.path.isfile(os.path.join(USER_DATA_DIR, f)) and f.endswith(('.yaml', '.yml'))]
        return {"images": sorted(images), "user_datas": sorted(user_datas)}
    except Exception as e:
        return {"images": [], "user_datas": [], "error": str(e)}

@app.get("/api/assets")
def get_assets():
    return get_deploy_files()

@app.post("/api/assets/upload")
def upload_asset(file: UploadFile = File(...), type: str = Form(...)):
    target_dir = IMAGE_DIR if type == "image" else USER_DATA_DIR
    file_path = os.path.join(target_dir, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"ok": True, "filename": file.filename}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/assets/{type}/{filename}")
def delete_asset(type: str, filename: str):
    target_dir = IMAGE_DIR if type == "image" else USER_DATA_DIR
    file_path = os.path.join(target_dir, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "File not found"}

class ActionPayload(BaseModel):
    uuids: List[str]
    action: str

@app.post("/api/actions")
def perform_action(payload: ActionPayload):
    task_id = uuid.uuid4().hex[:12]

    def _bg_action():
        for uuid_node in payload.uuids:
            try:
                if payload.action in ["power-on", "power-off", "reboot"]:
                    target = payload.action.replace("-", " ")
                    if target == "reboot": target = "rebooting"
                    url = f"{IRONIC_BASE_URL}/nodes/{uuid_node}/states/power"
                    requests.put(url, headers=IRONIC_HEADERS, json={"target": target})
                elif payload.action == "clean":
                    url = f"{IRONIC_BASE_URL}/nodes/{uuid_node}/states/provision"
                    clean_payload = {
                        "target": "clean",
                        "clean_steps": [
                            {
                                "interface": "deploy",
                                "step": "erase_devices_metadata"
                            }
                        ]
                    }
                    requests.put(url, headers=IRONIC_HEADERS, json=clean_payload)
                elif payload.action in ["manage", "provide", "abort", "rebuild"]:
                    url = f"{IRONIC_BASE_URL}/nodes/{uuid_node}/states/provision"
                    requests.put(url, headers=IRONIC_HEADERS, json={"target": payload.action})
                elif payload.action == "undeploy":
                    url = f"{IRONIC_BASE_URL}/nodes/{uuid_node}/states/provision"
                    requests.put(url, headers=IRONIC_HEADERS, json={"target": "deleted"})
                elif payload.action == "delete-node":
                    url = f"{IRONIC_BASE_URL}/nodes/{uuid_node}"
                    
                    # Fetch bmc_ip to remove credentials if they exist
                    try:
                        node_r = requests.get(url, headers=IRONIC_HEADERS)
                        if node_r.ok:
                            node_data = node_r.json()
                            bmc_ip = get_bmc_ip(node_data)
                            if bmc_ip and bmc_ip != "N / A":
                                creds = get_redfish_creds()
                                if bmc_ip in creds:
                                    del creds[bmc_ip]
                                    save_redfish_creds(creds)
                    except:
                        pass
                    
                    # Fetch ports to remove dnsmasq entries
                    try:
                        ports_r = requests.get(f"{url}/ports", headers=IRONIC_HEADERS)
                        if ports_r.ok:
                            for p in ports_r.json().get("ports", []):
                                mac = p.get("address")
                                if mac:
                                    dnsmasq_file = f"/etc/dnsmasq.d/ironic-hosts.d/{mac.lower()}"
                                    subprocess.run(f"sudo rm -f {dnsmasq_file} && sudo systemctl restart dnsmasq", shell=True)
                    except:
                        pass
                    
                    requests.delete(url, headers=IRONIC_HEADERS)
            except Exception as e:
                pass

    threading.Thread(target=_bg_action, daemon=True).start()
    return {"ok": True, "task_id": task_id, "message": "Action started in background"}

class DeployPayload(BaseModel):
    uuids: List[str]
    image: str
    user_data: str

@app.post("/api/deploy")
def perform_deploy(payload: DeployPayload):
    results = {}
    for uuid in payload.uuids:
        try:
            # 1. Image Info (Match CLI: http://IP:8080/image)
            checksum, algo = get_file_checksum(f"images/{payload.image}")
            image_url = f"http://{CONTROLLER_IP}:{IMAGE_PORT}/images/{payload.image}"

            patch_data = [
                {"op": "add", "path": "/instance_info/image_source", "value": image_url},
                {"op": "add", "path": "/instance_info/image_os_hash_algo", "value": algo},
                {"op": "add", "path": "/instance_info/image_os_hash_value", "value": checksum},
                {"op": "add", "path": "/instance_info/root_gb", "value": 0},
                {"op": "add", "path": "/properties/root_device", "value": {"name": "/dev/sda"}}
            ]            
            # 2. Configdrive (Match CLI: json structure)
            try:
                user_data_path = os.path.join(HTTPBOOT_DIR, "user-data", payload.user_data)
                cat_out = subprocess.run(["sudo", "-n", "cat", user_data_path], capture_output=True, text=True)
                if cat_out.returncode == 0:
                    # CLI used a json file content. Usually {"user_data": "..."}
                    configdrive_obj = {"user_data": cat_out.stdout}
                    patch_data.append({"op": "add", "path": "/instance_info/configdrive", "value": configdrive_obj})
            except: pass

            log_request("PATCH", f"{IRONIC_BASE_URL}/nodes/{uuid}", patch_data)
            r_patch = requests.patch(f"{IRONIC_BASE_URL}/nodes/{uuid}", headers=IRONIC_HEADERS, json=patch_data)
            if not r_patch.ok:
                results[uuid] = handle_ironic_response(r_patch)
                continue
            
            # 3. Start Deploy
            r_deploy = requests.put(f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision", headers=IRONIC_HEADERS, json={"target": "active"})
            results[uuid] = handle_ironic_response(r_deploy)
            
        except Exception as e:
            results[uuid] = {"ok": False, "error": str(e)}
            
    return {"ok": True, "results": results}

class RaidPayload(BaseModel):
    uuids: List[str]
    action: str

@app.post("/api/raid")
def configure_raid(payload: RaidPayload):
    results = {}
    for uuid in payload.uuids:
        try:
            if payload.action == "create":
                # Apply RAID config first
                raid_config_payload = {
                    "logical_disks": [
                        {
                            "size_gb": "MAX",
                            "raid_level": "1",
                            "is_root_volume": True,
                            "controller": "software"
                        }
                    ]
                }
                r_config = requests.put(f"{IRONIC_BASE_URL}/nodes/{uuid}/states/raid", headers=IRONIC_HEADERS, json=raid_config_payload)
                if not r_config.ok:
                    results[uuid] = handle_ironic_response(r_config)
                    continue

                # Then clean steps
                clean_payload = {
                    "target": "clean",
                    "clean_steps": [
                        {"interface": "deploy", "step": "erase_devices_metadata"},
                        {"interface": "raid", "step": "create_configuration"}
                    ]
                }
                r_clean = requests.put(f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision", headers=IRONIC_HEADERS, json=clean_payload)
                results[uuid] = handle_ironic_response(r_clean)

            elif payload.action == "delete":
                clean_payload = {
                    "target": "clean",
                    "clean_steps": [
                        {"interface": "raid", "step": "delete_configuration"},
                        {"interface": "deploy", "step": "erase_devices_metadata"}
                    ]
                }
                r_clean = requests.put(f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision", headers=IRONIC_HEADERS, json=clean_payload)
                results[uuid] = handle_ironic_response(r_clean)
            else:
                results[uuid] = {"ok": False, "error": "Invalid RAID action"}
        except Exception as e:
            results[uuid] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results}

class RedfishPayload(BaseModel):
    uuids: List[str]
    address: str
    username: str
    password: str

@app.post("/api/redfish")
def update_redfish(payload: RedfishPayload):
    results = {}
    creds = get_redfish_creds()
    clean_ip = payload.address.replace('https://', '').replace('http://', '').strip()
    
    for uuid in payload.uuids:
        try:
            patch_data = [
                {
                    "op": "replace",
                    "path": "/driver",
                    "value": "redfish"
                },
                {
                    "op": "replace",
                    "path": "/driver_info",
                    "value": {
                        "redfish_address": f"https://{clean_ip}",
                        "redfish_username": payload.username,
                        "redfish_password": payload.password,
                        "redfish_system_id": "/redfish/v1/Systems/1",
                        "redfish_verify_ca": False
                    }
                },
                {
                    "op": "replace",
                    "path": "/bios_interface",
                    "value": "redfish"
                },
                {
                    "op": "replace",
                    "path": "/boot_interface",
                    "value": "ipxe"
                },
                {
                    "op": "replace",
                    "path": "/deploy_interface",
                    "value": "direct"
                },
                {
                    "op": "replace",
                    "path": "/inspect_interface",
                    "value": "agent"
                },
                {
                    "op": "replace",
                    "path": "/management_interface",
                    "value": "redfish"
                },
                {
                    "op": "replace",
                    "path": "/power_interface",
                    "value": "redfish"
                },
                {
                    "op": "replace",
                    "path": "/raid_interface",
                    "value": "agent"
                },
                {
                    "op": "replace",
                    "path": "/vendor_interface",
                    "value": "no-vendor"
                }
            ]
            
            r = requests.patch(f"{IRONIC_BASE_URL}/nodes/{uuid}", headers=IRONIC_HEADERS, json=patch_data)
            resp = handle_ironic_response(r)
            results[uuid] = resp
            if resp.get("ok"):
                creds[clean_ip] = {
                    "username": payload.username,
                    "password": payload.password
                }
        except Exception as e:
            results[uuid] = {"ok": False, "error": str(e)}
            
    save_redfish_creds(creds)
    return {"ok": True, "results": results}

class RenamePayload(BaseModel):
    uuid: str
    new_name: str

@app.post("/api/nodes/rename")
def rename_node(payload: RenamePayload):
    try:
        patch_data = [{"op": "replace", "path": "/name", "value": payload.new_name}]
        r = requests.patch(f"{IRONIC_BASE_URL}/nodes/{payload.uuid}", headers=IRONIC_HEADERS, json=patch_data)
        return handle_ironic_response(r)
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/stats")
def get_stats():
    try:
        r = requests.get(f"{IRONIC_BASE_URL}/nodes?detail=True", headers=IRONIC_HEADERS)
        nodes = r.json().get("nodes", [])
        
        error_count = 0
        for n in nodes:
            prov = (n.get("provision_state") or "").lower()
            err = n.get("last_error") or n.get("fault")
            if err or "error" in prov or "failed" in prov:
                error_count += 1
                
        return {
            "total": len(nodes),
            "power_on": sum(1 for n in nodes if n.get("power_state") == "power on"),
            "active": sum(1 for n in nodes if n.get("provision_state") == "active"),
            "error": error_count
        }
    except:
        return {"total": 0, "power_on": 0, "active": 0, "error": 0}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
@app.get("/")
def read_root(): return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/builder")
def read_builder(): return FileResponse(os.path.join(BASE_DIR, "builder.html"))

@app.get("/cloud-init")
def read_cloud_init(): return FileResponse(os.path.join(BASE_DIR, "cloud-init.html"))

app.mount("/", StaticFiles(directory=BASE_DIR), name="static")
