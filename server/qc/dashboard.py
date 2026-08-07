#!/usr/bin/env python3
"""WinRM QC 로직 (Ironic 대시보드에 서버사이드로 통합, 2026-08-06).

원본은 사용자 노트북에서 돌던 pywebview/tkinter 데스크톱 앱(sangsang)의
qc_dashboard.py. 이 파일은 그 원본에서 tkinter GUI 클래스(QCDashboard 및
각종 Dialog)만 잘라낸 버전 — WinRMClient/Server 및 모든 PowerShell 스크립트
본문은 원본 그대로(수정 없이) 가져왔다. 스크립트는 원격 Windows 대상에서
실행되는 내용이라 이 서버가 Linux라는 사실과 무관하다.

바뀐 건 WinRMClient의 접속 계층(run_local/run_remote/ping)과, PSSession 파일전송
(Copy-Item -ToSession/-FromSession, pywinrm엔 없음)을 쓰던 copy_to_remote/
copy_from_remote(zip+base64 방식으로 재작성)뿐이다. 이 외의 모든 메서드
(get_pnp_devices, check_activation, stop_winrm 등)는 그냥 self.run_remote(ip,
script)를 호출할 뿐이라 변경 없음."""

from . import _md4_shim  # noqa: F401 — must run before `import winrm` (see that module)
import winrm
import json, re, shutil, subprocess, sys, threading, time, base64, os, tempfile, zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# PyInstaller로 exe 패키징 시 __file__ 은 임시 압축해제 경로를 가리키므로 쓸 수 없다.
# 실행파일(exe) 옆 폴더를 기준으로 설정/서버목록/캡처 등을 저장해야 재실행해도 값이 유지된다.
BASE_DIR     = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_FILE  = BASE_DIR / "config.json"
SERVERS_FILE = BASE_DIR / "servers.json"
QC_TOOL_DIR  = BASE_DIR / "WindowsQC"

DEFAULT_CONFIG = {
    "username": "super", "password": "1", "sales_number": "",
    "local_output_dir": str(Path.home() / "Desktop" / "QC_Results"),
    "remote_qc_path": "C:\\Users\\super\\Desktop\\WindowsQC",
    "client_profile": "sangsang",  # 사이드바에 어떤 업체용 항목을 보여줄지 (client_profiles.py 참고)
}

# ── 다크 테마 색상 (x.ai / Grok 스타일)
BG      = "#0d0d0d"
SURFACE = "#141414"
CARD    = "#1c1c1c"
BORDER  = "#2a2a2a"
TEXT    = "#e2e2e2"
MUTED   = "#5a5a5a"
ACCENT  = "#6366f1"
GREEN   = "#22c55e"
RED     = "#ef4444"
YELLOW  = "#eab308"
BLUE    = "#3b82f6"
BTN     = "#1e1e1e"
BTN_H   = "#2a2a2a"
SEL_BG  = "#1a1d2e"


