# 진행상황 & 이슈 로그

미니 3D 스캐너 프로젝트의 진행 상황, 이슈, 해결 방법을 날짜별로 기록합니다.
**새 항목은 맨 위에 추가**합니다 (최신 항목이 먼저 보이도록).

---

## 2026-09-15

### 진행 상황
- 프로젝트 방향 확정: 멀티뷰 스테레오 방식, 카메라 3대(서로 다른 기종 혼합), Python + OpenCV, 최종 출력은 포인트 클라우드(.ply)
- 초기 코드 스캐폴드 작성 완료
  - `src/utils/list_cameras.py` — 카메라 인덱스/해상도 탐색
  - `src/calibration/calibrate_single.py` — 카메라별 내부 파라미터 캘리브레이션
  - `src/calibration/calibrate_stereo.py` — 카메라 쌍 간 상대 위치(R, T) 캘리브레이션
  - `src/capture/capture_images.py` — 3대 동시 촬영
  - `src/reconstruction/triangulate.py` — 특징점 매칭 + 삼각측량 → 포인트 클라우드
  - `src/visualize/view_pointcloud.py` — Open3D 시각화/후처리
- 로드맵 문서(`프로젝트-로드맵.md`) 작성 및 프로젝트에 저장
- Windows(Python 3.13) 환경에서 `pip install -r requirements.txt` 시도 중 open3d 설치 실패 이슈 발견 → 아래 이슈 항목 참고, 당일 수정 완료
  - `requirements.txt`에서 open3d 제거 (핵심 파이프라인은 open3d 불필요하게 정리)
  - `requirements-viz.txt` 신설 (Open3D 전용, 버전 제약 명시)
  - `src/visualize/view_pointcloud_matplotlib.py` 추가: Open3D 없이 matplotlib만으로 포인트 클라우드 미리보기 가능
  - `view_pointcloud.py`는 open3d 미설치 시 친절한 안내 메시지 후 종료하도록 수정
  - README에 "Open3D 설치 문제" 섹션 추가 (원인, 임시 대체 방법, 별도 3.11/3.12 venv 만드는 법)
- `list_cameras.py --preview` 실행 결과, 카메라 3대 모두 인덱스 0/1/2로 정상 인식됨
  - cam0, cam1: 최대 해상도 640x480 (1280x720/1920x1080 요청해도 640x480으로 고정됨)
  - cam2: 1920x1080까지 지원
  - → 3대 공통 촬영 해상도를 **640x480**으로 통일하기로 결정 (cam0/1의 한계에 맞춤).
    `capture_images.py`, `calibrate_single.py`, `calibrate_stereo.py`의 기본 `--width/--height`를
    640x480으로 변경. 추후 품질을 더 올리고 싶으면 카메라 교체 또는 카메라별 다른 해상도를
    쓰도록 캡처 스크립트를 확장하는 것을 고려 (지금은 단순화를 위해 보류).
- 프린터가 없어 체커보드를 만들 수 없는 상황 확인 → 화면 표시 방식으로 대체
  - `src/utils/generate_checkerboard.py` 신설: 체커보드 패턴을 PNG로 생성 (기본 내부 코너 9x6)
  - `data/checkerboard_9x6.png` 생성 완료, 사용자에게 전달함
  - README에 "체커보드 준비 (프린터가 없을 때)" 섹션 추가: 화면에 띄우고 자로 실측 → `--square`에
    입력하는 절차, 화면 밝기 낮추기(글레어 방지) 팁, 나중에 인쇄할 때 주의사항(실제 크기 100% 인쇄) 포함
- **카메라 3대 개별(단일) 캘리브레이션 완료** — `calibrate_single.py`로 cam0/cam1/cam2 각각의
  intrinsics(K, dist) 산출 및 `.npz` 저장. RMS 재투영 오차 3대 모두 0.4대(px) — 기준(0.5 이하) 통과, 양호.
- 체커보드(화면 표시) 정사각형 한 칸 실측 완료: **30mm(3cm)**. 이 값을 앞으로 모든
  `--square` 옵션에 사용 (스테레오 캘리브레이션부터 실제 스케일에 영향을 주므로 중요).
