"""사이드바에 올라갈 수 있는 모든 액션의 정의.

여기는 "그 액션이 뭔지"(라벨/아이콘/실행방식)만 알고, "어느 업체가 어떤 걸 보는지"는
client_profiles.py 가 결정한다 — 새 업체가 생겨도 이 파일은 그대로 두고 client_profiles.py에
목록만 추가하면 된다.

kind:
  "batch"  — 클릭하면 (confirm 이 있으면 먼저 확인창을 띄우고) action 이름으로 runBatch() 호출.
             지금 대부분의 항목이 여기 해당.
  "custom" — 이름변경/정품인증/장치현황처럼 서버별 입력 폼이나 그리드 모달을 띄워야 하는
             소수만. handler 이름으로 web/app.js 의 SPECIAL_HANDLERS 테이블에서 찾아 실행한다.
"""

ACTION_REGISTRY = {
    # ── 조회 ──────────────────────────────────────────────
    "connect":          {"label": "연결확인",         "icon": "zap",            "kind": "batch",  "action": "batch_connect"},
    "devices":          {"label": "장치조회",         "icon": "cpu",            "kind": "batch",  "action": "batch_devices"},
    "all_devices":      {"label": "장치 현황",         "icon": "list",           "kind": "custom", "handler": "all_devices"},
    "activation_check": {"label": "인증확인",         "icon": "key",            "kind": "batch",  "action": "batch_activation_check"},

    # ── 작업 ──────────────────────────────────────────────
    "rename":           {"label": "이름변경",         "icon": "edit",           "kind": "custom", "handler": "rename"},
    "activate":         {"label": "정품인증",         "icon": "key",            "kind": "custom", "handler": "activate"},
    "qc":               {"label": "QC 스크립트 실행", "icon": "clipboardCheck", "kind": "batch",  "action": "batch_qc"},
    "time_sync":        {"label": "시간동기화",       "icon": "clock",          "kind": "batch",  "action": "batch_time_sync"},

    # ── 초기화 (공통) ─────────────────────────────────────
    "stop_winrm":       {"label": "WinRM 종료",       "icon": "plug",           "kind": "batch",  "action": "batch_stop_winrm",
                          "confirm": {"title": "WinRM 종료",
                                      "message": "선택한 서버의 WinRM을 원래 상태로 되돌리고 끕니다. "
                                                 "이후 원격 명령이 불가능하며, 결과는 서버 화면에 자동으로 표시됩니다."}},
    "cloudbase_init":   {"label": "CloudBase 초기화", "icon": "trash",          "kind": "batch",  "action": "batch_cloudbase_init"},

    # ── 기린 전용 ─────────────────────────────────────────
    "boot_folder":      {"label": "부팅디스크",       "icon": "disc",           "kind": "batch",  "action": "batch_boot_folder"},
    "volumes_check":    {"label": "볼륨확인",         "icon": "database",       "kind": "batch",  "action": "batch_volumes_check"},
    "volumes":          {"label": "HDD볼륨(E,F)",     "icon": "hardDrive",      "kind": "batch",  "action": "batch_volumes"},

    # ── SuperSolution(sangsang) 전용 ──────────────────────
    "open_rst":         {"label": "RST 창열기",       "icon": "eye",            "kind": "batch",  "action": "batch_open_rst"},
    "power_high":       {"label": "전원 고성능 변경", "icon": "power",          "kind": "batch",  "action": "batch_power_high"},
    "raid1":            {"label": "RAID 1 구성",      "icon": "hardDrive",      "kind": "batch",  "action": "batch_raid1",
                          "confirm": {"title": "RAID 1 구성",
                                      "message": "선택한 서버에서 RAID 1 볼륨을 생성합니다. "
                                                 "대상 디스크의 기존 데이터가 사라질 수 있으며 되돌릴 수 없습니다."}},
    "install_rst":      {"label": "RST 설치",         "icon": "hardDrive",      "kind": "batch",  "action": "batch_install_rst"},
    "temp_cleanup":     {"label": "Temp 초기화",      "icon": "trash",          "kind": "batch",  "action": "batch_temp_cleanup"},
}