# ═══════════════════════════════════════════════════════════════════
# WinRM 클라이언트
# ═══════════════════════════════════════════════════════════════════
class WinRMClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password

    # ── 원격 접속 (pywinrm 기반, 2026-08-06 교체) ───────────────────────
    # 원본은 이 프로세스가 Windows에서 돌아간다고 가정하고, 로컬 PowerShell을
    # 띄워 `Invoke-Command -ComputerName -Credential` 로 WinRM 접속을 했다. 이
    # 서버는 Linux라 PowerShell 자체가 없어서, WinRM 프로토콜을 순수 파이썬으로
    # 구현한 pywinrm(winrm.Session.run_ps)으로 접속 계층만 교체했다. 반환값
    # 형태(status_code, stdout, stderr)는 원본 run_local/run_remote와 동일하게
    # 맞춰서, 이 파일의 나머지 메서드(get_pnp_devices, check_activation,
    # stop_winrm 등 — 전부 self.run_remote(ip, script)만 호출)는 스크립트
    # 본문 그대로 수정 없이 동작한다.
    def _session(self, ip):
        return winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(self.username, self.password),
            transport="ntlm",
            server_cert_validation="ignore",
            operation_timeout_sec=90,
            read_timeout_sec=95,
        )

    def run_remote(self, ip, script, timeout=60):
        # 한글 깨짐 방지: PowerShell 콘솔 출력을 UTF-8로 고정 (원본과 동일)
        utf8_prefix = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;" \
                      "$OutputEncoding=[System.Text.Encoding]::UTF8;"
        try:
            r = self._session(ip).run_ps(utf8_prefix + script)
            out = (r.std_out or b"").decode("utf-8", errors="replace").strip()
            err = (r.std_err or b"").decode("utf-8", errors="replace").strip()
            return r.status_code, out, err
        except Exception as e:
            return -1, "", str(e)

    def run_local(self, script, timeout=60):
        """원본에선 "이 프로세스를 돌리는 로컬 PC에서" 실행 — copy_to_remote/
        copy_from_remote가 PSSession(Copy-Item -ToSession/-FromSession)을 로컬에서
        굴리려고 썼던 것. pywinrm엔 그 세션 파일전송 개념이 없어서 저 둘은 아래에서
        base64 방식(run_remote만으로 동작)으로 재작성했고, 그 결과 run_local의
        실사용 호출부는 이제 없다. 혹시 남아있는 호출부가 있다면 조용히 성공한
        척하는 대신 바로 알 수 있게 에러를 돌려준다."""
        return -1, "", "run_local is not available on this (Linux) host — use run_remote."

    def ping(self, ip):
        # 원본은 로컬 PowerShell의 Test-Connection(ICMP)을 썼다 — 여기선 Linux의
        # 네이티브 ping 커맨드로 동일한 걸 확인한다.
        try:
            r = subprocess.run(["ping", "-c", "1", "-W", "2", ip],
                                capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def test_winrm(self, ip):
        _, out, _ = self.run_remote(ip, "'WINRM_OK'", timeout=15)
        return "WINRM_OK" in out

    def get_boot_time(self, ip):
        """재부팅 감지에 쓰는 실제 부팅시각 — 재부팅 명령 직후엔 아직 이전 세션이 살아있어서
        WinRM이 곧바로 응답하는 경우가 있는데(재부팅이 실제로 시작되기 전), 이 값을 재부팅
        명령 보낸 시각과 비교해서 "진짜 새로 켜진 것"인지 "예전 세션의 잔여 응답"인지 구분한다."""
        _, out, _ = self.run_remote(
            ip, "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')",
            timeout=15)
        return (out or "").strip()

    def has_active_session(self, ip, username):
        """WinRM(서비스)이 응답한다고 해서 사람이 로그인해서 바탕화면까지 뜬 건 아니다 —
        그 계정의 세션이 실제로 "Active"(로그인+바탕화면 진입 완료) 상태인지까지 확인해야
        "진짜 준비된 시점"이다. query user 의 STATE 칸 문자열("Active")은 Windows 표시 언어에
        따라 달라지는데(한국어면 "활성"), 대상 서버가 전부 영문 Windows로 확정되어 있어서
        이 방식을 쓴다 — 다국어 서버가 섞이면 다시 explorer.exe 소유자 확인(Win32_Process+
        GetOwner) 방식으로 되돌려야 함."""
        u = username.replace("'", "''")
        script = f"""
$sessions = query user 2>$null
$active = $sessions | Where-Object {{ $_ -match [regex]::Escape('{u}') -and $_ -match 'Active' }}
if ($active) {{ 'SESSION_ACTIVE' }} else {{ 'SESSION_INACTIVE' }}
"""
        _, out, _ = self.run_remote(ip, script, timeout=15)
        return "SESSION_ACTIVE" in (out or "")

    def get_computer_name(self, ip):
        return self.run_remote(ip, "$env:COMPUTERNAME", timeout=15)

    def get_os_build(self, ip):
        """Windows 10/11 판정용 빌드번호 (11은 22000 이상) — 장치관리자/내 PC 캡처만 OS별로
        동작방식이 달라서 그 두 캡처 직전에만 조회한다. 실패하면 None(호출부에서 win11로 간주)."""
        _, out, _ = self.run_remote(ip, "(Get-CimInstance Win32_OperatingSystem).BuildNumber", timeout=15)
        try:
            return int((out or "").strip())
        except ValueError:
            return None

    def get_pnp_devices(self, ip):
        script = r"""
# 하드웨어 스펙
$cpus    = @(Get-CimInstance Win32_Processor -EA SilentlyContinue)
$cpuName = if ($cpus) { ($cpus[0].Name.Trim() -replace '\s+',' ') } else { '' }
$cpuCnt  = $cpus.Count
$ramGB   = try { [int]([math]::Round(
    (Get-CimInstance Win32_ComputerSystem -EA Stop).TotalPhysicalMemory / 1GB)) } catch { 0 }
$gpuObj  = Get-CimInstance Win32_VideoController -EA SilentlyContinue |
    Where-Object { $_.Name -notmatch 'Microsoft Basic|Remote Desktop|Hyper-V' } |
    Select-Object -First 1
$gpuName = if ($gpuObj) { $gpuObj.Name } else { '' }
$nicObjs = @(Get-CimInstance Win32_NetworkAdapter -EA SilentlyContinue |
    Where-Object { $_.PhysicalAdapter -eq $true })
$nicDisp = if ($nicObjs.Count -gt 1) { "$($nicObjs[0].Name) ×$($nicObjs.Count)" }
           elseif ($nicObjs.Count -eq 1) { $nicObjs[0].Name } else { '' }
$specs = [PSCustomObject]@{
    cpu=$cpuName; cpu_count=$cpuCnt; ram_gb=$ramGB; gpu=$gpuName; nic=$nicDisp }

# PnP 장치
$cats = [ordered]@{
    'Network Adapters'='Net'; 'Display Adapters'='Display';
    'Disk Drives'='DiskDrive'; 'Security Devices'='SecurityDevices' }
$all = [System.Collections.Generic.List[object]]::new()
foreach ($cat in $cats.Keys) {
    # -PresentOnly 없으면 과거에 연결됐다 지금은 없는 "phantom" 장치(예: VM 스냅샷/재구성 이력이
    # 남긴 예전 가상 디스크 항목)까지 같이 나온다. 이런 phantom 장치는 Status가 OK가 아니지만
    # (보통 Unknown/CM_PROB_PHANTOM) 장치관리자 기본 화면(숨김장치 표시 꺼짐)에는 애초에 안 보이는
    # 존재라서, 기술자가 장치관리자로는 "이상 없음"으로 보는데 여기서는 "이상감지"로 잘못
    # 뜨는 원인이었다. 장치관리자와 동일하게 현재 실제로 붙어있는 장치만 본다.
    Get-PnpDevice -Class $cats[$cat] -PresentOnly -EA SilentlyContinue | ForEach-Object {
        $all.Add([PSCustomObject]@{
            Category=$cat; Name="$($_.FriendlyName)"; Status="$($_.Status)" }) } }
[PSCustomObject]@{ specs=$specs; devices=$all } | ConvertTo-Json -Depth 3 -Compress"""
        return self.run_remote(ip, script, timeout=40)

    def get_disk_volumes(self, ip):
        script = r"""
$r = Get-Partition | Where-Object DriveLetter | Sort-Object DriveLetter | ForEach-Object {
    $v = Get-Volume -Partition $_ -ErrorAction SilentlyContinue
    [PSCustomObject]@{Letter="$($_.DriveLetter)";DiskNum=$_.DiskNumber;
        SizeGB=[math]::Round($_.Size/1GB,1);
        FreeGB=if($v){[math]::Round($v.SizeRemaining/1GB,1)}else{0};
        FS=if($v){"$($v.FileSystem)"}else{"N/A"};
        Label=if($v){"$($v.FileSystemLabel)"}else{""}
        Health=if($v){"$($v.OperationalStatus)"}else{"N/A"}}
}
if ($r) { $r | ConvertTo-Json -Depth 2 -Compress } else { "[]" }"""
        return self.run_remote(ip, script, timeout=30)

    def check_boot_folder(self, ip):
        script = r"""
$result = "UNKNOWN"
$userDirs = @(Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { "$($_.FullName)\Desktop" })
$desktops = @("C:\Users\Public\Desktop") + $userDirs
foreach ($d in $desktops) {
    if (Test-Path "$d\1") { $result = "DISK_A"; break }
    if (Test-Path "$d\2") { $result = "DISK_B"; break }
}
$result"""
        return self.run_remote(ip, script, timeout=20)

    def check_activation(self, ip):
        script = r"""
$p = Get-CimInstance SoftwareLicensingProduct -ErrorAction SilentlyContinue |
     Where-Object {$_.PartialProductKey -and $_.Name -like "Windows*"} | Select-Object -First 1
if ($p) {
    switch ($p.LicenseStatus) {
        0 { "Unlicensed" } 1 { "Licensed" } default { "Other($($p.LicenseStatus))" }
    }
} else { "NOT_FOUND" }"""
        return self.run_remote(ip, script, timeout=30)

    def activate_windows(self, ip, key):
        k = key.strip().replace("'", "''")
        script = f"""
$out = @()
try {{ $r = cscript //NoLogo C:\\Windows\\System32\\slmgr.vbs /ipk {k} 2>&1
      $out += "IPK: " + ($r -join " ") }} catch {{ $out += "IPK_ERR: $_" }}
try {{ $r = cscript //NoLogo C:\\Windows\\System32\\slmgr.vbs /ato 2>&1
      $out += "ATO: " + ($r -join " ") }} catch {{ $out += "ATO_ERR: $_" }}
$out -join "|||" """
        return self.run_remote(ip, script, timeout=120)

    def rename_computer(self, ip, name):
        n = name.replace("'", "''")
        return self.run_remote(ip, f"Rename-Computer -NewName '{n}' -Force; 'RENAMED'", timeout=30)

    def shutdown(self, ip):
        return self.run_remote(ip, "Stop-Computer -Force; 'SHUTDOWN_SENT'", timeout=15)

    def stop_winrm(self, ip, username):
        """서버 납품 직전 보안 정책상 WinRM을 꺼야 하는데, cloud-init이 최초 부팅 시 서비스
        시작유형(Automatic)뿐 아니라 레지스트리(LocalAccountTokenFilterPolicy), 방화벽 규칙
        (커스텀 "WinRM-HTTP" + winrm quickconfig 가 자동으로 켠 "Windows Remote Management"
        내장 그룹), 클라이언트 TrustedHosts("*"), 리스너까지 같이 건드려놨다 — 그래서 서비스만
        꺼서는 "원래 상태로 복원"이 안 되고, 이 5가지를 전부 되돌려야 한다.

        끄고 나면 대시보드로는 더 이상 조회가 안 되므로(WinRM 자체가 끊김), 기술자가 서버실에
        가서 확인할 때 직접 명령어를 입력하지 않아도 되도록: 변경 "전" 상태를 먼저 파일로
        스냅샷 해두고, 대상 계정의 인터랙티브 세션(실제 로그인된 화면)에서 PowerShell 창을
        띄우는 예약작업을 등록해둔다. 이 창은 일부러 몇 초 늦게(변경 후 상태를 확실히 반영할
        시간을 준 뒤) "전/후 비교"를 띄우고 -NoExit 로 열린 채로 남아있어서, 기술자가 나중에
        서버 화면을 보면 이미 결과가 떠 있다 — 그 자리에서 확인 후 창을 닫고 서버를 종료하면 됨.

        Stop-Service 만 별도 취급하는 이유: 이 명령 자체가 WinRM 을 타고 전달되므로 그 자리에서
        바로 실행하면 응답을 돌려받기 전에 통신이 끊길 위험이 있다. 나머지(레지스트리/방화벽/
        TrustedHosts/리스너/시작유형)는 로컬 OS 상태 변경일 뿐 지금 연결을 안 끊으므로 먼저
        동기적으로 전부 처리하고, 맨 마지막에만 10초 뒤 서비스를 내리도록 예약해서, 예약 직후
        바로 REVERT_SCHEDULED 응답을 돌려받는다. 전/후 비교 창은 13초 뒤(서비스가 확실히 꺼진
        다음)에 뜨도록 여유를 둔다.

        **주의(실사용 중 발견한 버그)**: 처음엔 `Start-Process`로 띄운 분리 프로세스에 지연
        종료를 맡겼는데, 실제로는 서비스가 절대 안 꺼졌다 — WinRM 원격 세션이 만든 자식 프로세스는
        그 세션의 Job Object 에 묶여 있어서, 스크립트가 끝나고 세션이 닫히는 즉시(=거의 바로) 그
        자식 프로세스까지 강제 종료돼버린다. 그래서 `schtasks`(SYSTEM 권한, 세션과 완전히 무관한
        절대시각 예약)로 교체했다 — 방화벽/레지스트리 변경은 동기 처리라 정상 반영됐지만
        서비스만 계속 Running 으로 남아있던 게 이 버그의 증상이었다.

        **주의**: 뷰어 스크립트는 반드시 base64로 파일에 써야 한다 — 이 메서드의 전체 스크립트는
        `run_remote()`를 통해 매 줄 8칸이 강제로 들여쓰기된 채 `Invoke-Command -ScriptBlock { }`
        안에 들어가는데, PowerShell의 `@'...'@` 히어스트링은 닫는 `'@`가 반드시 줄 맨 앞(0칸)에
        와야 해서 그 들여쓰기 때문에 깨진다(capture_device_manager 등 다른 메서드들이 전부
        base64+파일쓰기 방식을 쓰는 이유와 동일).

        전/후 상태는 `key=value` 한 줄씩으로 저장해서(`ConvertFrom-StringData`로 다시 읽음)
        뷰어에서 표(Format-Table)로 나란히 비교하도록 한다 — 예전처럼 두 블록을 위아래로
        쌓아두면 항목별로 눈으로 대조하기 번거로워서, 한 줄에 항목/전/후가 다 보이게 바꿨다.
        "변경 전" 상태는 REVERT_SCHEDULED 응답에도 같이 실어 보내서 대시보드 로그에 즉시
        표시한다 — "변경 후"는 그 시점엔 WinRM이 이미 끊겨있어 대시보드로는 조회 자체가
        불가능하므로(서버 화면의 뷰어 창으로만 확인 가능), 어차피 못 보내는 값이다."""
        u = username.replace('"', '')

        state_snippet = r"""
$svc = Get-Service WinRM
$thReg = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\WinRM\Client' -Name TrustedHosts -EA SilentlyContinue).TrustedHosts
$ltf = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name LocalAccountTokenFilterPolicy -EA SilentlyContinue).LocalAccountTokenFilterPolicy
$fwOut = (netsh advfirewall firewall show rule name="WinRM-HTTP") -join "`n"
$fwCustom = if ($fwOut -match 'No rules match') { 'None' } elseif ($fwOut -match 'Enabled:\s*Yes') { 'Yes' } elseif ($fwOut -match 'Enabled:\s*No') { 'No' } else { 'Unknown' }
$fwGroupOut = (netsh advfirewall firewall show rule group="Windows Remote Management") -join "`n"
$fwGroupEnabledCnt = ([regex]::Matches($fwGroupOut, 'Enabled:\s*Yes')).Count
$fwGroup = if ($fwGroupOut -match 'No rules match') { 'None' } elseif ($fwGroupEnabledCnt -gt 0) { "Yes($fwGroupEnabledCnt)" } else { 'No' }
$listenerOut = winrm enumerate winrm/config/Listener 2>$null
$listenerState = if ($listenerOut -match 'Listener') { 'Yes' } else { 'No' }
"""

        viewer_script = (r"""
# 고정 대기시간 대신 서비스가 실제로 Stopped 될 때까지 최대 40초 폴링한다 — 방화벽 규칙이
# 2종(netsh 2회)에 예약작업 등록/트리거까지 겹치면 STEP1~6 전체가 예상보다 오래 걸릴 수 있어서
# (실사용 중 확인됨), 고정 대기 시간을 잘못 추정하면 아직 서비스가 안 꺼진 시점에 "변경 후"를
# 읽어버려 Running 으로 잘못 표시되는 경합이 생긴다.
$deadline = (Get-Date).AddSeconds(40)
while ((Get-Date) -lt $deadline) {
    if ((Get-Service WinRM -EA SilentlyContinue).Status -eq 'Stopped') { break }
    Start-Sleep -Seconds 1
}
$scriptDir = "C:\Windows\Setup\Scripts"
$b = ConvertFrom-StringData (Get-Content "$scriptDir\winrm-before.txt" -Raw)
""" + state_snippet + r"""
$a = @{
    ServiceStatus = "$($svc.Status)"
    ServiceStartType = "$($svc.StartType)"
    TrustedHosts = $(if ([string]::IsNullOrEmpty($thReg)) { '(empty)' } else { $thReg })
    TokenFilterPolicy = $(if ($null -eq $ltf) { '(none)' } else { "$ltf" })
    FirewallCustom = $fwCustom
    FirewallGroup = $fwGroup
    Listener = $listenerState
}
# 항목별로 "정상 원복 조건"을 정의해서 항목마다 OK(초록)/FAIL(빨강+사유)로 표시한다 —
# Format-Table 은 색을 못 입혀서 한눈에 안 들어온다는 피드백으로, Write-Host 기반 체크리스트로 교체.
$checks = @(
    @{ Key='ServiceStatus';     Label='서비스 상태';       Ok={param($v) $v -eq 'Stopped'}; Desc='서비스가 아직 꺼지지 않았습니다' }
    @{ Key='ServiceStartType';  Label='시작 유형';         Ok={param($v) $v -eq 'Manual'};  Desc='시작유형이 Manual로 복원되지 않았습니다' }
    @{ Key='TrustedHosts';      Label='TrustedHosts';      Ok={param($v) $v -eq '(empty)'}; Desc='TrustedHosts가 비워지지 않았습니다' }
    @{ Key='TokenFilterPolicy'; Label='토큰필터정책';      Ok={param($v) $v -eq '(none)'};  Desc='레지스트리 키가 제거되지 않았습니다' }
    @{ Key='FirewallCustom';    Label='방화벽(전용규칙)';  Ok={param($v) $v -eq 'None'};    Desc='WinRM-HTTP 방화벽 규칙이 삭제되지 않았습니다' }
    @{ Key='FirewallGroup';     Label='방화벽(내장그룹)';  Ok={param($v) $v -eq 'No'};      Desc='내장 방화벽 그룹이 비활성화되지 않았습니다' }
    @{ Key='Listener';          Label='리스너';            Ok={param($v) $v -eq 'No'};      Desc='WinRM 리스너가 삭제되지 않았습니다' }
)

# 한글은 콘솔에서 2칸(전각) 폭을 차지하는데 PowerShell 문자열 패딩은 "글자 수"만 세기 때문에,
# 한글/영문이 섞인 라벨을 -f 포맷의 고정폭으로 맞추면 줄이 안 맞는다. 표시폭 기준으로 직접
# 패딩해서 표(박스 그리기 문자)의 세로줄이 전부 맞물리게 한다.
function Get-DispWidth([string]$s) {
    $w = 0
    foreach ($ch in $s.ToCharArray()) { if ([int][char]$ch -gt 0x2E80) { $w += 2 } else { $w += 1 } }
    return $w
}
function Pad-Disp([string]$s, [int]$width) {
    $w = Get-DispWidth $s
    if ($w -ge $width) { return $s }
    return $s + (' ' * ($width - $w))
}
$colW = @{ item = 16; before = 12; after = 12; status = 6 }
function Row([string]$item, [string]$before, [string]$after, [string]$status) {
    return "│ " + (Pad-Disp $item $colW.item) + " │ " + (Pad-Disp $before $colW.before) + " │ " +
        (Pad-Disp $after $colW.after) + " │ " + (Pad-Disp $status $colW.status) + " │"
}
$top    = "┌" + ("─" * ($colW.item+2)) + "┬" + ("─" * ($colW.before+2)) + "┬" + ("─" * ($colW.after+2)) + "┬" + ("─" * ($colW.status+2)) + "┐"
$mid    = "├" + ("─" * ($colW.item+2)) + "┼" + ("─" * ($colW.before+2)) + "┼" + ("─" * ($colW.after+2)) + "┼" + ("─" * ($colW.status+2)) + "┤"
$bottom = "└" + ("─" * ($colW.item+2)) + "┴" + ("─" * ($colW.before+2)) + "┴" + ("─" * ($colW.after+2)) + "┴" + ("─" * ($colW.status+2)) + "┘"

Clear-Host
Write-Host ""
Write-Host "  WinRM 비활성화 결과 (변경 전 / 후 비교)" -ForegroundColor Cyan
Write-Host ""
Write-Host ("  " + $top) -ForegroundColor DarkGray
Write-Host ("  " + (Row '항목' '변경 전' '변경 후' '상태')) -ForegroundColor White
Write-Host ("  " + $mid) -ForegroundColor DarkGray

$failCount = 0
$failNotes = @()
foreach ($c in $checks) {
    $bv = [string]$b[$c.Key]
    $av = [string]$a[$c.Key]
    $isOk = & $c.Ok $av
    $status = if ($isOk) { 'OK' } else { 'FAIL' }
    $color = if ($isOk) { 'Green' } else { 'Red' }
    Write-Host ("  " + (Row $c.Label $bv $av $status)) -ForegroundColor $color
    if (-not $isOk) {
        $failCount++
        $failNotes += ("  ✗ " + $c.Label + " — " + $c.Desc)
    }
}
Write-Host ("  " + $bottom) -ForegroundColor DarkGray
Write-Host ""

if ($failCount -eq 0) {
    Write-Host ("  ✓ 전체 정상 원복 확인됨 (" + $checks.Count + "/" + $checks.Count + ")") -ForegroundColor Green
} else {
    Write-Host ("  ✗ " + $failCount + "개 항목 원복 실패 (" + ($checks.Count - $failCount) + "/" + $checks.Count + " 정상)") -ForegroundColor Red
    Write-Host ""
    foreach ($n in $failNotes) { Write-Host $n -ForegroundColor Red }
}
Write-Host ""
Write-Host "  확인 후 이 창을 닫고 서버를 종료해 주세요." -ForegroundColor White
Write-Host ""
schtasks /delete /tn "ShowWinrmRevert" /f
""")
        UTF8_BOM = b"\xef\xbb\xbf"
        b64v = base64.b64encode(UTF8_BOM + viewer_script.encode("utf-8")).decode("ascii")

        script = (r"""
$scriptDir = "C:\Windows\Setup\Scripts"
New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null

# STEP 1. 변경 전 스냅샷 — key=value 줄로 저장(뷰어에서 ConvertFrom-StringData 로 다시 읽음)
""" + state_snippet + r"""
$before = @(
    "ServiceStatus=$($svc.Status)"
    "ServiceStartType=$($svc.StartType)"
    "TrustedHosts=$(if ([string]::IsNullOrEmpty($thReg)) { '(empty)' } else { $thReg })"
    "TokenFilterPolicy=$(if ($null -eq $ltf) { '(none)' } else { $ltf })"
    "FirewallCustom=$fwCustom"
    "FirewallGroup=$fwGroup"
    "Listener=$listenerState"
)
$before -join "`n" | Out-File "$scriptDir\winrm-before.txt" -Encoding UTF8 -Force

# STEP 2. 뷰어 스크립트 파일 작성 (base64 로 전달 — 인용부호/줄바꿈이 재들여쓰기로 깨지는 것 방지)
$vb = [System.Convert]::FromBase64String('__VIEWER_B64__')
[System.IO.File]::WriteAllBytes("$scriptDir\show-winrm-revert.ps1", $vb)

# STEP 3. 예약 작업 등록 — 대상 계정의 인터랙티브 세션(실제 로그인된 화면)에서 실행
# 주의: /it(Interactive) 예약작업은 /ru 로 지정한 계정이 "이 시점에 실제로 로그인되어 있어야"
# 실행된다 — 로그인되어 있지 않으면 작업이 등록/트리거는 되지만 조용히 실행되지 않는다
# (capture_device_manager 의 devmgmt 캡처와 동일한 제약). 그래서 등록/트리거 결과 코드와
# 현재 로그인 세션 목록을 진단정보로 같이 돌려받는다 — 뷰어 창이 안 뜨면 이걸로 원인 확인.
schtasks /create /tn "ShowWinrmRevert" /tr "powershell.exe -NoExit -ExecutionPolicy Bypass -WindowStyle Normal -File $scriptDir\show-winrm-revert.ps1" /sc once /st 23:59 /ru "__USER__" /it /rl HIGHEST /f | Out-Null
$createExit = $LASTEXITCODE

# STEP 4. 즉시 트리거 — 실제 화면 표시는 위 뷰어 스크립트의 Start-Sleep 13초 뒤에 이루어짐
schtasks /run /tn "ShowWinrmRevert" | Out-Null
$runExit = $LASTEXITCODE
$sessions = (query user 2>&1 | Out-String).Trim() -replace "`r?`n", " | "
$diag = "예약작업생성=$createExit(0=성공) 예약작업트리거=$runExit(0=성공) 대상계정=__USER__ " +
    "현재세션목록=[$sessions] (뷰어 창이 안 뜨면 대상계정이 세션목록에 Active 로 없는지 확인)"

# STEP 5. WinRM 및 관련 설정 원복
Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name LocalAccountTokenFilterPolicy -Force -EA SilentlyContinue
Get-NetFirewallRule -EA SilentlyContinue | Where-Object { $_.DisplayName -eq 'WinRM-HTTP' -or $_.Name -eq 'WinRM-HTTP' } | Remove-NetFirewallRule -EA SilentlyContinue
Disable-NetFirewallRule -DisplayGroup 'Windows Remote Management' -EA SilentlyContinue
Clear-Item -Path WSMan:\localhost\Client\TrustedHosts -Force -EA SilentlyContinue
winrm delete winrm/config/Listener?Address=*+Transport=HTTP 2>$null
Set-Service WinRM -StartupType Manual

# STEP 6. 서비스 자체는 지금 이 명령을 실어나르는 통신 수단이라 10초 뒤 지연 종료해야 하는데,
# Start-Process 로 띄운 자식 프로세스는 이 WinRM 원격 세션의 Job Object 에 묶여 있어서 세션이
# 끝나는 즉시(=이 스크립트 반환 직후) 같이 강제 종료돼버려 실제로는 실행되지 못한다(서비스
# 상태가 변경 후에도 계속 Running 으로 남아있던 원인 1). 세션 종료와 무관하게 살아남는 별도
# 예약작업(SYSTEM 권한 — 로그인 여부와도 무관)으로 절대시각을 지정해 예약한다.
# **주의(실사용 중 발견한 버그 2)**: 처음엔 schtasks.exe CLI(`/st HH:mm[:ss]` 문자열 + `/z`)로
# 만들었는데 이 환경에서 `/z`가 "ERROR: The task XML is missing a required element or attribute."로
# 곧바로 실패하는 걸 직접 재현 확인함(`/z` 없이도 `/st`가 분 단위까지만 지원돼서, 현재 분의
# 이미 지난 초를 목표로 잡으면 "오늘은 이미 지난 시각"으로 오판해 내일로 예약될 위험도 있었음).
# `New-ScheduledTaskTrigger -Once -At <DateTime>`(초 단위 정밀도, 문자열 왕복 없음)로 교체 —
# 8초 지연으로 실제 발동/성공까지 직접 테스트 검증함.
Unregister-ScheduledTask -TaskName "StopWinrmDelayed" -Confirm:$false -EA SilentlyContinue
$stopAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "Stop-Service WinRM -Force"'
$stopTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10)
$stopPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "StopWinrmDelayed" -Action $stopAction -Trigger $stopTrigger -Principal $stopPrincipal -Force | Out-Null
$beforeSummary = ($before -join ' | ')
"REVERT_SCHEDULED`n###BEFORE### $beforeSummary`n###DIAG### $diag"
""").replace("__USER__", u).replace("__VIEWER_B64__", b64v)
        # STEP1의 netsh 조회 2회 + STEP3/4/6의 schtasks 호출 3회가 겹치면서 실사용 중 20초를
        # 넘기는 게 확인됨(외부 프로세스 기동 오버헤드 누적) — 실제로는 정상 완료되는데 로컬
        # 타임아웃만 먼저 끊겨서 "Timeout" 오탐이 났었다. 여유있게 45초로 늘림.
        return self.run_remote(ip, script, timeout=45)

    def restart(self, ip):
        return self.run_remote(ip, "Restart-Computer -Force; 'RESTART_SENT'", timeout=15)

    def create_hdd_volumes(self, ip):
        script = r"""
$out = @()

# E, F 이미 존재하면 Skip
$existingEF = Get-Partition | Where-Object { $_.DriveLetter -in @("E","F") }
if ($existingEF) {
    foreach ($p in ($existingEF | Sort-Object DriveLetter)) {
        $out += "EXISTS: $($p.DriveLetter): Disk$($p.DiskNumber) $([math]::Round($p.Size/1GB,1))GB"
    }
    $out -join "|||"; return
}

# ── VM 판별 (Win32_ComputerSystem 제조사/모델 키워드)
$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
$vmKeys = @("virtual","vmware","virtualbox","qemu","kvm","xen","hyper-v","vbox","virtio")
$isVM = ($vmKeys | Where-Object {
    $cs.Manufacturer -ilike "*$_*" -or $cs.Model -ilike "*$_*"
}).Count -gt 0

# 비부팅/비시스템 논리 디스크 목록
$candidates = @(Get-Disk | Where-Object {
    $_.OperationalStatus -eq "Online" -and -not $_.IsBoot -and -not $_.IsSystem
} | Sort-Object Number)

if ($isVM) {
    # [VM 임시] 150GB 이상을 HDD로 간주 ← 실제 장비 납품 시 이 분기 삭제
    $out += "INFO: VM 환경 감지 [$($cs.Manufacturer) / $($cs.Model)] — 150GB 이상을 HDD로 간주"
    $targets = @($candidates | Where-Object { $_.Size -ge 150GB })
} else {
    # 베어메탈: Get-PhysicalDisk MediaType = HDD 필터
    $physDisks = Get-PhysicalDisk -ErrorAction SilentlyContinue
    $hddDevIds = @($physDisks | Where-Object { $_.MediaType -eq "HDD" } |
        Select-Object -ExpandProperty DeviceId)

    if ($hddDevIds.Count -gt 0) {
        $targets = @($candidates | Where-Object { $_.Number.ToString() -in $hddDevIds })
        $out += "INFO: 베어메탈 환경 — MediaType=HDD 디스크 $($targets.Count)개 감지"
    } else {
        $out += "WARN: MediaType 감지 불가 — 비부팅/비시스템 디스크 전체 대상"
        $targets = $candidates
    }
}

# 감지 결과 출력
foreach ($d in $candidates) {
    $flag = if ($d -in $targets) { "→ 대상" } else { "→ 제외" }
    $out += "SCAN: Disk$($d.Number) $([math]::Round($d.Size/1GB,0))GB $flag"
}

if ($targets.Count -eq 0) {
    $out += "NO_TARGET: 조건에 맞는 디스크 없음"
    $out -join "|||"; return
}

# 볼륨 생성
$letters = @("E","F"); $idx = 0
foreach ($disk in $targets) {
    if ($idx -ge $letters.Count) { break }
    $ltr = $letters[$idx]
    try {
        if ($disk.PartitionStyle -eq "RAW") {
            Initialize-Disk -Number $disk.Number -PartitionStyle GPT -ErrorAction Stop
        }
        New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter $ltr `
            -ErrorAction Stop | Out-Null
        Format-Volume -DriveLetter $ltr -FileSystem NTFS `
            -NewFileSystemLabel "" -Confirm:$false -ErrorAction Stop | Out-Null
        $out += "OK: Disk$($disk.Number) → ${ltr}: $([math]::Round($disk.Size/1GB,1))GB"
        $idx++
    } catch {
        $out += "ERR: Disk$($disk.Number) → ${ltr}: $($_.Exception.Message)"
        $idx++
    }
}
$out -join "|||" """
        return self.run_remote(ip, script, timeout=180)

    def pull_qc_from_share(self, ip, share_path, share_user, share_pass, dest_path):
        """원격 서버가 SMB 공유에서 QC 툴을 직접 가져옴. share_path 는 QC 툴 폴더(WindowsQC) 자체를
        가리키는 공유(QcShare)라서, 공유 루트의 내용물(*)을 dest_path 로 그대로 복사한다 — 예전
        외부 공유서버 구조(공유 루트 밑에 WindowsQC 하위폴더가 있던 것)와 달리 여기서
        "\\WindowsQC"를 한 번 더 붙이면 존재하지 않는 이중 경로가 되어 실패한다."""
        sp  = share_path.replace("'", "''")
        su  = share_user.replace("'", "''")
        spw = share_pass.replace("'", "''")
        dp  = dest_path.replace("'", "''")
        script = f"""
if (Test-Path '{dp}') {{ Remove-Item '{dp}' -Recurse -Force -EA SilentlyContinue }}
New-Item -ItemType Directory -Path '{dp}' -Force | Out-Null
# SMB 마운트 (기존 연결 먼저 해제)
& net use '{sp}' /delete /y 2>$null | Out-Null
$r = & net use '{sp}' '{spw}' /user:'{su}' 2>&1
if ($LASTEXITCODE -ne 0) {{ "PULL_ERR: net use failed — $r"; exit }}
Copy-Item -Path '{sp}\\*' -Destination '{dp}' -Recurse -Force -EA Stop
& net use '{sp}' /delete /y 2>$null | Out-Null
"PULL_OK: {dp}" """
        return self.run_remote(ip, script, timeout=120)

    def copy_to_remote(self, ip, local_path, remote_path):
        """원본은 로컬 PSSession + `Copy-Item -ToSession`(PowerShell 원격 세션의 파일전송
        기능, pywinrm엔 없음)으로 local_path의 *내용물*을 remote_path에 통째로 복사했다.
        pywinrm으로는 그 세션 기반 전송을 직접 못 쓰므로, 대신: 로컬에서 local_path를
        zip으로 묶고 → base64로 인코딩해 run_remote 스크립트에 실어 보내서 원격에 파일로
        쓰고 → 원격에서 Expand-Archive로 그 자리에서 풀게 한다. 결과(remote_path 안에
        local_path의 내용물이 그대로 풀려있음)는 원본과 동일하지만, WinRM 메시지 크기
        제한상 아주 큰 폴더(수백MB대)는 실패할 수 있다 — 이게 걱정되면 서버 설정에
        qc_share_user/qc_share_pass를 채워서 SMB 경로(pull_qc_from_share)를 우선 쓰는
        원래 경로를 타게 하는 게 낫다(이 메서드는 그 SMB 경로가 안 될 때의 대체 수단)."""
        try:
            zip_base = shutil.make_archive(
                str(Path(tempfile.mkdtemp()) / "qc_push"), "zip", root_dir=local_path)
            b64 = base64.b64encode(Path(zip_base).read_bytes()).decode("ascii")
        except Exception as e:
            return -1, "", f"COPY_ERR: local zip failed — {e}"
        finally:
            try:
                Path(zip_base).unlink(missing_ok=True)
            except Exception:
                pass
        rp = remote_path.replace("'", "''")
        script = f"""
try {{
    New-Item -ItemType Directory -Path '{rp}' -Force | Out-Null
    $tmpZip = Join-Path $env:TEMP ("qc_push_" + [guid]::NewGuid().ToString("N") + ".zip")
    [IO.File]::WriteAllBytes($tmpZip, [Convert]::FromBase64String('{b64}'))
    Expand-Archive -Path $tmpZip -DestinationPath '{rp}' -Force
    Remove-Item $tmpZip -Force -EA SilentlyContinue
    "COPY_OK"
}} catch {{ "COPY_ERR: $($_.Exception.Message)" }}"""
        return self.run_remote(ip, script, timeout=180)

    def run_qc_via_task(self, ip, remote_qc_path, username):
        task = f"QCRun_{int(time.time())}"
        rp = remote_qc_path.replace("'", "\\'")
        u  = username.replace("'", "\\'")
        # 맹목 Sleep 대신 ZIP 생성 감지로 완료 판단 (최대 360초)
        script = f"""
$taskName = '{task}'
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -EA SilentlyContinue
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "{rp}\\5-hardwareQC.ps1"' `
    -WorkingDirectory '{rp}'
$principal = New-ScheduledTaskPrincipal -UserId '{u}' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $taskName `
    -InputObject (New-ScheduledTask -Action $action -Principal $principal) -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
# 폴더 + ZIP 둘 다 생성될 때까지 5초 간격으로 감지 (최대 360초)
$deadline = (Get-Date).AddSeconds(360)
$found = $false
while ((Get-Date) -lt $deadline) {{
    Start-Sleep -Seconds 5
    $zip = Get-ChildItem -Path '{rp}' -File -EA SilentlyContinue |
        Where-Object {{ $_.Name -match '_\\d{{4}}-\\d{{2}}-\\d{{2}}_\\d{{6}}\\.zip$' }} |
        Select-Object -First 1
    $dir = Get-ChildItem -Path '{rp}' -Directory -EA SilentlyContinue |
        Where-Object {{ $_.Name -match '_\\d{{4}}-\\d{{2}}-\\d{{2}}_\\d{{6}}$' }} |
        Select-Object -First 1
    if ($zip -and $dir) {{ $found = $true; break }}
}}
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -EA SilentlyContinue
if ($found) {{ "QC_DONE" }} else {{ "QC_TIMEOUT" }} """
        return self.run_remote(ip, script, timeout=400)

    def find_qc_output(self, ip, remote_qc_path):
        rp = remote_qc_path.replace("'", "\\'")
        # 5-hardwareQC.ps1 은 실행 초반(결과 폴더 생성 직후)부터 그 폴더가 존재하고 스크립트가
        # 끝날 때까지 계속 그 안에 파일을 채워나간다 — ZIP(Compress-Archive)은 스크립트의 맨
        # 마지막 줄에서만 생성된다. 그래서 "폴더 존재"는 완료 신호가 될 수 없다(스크립트가
        # 한창 실행 중인데 완료로 오판해서 결과를 조기 복사 + 원격 폴더를 삭제해버리는 사고로
        # 이어짐 — 실제로 발생했던 버그). 오직 ZIP 파일 존재만을 완료 신호로 인정한다.
        script = f"""
$zip = Get-ChildItem -Path '{rp}' -File -ErrorAction SilentlyContinue |
    Where-Object {{ $_.Name -match '_\\d{{4}}-\\d{{2}}-\\d{{2}}_\\d{{6}}\\.zip$' }} |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($zip) {{ $zip.FullName }} else {{ "NOT_FOUND" }}"""
        return self.run_remote(ip, script, timeout=20)

    def copy_from_remote(self, ip, remote_path, local_path):
        """원본은 로컬 PSSession + `Copy-Item -FromSession`으로 remote_path(파일이든
        폴더든)를 local_path 밑에 그대로 복사했다. pywinrm 대체: 원격에서
        Compress-Archive로 그 자리에서 zip을 만들어(파일/폴더 둘 다 이 명령 하나로
        처리됨 — zip 안에 원본과 동일한 최상위 이름이 들어감) base64로 받아오고,
        로컬에서 그 zip을 local_path에 풀어서 동일한 결과 경로를 재현한다. 대용량
        결과물(WinRM 응답 크기 제한)엔 copy_to_remote와 같은 한계가 있음 — QC 결과
        ZIP 하나 정도 크기면 문제없이 동작함."""
        rp = remote_path.replace("'", "''")
        script = f"""
try {{
    if (-not (Test-Path '{rp}')) {{ "COPY_ERR: not found: {rp}"; exit }}
    $tmpZip = Join-Path $env:TEMP ("qc_pull_" + [guid]::NewGuid().ToString("N") + ".zip")
    Compress-Archive -Path '{rp}' -DestinationPath $tmpZip -Force
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($tmpZip))
    Remove-Item $tmpZip -Force -EA SilentlyContinue
    "COPY_B64:" + $b64
}} catch {{ "COPY_ERR: $($_.Exception.Message)" }}"""
        code, out, err = self.run_remote(ip, script, timeout=120)
        if not out.startswith("COPY_B64:"):
            return code, out, err
        try:
            zip_bytes = base64.b64decode(out[len("COPY_B64:"):])
            Path(local_path).mkdir(parents=True, exist_ok=True)
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_zip = tmp_dir / "qc_pull.zip"
            tmp_zip.write_bytes(zip_bytes)
            with zipfile.ZipFile(tmp_zip) as zf:
                zf.extractall(local_path)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return 0, "COPY_OK", ""
        except Exception as e:
            return -1, "", f"COPY_ERR: local extract failed — {e}"

    def devmgmt_work_dir(self, username):
        """캡처 작업용 원격 바탕화면 폴더 (작업 완료 후 삭제됨)"""
        return f"C:\\Users\\{username}\\Desktop\\DevCapture"

    def _screenshot_capture_code(self, wd, img_filename, status_filename):
        """화면 캡처 PowerShell 코드 — `Graphics.CopyFromScreen`으로 화면을 직접 캡처한다.
        예전엔 SendKeys로 PRTSC 키 입력을 흉내낸 뒤 클립보드를 읽는 방식이었는데, 부팅 직후
        뜨는 알림 토스트("Meet Now" 등)나 시계/캘린더 플라이아웃처럼 애니메이션이 있는 UI가
        떠 있으면 SendKeys 타이밍이 어긋나거나 클립보드가 제때 안 채워져서 캡처가 새까맣게
        나오는 문제가 있었다. 키 입력/클립보드에 의존하지 않고 화면을 직접 읽어오면 이 문제를
        피할 수 있다."""
        tpl = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
New-Item -Path "__WD__" -ItemType Directory -Force -EA SilentlyContinue | Out-Null
try {
    $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save("__WD__\__IMG__")
    $g.Dispose()
    $bmp.Dispose()
    "CAPTURE_OK" | Out-File "__WD__\__STATUS__" -Encoding UTF8
} catch {
    "ERR: $($_.Exception.Message)" | Out-File "__WD__\__STATUS__" -Encoding UTF8
}
"""
        return (tpl.replace("__WD__", wd)
                   .replace("__IMG__", img_filename)
                   .replace("__STATUS__", status_filename))

    def capture_device_manager(self, ip, username, is_win11=True):
        """Task1: devmgmt 열고 전체확장+맨위 → Task2: 화면 직접 캡처→PNG
        is_win11=False 면 Windows 10에서 검증된 예전 문구(OS버전 로그/루트아이템 로그 없음)를
        그대로 쓴다 — 기능은 동일하지만 "OS별로 정확히 그 버전 코드를 보낸다"는 원칙을 지킨다."""
        u  = username.replace("'", "\\'")
        ts = int(time.time())
        t1 = f"DevOpen_{ts}"
        t2 = f"DevCap_{ts}"
        wd = self.devmgmt_work_dir(username)
        w  = wd.replace("'", "\\'")

        # ── Task1 스크립트: devmgmt 열기 + SysTreeView32 를 Win32 메시지로 직접 제어해서
        # 필요한 4개 카테고리(네트워크/디스크/디스플레이/보안장치)만 펼치고 나머지는 접음.
        # 마우스 좌표 클릭/키보드 시뮬레이션 방식(예전 UIAutomation 기반)보다 화면 배율·창
        # 위치·포커스 상태에 영향을 받지 않아 훨씬 안정적 (한/영 OS 모두 텍스트 매칭 지원).
        expand_code_tpl = r"""
$log = @()
try {
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public struct RECT4 { public int Left; public int Top; public int Right; public int Bottom; }

public class TV4 {
    public delegate bool EnumChildProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumChildProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT4 lpRect);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll")] public static extern IntPtr VirtualAllocEx(IntPtr hProcess, IntPtr addr, uint size, uint allocType, uint protect);
    [DllImport("kernel32.dll")] public static extern bool VirtualFreeEx(IntPtr hProcess, IntPtr addr, uint size, uint freeType);
    [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr hProcess, IntPtr baseAddr, byte[] buffer, int size, out IntPtr written);
    [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr baseAddr, byte[] buffer, int size, out IntPtr read);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);

    [StructLayout(LayoutKind.Sequential)]
    public struct TVITEM {
        public uint mask; public IntPtr hItem; public uint state; public uint stateMask;
        public IntPtr pszText; public int cchTextMax; public int iImage; public int iSelectedImage;
        public int cChildren; public IntPtr lParam;
    }

    public const uint TVGN_ROOT = 0x0, TVGN_CHILD = 0x4, TVGN_NEXT = 0x1;
    public const uint TVIF_TEXT = 0x1;
    public const uint TVM_GETNEXTITEM = 0x110A;
    public const uint TVM_GETITEMW = 0x113E;
    public const uint TVM_EXPAND = 0x1102;
    public const uint TVE_EXPAND = 0x2, TVE_COLLAPSE = 0x1;
    public const uint PROCESS_ALL_ACCESS = 0x1F0FFF;
    public const uint MEM_COMMIT = 0x1000, MEM_RELEASE = 0x8000, PAGE_READWRITE = 0x04;

    public static IntPtr FoundTree = IntPtr.Zero;
    public static bool Callback(IntPtr hWnd, IntPtr lParam) {
        StringBuilder sb = new StringBuilder(256);
        GetClassName(hWnd, sb, 256);
        if (sb.ToString() == "SysTreeView32") { FoundTree = hWnd; return false; }
        EnumChildWindows(hWnd, Callback, IntPtr.Zero);
        return true;
    }
    public static IntPtr FindTreeView(IntPtr rootHwnd) {
        FoundTree = IntPtr.Zero;
        EnumChildWindows(rootHwnd, Callback, IntPtr.Zero);
        return FoundTree;
    }

    public static string GetItemText(IntPtr hwndTree, IntPtr hItem, IntPtr hProc) {
        int bufSize = 512;
        IntPtr remoteBuf = VirtualAllocEx(hProc, IntPtr.Zero, (uint)bufSize, MEM_COMMIT, PAGE_READWRITE);
        IntPtr remoteStruct = VirtualAllocEx(hProc, IntPtr.Zero, (uint)Marshal.SizeOf(typeof(TVITEM)), MEM_COMMIT, PAGE_READWRITE);

        TVITEM item = new TVITEM();
        item.mask = TVIF_TEXT; item.hItem = hItem; item.pszText = remoteBuf; item.cchTextMax = bufSize / 2;

        int structSize = Marshal.SizeOf(typeof(TVITEM));
        byte[] structBytes = new byte[structSize];
        IntPtr structPtr = Marshal.AllocHGlobal(structSize);
        Marshal.StructureToPtr(item, structPtr, false);
        Marshal.Copy(structPtr, structBytes, 0, structSize);
        Marshal.FreeHGlobal(structPtr);

        IntPtr written;
        WriteProcessMemory(hProc, remoteStruct, structBytes, structSize, out written);
        SendMessage(hwndTree, TVM_GETITEMW, IntPtr.Zero, remoteStruct);

        byte[] textBytes = new byte[bufSize];
        IntPtr read;
        ReadProcessMemory(hProc, remoteBuf, textBytes, bufSize, out read);
        string text = Encoding.Unicode.GetString(textBytes).TrimEnd('\0');

        VirtualFreeEx(hProc, remoteBuf, 0, MEM_RELEASE);
        VirtualFreeEx(hProc, remoteStruct, 0, MEM_RELEASE);
        return text;
    }
}
"@

