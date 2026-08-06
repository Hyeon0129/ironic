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
- **Inspect 액션 (2026-08-06 추가):** 사이드바 Manage↔Provide 사이. `/api/actions`가 `"inspect"`를 `manage`/`provide`와 동일하게 provision target으로 그대로 전달. 이게 없으면 노드 하드웨어 인벤토리(아래 Node Detail 모달의 CPU/Memory/Disk/NIC)가 절대 채워지지 않음 — inspect 없이는 Ironic이 인벤토리를 수집할 기회가 없음.
- **Node Detail 모달 (2026-08-06 추가):** 테이블 행 클릭(체크박스/버튼 제외) 시 알람 모달(`#alarmModal`)과 동일한 `modal-backdrop` 스타일로 열림(가로 스크롤 없음, `max-height:85vh`로 화면 정중앙 고정). 좌측 55% = 기본 정보 그리드(Node Name/UUID/Power/Provision/Maintenance/OS IP/BMC IP/CPU/Memory/Disk/NIC/Driver/Deployed Image/Last Error), 우측 45% = Recent History(각자 독립 세로 스크롤).
  - **하드웨어 정보는 `node.properties`가 아니라 `GET /v1/nodes/{uuid}/inventory`(API 마이크로버전 **1.81** 필요 — 전역 헤더는 1.80이라 이 호출에서만 오버라이드)에서 가져옴.** `inspect_interface: agent`(이 프로젝트 driver 설정) 조합에서는 inspect를 돌려도 `properties.cpus/memory_mb/local_gb`가 절대 채워지지 않는다는 걸 실제 노드로 확인함(inspect된 노드도 `properties`엔 `cpu_arch`만 남음) — `baremetal node inventory save`가 보여주는 것과 동일한 데이터를 이 엔드포인트가 REST로 제공해서 그걸 씀. 노드가 inspect 전이면 인벤토리가 비어서 "Not inspected yet"으로 표시됨(버그 아님).
  - **NIC의 IP는 표시 안 함:** inventory의 `interfaces[].ipv4_address`는 IPA 램디스크가 클리닝/인스펙션 당시 잡았던 IP라 배포 후 실제 OS IP와 다름(실제로 다른 값으로 확인됨) — 혼동 방지로 NIC 줄엔 이름+MAC만 표시, 현재 IP는 이미 있는 "OS IP" 필드(dnsmasq lease 기준)가 담당.
  - 용량 단위는 1024진법(GiB를 GB로 표기) 통일, 딱 안 맞아떨어지면 소수 1자리(`16.4 GB`), 맞아떨어지면 정수(`32 GB`, `50 GB`)로 표시.
  - 백엔드 `GET /api/nodes/{uuid}/detail`이 Ironic Node History API(`GET /v1/nodes/{uuid}/history`, 마이크로버전 1.78+, 이 프로젝트는 1.80 사용 중)도 같이 조회해서 `last_error`가 찍힐 때마다 쌓이는 이벤트 로그를 최근 15개까지 보여줌 — Ironic 자체엔 "배포 히스토리"라는 개념이 따로 없고, 이 History API가 사실상 제일 가까운 기능임. severity(ERROR/WARNING/INFO)별로 아이콘 글리프 자체가 다름(`getHistoryIcon()` in `js/main.js`).
- **Image & Assets 완전 삭제(2026-08-06):** 이미지는 이제 별도 프로그램으로 빌드하므로, 대시보드 내 OS Builder/Cloud-init 생성기/Asset Manager(업로드·삭제) 기능은 구버전 취급하여 프론트(`index.html`의 주석 처리된 사이드바 블록, `unifiedBuilderModal`, `assetManagerModal`)와 백엔드(`server/main.py`의 `/api/ssh-keys`, `/api/assets/build*`, `/api/assets/userdata`, `/api/assets`, `/api/assets/upload`, `/api/assets/{type}/{filename}`) 전부 제거. `js/actions.js`도 관련 죽은 함수(`startBuildImage`, `refreshAssets`, `addPartitionRow` 등) 다 정리됨. 이미지/유저데이터 파일은 이제 `/var/lib/ironic/httpboot/images`, `/var/lib/ironic/httpboot/user-data`에 외부에서 직접 배치하고, 대시보드는 `/api/deploy_files`로 그 디렉토리 목록만 읽어 Deploy 모달 드롭다운에 보여줌 — 이 목록/Deploy 흐름만 유지됨. (과거 `/builder`, `/cloud-init` 단독 페이지 라우트는 이미 2026-07-13에 제거된 상태였음.)

