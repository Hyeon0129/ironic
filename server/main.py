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
IRONIC_BASE_URL = "http://localhost:6385/v1"
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

IMAGE_DIR = "/var/lib/ironic/httpboot/images"
USER_DATA_DIR = "/var/lib/ironic/httpboot/user-data"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

@app.get("/api/deploy_files")
def get_deploy_files() -> Dict[str, List[str]]:
    try:
        images = []
        user_datas = []
        if os.path.exists(IMAGE_DIR):
            images = [f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f)) and f.endswith(('.qcow2', '.raw'))]
        if os.path.exists(USER_DATA_DIR):
            user_datas = [f for f in os.listdir(USER_DATA_DIR) if os.path.isfile(os.path.join(USER_DATA_DIR, f)) and f.endswith(('.yaml', '.yml', '.ps1'))]
        return {"images": sorted(images), "user_datas": sorted(user_datas)}
    except Exception as e:
        return {"images": [], "user_datas": [], "error": str(e)}

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
                elif payload.action in ["manage", "provide", "abort", "rebuild", "inspect"]:
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
                {"op": "add", "path": "/instance_info/root_gb", "value": 0}
            ]

            # No root_device hint is sent, so Ironic/IPA picks the first suitable
            # disk itself instead of failing on nodes without a literal /dev/sda.
            # Clear any stale hint left over from a previous deploy on this node.
            try:
                node_r = requests.get(f"{IRONIC_BASE_URL}/nodes/{uuid}", headers=IRONIC_HEADERS)
                if node_r.ok and node_r.json().get("properties", {}).get("root_device"):
                    patch_data.append({"op": "remove", "path": "/properties/root_device"})
            except: pass
            
            if payload.image.lower().endswith('.raw'):
                patch_data.append({"op": "add", "path": "/instance_info/image_disk_format", "value": "raw"})
            
            # 2. Configdrive (Match CLI: json structure)
            try:
                user_data_path = os.path.join(HTTPBOOT_DIR, "user-data", payload.user_data)
                cat_out = subprocess.run(["sudo", "-n", "cat", user_data_path], capture_output=True, text=True)
                if cat_out.returncode == 0:
                    # Strip a leading UTF-8 BOM (e.g. Windows-authored .ps1 files),
                    # matching the encoding='utf-8-sig' behavior used to build configdrive.json manually.
                    userdata = cat_out.stdout
                    if userdata.startswith('\ufeff'):
                        userdata = userdata[1:]
                    configdrive_obj = {"user_data": userdata}
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

@app.get("/api/nodes/{uuid}/detail")
def get_node_detail(uuid: str):
    """Single-node detail popup: current Ironic state + recent history.
    History uses the Node History API (Ironic microversion 1.78+, already
    covered by our X-OpenStack-Ironic-API-Version: 1.80) which records an
    event every time last_error is set — closest thing Ironic has to a
    per-node deploy/error log."""
    try:
        r = requests.get(f"{IRONIC_BASE_URL}/nodes/{uuid}", headers=IRONIC_HEADERS)
        if not r.ok:
            return {"ok": False, "error": f"Node not found ({r.status_code})"}
        n = r.json()

        os_ip = get_os_ip_batch_api([n]).get(uuid, "N / A")
        bmc_ip = get_bmc_ip(n)

        history = []
        try:
            hr = requests.get(f"{IRONIC_BASE_URL}/nodes/{uuid}/history", headers=IRONIC_HEADERS)
            if hr.ok:
                events = hr.json().get("history", [])
                # Most recent first, cap it so the popup stays a glance not a log dump.
                history = sorted(events, key=lambda e: e.get("created_at") or "", reverse=True)[:15]
        except: pass

        # node.properties (cpus/memory_mb/local_gb) is an ironic-inspector-era
        # concept and stays empty with inspect_interface=agent (verified live
        # against this box — even an already-inspected node's properties only
        # ever carries cpu_arch). The real per-node hardware detail lives in
        # the introspection inventory instead — same data `baremetal node
        # inventory save` prints — so pull that and reshape it into a few
        # human-readable fields instead of trusting properties.
        inventory = {}
        try:
            inv_headers = IRONIC_HEADERS.copy()
            inv_headers["X-OpenStack-Ironic-API-Version"] = "1.81"  # min version for /inventory
            ir = requests.get(f"{IRONIC_BASE_URL}/nodes/{uuid}/inventory", headers=inv_headers)
            if ir.ok:
                inventory = ir.json().get("inventory") or {}
        except: pass

        def clean_gb(gb):
            # Round to 1 decimal, but print "50" instead of "50.0" when exact.
            if gb is None:
                return None
            gb = round(gb, 1)
            return int(gb) if gb == int(gb) else gb

        def bytes_to_gb(n_bytes):
            return clean_gb(n_bytes / (1024 ** 3)) if n_bytes else None

        cpu = inventory.get("cpu") or {}
        memory = inventory.get("memory") or {}
        memory_mb = memory.get("physical_mb")
        memory_gb = clean_gb(memory_mb / 1024) if memory_mb else None

        disks = [{
            "name": d.get("name"),
            "size_gb": bytes_to_gb(d.get("size")),
            "vendor": d.get("vendor"),
            "serial": d.get("serial"),
        } for d in (inventory.get("disks") or [])]

        interfaces = [{
            "name": i.get("name"),
            "mac_address": i.get("mac_address"),
            "ipv4_address": i.get("ipv4_address"),
        } for i in (inventory.get("interfaces") or [])]

        return {
            "ok": True,
            "node": {
                "uuid": n.get("uuid"),
                "name": n.get("name"),
                "driver": n.get("driver"),
                "resource_class": n.get("resource_class"),
                "power_state": n.get("power_state"),
                "provision_state": n.get("provision_state"),
                "maintenance": bool(n.get("maintenance")),
                "maintenance_reason": n.get("maintenance_reason"),
                "last_error": n.get("last_error"),
                "instance_info": n.get("instance_info") or {},
                "created_at": n.get("created_at"),
                "updated_at": n.get("updated_at"),
                "os_ip": os_ip,
                "bmc_ip": bmc_ip,
            },
            "inventory": {
                "cpu_model": cpu.get("model_name"),
                "cpu_arch": cpu.get("architecture"),
                "memory_gb": memory_gb,
                "disks": disks,
                "interfaces": interfaces,
            },
            "history": history,
        }
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

# Only the frontend's own asset folders are exposed here — NOT a mount of
# BASE_DIR itself. Mounting "/" -> BASE_DIR used to serve the entire repo
# root as static files (server/main.py source, ironic.conf, redfish_creds.json,
# mac_list.txt, .git/ with old plaintext secrets in history, logs, etc. were
# all publicly GET-able on this port). Add new static dirs here explicitly
# if the frontend grows one — never re-mount BASE_DIR directly.
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
app.mount("/icon", StaticFiles(directory=os.path.join(BASE_DIR, "icon")), name="icon")