$log += "PID=$PID SessionId=$((Get-Process -Id $PID).SessionId) User=$env:USERNAME OS=$([System.Environment]::OSVersion.VersionString)"
Get-Process -Name mmc -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
$proc = Start-Process "mmc.exe" -ArgumentList "devmgmt.msc" -PassThru
$hwndMain = [IntPtr]::Zero
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    $hwndMain = $proc.MainWindowHandle
    if ($hwndMain -ne [IntPtr]::Zero) { break }
}
$log += "mmc PID=$($proc.Id) hwndMain=$hwndMain (대기 ${i}x500ms)"
# Windows는 창을 마지막에 닫았을 때의 크기/위치를 기억했다가 다음에 열 때 그대로 복원한다 —
# 그래서 SW_MAXIMIZE 한 번만 호출하고 끝내면, 예전에 작은 창으로 닫은 적이 있을 경우 계속
# 작게 열린다(실사용 중 재현/확인됨). 좌표를 화면 전체 크기로 직접 강제 지정하고, 실제로
# 그렇게 됐는지 GetWindowRect 로 확인해서 안 맞으면 최대 3번까지 재시도한다.
if ($hwndMain -ne [IntPtr]::Zero) {
    $screenBounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $tries = 0
    for ($try = 0; $try -lt 3; $try++) {
        $tries = $try + 1
        [TV4]::ShowWindow($hwndMain, 9) | Out-Null
        [TV4]::SetForegroundWindow($hwndMain) | Out-Null
        Start-Sleep -Milliseconds 300
        [TV4]::SetWindowPos($hwndMain, [IntPtr]::Zero, $screenBounds.X, $screenBounds.Y, $screenBounds.Width, $screenBounds.Height, 0x0040) | Out-Null
        Start-Sleep -Milliseconds 500
        $rect4 = New-Object RECT4
        [TV4]::GetWindowRect($hwndMain, [ref]$rect4) | Out-Null
        $rw = $rect4.Right - $rect4.Left
        $rh = $rect4.Bottom - $rect4.Top
        if ([Math]::Abs($rw - $screenBounds.Width) -lt 10 -and [Math]::Abs($rh - $screenBounds.Height) -lt 10) { break }
    }
    $log += "mmc rect=$($rect4.Left),$($rect4.Top)-$($rect4.Right),$($rect4.Bottom) 화면=$($screenBounds.Width)x$($screenBounds.Height) 시도=$tries"
}
Start-Sleep -Milliseconds 500

