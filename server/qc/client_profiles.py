"""업체(클라이언트)별 사이드바 구성 — 어떤 섹션에 action_registry.py 의 어떤 항목 id를
어느 순서로 보여줄지만 정의한다. 새 업체가 생기면 여기에 프로필 하나만 추가하면 되고,
액션 자체(구현/아이콘/확인문구)는 건드릴 필요 없다.

공통 항목(연결확인/장치조회/장치현황/인증확인, 이름변경/정품인증/QC스크립트실행/시간동기화,
WinRM종료, CloudBase초기화)은 모든 프로필에 그대로 반복해서 넣는다 — 프로필 하나만 봐도
그 업체 사이드바 전체가 눈에 보이는 게, "공통에서 상속하고 일부만 override"하는 것보다
30개로 늘어났을 때 오히려 추적하기 쉽다."""

CLIENT_PROFILES = {
    "sangsang": {
        "display_name": "상상솔루션",
        "sections": [
            {"label": "조회", "items": ["connect", "devices", "all_devices", "activation_check", "open_rst"]},
            {"label": "작업", "items": ["rename", "activate", "qc", "time_sync", "power_high", "raid1"]},
            {"label": "설치", "items": ["install_rst"]},
            {"label": "초기화", "items": ["temp_cleanup", "stop_winrm", "cloudbase_init"]},
        ],
        "table_columns": [],
    },
    "kirin": {
        "display_name": "기린",
        "sections": [
            {"label": "조회", "items": ["connect", "devices", "all_devices", "boot_folder", "volumes_check", "activation_check"]},
            {"label": "작업", "items": ["rename", "volumes", "activate", "qc", "time_sync"]},
            {"label": "초기화", "items": ["stop_winrm", "cloudbase_init"]},
        ],
        # 대시보드 표에도 부팅/볼륨 칸이 추가로 필요 (WinRM_Dashboard 원본 기준)
        "table_columns": ["boot", "vol"],
    },
}

DEFAULT_CLIENT_PROFILE = "sangsang"
