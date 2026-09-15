# 미니 3D 스캐너 (OpenCV 멀티뷰 스테레오)

카메라 3대(서로 다른 기종 웹캠)를 이용해 멀티뷰 스테레오 방식으로 물체를 스캔하고
포인트 클라우드(점군)를 생성하는 프로젝트입니다.

## 전체 파이프라인

1. **단일 카메라 캘리브레이션** (`src/calibration/calibrate_single.py`)
   각 카메라의 내부 파라미터(초점거리, 주점, 렌즈 왜곡계수)를 체커보드로 구합니다.
   카메라 기종이 다르므로 **카메라 3대 모두 개별로** 실행해야 합니다.

2. **스테레오(다중 카메라) 캘리브레이션** (`src/calibration/calibrate_stereo.py`)
   카메라 쌍이 동시에 찍은 **ChArUco 보드**(체커보드+ArUco 마커, 아래 "왜 ChArUco를 쓰는가"
   참고) 이미지로 두 카메라 간 상대 위치(회전 R, 이동 t)를 구합니다. 카메라 0을 기준(world
   origin)으로 잡고, (0↔1), (0↔2) 두 쌍을 각각 캘리브레이션합니다.

3. **동시 촬영** (`src/capture/capture_images.py`)
   3대의 카메라에서 최대한 동기화된 프레임을 캡처해 스캔 대상 이미지를 저장합니다.

4. **매칭 + 삼각측량 → 포인트 클라우드** (`src/reconstruction/triangulate.py`)
   카메라 쌍 사이의 대응점을 특징 매칭(ORB/SIFT)으로 찾고, 캘리브레이션 결과로 얻은
   투영행렬(projection matrix)로 삼각측량해 3D 점을 계산합니다. 두 쌍(0-1, 0-2)의
   결과를 하나의 좌표계(카메라 0 기준)로 합칩니다.

5. **시각화/저장** (`src/visualize/view_pointcloud.py`)
   Open3D로 포인트 클라우드를 보고 `.ply` 파일로 저장합니다. Open3D를 설치할 수 없는 환경(아래
   "Open3D 설치 문제" 참고)에서는 `src/visualize/view_pointcloud_matplotlib.py`로 임시 확인 가능합니다.

## 폴더 구조

```
mini3d_scanner/
├── requirements.txt
├── data/
│   ├── calibration_images/{cam0,cam1,cam2}/   # 체커보드 캘리브레이션 사진
│   ├── captures/                              # 실제 스캔 대상 촬영 이미지
│   └── output/                                # 캘리브레이션 결과(.npz), 포인트클라우드(.ply)
└── src/
    ├── utils/
    │   ├── list_cameras.py
    │   ├── generate_checkerboard.py     # 단일 캘리브레이션용 체커보드 이미지 생성
    │   └── generate_charuco_board.py    # 스테레오 캘리브레이션용 ChArUco 보드 이미지 생성
    ├── calibration/
    │   ├── calibrate_single.py
    │   └── calibrate_stereo.py
    ├── capture/
    │   └── capture_images.py
    ├── reconstruction/
    │   └── triangulate.py
    └── visualize/
        ├── view_pointcloud.py               # Open3D 필요 (Python 3.12 이하)
        └── view_pointcloud_matplotlib.py     # Open3D 없이 쓰는 대체 뷰어
```

## 하드웨어 팁 (서로 다른 웹캠 3대 혼합 환경)

- 3대 모두 **같은 해상도/프레임레이트**로 설정하는 것을 강력 추천합니다 (`capture_images.py`의
  `TARGET_WIDTH/HEIGHT/FPS`). 기종이 다르면 자동 노출/화이트밸런스도 다르게 동작하므로,
  가능하면 수동 노출로 고정하세요 (`cv2.CAP_PROP_AUTO_EXPOSURE`).
- 카메라 배치는 물체를 중심으로 정삼각형에 가깝게, 카메라 사이 각도는 30~60도 정도가
  스테레오 매칭이 잘 되는 범위입니다 (너무 벌어지면 대응점을 찾기 어렵습니다).
- 체커보드는 인쇄해서 평평한 판에 붙이고, 캘리브레이션 촬영 시 화면 전체 영역(가장자리 포함)을
  다양한 각도/거리로 20장 이상 찍는 것을 권장합니다.