$hwndTree = [TV4]::FindTreeView($hwndMain)
$log += "트리뷰: $hwndTree"

if ($hwndTree -ne [IntPtr]::Zero) {
    $treePid = 0
    [TV4]::GetWindowThreadProcessId($hwndTree, [ref]$treePid) | Out-Null
    $hProc = [TV4]::OpenProcess([TV4]::PROCESS_ALL_ACCESS, $false, $treePid)

    # 한글/영문 둘 다 매칭 (OS 언어 무관하게 동작)
    $keep = @(
        "네트워크 어댑터", "Network adapters",
        "디스크 드라이브", "Disk drives",
        "디스플레이 어댑터", "Display adapters",
        "보안 장치", "Security devices"
    )

    $rootItem = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_ROOT, [IntPtr]::Zero)
    $log += "루트 아이템: $rootItem"
    $item = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_CHILD, $rootItem)

    while ($item -ne [IntPtr]::Zero) {
        $text = [TV4]::GetItemText($hwndTree, $item, $hProc)
        if ($keep -contains $text) {
            [TV4]::SendMessage($hwndTree, [TV4]::TVM_EXPAND, [IntPtr][TV4]::TVE_EXPAND, $item) | Out-Null
            $log += "'$text' : 펼침"
        } else {
            [TV4]::SendMessage($hwndTree, [TV4]::TVM_EXPAND, [IntPtr][TV4]::TVE_COLLAPSE, $item) | Out-Null
            $log += "'$text' : 접음"
        }
        $item = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_NEXT, $item)
    }
    [TV4]::CloseHandle($hProc)
}
} catch {
    $log += "EXCEPTION: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
    $log += "STACK: $($_.ScriptStackTrace)"
}

