"""action_registry.py 와 같은 목적이지만 사이드바가 아니라 대시보드 표의 "선택적" 컬럼용.
전원/컴퓨터명/IP/Ping/WinRM/CPU/RAM/GPU/NIC/인증/QC/장치/캡처는 모든 업체 공통이라 표
자체(web/index.html)에 고정으로 박혀있고, 여기는 일부 업체에서만 필요한 컬럼만 등록한다."""

TABLE_COLUMN_REGISTRY = {
    "boot": {"label": "부팅", "icon": "disc"},
    "vol":  {"label": "볼륨", "icon": "database"},
}