- **스테레오 캘리브레이션 첫 시도 실패** — cam0-1 RMS 28.26, cam0-2 RMS 24.91 (정상 범위는
  1px 이하). 원인 분석 및 근본 수정 완료: 아래 이슈 항목 참고.
- **ChArUco로 전환 후에도 재시도 결과 RMS가 더 나빠짐** — cam0-1 RMS 62.51 (62쌍), cam0-2 RMS
  82.39 (59쌍). correspondence(ID 매칭) 자체는 합성 테스트로 이미 검증했었기 때문에, 원인은
  다른 곳(카메라 간 비동기 캡처로 인한 프레임 불일치 등)일 가능성이 높다고 보고 진단 도구 추가:
  아래 이슈 항목 참고.
- **GitHub 업로드 준비 중 진짜 원인 발견**: 사용자 컴퓨터(`C:\Temp\python\mini3d_scanner`)를
  연결해서 파일을 확인해보니 `calibrate_stereo.py`가 7,203바이트 — ChArUco/진단 기능이 들어간
  최신 버전(15,889바이트)이 아니라 **맨 처음의 일반 체커보드 버전 그대로**였고,
  `generate_charuco_board.py`, `data/charuco_10x7.png`도 아예 없었음. 즉 "ChArUco로 바꾼 뒤
  RMS가 더 나빠졌다"고 보고된 62.51/82.39는 사실 ChArUco가 아니라 **여전히 일반 체커보드
  버전**으로 캡처한 결과였음 (매번 보내드린 zip을 압축 해제해서 덮어쓰는 과정이 누락된 것으로
  보임). → 두 번째 "실패"는 ChArUco 방식의 실패가 아니라 아직 시도조차 안 된 것이었다는 뜻.
  파일 동기화 후 ChArUco 방식을 실제로 처음 시도하게 됨.

### 다음 작업 (To-do)
- [x] `python src/utils/list_cameras.py --preview`로 카메라 인덱스 ↔ 물리 카메라 매핑 확인 및 지원 해상도 점검
- [ ] cam0/cam1/cam2가 실제로 어떤 물리적 카메라(브랜드/위치)인지 기록해두기 (재연결 시 인덱스가 바뀔 수 있음에 유의)
- [x] `checkerboard_9x6.png`를 화면(모니터/태블릿/휴대폰)에 띄우고 정사각형 한 칸을 자로 실측 (mm)
- [x] 실측값으로 카메라별 단일 캘리브레이션 촬영 및 실행 (`calibrate_single.py --square <실측값>`, cam0/1/2 모두 완료)
- [x] 단일 캘리브레이션 RMS 재투영 오차값 기록 및 검토 (3대 모두 0.4대(px), 기준 0.5 이하 통과)
- [x] ~~카메라 쌍 스테레오 캘리브레이션 진행~~ → RMS 25~28로 실패, 원인(체커보드 코너 순서 모호성) 확인,
      ChArUco 보드 방식으로 `calibrate_stereo.py` 재작성 완료
- [x] ChArUco 보드로 스테레오 캘리브레이션 재촬영 및 실행 → RMS 62.51 / 82.39로 오히려 더 나쁨.
      `calibrate_stereo.py`에 프레임별 오차 진단(`stereoCalibrateExtended`) + 자동 이상치 제거 추가
- [ ] `--recompute-only`로 기존 62쌍/59쌍 이미지에 새 진단 기능 실행 → 이상치 제거로 RMS가
      2px 이하로 내려오는지 확인 → **보류: 캘리브레이션 품질 개선보다 전체 파이프라인을 먼저
      끝까지 한 번 돌려보기로 결정 (2026-09-15). 현재 저장된 stereo_0_1.npz/stereo_0_2.npz를
      그대로 쓰고, 결과 품질이 안 좋으면 나중에 이 단계로 돌아와서 보완**
