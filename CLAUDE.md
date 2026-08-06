# Ironic Dashboard Project (QC Core -> Ironic)

## 프로젝트 개요
OpenStack Ironic(Bifrost 경량 환경)을 제어하여 베어메탈 서버의 발견, 전원 제어, 이미지 빌드, 프로비저닝 등을 관리하는 웹 대시보드. 기존 하드웨어 QC용 도구에서 Ironic 전용 관리 도구로 전환됨.

## 아키텍처 및 환경
- **프론트엔드:** Vanilla JS, HTML/CSS (`index.html`, `js/`, `css/`)
- **백엔드:** Python FastAPI (`server/main.py`), 포트 8000
- **인프라:** OpenStack Bifrost (Standalone Ironic). CLI(`openstack` 등) 대신 100% REST API로 Ironic과 통신. Ironic API 세부 계약(엔드포인트, PATCH 포맷, provision/power state 전이 등)은 메모리의 `ironic-api-reference` 참고.
- **대상 환경:** 주로 실제 베어메탈(IPMI/Redfish 사용), 테스트용으로 VM 혼용 가능.
- **설정 파일:** `ironic.conf`(Ironic conductor 설정), `mac_list.txt`(등록 노드 MAC/IP 매핑), `dnsmasq.conf`/`dnsmasq.d/` — 이 파일들은 실제 배포 환경의 자격 증명/토폴로지를 담고 있으므로 `.gitignore` 처리되어 있음 (아래 "시크릿 관리" 참고).

## 주요 결정 사항 및 제약 조건
1. **VM 및 Redfish 예외:** VM은 IPMI/Redfish 테스트에서 제외, 베어메탈(Redfish 필수) 중심으로 스캔/등록.
2. **Dnsmasq 재시작(Reload):** 노드 등록/삭제 시 MAC 허용/제거 파일이 수정되며, 즉시 `systemctl restart dnsmasq` 호출해 반영.
3. **RAID 설정:** 테스트 환경이므로 RAID 1 고정. (VM 디스크 개수 부족 등으로 실패하는 이슈는 테스트 환경이므로 무시)
4. **전원 상태 조회:** Ironic이 전원 상태를 자체 동기화하기 전(초기 등록 직후 등)에만 Redfish 직접 조회를 임시로 허용. 이후엔 Ironic의 `power_state`를 우선 신뢰.
5. **Configdrive JSON 주입 방식:** Cloud-init User-Data는 JSON 포맷(`{"user_data": "..."}`)으로 Ironic API를 통해 주입. `server/main.py`가 `sudo cat`으로 읽은 파일 내용 맨 앞에 UTF-8 BOM(U+FEFF, Windows에서 작성된 `.ps1` 등에서 흔함)이 있으면 잘라내고 넣는다(2026-07-13 추가) — 안 하면 BOM이 스크립트 앞에 그대로 섞여 들어가 실행이 깨질 수 있음. 네트워크/메타데이터 이슈 발생 시 이 부분을 우선 점검.
6. **Deploy 시 RAM 부족 이슈 (VM):** VM 환경에서 배포 중 `No space left on device` 에러 발생 시 대상 VM의 RAM 크기 확인 필요. Ironic `direct` 배포 방식은 이미지를 대상 노드 RAM(`/tmp`)에 다운로드하므로, 이미지 크기(예: 1.5GB)보다 큰 여유 RAM(최소 4GB 이상 권장) 필요.
7. **Root device hint를 보내지 않음:** `/api/deploy`는 `properties/root_device`를 의도적으로 지정하지 않는다(2026-07-13부터). 예전엔 `{"name": "/dev/sda"}`로 하드코딩했었는데, VM(virtio → `/dev/vda`)이나 sda가 없는 베어메탈에서 `deploy.write_image` 단계가 "No suitable device was found for deployment using these hints {'name': '/dev/sda'}"로 실패했음. CLI 절차와 동일하게 hint를 생략해 Ironic/IPA가 적합한 디스크를 자동 선택하도록 함. 이 노드가 과거에 한 번이라도 이 대시보드로 deploy된 적이 있다면 그때 박힌 `root_device` 값이 노드에 남아있을 수 있어, deploy 직전에 조회해서 남아있으면 `remove` op로 지움.
8. **백엔드 프로세스 관리 제한:** 8000번 포트는 사용자가 상시 모니터링/사용 중이므로, 코드 수정 후에도 `pkill`, `kill` 등으로 프로세스를 강제 종료하거나 서버를 재시작하지 않는다. 서비스 반영은 사용자가 직접 관리.

## 주요 기능 (메뉴 구성)
- **Ironic Actions (노드 액션):** 전원 관리, 노드 상태 제어(Manage, Provide, Deploy, Clean 등), 노드 이름 변경, 삭제 등.
- **Image & Assets:** 사이드바에서 비활성화(주석 처리)된 상태. 과거 존재했던 `/builder`(OS Builder), `/cloud-init`(User-Data Gen) 단독 페이지와 관련 백엔드 라우트는 2026-07-13에 완전히 제거됨 — 필요 시 git 이력(커밋 이전 `builder.html`/`cloud-init.html`, `server/main.py`의 `/builder`·`/cloud-init` 라우트)에서 복원 가능.

## 시크릿 관리
- `redfish_creds.json`(BMC 자격 증명), `ironic.conf`(DB/service-catalog 비밀번호 포함) — 과거 git에 평문으로 커밋되어 있었음. 2026-07-13에 `git rm --cached` + `.gitignore` 처리로 **향후 커밋부터** 추적 제외. 단, 과거 커밋 이력에는 여전히 남아있음 (이력까지 지우려면 `git filter-repo` 등으로 별도 재작성 필요 — 원격(`Hyeon0129/ironic`)에 force-push가 필요한 민감 작업이므로 사전 협의 후 진행).
- `uvicorn.log`, `server/__pycache__/*.pyc`도 함께 `.gitignore` 처리.

## 작업 이력
과거 작업 이력(UI 테마 조정, 빌더 페이지 개편 등)은 git log를 참고. 이 문서는 "현재 상태 + 왜 이렇게 되어 있는지"에 집중하고, 세부 변경 나열은 git 커밋 메시지에 위임한다.

- [2026-07-13] `GEMINI.md` → `CLAUDE.md` 마이그레이션. `bak_ironic/`, `builder.html`, `cloud-init.html`(및 `server/main.py`의 관련 죽은 라우트) 완전 삭제. `redfish_creds.json`/`ironic.conf`/`uvicorn.log`/`*.pyc`를 git 추적에서 제외(`.gitignore` + `git rm --cached`), 향후 커밋부터만 반영(과거 이력엔 비밀번호 잔존, 미해결).
- [2026-07-13] Deploy 로직 버그 수정 (`server/main.py` `/api/deploy`): `properties/root_device`를 `/dev/sda`로 강제 지정하던 코드를 제거 — VM(virtio) 등 sda가 없는 노드에서 `deploy.write_image` 단계가 "No suitable device was found for deployment using these hints {'name': '/dev/sda'}"로 실패하던 문제의 원인이었음. 이제 hint를 생략해 Ironic/IPA 자동 선택에 맡기고, 과거에 박힌 잔여 hint는 deploy 직전 조회해 자동 제거. Configdrive용 user-data 내용에서 선행 UTF-8 BOM(U+FEFF)도 제거하도록 보완.