$log | Out-File "__WD__\devmgr_debug.txt" -Force -Encoding UTF8
"""
        if not is_win11:
            expand_code_tpl = (expand_code_tpl
                .replace(
                    '$log += "PID=$PID SessionId=$((Get-Process -Id $PID).SessionId) User=$env:USERNAME OS=$([System.Environment]::OSVersion.VersionString)"',
                    '$log += "PID=$PID SessionId=$((Get-Process -Id $PID).SessionId) User=$env:USERNAME"')
                .replace(
                    '$rootItem = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_ROOT, [IntPtr]::Zero)\n'
                    '    $log += "루트 아이템: $rootItem"\n'
                    '    $item = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_CHILD, $rootItem)',
                    '$root = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_ROOT, [IntPtr]::Zero)\n'
                    '    $item = [TV4]::SendMessage($hwndTree, [TV4]::TVM_GETNEXTITEM, [IntPtr][TV4]::TVGN_CHILD, $root)'))
        expand_code = expand_code_tpl.replace("__WD__", wd)
        # ── Task2 스크립트: 화면 직접 캡처 → PNG 저장 (바탕화면 작업폴더)
        capture_code = self._screenshot_capture_code(wd, "devmgmt_capture.png", "devmgmt_status.txt")
        # 두 스크립트를 base64로 원격 저장
        # Windows PowerShell 5.1 은 BOM 없는 .ps1 파일을 UTF-8이 아니라 시스템 기본 코드페이지
        # (한글 Windows면 CP949)로 읽는다 — 그러면 스크립트 안의 한글 문자열("네트워크 어댑터" 등)이
        # 깨져서 트리 항목 텍스트와 매칭이 안 될 수 있다. UTF-8 BOM(EF BB BB)을 붙여써서 파일
        # 인코딩을 명확히 표시해야 한글이 깨지지 않는다.
        UTF8_BOM = b"\xef\xbb\xbf"
        b64e = base64.b64encode(UTF8_BOM + expand_code.encode("utf-8")).decode("ascii")
        b64c = base64.b64encode(UTF8_BOM + capture_code.encode("utf-8")).decode("ascii")
        _, wout, werr = self.run_remote(ip, f"""
