from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any
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
                
        arp_out = subprocess.run(["arp", "-n"], capture_output=True, text=True)
        arp_mapping = []
        for line in arp_out.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and ":" in parts[2]:
                ip = parts[0]
                mac = parts[2].lower()
                arp_mapping.append((ip, mac))

        for nu, macs in node_macs.items():
            ips = []
            for ip, arp_mac in arp_mapping:
                if arp_mac in macs:
                    if ip not in ips:
                        ips.append(ip)
            
            if not ips:
                node_to_ips[nu] = "N / A"
            else:
                active_ip = "N / A"
                for ip in ips:
                    ping_out = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True)
                    if ping_out.returncode == 0:
                        active_ip = ip
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
        
        rows = []
        for i, n in enumerate(nodes):
            uuid = n.get("uuid") or ""
            prov = n.get("provision_state") or ""
            
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
                "power": n.get("power_state") or "",
                "os_ip": node_to_ips.get(uuid, "N / A"),
                "bmc_ip": get_bmc_ip(n),
                "provision_state": prov,
                "uuid": uuid,
                "maintenance": bool(n.get("maintenance")),
                "health": "error" if is_error else "ok",
                "last_error": err_msg
            })
        return {"rows": rows}
    except Exception as e:
        return {"rows": [], "error": str(e)}

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

@app.get("/api/deploy_files")
def get_deploy_files():
    try:
        images = []
        user_datas = []
        out = subprocess.run(["sudo", "-n", "ls", "-1", HTTPBOOT_DIR], capture_output=True, text=True)
        if out.returncode == 0:
            for f in out.stdout.splitlines():
                f = f.strip()
                if f.endswith(".qcow2") or f.endswith(".raw"): images.append(f)
                elif f.endswith(".yaml") or f.endswith(".yml") or f.endswith(".ps1"): user_datas.append(f)
        return {"images": sorted(images), "user_datas": sorted(user_datas)}
    except Exception as e:
        return {"images": [], "user_datas": [], "error": str(e)}

class ActionPayload(BaseModel):
    uuids: List[str]
    action: str

@app.post("/api/actions")
def perform_action(payload: ActionPayload):
    results = {}
    for uuid in payload.uuids:
        try:
            if payload.action in ["power-on", "power-off", "reboot"]:
                target = payload.action.replace("-", " ")
                if target == "reboot": target = "rebooting"
                url = f"{IRONIC_BASE_URL}/nodes/{uuid}/states/power"
                r = requests.put(url, headers=IRONIC_HEADERS, json={"target": target})
                results[uuid] = handle_ironic_response(r)
            elif payload.action == "clean":
                url = f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision"
                clean_payload = {
                    "target": "clean",
                    "clean_steps": [
                        {
                            "interface": "deploy",
                            "step": "erase_devices_metadata"
                        }
                    ]
                }
                r = requests.put(url, headers=IRONIC_HEADERS, json=clean_payload)
                results[uuid] = handle_ironic_response(r)
            elif payload.action in ["manage", "provide", "abort", "rebuild"]:
                url = f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision"
                r = requests.put(url, headers=IRONIC_HEADERS, json={"target": payload.action})
                results[uuid] = handle_ironic_response(r)
            elif payload.action == "undeploy":
                url = f"{IRONIC_BASE_URL}/nodes/{uuid}/states/provision"
                r = requests.put(url, headers=IRONIC_HEADERS, json={"target": "deleted"})
                results[uuid] = handle_ironic_response(r)
            else:
                results[uuid] = {"ok": False, "error": "Unsupported action"}
        except Exception as e:
            results[uuid] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results}

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
            checksum, algo = get_file_checksum(payload.image)
            image_url = f"http://{CONTROLLER_IP}:{IMAGE_PORT}/{payload.image}"

            patch_data = [
                {"op": "add", "path": "/instance_info/image_source", "value": image_url},
                {"op": "add", "path": "/instance_info/image_os_hash_algo", "value": algo},
                {"op": "add", "path": "/instance_info/image_os_hash_value", "value": checksum},
                {"op": "add", "path": "/instance_info/root_gb", "value": 50}
            ]
            
            # 2. Configdrive (Match CLI: json structure)
            try:
                user_data_path = os.path.join(HTTPBOOT_DIR, payload.user_data)
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
                        "redfish_address": f"https://{payload.address.replace('https://', '').replace('http://', '')}",
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
                    "value": "redfish-virtual-media"
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
            results[uuid] = handle_ironic_response(r)
        except Exception as e:
            results[uuid] = {"ok": False, "error": str(e)}
            
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
app.mount("/", StaticFiles(directory=BASE_DIR), name="static")