- `cv2.VideoCapture(index)`의 index는 OS/USB 포트에 따라 바뀔 수 있으니, 실행 전
  `list_cameras()` 유틸(각 스크립트 상단 주석 참고)로 인덱스를 먼저 확인하세요.

## 빠른 시작

```bash
pip install -r requirements.txt

# 0) 카메라 인덱스/해상도 확인 (어떤 인덱스가 어떤 물리 카메라인지 --preview로 확인 권장)
python src/utils/list_cameras.py --preview

# 1) 카메라별 캘리브레이션 사진 촬영 (체커보드 들고 다양한 각도로)
python src/calibration/calibrate_single.py --cam 0 --out data/output/cam0_intrinsics.npz
python src/calibration/calibrate_single.py --cam 1 --out data/output/cam1_intrinsics.npz
python src/calibration/calibrate_single.py --cam 2 --out data/output/cam2_intrinsics.npz

# 2) ChArUco 보드 생성 (화면에 띄우고 자로 실측, 아래 "왜 ChArUco를 쓰는가" 참고) 후
#    카메라 쌍 스테레오 캘리브레이션 (0-1, 0-2 동시 촬영). --square는 실측한 mm 값으로 교체.
python src/utils/generate_charuco_board.py --out data/charuco_10x7.png
python src/calibration/calibrate_stereo.py --cams 0 1 --square 30 \
    --intr0 data/output/cam0_intrinsics.npz --intr1 data/output/cam1_intrinsics.npz \
    --out data/output/stereo_0_1.npz
python src/calibration/calibrate_stereo.py --cams 0 2 --square 30 \
    --intr0 data/output/cam0_intrinsics.npz --intr1 data/output/cam2_intrinsics.npz \
    --out data/output/stereo_0_2.npz

# 3) 스캔 대상 동시 촬영
python src/capture/capture_images.py --cams 0 1 2 --out data/captures/session1

# 4) 포인트 클라우드 생성
python src/reconstruction/triangulate.py --session data/captures/session1 \
    --stereo01 data/output/stereo_0_1.npz --stereo02 data/output/stereo_0_2.npz \
    --out data/output/pointcloud.ply

# 5) 시각화 (Open3D 설치된 경우)
python src/visualize/view_pointcloud.py --ply data/output/pointcloud.ply
# 또는 Open3D 없이 (아래 "Open3D 설치 문제" 참고)
python src/visualize/view_pointcloud_matplotlib.py --ply data/output/pointcloud.ply
```

## Open3D 설치 문제 (Python 3.13/3.14)