New-Item -Path '{w}' -ItemType Directory -Force -EA SilentlyContinue | Out-Null
$be = [System.Convert]::FromBase64String('{b64e}')
[System.IO.File]::WriteAllBytes('{w}\\expand_devmgmt.ps1', $be)
$bc = [System.Convert]::FromBase64String('{b64c}')
[System.IO.File]::WriteAllBytes('{w}\\prtsc_capture.ps1', $bc)
Remove-Item '{w}\\devmgmt_status.txt' -EA SilentlyContinue
Remove-Item '{w}\\devmgr_debug.txt' -EA SilentlyContinue
"WRITE_OK" """, timeout=30)
        if "WRITE_OK" not in wout:
            return -1, "WRITE_ERR", werr

        run_tasks = f"""
$prin = New-ScheduledTaskPrincipal -UserId '{u}' -LogonType Interactive -RunLevel Highest

# Task1: devmgmt 열기 + 전체 확장
Unregister-ScheduledTask -TaskName '{t1}' -Confirm:$false -EA SilentlyContinue
$a1 = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{w}\\expand_devmgmt.ps1"'
Register-ScheduledTask -TaskName '{t1}' `
    -InputObject (New-ScheduledTask -Action $a1 -Principal $prin) -Force | Out-Null
Start-ScheduledTask -TaskName '{t1}'

# Task1 완료 신호(devmgr_debug.txt, 스크립트 맨 마지막 줄에서 생성)를 최대 30초까지 폴링.
# 예전엔 고정 12초만 기다렸는데, 장치관리자가 열리고 트리를 펼치는 데 그보다 오래 걸리는
# 느린 장비에서는 아직 안 열린 화면을 그대로 캡처해버리는 문제가 있었다.
$dl1 = (Get-Date).AddSeconds(30)
$t1Found = $false
while ((Get-Date) -lt $dl1) {{
    if (Test-Path '{w}\\devmgr_debug.txt') {{ $t1Found = $true; Start-Sleep -Milliseconds 500; break }}
    Start-Sleep -Milliseconds 500
}}
# Task1이 실제로 "실행됐는지"(LastTaskResult=0) 확인 — LogonType Interactive 작업은 해당 계정이
# 그 컴퓨터에 대화형으로 로그온되어 있지 않으면 작업 자체가 아예 실행되지 않을 수 있다.
# devmgr_debug.txt 가 안 생겼을 때 "왜"인지 눈으로 보이도록 결과 코드 + 현재 세션 목록을 남긴다.
$t1Result = (Get-ScheduledTaskInfo -TaskName '{t1}' -EA SilentlyContinue).LastTaskResult
$sessions = (query user 2>&1 | Out-String).Trim() -replace "`r?`n", " | "

# Task2: 화면 캡처
Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
$a2 = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{w}\\prtsc_capture.ps1"'
Register-ScheduledTask -TaskName '{t2}' `
    -InputObject (New-ScheduledTask -Action $a2 -Principal $prin) -Force | Out-Null