- [ ] 스캔 대상 동시 촬영 (`capture_images.py --cams 0 1 2`)
- [ ] 포인트 클라우드 생성 (`triangulate.py`)
- [ ] 포인트 클라우드 확인 (`view_pointcloud_matplotlib.py` — Open3D 없이도 가능)
- [ ] 전체 파이프라인 1회 완주 후, 결과 보고 캘리브레이션/삼각측량 품질 개선 필요 여부 판단
- [x] 사용자 컴퓨터(`C:\Temp\python\mini3d_scanner`) 연결 후 최신 코드로 동기화 + GitHub 저장소
      (`hoooni10099/OpenCV_3D_Scanner`)에 최초 업로드
- [ ] **ChArUco 보드로 스테레오 캘리브레이션 실제로 재시도** (지금까지는 옛날 체커보드 버전으로
      실행되고 있었음이 확인됨 — 진짜 ChArUco 결과는 아직 없음)
- [ ] (위에서도 RMS 높으면) 카메라 미러링 여부 확인, 보드를 완전히 정지한 채로 재촬영
- [ ] (선택) Open3D 후처리가 필요해지면 Python 3.11/3.12 venv 만들어 `requirements-viz.txt` 설치

### 이슈 / 해결
| 상태 | 이슈 | 해결 방법 |
|---|---|---|
| 해결됨 | Windows, Python 3.13 환경에서 `pip install -r requirements.txt` 시 `open3d` 설치 실패 (`ERROR: No matching distribution found for open3d>=0.18.0`) | 원인 확인: Open3D 최신 릴리즈(0.19.0, 2025-01-08)는 Python 3.8~3.12까지만 지원하며 2026-09-15 기준 3.13/3.14 미지원 (github.com/isl-org/Open3D/issues/7318). `requirements.txt`에서 open3d 분리, matplotlib 기반 대체 뷰어 추가. 정식 Open3D 기능이 필요하면 별도 Python 3.11/3.12 venv에서 `requirements-viz.txt` 설치 권장. |
| 정보/해결됨 | `list_cameras.py` 실행 시 `WARN ... libavdevice`, `ERROR ... obsensor ... Camera index out of range` 로그 출력 | 원인: 기본 `--max-index 5`라서 존재하지 않는 인덱스 3~5까지 탐색을 시도하며 OpenCV 백엔드가 남기는 경고/에러 로그. 카메라는 정상적으로 0/1/2 3대 모두 인식됐으므로 실제 오류 아님(무시 가능). 신경 쓰이면 `--max-index 2`로 실행 범위를 좁히면 로그가 사라짐. |
| 확인 필요 | cam0/cam1이 640x480, cam2가 1920x1080까지 지원 — 3대 해상도가 서로 다름 | 지금은 640x480(cam0/1 한계)로 3대를 통일해 진행하기로 결정. 스캔 품질을 높이고 싶어지면 이후 카메라별 해상도를 다르게 쓰도록 캡처 스크립트 확장 검토. |
| 해결됨 | 프린터가 없어 종이 체커보드를 준비할 수 없음 | `generate_checkerboard.py`로 체커보드 PNG 생성 후 모니터/태블릿/휴대폰 화면에 띄워서 종이 대신 사용하기로 함. 화면마다 픽셀 밀도가 달라 자로 실측한 정사각형 크기(mm)를 `--square`에 입력해야 함. |
| 해결됨 | **스테레오 캘리브레이션 RMS가 25~28px로 폭발** (cam0-1: 28.26, cam0-2: 24.91 — 정상은 1px 이하). 단일 카메라 캘리브레이션은 3대 모두 0.4px대로 정상이었는데 스테레오만 비정상적으로 큼 | 원인: 일반 체커보드는 180도 회전해도 똑같이 생겨서, 서로 각도 차이가 큰(~50도) 두 카메라가 동시에 같은 체커보드를 보면 OpenCV의 findChessboardCorners가 두 이미지에서 코너를 반대 순서로 인식하는 경우가 흔함 → objpoints[i]가 imgpoints_a[i]/imgpoints_b[i]에서 서로 다른 물리적 코너를 가리키게 되어 계산이 틀어짐 (단일 카메라 캘리브레이션은 카메라 하나 안에서만 자기 일관적이면 되므로 이 문제와 무관). 호모그래피 기반으로 순서를 자동 판별하는 방법을 먼저 시도했으나, 합성 데이터로 검증한 결과 정사각형 격자는 반전된 순서도 호모그래피 상 완전히 유효해서 구분이 원천적으로 불가능함을 확인 (실패). 최종 해결: **ChArUco 보드**(체커보드+ArUco 마커)로 전환 — 각 코너가 고유 ID를 가져 시점에 관계없이 correspondence가 명확함. `src/utils/generate_charuco_board.py` 신설, `calibrate_stereo.py`를 ChArUco 검출(`cv2.aruco.CharucoDetector`) + ID 매칭 방식으로 전면 재작성. 합성 테스트로 서로 다른 두 시점 간 ID 매칭 정확도 서브픽셀(~0.2px) 수준 확인. 기존 단일 카메라 캘리브레이션(K, dist)은 보드 종류와 무관하게 유효하므로 재작업 불필요. 단, 스테레오 캘리브레이션은 ChArUco 보드로 재촬영 필요 (기존 체커보드 사진 재사용 불가). |
| 원인 파악됨 (재시도 대기) | **ChArUco로 바꾼 뒤에도 RMS가 더 나빠짐** (cam0-1: 62.51 → 62쌍, cam0-2: 82.39 → 59쌍). ID 기반 correspondence는 합성 테스트로 이미 정확함을 확인했었기 때문에(서브픽셀 수준), 코너 매칭 자체가 원인일 가능성은 낮음 | 처음엔 "카메라 비동기 캡처로 인한 타이밍 불일치"를 유력한 원인으로 보고 `calibrate_stereo.py`에 (1) `cv2.stereoCalibrateExtended`로 프레임별 재투영 오차 계산 + 임계값(`--outlier-threshold-px`, 기본 3px) 초과 프레임 자동 제거 반복 로직, (2) `cv2.CAP_PROP_BUFFERSIZE=1` 설정을 추가했음(합성 테스트로 유효성 검증 완료, 정상 프레임 사이 나쁜 프레임 1개를 정확히 찾아 제거하고 RMS를 0에 가깝게 회복). **그런데 GitHub 업로드 준비 중 사용자 컴퓨터를 확인해보니 진짜 원인이 따로 있었음**: 그 RMS 62.51/82.39는 ChArUco 버전이 아니라 여전히 **맨 처음의 일반 체커보드 버전**으로 캡처한 결과였음 (아래 새 이슈 항목 참고). 즉 ChArUco 방식은 아직 실제로 검증되지 않음 — 진단/이상치 제거 기능은 여전히 유용하지만, RMS 62/82의 직접 원인은 아니었을 가능성이 높음. 파일 동기화 완료 후 ChArUco로 재시도 예정. |
| 해결됨 | **사용자 컴퓨터의 로컬 프로젝트 폴더가 매번 전달한 zip 내용으로 갱신되지 않고 있었음** — `calibrate_stereo.py`가 7,203바이트(최초 일반 체커보드 버전 그대로, 최신본은 15,889바이트)였고 `generate_charuco_board.py`/`data/charuco_10x7.png`가 아예 존재하지 않았음. 즉 지금까지 보고된 두 번의 스테레오 캘리브레이션 실패(RMS 28/25, RMS 62/82)가 모두 실제로는 같은 구버전 스크립트로 실행된 것이었고, ChArUco 방식은 한 번도 실제로 테스트되지 않았음 | GitHub 업로드를 위해 사용자 컴퓨터(`C:\Temp\python\mini3d_scanner`)에 연결해 `device_list_dir`로 파일 크기를 대조하다가 발견. 최신 코드가 담긴 zip을 사용자 컴퓨터로 직접 전송한 뒤 그 자리에서 압축 해제(덮어쓰기)하여 동기화하고, 그 상태로 GitHub 저장소에 최초 업로드함. 이후로는 GitHub 저장소가 기준(source of truth)이 되므로, 다음부터는 새 코드를 받을 때 `git pull`로 동기화하면 이런 누락을 예방할 수 있음. |