## 시크릿 관리
- `redfish_creds.json`(BMC 자격 증명), `ironic.conf`(DB/service-catalog 비밀번호 포함) — 과거 git에 평문으로 커밋되어 있었음. 2026-07-13에 `git rm --cached` + `.gitignore` 처리로 **향후 커밋부터** 추적 제외. 단, 과거 커밋 이력에는 여전히 남아있음 (이력까지 지우려면 `git filter-repo` 등으로 별도 재작성 필요 — 원격(`Hyeon0129/ironic`)에 force-push가 필요한 민감 작업이므로 사전 협의 후 진행).
- `uvicorn.log`, `server/__pycache__/*.pyc`도 함께 `.gitignore` 처리.
- **[2026-08-06] StaticFiles 마운트 실수로 레포 루트 전체가 8000번 포트에 그대로 노출되고 있었음(실제 서버에서 확인, curl로 200 응답 재현됨):** `server/main.py`가 `app.mount("/", StaticFiles(directory=BASE_DIR))`로 **레포 루트 전체**를 서빙하고 있어서, `.git/`(과거 커밋의 평문 비밀번호 포함), `server/main.py` 소스, `ironic.conf`, `redfish_creds.json`, `mac_list.txt`, 로그 파일까지 인증 없이 그냥 GET으로 받아갈 수 있었음. 프론트가 실제로 쓰는 건 `css/`, `js/`, `icon/`뿐이라 이 세 개만 명시적으로 마운트하도록 수정. **이 변경은 서버 프로세스 재시작 후에만 반영됨**(라우트/마운트는 import 시점에 결정되므로 정적 파일 내용 수정과 다르게 재시작이 필요) — 8번 항목(포트 8000 재시작 금지 규칙)에 따라 재시작은 사용자가 직접 진행. 앞으로 프론트 정적 자산 폴더가 추가되면 BASE_DIR 전체를 다시 마운트하지 말고 그 폴더만 개별로 추가할 것.

## 작업 이력
과거 작업 이력(UI 테마 조정, 빌더 페이지 개편 등)은 git log를 참고. 이 문서는 "현재 상태 + 왜 이렇게 되어 있는지"에 집중하고, 세부 변경 나열은 git 커밋 메시지에 위임한다.

- [2026-07-13] `GEMINI.md` → `CLAUDE.md` 마이그레이션. `bak_ironic/`, `builder.html`, `cloud-init.html`(및 `server/main.py`의 관련 죽은 라우트) 완전 삭제. `redfish_creds.json`/`ironic.conf`/`uvicorn.log`/`*.pyc`를 git 추적에서 제외(`.gitignore` + `git rm --cached`), 향후 커밋부터만 반영(과거 이력엔 비밀번호 잔존, 미해결).
- [2026-07-13] Deploy 로직 버그 수정 (`server/main.py` `/api/deploy`): `properties/root_device`를 `/dev/sda`로 강제 지정하던 코드를 제거 — VM(virtio) 등 sda가 없는 노드에서 `deploy.write_image` 단계가 "No suitable device was found for deployment using these hints {'name': '/dev/sda'}"로 실패하던 문제의 원인이었음. 이제 hint를 생략해 Ironic/IPA 자동 선택에 맡기고, 과거에 박힌 잔여 hint는 deploy 직전 조회해 자동 제거. Configdrive용 user-data 내용에서 선행 UTF-8 BOM(U+FEFF)도 제거하도록 보완.
- [2026-08-06] Image & Assets(OS Builder, Cloud-init 생성기, Asset Manager 업로드/삭제) 기능 완전 제거 — 이미지가 이제 별도 프로그램으로 빌드되어 대시보드 내 빌드 기능이 불필요해졌음. `index.html`의 주석 처리된 사이드바 블록과 `unifiedBuilderModal`/`assetManagerModal`, `server/main.py`의 `/api/ssh-keys`·`/api/assets/build*`·`/api/assets/userdata`·`/api/assets`·`/api/assets/upload`·`/api/assets/{type}/{filename}`, `js/actions.js`의 관련 함수들을 모두 삭제. `/api/deploy_files`(Deploy 모달의 이미지/유저데이터 드롭다운용 디렉토리 목록 조회)만 유지 — 파일은 이제 `/var/lib/ironic/httpboot/images`, `.../user-data`에 외부에서 직접 배치.
- [2026-08-06] Node Detail 모달 + Inspect 액션 추가, StaticFiles 마운트 취약점 수정 (자세한 내용은 위 "주요 기능"/"시크릿 관리" 섹션). 셋 다 라우트/마운트 레벨 변경이라 서버 재시작 후에만 반영됨.