Start-ScheduledTask -TaskName '{t2}'

# 완료 감지 (최대 15초)
$dl = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $dl) {{
    Start-Sleep -Seconds 2
    $st = Get-Content '{w}\\devmgmt_status.txt' -EA SilentlyContinue
    if ($st -match 'CAPTURE_OK|ERR') {{ break }}
}}
Unregister-ScheduledTask -TaskName '{t1}' -Confirm:$false -EA SilentlyContinue
Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
Get-Process -Name mmc -EA SilentlyContinue | Stop-Process -Force
$status = Get-Content '{w}\\devmgmt_status.txt' -EA SilentlyContinue
$debug  = (Get-Content '{w}\\devmgr_debug.txt' -EA SilentlyContinue) -join ' / '
"$status`n###DIAG### Task1_찾음=$t1Found Task1_LastTaskResult=$t1Result(0=정상실행, 그외=미실행/실패) 세션목록=[$sessions] 트리로그=[$debug]" """
        return self.run_remote(ip, run_tasks, timeout=90)

    # ── 장치관리자 외 4종 캡처(내PC/디스크관리/시스템정보/인증정보) 공용 파이프라인 ──
    # devmgmt 는 SysTreeView32 를 펼치는 추가 단계가 있어 capture_device_manager 로 따로
    # 유지하고, 나머지 4종은 "대상 창 열기+최대화"만 다르고 화면 캡처/정리 흐름은 동일해서
    # 공용화했다. 신뢰성을 위한 장치관리자 캡처의 검증된 패턴(Interactive 예약작업 + 완료
    # 신호파일 폴링 + UTF-8 BOM + ###DIAG### 진단블록)을 그대로 재사용한다.
    _OPEN_SCRIPT_BODIES = {
        "mypc": r"""
Start-Process "explorer.exe" -ArgumentList "shell:MyComputerFolder"
$win = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    $shell = New-Object -ComObject Shell.Application
    # Windows 11: 탭 UI라도 Shell.Application.Windows()는 여전히 top-level explorer 창 단위로 잡힘.
    # LocationName이 비어있는 경우(탭 전환 중 등)까지 대비해 LocationURL(This PC의 CLSID)도 같이 확인
    $win = $shell.Windows() | Where-Object {
        $_.LocationName -eq "내 PC" -or $_.LocationName -eq "This PC" -or
        $_.LocationURL -like "*::{20D04FE0*"
    } | Select-Object -First 1
    if ($win) { break }
}
$__diag__ = "탐색기 창: $(if ($win) {'찾음'} else {'못찾음'}) (대기 ${i}x500ms)"
$hwnd = if ($win) { [IntPtr]$win.HWND } else { [IntPtr]::Zero }
__FORCE_FULLSCREEN__
$log += $__diag__
""",
        "diskmgmt": r"""
Get-Process -Name mmc -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
$proc = Start-Process "mmc.exe" -ArgumentList "diskmgmt.msc" -PassThru
$hwnd = [IntPtr]::Zero
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    $hwnd = $proc.MainWindowHandle
    if ($hwnd -ne [IntPtr]::Zero) { break }
}
$__diag__ = "diskmgmt PID=$($proc.Id) hwnd=$hwnd (대기 ${i}x500ms)"
__FORCE_FULLSCREEN__
$log += $__diag__
""",
        "about": r"""
Get-Process -Name SystemSettings -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Start-Process "ms-settings:about"
$hwnd = [IntPtr]::Zero
$cand = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    $cand = Get-Process -Name SystemSettings,ApplicationFrameHost -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle } |
        Select-Object -First 1
    if ($cand) { $hwnd = $cand.MainWindowHandle; break }
}
# 닫기 단계(별도 원격 실행, 이 스크립트의 변수는 못 씀)에서 정확히 이 프로세스만 골라서 닫을 수
# 있도록 PID를 파일로 남긴다 — 제목 문자열("설정"/"Settings")로 다시 찾으려 하면 실제 창
# 제목이 페이지별로 달라서("정보" 등) 안 맞아 닫기가 조용히 실패하는 문제가 있었다.
if ($cand) { "$($cand.Id)" | Out-File "__WD__\settings_pid.txt" -Force -Encoding UTF8 }
$__diag__ = "정보 hwnd=$hwnd 제목=$(if ($cand) { $cand.MainWindowTitle } else { '-' }) (대기 ${i}x500ms)"
__FORCE_FULLSCREEN__
$log += $__diag__
""",
        "activation": r"""
Get-Process -Name SystemSettings -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Start-Process "ms-settings:activation"
$hwnd = [IntPtr]::Zero
$cand = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    $cand = Get-Process -Name SystemSettings,ApplicationFrameHost -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle } |
        Select-Object -First 1
    if ($cand) { $hwnd = $cand.MainWindowHandle; break }
}
if ($cand) { "$($cand.Id)" | Out-File "__WD__\settings_pid.txt" -Force -Encoding UTF8 }
$__diag__ = "인증정보 hwnd=$hwnd 제목=$(if ($cand) { $cand.MainWindowTitle } else { '-' }) (대기 ${i}x500ms)"
__FORCE_FULLSCREEN__
$log += $__diag__
""",
    }

    # mypc 는 Windows 11에서 탐색기 탭 UI 대응(대기루프 연장 + LocationURL 매칭)을 추가했는데,
    # Windows 10 대상에서는 이 추가 매칭 조건이 오히려 엉뚱한 창을 잡는 등 실사용 중 캡처가
    # 원하는 대로 안 되는 문제가 확인되어, Windows 10에서는 원래 검증됐던 문구를 그대로 쓴다.
    _OPEN_SCRIPT_BODIES_WIN10 = {
        "mypc": r"""
Start-Process "explorer.exe" -ArgumentList "shell:MyComputerFolder"
$win = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    $shell = New-Object -ComObject Shell.Application
    $win = $shell.Windows() | Where-Object { $_.LocationName -eq "내 PC" -or $_.LocationName -eq "This PC" } | Select-Object -First 1
    if ($win) { break }
}
$__diag__ = "탐색기 창: $(if ($win) {'찾음'} else {'못찾음'}) (대기 ${i}x500ms)"
$hwnd = if ($win) { [IntPtr]$win.HWND } else { [IntPtr]::Zero }
__FORCE_FULLSCREEN__
$log += $__diag__
""",
    }

    # Windows/앱들은 "마지막으로 닫힐 때의 창 크기·위치"를 기억했다가 다음에 열 때 그대로
    # 복원한다 — 그래서 예전엔 한 번이라도 창을 작게 줄인 채로 닫으면 다음 캡처 때도 계속
    # 작은 창으로 열렸다(사용자가 직접 재현/확인). SW_MAXIMIZE 한 번만 호출하고 끝내는 대신,
    # 창 좌표를 화면 전체 크기로 명시적으로 강제 지정하고, 앱이 자기 마음대로 다시 원래
    # 기억해둔 크기로 되돌리는 경우에 대비해 실제 크기를 GetWindowRect 로 확인해서 안 맞으면
    # 최대 3번까지 재시도한다. mypc/diskmgmt/about/activation 4종 전부 이 로직을 공유한다.
    _FORCE_FULLSCREEN = r"""
if ($hwnd -ne [IntPtr]::Zero) {
    $screenBounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $tries = 0
    for ($try = 0; $try -lt 3; $try++) {
        $tries = $try + 1
        [NativeWin]::ShowWindow($hwnd, 9) | Out-Null
        [NativeWin]::SetForegroundWindow($hwnd) | Out-Null
        Start-Sleep -Milliseconds 200
        [NativeWin]::SetWindowPos($hwnd, [IntPtr]::Zero, $screenBounds.X, $screenBounds.Y, $screenBounds.Width, $screenBounds.Height, 0x0040) | Out-Null
        Start-Sleep -Milliseconds 400
        $rect = New-Object RECT
        [NativeWin]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
        $rw = $rect.Right - $rect.Left
        $rh = $rect.Bottom - $rect.Top
        if ([Math]::Abs($rw - $screenBounds.Width) -lt 10 -and [Math]::Abs($rh - $screenBounds.Height) -lt 10) { break }
    }
    $__diag__ += " rect=$($rect.Left),$($rect.Top)-$($rect.Right),$($rect.Bottom) 화면=$($screenBounds.Width)x$($screenBounds.Height) 시도=$tries"
}
"""

    # about/activation 은 제목 문자열로 다시 찾아서 닫으려 하면(예전 방식) 페이지별로 실제 창
    # 제목이 달라서("정보"/"활성화" 등, "설정"/"Settings"과 매칭 안 됨) 아무 것도 안 걸려서
    # 캡처 후 자동 닫기가 조용히 실패하는 문제가 있었다. 여는 단계에서 파일로 남겨둔 PID를
    # 읽어서 정확히 그 프로세스만 닫고, 혹시 그 파일이 없으면(예전 캡처 등) 이름 기준으로
    # SystemSettings 만 안전하게 폴백 종료한다 — ApplicationFrameHost 는 다른 UWP 앱(메일,
    # 스토어 등)도 같이 호스팅하므로 이름만으로 무조건 종료하면 안 된다.
    _SETTINGS_CLOSE = r"""$__pidFile = "__WD__\settings_pid.txt"