Open3D 최신 버전(0.19.0, 2025-01-08 릴리즈)은 **Python 3.8~3.12까지만 지원**합니다.
Python 3.13/3.14에서는 `pip install open3d`가 `No matching distribution found` 오류로 실패합니다
(2026-09-15 기준 미해결, 관련 이슈: https://github.com/isl-org/Open3D/issues/7318).

- `requirements.txt`에서 open3d를 뺐기 때문에, **카메라 인식/캘리브레이션/촬영/삼각측량까지는
  Python 3.13에서도 그대로 진행 가능**합니다.
- 포인트 클라우드를 빠르게 확인만 하고 싶다면 Open3D 없이 동작하는
  `src/visualize/view_pointcloud_matplotlib.py`를 쓰세요 (노이즈 제거 등 후처리는 미지원).
- 노이즈 제거/다운샘플링/메쉬 변환 등 Open3D의 후처리 기능이 필요해지면, 이 프로젝트와는
  별도로 **Python 3.11 또는 3.12 가상환경**을 만들어 그 안에서만 `pip install -r requirements-viz.txt`를
  실행하세요. Windows에서 Python 3.11/3.12가 이미 설치돼 있다면:
  ```powershell
  py -3.11 -m venv .venv311
  .venv311\Scripts\activate
  pip install -r requirements.txt -r requirements-viz.txt
  ```
  설치돼 있지 않다면 python.org에서 3.11 또는 3.12 설치 프로그램을 받아 설치한 뒤 위 명령을 실행하세요.

## 체커보드 기본 설정

기본값은 **내부 코너 9x6, 정사각형 한 변 25mm**입니다 (`--cols 9 --rows 6 --square 25`로 변경 가능).
사용하는 체커보드 실측 치수에 맞게 반드시 조정하세요. 실제 크기와 다르면 전체 스케일이 어긋납니다.

## 체커보드 준비 (프린터가 없을 때 — 화면에 띄워서 사용)

프린터가 없어도 모니터/태블릿/휴대폰 화면에 체커보드 이미지를 띄워서 종이 대신 쓸 수 있습니다.
캘리브레이션 알고리즘은 흑백 격자 패턴만 인식하므로 화면이든 종이든 상관없습니다.

```bash
python src/utils/generate_checkerboard.py --out data/checkerboard_9x6.png
```

1. 생성된 `checkerboard_9x6.png`를 화면에 띄웁니다 (이미지 뷰어의 "실제 크기/100%" 옵션 사용,
   또는 그냥 전체화면으로 띄워도 됩니다 — 어차피 3번에서 실측하므로 배율은 중요하지 않습니다).
2. **자로 정사각형 한 칸의 실제 길이(mm)를 측정**합니다. 화면마다 픽셀 밀도가 다르므로 이 실측값이
   정확도를 좌우합니다. 화면을 확대/축소했다면 다시 측정하세요.
3. 측정한 값을 캘리브레이션 스크립트의 `--square`에 그대로 입력합니다.
   예: 측정값이 20.3mm이면 `--square 20.3`.
4. 화면(노트북/태블릿/휴대폰)을 손에 들고 카메라 앞에서 다양한 각도/거리로 보여주며 촬영합니다.
   종이와 달리 화면 자체를 구부릴 수는 없으니, 대신 화면을 든 채로 위치와 각도를 바꿔가며
   화면 전체 영역(가장자리 포함)에서 골고루 20장 이상 찍으세요.
5. 화면 밝기를 약간 낮추면 카메라에 하얀 사각형이 번지는 것(블루밍/글레어)을 줄일 수 있습니다.
6. 카메라 3대가 동시에 봐야 하는 `calibrate_stereo.py` 단계에서도 화면 하나로 그대로 사용 가능합니다
   (화면을 든 채로 두 카메라가 동시에 보이는 위치에 놓으면 됩니다).

나중에 프린터를 쓸 수 있게 되면, `checkerboard_9x6.png`를 인쇄하되 **"실제 크기(100%)"로 인쇄**하고
("전체 페이지에 맞추기" 금지) 인쇄물도 자로 재확인한 뒤 `--square` 값을 갱신하세요.

## 왜 스테레오 캘리브레이션에는 일반 체커보드 대신 ChArUco 보드를 쓰는가

2026-09-15에 실제로 겪은 문제입니다: 일반 체커보드로 `calibrate_stereo.py`를 실행했더니
RMS 재투영 오차가 25~28px씩 나왔습니다 (정상 범위는 1px 이하). 원인을 찾아보니, **일반
체커보드는 180도 회전해도 똑같이 생겨서**, 카메라 0과 카메라 1처럼 서로 각도 차이가 큰
(약 50도) 두 카메라가 동시에 같은 체커보드를 보면 OpenCV가 두 이미지에서 코너를 정반대
순서로 인식하는 경우가 흔하다는 걸 확인했습니다. 이러면 "카메라0의 3번 코너"와
"카메라1의 3번 코너"가 실제로는 서로 다른 물리적 점을 가리키게 되어 계산이 완전히
틀어집니다. (참고로 순수 기하학적 방법, 예를 들어 호모그래피로 두 순서 중 뭐가 맞는지
판별하는 방법도 시도해봤지만, 정사각형 격자는 반전된 순서도 "수학적으로 유효한" 격자라서
구분이 불가능하다는 것도 확인했습니다 — 단일 카메라 캘리브레이션은 카메라 하나 안에서만
자기 일관적이면 되므로 이 문제와 무관하게 항상 정상적으로 낮은 RMS가 나왔습니다.)

**ChArUco 보드**(체커보드 칸 사이사이에 고유 ID를 가진 작은 ArUco 마커가 있는 보드)를 쓰면
각 코너가 "몇 번 코너인지"가 시점에 관계없이 명확해져서, 두 카메라에서 같은 ID로 검출된
코너끼리만 짝지으면 이 문제 자체가 사라집니다. 그래서 `calibrate_stereo.py`는 이제 ChArUco
보드를 사용하도록 변경했습니다:

```bash
python src/utils/generate_charuco_board.py --out data/charuco_10x7.png
```

사용법은 기존 체커보드와 거의 같습니다 (화면에 띄우고 자로 정사각형 한 칸을 실측 → `--square`에
입력). 이미 완료하신 **단일 카메라 캘리브레이션(cam0/1/2의 K, dist)은 그대로 유효**하니
다시 하실 필요 없습니다 — 어떤 보드로 구했는지와 무관한 값입니다. 다만 **스테레오 캘리브레이션은
ChArUco 보드로 다시 촬영**해야 합니다 (기존 체커보드 사진으로는 ChArUco 마커가 없어서 검출이
안 됩니다).

## ChArUco로 바꿨는데도 RMS가 높게 나온다면 (2026-09-15 실제 사례)

ChArUco로 바꾼 뒤에도 RMS가 수십 px로 나오는 경우가 있었습니다. 원인은 correspondence
자체(코너 순서)가 아니라, **두 카메라가 하드웨어적으로 동기화돼 있지 않다는 것**이었습니다.
`cap_a.grab(); cap_b.grab()`을 연달아 불러도 두 카메라의 내부 버퍼링/노출 타이밍 차이 때문에
실제로는 몇십 ms씩 어긋난 순간을 캡처할 수 있고, 그 사이에 보드가 조금이라도 움직였다면
"동시에 찍은 척" 하는 두 이미지가 실제로는 다른 순간의 보드 위치를 담게 됩니다 —
correspondence(ID)는 정확해도 기하학적으로 안 맞는 것이죠.

이를 위해 `calibrate_stereo.py`에 두 가지를 추가했습니다.

1. **프레임별 오차 진단 + 자동 이상치 제거**: `cv2.stereoCalibrateExtended`로 각 촬영 쌍의
   개별 재투영 오차를 계산하고, 오차가 `--outlier-threshold-px`(기본 3px)보다 큰 프레임을
   자동으로 제외한 뒤 재계산합니다 (최대 `--max-outlier-rounds`회 반복). 합성 데이터로 검증한
   결과, 나머지가 정상이라면 이상한 프레임 1개만 있어도 정확히 찾아내 제거하고 RMS를
   0에 가깝게 회복시키는 것을 확인했습니다.
2. **캡처 버퍼 축소**: 라이브 캡처 시 `cv2.CAP_PROP_BUFFERSIZE`를 1로 낮춰서, 오래된(지연된)
   프레임이 아니라 최신 프레임을 읽도록 했습니다.

**지금 바로 해볼 수 있는 것**: 이미 촬영해두신 이미지가 있다면 다시 찍지 않고 `--recompute-only`로
새 진단 기능만 먼저 확인할 수 있습니다.

```bash
python src/calibration/calibrate_stereo.py --cams 0 1 --square <실측값> --recompute-only \
    --intr0 data/output/cam0_intrinsics.npz --intr1 data/output/cam1_intrinsics.npz \
    --out data/output/stereo_0_1.npz
```

실행하면 프레임별 오차가 큰 순서대로 출력되고, 이상치를 제거하면서 RMS가 어떻게 바뀌는지
보여줍니다. 이걸로도 RMS가 2px 이하로 안 내려온다면 개별 프레임 문제가 아니라 다음을
의심해봐야 합니다 (스크립트도 이 경우 경고를 출력합니다):

- 카메라 중 하나가 영상을 좌우 반전(미러링)해서 내보내고 있지는 않은지 (일부 웹캠은 기본
  소프트웨어 설정으로 미러링되어 있습니다)
- 캡처 시 보드를 완전히 멈춘 채로 찍었는지 (다음 촬영부터는 캡처 직전 1초 정도 완전히
  정지 상태를 유지해보세요)
- `--intr0`/`--intr1`에 카메라를 서로 바꿔 넣지 않았는지

## 다음 단계 아이디어 (필요시)

- 포인트 클라우드가 노이즈가 많으면 Open3D의 `remove_statistical_outlier`로 후처리
- 여러 각도(턴테이블 회전)로 여러 번 스캔 후 ICP로 정합(registration)하면 커버리지 향상
- 포인트 클라우드 → 메쉬가 필요해지면 Open3D의 Poisson/Ball-Pivoting 재구성 추가 가능
