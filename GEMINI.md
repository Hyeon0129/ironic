# Ironic Dashboard Project (QC Core -> Ironic)

## 프로젝트 개요
이 프로젝트는 OpenStack Ironic(Bifrost 경량 환경)을 제어하여 베어메탈 서버의 발견, 전원 제어, 이미지 빌드, 프로비저닝 등을 관리하는 웹 대시보드입니다. 기존 하드웨어 QC용 도구에서 Ironic 전용 관리 도구로 전환되었습니다.

## 아키텍처 및 환경
- **프론트엔드:** Vanilla JS, HTML/CSS (기존 QC Core UI/UX 활용)
- **백엔드:** Python FastAPI
- **인프라:** OpenStack Bifrost (Standalone Ironic). CLI(`openstack` 등) 대신 100% REST API를 사용하여 Ironic과 통신합니다.
- **대상 환경:** 주로 실제 베어메탈(IPMI/Redfish 사용), 테스트용으로 VM 혼용 가능.

## 주요 결정 사항 및 제약 조건 (히스토리)
1. **VM 및 Redfish 예외:** VM은 IPMI/Redfish 테스트에서 제외하며, 베어메탈(Redfish 필수) 중심으로 스캔/등록합니다.
2. **Dnsmasq 재시작(Reload):** 노드가 등록되거나 삭제될 때 MAC 주소를 허용/제거하는 파일이 수정되며, 이때 즉각적으로 `systemctl restart dnsmasq`를 호출해 변경사항을 반영합니다.
3. **RAID 설정:** 테스트 환경이므로 RAID 1로 고정하여 사용합니다. (VM에서 디스크 개수 부족 등으로 실패하는 이슈는 테스트 환경이므로 무시)
4. **전원 상태 조회:** Ironic이 자체적으로 전원 상태를 동기화하기 전(초기 등록 직후 등)에만 Redfish로 직접 전원 상태를 조회하는 임시 방편을 허용합니다. 이후엔 Ironic의 `power_state`를 우선 신뢰합니다.
5. **Configdrive JSON 주입 방식:** Cloud-init을 위한 User-Data는 JSON 포맷(`{"user_data": "..."}`)으로 Ironic API를 통해 주입됩니다. 추후 네트워크나 메타데이터 이슈 발생 시 이 부분을 중점적으로 점검합니다.
6. **Deploy 시 RAM 부족 이슈 (VM):** VM 환경에서 배포 중 `No space left on device` 에러가 발생할 경우, 대상 VM의 RAM 크기를 확인해야 합니다. Ironic의 `direct` 배포 방식은 이미지를 대상 노드의 RAM(`/tmp`)에 다운로드하므로, 이미지 크기(예: 1.5GB)보다 큰 여유 RAM 공간(최소 4GB 이상 권장)이 필요합니다.
7. **백엔드 프로세스 관리 제한:** 8000번 포트는 사용자가 상시 모니터링 및 사용 중이므로, AI 에이전트는 파일 수정 후 `pkill`, `kill` 등을 이용한 프로세스 강제 종료나 서버 재시작을 수행하지 않습니다. 서비스 반영 여부는 사용자가 직접 관리합니다.

## 주요 기능 (메뉴 구성)
- **Ironic Actions (노드 액션):** 전원 관리, 노드 상태 제어(Manage, Provide, Deploy, Clean 등), 노드 이름 변경, 삭제 등.
- **Image & Assets (자산 관리):** OS Builder(이미지 빌더), User-Data Gen(Cloud-init 생성), Asset Manager(파일 업로드/관리). "Builder" 기능은 별도의 단독 웹 페이지(`/builder`)로 완전히 분리되었습니다.

## 작업 및 변경 이력
- [2026-05-06] 프로젝트 배경 및 목적, 작업 지침 인수인계서 작성 (`GEMINI.md` 생성).
- [2026-05-06] `server/main.py`: Dnsmasq 파일 조작 시 데몬 재시작(`systemctl restart dnsmasq`) 명령어 추가.
- [2026-05-06] `server/main.py`: 이미지 참조 경로를 `/var/lib/ironic/httpboot/image` 에서 `/var/lib/ironic/httpboot/images` 로 수정.
- [2026-05-06] 빌더 페이지(`/builder`) 개편 및 이미지 빌드 로직 보완:
  - `builder.html` 내 메인 패널의 좌우 길이를 Cloud-init 및 메인 페이지와 동일하게 맞춤.
  - 3열 레이아웃을 심플한 2열 레이아웃으로 간소화하고, 터미널 로그 화면을 파티션 설정 하단으로 재배치.
  - 백엔드(`server/main.py`)의 `disk-image-create` 실행 시 백엔드 콘솔과 `build.log`에 실시간 `tee` 출력 구현.
  - DIB (Diskimage-builder) 파티션 설정 오류(`Config entry not a dict: /`) 해결을 위해 **Nested YAML 포맷**을 직접 문자열로 환경변수에 주입하도록 수정 (CLI 환경과 동일하게 구현).
  - User-Data 패칭을 위해 부팅 파티션에 `mkfs_boot` 라벨을 강제 할당하도록 로직 보완.
  - HTML 파일 내 모든 JS/CSS 경로에서 버전 번호(`?v=...`)를 제거하여 브라우저 새로고침 시 항상 최신 파일이 반영되도록 변경.
  - 웹 새로고침 시에도 빌드 상태와 로그를 실시간으로 터미널 UI에서 유지하도록 `resumeBuildPolling` 캐싱 방지 및 안정성 강화.
  - "Additional Packages" 항목에 사용자 정의 패키지 입력을 위한 텍스트 필드 추가 및 `minimal` 버전 명시.
  - Asset Manager 리스트에서 `.qcow2`, `.raw`, `.yaml`, `.yml` 확장자만 정확하게 필터링하여 출력하도록 수정.
  - 빌드 중지(Stop) API 및 UI 버튼 기능 추가.
  - FastAPI 백엔드 재시작 및 포트(8000) 정상화 (8001번 포트 유지).
  - 사이드바 Asset Manager 새로고침 시 아이콘 회전 애니메이션 개선.
- [2026-05-06] 사이드바 Deploy 기능 복구 및 UI 연동:
  - `js/actions.js`에서 호출하는 `deployModal`이 모든 HTML(`index.html`, `builder.html`, `cloud-init.html`)에서 누락되었던 문제를 발견하고 모달 HTML 코드를 삽입하여 복구.
  - `Deploy` 클릭 시 이미지와 User-Data를 선택할 수 있는 팝업이 정상적으로 나타나도록 수정 완료.
  - 배포(Deploy) 시 이미지 선택 목록에서 `.qcow2`, `.raw` 이외의 불필요한 파일(`build.log`, `.sha256`)이 노출되지 않도록 백엔드 `get_deploy_files` API 필터링 조건 강화 및 프론트엔드 캐싱 방지 로직 적용.