if (Test-Path $__pidFile) {
    $__spid = Get-Content $__pidFile -EA SilentlyContinue
    if ($__spid) { Stop-Process -Id $__spid -Force -EA SilentlyContinue }
    Remove-Item $__pidFile -EA SilentlyContinue
} else {
    Get-Process -Name SystemSettings -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
}"""

    _CLOSE_SCRIPTS = {
        "mypc": ('$sh = New-Object -ComObject Shell.Application; '
                 '$sh.Windows() | Where-Object { $_.LocationName -eq "내 PC" -or $_.LocationName -eq "This PC" } '
                 '| ForEach-Object { $_.Quit() }'),
        "diskmgmt": 'Get-Process -Name mmc -EA SilentlyContinue | Stop-Process -Force',
        "about": "__SETTINGS_CLOSE__",
        "activation": "__SETTINGS_CLOSE__",
    }

    def _build_open_script(self, kind, wd, is_win11=True):
        head = r"""
$log = @()
try {
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
public class NativeWin {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}
"@
$log += "PID=$PID SessionId=$((Get-Process -Id $PID).SessionId) User=$env:USERNAME OS=$([System.Environment]::OSVersion.VersionString)"
"""
        tail = r"""
} catch {
    $log += "EXCEPTION: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
    $log += "STACK: $($_.ScriptStackTrace)"
}
$log | Out-File "__WD__\open_debug.txt" -Force -Encoding UTF8
"""
        body_src = self._OPEN_SCRIPT_BODIES[kind]
        if not is_win11:
            body_src = self._OPEN_SCRIPT_BODIES_WIN10.get(kind, body_src)
        body = body_src.replace("__FORCE_FULLSCREEN__", self._FORCE_FULLSCREEN)
        return (head + body + tail).replace("__WD__", wd)

    def capture_window(self, ip, username, kind, is_win11=True):
        """장치관리자 외 4종 캡처(mypc/diskmgmt/about/activation) 공용 실행.
        is_win11 은 mypc 에서만 실제로 다른 문구를 고르는 데 쓰인다(_OPEN_SCRIPT_BODIES_WIN10
        참고) — 나머지 3종은 OS버전과 무관하게 이미 두 버전 모두 정상 동작해서 영향 없음."""
        u = username.replace("'", "\\'")
        ts = int(time.time())
        t1 = f"{kind}Open_{ts}"
        t2 = f"{kind}Cap_{ts}"
        wd = self.devmgmt_work_dir(username)
        w = wd.replace("'", "\\'")

        open_code = self._build_open_script(kind, wd, is_win11)
        capture_code = self._screenshot_capture_code(
            wd, f"capture_{kind}.png", f"capture_{kind}_status.txt")

        UTF8_BOM = b"\xef\xbb\xbf"
        b64e = base64.b64encode(UTF8_BOM + open_code.encode("utf-8")).decode("ascii")
        b64c = base64.b64encode(UTF8_BOM + capture_code.encode("utf-8")).decode("ascii")
        _, wout, werr = self.run_remote(ip, f"""
New-Item -Path '{w}' -ItemType Directory -Force -EA SilentlyContinue | Out-Null
$be = [System.Convert]::FromBase64String('{b64e}')
[System.IO.File]::WriteAllBytes('{w}\\open_{kind}.ps1', $be)
$bc = [System.Convert]::FromBase64String('{b64c}')
[System.IO.File]::WriteAllBytes('{w}\\capture_{kind}.ps1', $bc)
Remove-Item '{w}\\capture_{kind}_status.txt' -EA SilentlyContinue
Remove-Item '{w}\\open_debug.txt' -EA SilentlyContinue
"WRITE_OK" """, timeout=30)
        if "WRITE_OK" not in wout:
            return -1, "WRITE_ERR", werr

        run_tasks = f"""
$prin = New-ScheduledTaskPrincipal -UserId '{u}' -LogonType Interactive -RunLevel Highest

Unregister-ScheduledTask -TaskName '{t1}' -Confirm:$false -EA SilentlyContinue
$a1 = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{w}\\open_{kind}.ps1"'
Register-ScheduledTask -TaskName '{t1}' `
    -InputObject (New-ScheduledTask -Action $a1 -Principal $prin) -Force | Out-Null
Start-ScheduledTask -TaskName '{t1}'

$dl1 = (Get-Date).AddSeconds(30)
$t1Found = $false
while ((Get-Date) -lt $dl1) {{
    if (Test-Path '{w}\\open_debug.txt') {{ $t1Found = $true; Start-Sleep -Milliseconds 500; break }}
    Start-Sleep -Milliseconds 500
}}
$t1Result = (Get-ScheduledTaskInfo -TaskName '{t1}' -EA SilentlyContinue).LastTaskResult
$sessions = (query user 2>&1 | Out-String).Trim() -replace "`r?`n", " | "

Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
$a2 = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{w}\\capture_{kind}.ps1"'
Register-ScheduledTask -TaskName '{t2}' `
    -InputObject (New-ScheduledTask -Action $a2 -Principal $prin) -Force | Out-Null
Start-ScheduledTask -TaskName '{t2}'

$dl = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $dl) {{
    Start-Sleep -Seconds 2
    $st = Get-Content '{w}\\capture_{kind}_status.txt' -EA SilentlyContinue
    if ($st -match 'CAPTURE_OK|ERR') {{ break }}
}}
Unregister-ScheduledTask -TaskName '{t1}' -Confirm:$false -EA SilentlyContinue
Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
__CLOSE__
$status = Get-Content '{w}\\capture_{kind}_status.txt' -EA SilentlyContinue
$debug  = (Get-Content '{w}\\open_debug.txt' -EA SilentlyContinue) -join ' / '
"$status`n###DIAG### Task1_찾음=$t1Found Task1_LastTaskResult=$t1Result(0=정상실행, 그외=미실행/실패) 세션목록=[$sessions] 창로그=[$debug]" """
        close_script = (self._CLOSE_SCRIPTS[kind]
                        .replace("__SETTINGS_CLOSE__", self._SETTINGS_CLOSE)
                        .replace("__WD__", w))
        run_tasks = run_tasks.replace("__CLOSE__", close_script)
        return self.run_remote(ip, run_tasks, timeout=90)

    def capture_current_screen(self, ip, username):
        """지금 원격 데스크톱에 떠 있는 화면을 그대로 캡처 — 특정 창을 열거나 닫지 않고 있는
        그대로 화면을 직접 캡처한다. 서버실에 직접 안 들어가고도 "지금 이 시스템 화면이 뭘 하고
        있는지" 빠르게 확인하기 위한 용도라, 나머지 5종과 달리 여는/닫는 단계가 없다."""
        u = username.replace("'", "\\'")
        ts = int(time.time())
        t2 = f"ScreenCap_{ts}"
        wd = self.devmgmt_work_dir(username)
        w = wd.replace("'", "\\'")

        capture_code = self._screenshot_capture_code(
            wd, "capture_current.png", "capture_current_status.txt")

        UTF8_BOM = b"\xef\xbb\xbf"
        b64c = base64.b64encode(UTF8_BOM + capture_code.encode("utf-8")).decode("ascii")
        _, wout, werr = self.run_remote(ip, f"""
New-Item -Path '{w}' -ItemType Directory -Force -EA SilentlyContinue | Out-Null
$bc = [System.Convert]::FromBase64String('{b64c}')
[System.IO.File]::WriteAllBytes('{w}\\capture_current.ps1', $bc)
Remove-Item '{w}\\capture_current_status.txt' -EA SilentlyContinue
"WRITE_OK" """, timeout=30)
        if "WRITE_OK" not in wout:
            return -1, "WRITE_ERR", werr

        run_tasks = f"""
$prin = New-ScheduledTaskPrincipal -UserId '{u}' -LogonType Interactive -RunLevel Highest
Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
$a2 = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{w}\\capture_current.ps1"'
Register-ScheduledTask -TaskName '{t2}' `
    -InputObject (New-ScheduledTask -Action $a2 -Principal $prin) -Force | Out-Null
Start-ScheduledTask -TaskName '{t2}'

$dl = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $dl) {{
    Start-Sleep -Seconds 2
    $st = Get-Content '{w}\\capture_current_status.txt' -EA SilentlyContinue
    if ($st -match 'CAPTURE_OK|ERR') {{ break }}
}}
$t2Result = (Get-ScheduledTaskInfo -TaskName '{t2}' -EA SilentlyContinue).LastTaskResult
Unregister-ScheduledTask -TaskName '{t2}' -Confirm:$false -EA SilentlyContinue
$status = Get-Content '{w}\\capture_current_status.txt' -EA SilentlyContinue
"$status`n###DIAG### Task_LastTaskResult=$t2Result(0=정상실행, 그외=미실행/실패)" """
        return self.run_remote(ip, run_tasks, timeout=60)


# ═══════════════════════════════════════════════════════════════════
# 서버 모델
# ═══════════════════════════════════════════════════════════════════
class Server:
    def __init__(self, ip, serial):
        self.ip = ip
        self.serial = serial

    def to_dict(self):
        return {"ip": self.ip, "serial": self.serial}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("ip", ""), d.get("serial", ""))

