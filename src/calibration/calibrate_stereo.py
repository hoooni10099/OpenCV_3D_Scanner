"""
두 카메라 간 스테레오(상대 위치) 캘리브레이션 — ChArUco 보드 사용.

두 카메라로 ChArUco 보드를 '동시에' 촬영해서 카메라A 기준 카메라B의 회전(R)/이동(T)을 구합니다.
카메라 3대라면 이 스크립트를 (0,1)과 (0,2) 두 번 실행해서, 카메라 0을 공통 기준으로 삼으세요.

*** 2026-09-15: 일반 체커보드에서 ChArUco 보드로 변경한 이유 ***
처음엔 일반 체커보드로 이 스크립트를 만들었는데, 실제로 써보니 RMS 재투영 오차가
수십 px로 나오는 문제가 있었습니다. 원인은 일반 체커보드가 180도 회전해도 똑같이 생겨서,
서로 각도 차이가 큰 두 카메라가 동시에 같은 체커보드를 보면 OpenCV가 두 이미지에서 코너를
반대 순서로 인식하는 경우가 흔하기 때문입니다 (검증 결과, 호모그래피 등 순수 기하학적
방법으로는 이 반전을 구분할 수 없다는 것도 확인함 — 두 순서 모두 "수학적으로 유효한" 정사각
격자라서). ChArUco 보드는 각 칸 사이에 고유 ID를 가진 ArUco 마커가 있어서 각 코너의
정체성이 시점에 관계없이 명확하며, 두 카메라에서 같은 ID로 검출된 코너끼리만 짝지으면
correspondence 문제가 원천적으로 사라집니다.

사전 준비:
  1) src/utils/generate_charuco_board.py 로 ChArUco 보드 이미지 생성 후 화면에 띄우고
     정사각형 한 칸을 자로 실측 (mm)
  2) calibrate_single.py로 각 카메라의 K, dist(.npz)를 미리 구해둬야 함
     (기존에 일반 체커보드로 구한 결과를 그대로 써도 됩니다 — K, dist는 어떤 보드를
     썼는지와 무관하게 유효합니다)

사용 예:
    python calibrate_stereo.py --cams 0 1 --square 30 \
        --intr0 ../../data/output/cam0_intrinsics.npz \
        --intr1 ../../data/output/cam1_intrinsics.npz \
        --out ../../data/output/stereo_0_1.npz

    # 이미 촬영해둔 이미지로 카메라를 열지 않고 계산만 다시 하고 싶을 때
    python calibrate_stereo.py --cams 0 1 --square 30 --recompute-only \
        --intr0 ../../data/output/cam0_intrinsics.npz \
        --intr1 ../../data/output/cam1_intrinsics.npz \
        --out ../../data/output/stereo_0_1.npz
"""

import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np

# generate_charuco_board.py 의 기본값과 반드시 같아야 함
SQUARES_X = 10
SQUARES_Y = 7
ARUCO_DICT = cv2.aruco.DICT_4X4_50


def parse_args():
    p = argparse.ArgumentParser(description="스테레오 캘리브레이션 (카메라 쌍, ChArUco 보드)")
    p.add_argument("--cams", type=int, nargs=2, required=True, metavar=("CAM_A", "CAM_B"),
                    help="캘리브레이션할 두 카메라 인덱스, 예: --cams 0 1")
    p.add_argument("--intr0", type=str, required=True, help="cams[0]의 intrinsics .npz")
    p.add_argument("--intr1", type=str, required=True, help="cams[1]의 intrinsics .npz")
    p.add_argument("--squares-x", type=int, default=SQUARES_X, help="ChArUco 보드 가로 정사각형 개수")
    p.add_argument("--squares-y", type=int, default=SQUARES_Y, help="ChArUco 보드 세로 정사각형 개수")
    p.add_argument("--square", type=float, required=True,
                    help="정사각형 한 칸의 실측 길이 (mm) — generate_charuco_board.py 이미지를 화면에 "
                         "띄운 뒤 자로 잰 값")
    p.add_argument("--marker-ratio", type=float, default=0.7,
                    help="마커 크기/정사각형 크기 비율 (generate_charuco_board.py와 동일해야 함)")
    p.add_argument("--min-pairs", type=int, default=15)
    p.add_argument("--min-common-corners", type=int, default=8,
                    help="한 프레임에서 두 카메라 모두에 공통으로 검출돼야 하는 최소 코너 수")
    p.add_argument("--save-dir", type=str, default=None)
    p.add_argument("--out", type=str, required=True)
    p.add_argument("--width", type=int, default=640,
                    help="캡처 해상도 가로 (기본 640: 2026-09-15 점검 결과 cam0/1의 최대 해상도)")
    p.add_argument("--height", type=int, default=480,
                    help="캡처 해상도 세로 (기본 480)")
    p.add_argument("--recompute-only", action="store_true",
                    help="카메라를 열지 않고, save-dir에 이미 저장된 이미지만으로 계산을 다시 수행")
    p.add_argument("--outlier-threshold-px", type=float, default=3.0,
                    help="이 값(px)보다 개별 프레임 재투영 오차가 크면 이상치로 보고 자동 제외 후 재계산")
    p.add_argument("--max-outlier-rounds", type=int, default=5,
                    help="이상치 제거 반복 최대 횟수")
    return p.parse_args()


def build_board(args):
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (args.squares_x, args.squares_y),
        args.square, args.square * args.marker_ratio,
        dictionary,
    )
    return board


def detect_charuco(detector, gray):
    """(ids, corners) 반환. 검출 실패 시 (None, None)."""
    corners, ids, _, _ = detector.detectBoard(gray)
    if ids is None or len(ids) == 0:
        return None, None
    return ids.flatten(), corners.reshape(-1, 2)


def match_common_ids(ids_a, corners_a, ids_b, corners_b):
    """두 이미지에서 검출된 ChArUco 코너를 ID로 매칭 (시점이 달라도 correspondence가 명확함)."""
    common = np.intersect1d(ids_a, ids_b)
    if len(common) == 0:
        return None
    idx_a = {v: i for i, v in enumerate(ids_a)}
    idx_b = {v: i for i, v in enumerate(ids_b)}
    pts_a = np.array([corners_a[idx_a[c]] for c in common], dtype=np.float32).reshape(-1, 1, 2)
    pts_b = np.array([corners_b[idx_b[c]] for c in common], dtype=np.float32).reshape(-1, 1, 2)
    return common.astype(int), pts_a, pts_b


def main():
    args = parse_args()
    cam_a, cam_b = args.cams
    board = build_board(args)
    board_corners_3d = board.getChessboardCorners()  # id로 바로 인덱싱 가능 (mm 단위, --square 반영됨)

    save_dir = args.save_dir or os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "calibration_images", f"stereo_{cam_a}_{cam_b}"
    )
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    d0 = np.load(args.intr0)
    d1 = np.load(args.intr1)
    K0, dist0 = d0["K"], d0["dist"]
    K1, dist1 = d1["K"], d1["dist"]

    # 각 카메라의 기존 K, dist를 detector에 넘겨주면 서브픽셀 보정 정확도가 조금 더 좋아짐
    detector_a = cv2.aruco.CharucoDetector(board)
    detector_b = cv2.aruco.CharucoDetector(board)

    img_shape = None
    captured = 0

    if args.recompute_only:
        print(f"[--recompute-only] 카메라를 열지 않고 {save_dir} 안의 기존 이미지로만 계산합니다.")
    else:
        cap_a = cv2.VideoCapture(cam_a)
        cap_b = cv2.VideoCapture(cam_b)
        for cap in (cap_a, cap_b):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            # 버퍼를 1로 줄여서 오래된(지연된) 프레임이 아니라 최신 프레임을 읽도록 함.
            # 두 카메라는 하드웨어적으로 동기화돼 있지 않으므로, 버퍼링된 오래된 프레임을 읽으면
            # 'c'를 눌렀을 때 두 카메라가 실제로는 다른 순간의 보드 위치를 보게 될 수 있음
            # (보드가 움직이는 중이었다면 이게 큰 재투영 오차의 원인이 될 수 있음).
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap_a.isOpened() or not cap_b.isOpened():
            print(f"[오류] 카메라 {cam_a} 또는 {cam_b} 를 열 수 없습니다.", file=sys.stderr)
            sys.exit(1)

        print(f"두 카메라({cam_a}, {cam_b})에 ChArUco 보드가 '동시에' 모두 보이게 하고 'c'로 캡처, 'q'로 종료.")

        while True:
            ok_a = cap_a.grab()
            ok_b = cap_b.grab()
            if not (ok_a and ok_b):
                print("[경고] 프레임 grab 실패")
                continue
            ok_a, frame_a = cap_a.retrieve()
            ok_b, frame_b = cap_b.retrieve()
            if not (ok_a and ok_b):
                continue

            img_shape = frame_a.shape[:2][::-1]
            gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
            gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

            ids_a, corners_a = detect_charuco(detector_a, gray_a)
            ids_b, corners_b = detect_charuco(detector_b, gray_b)

            n_common = 0
            if ids_a is not None and ids_b is not None:
                n_common = len(np.intersect1d(ids_a, ids_b))

            disp_a, disp_b = frame_a.copy(), frame_b.copy()
            if ids_a is not None:
                cv2.aruco.drawDetectedCornersCharuco(disp_a, corners_a.reshape(-1, 1, 2), ids_a)
            if ids_b is not None:
                cv2.aruco.drawDetectedCornersCharuco(disp_b, corners_b.reshape(-1, 1, 2), ids_b)

            combined = np.hstack([
                cv2.resize(disp_a, (640, 360)),
                cv2.resize(disp_b, (640, 360)),
            ])
            cv2.putText(combined, f"captured pairs: {captured}  common corners: {n_common}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow(f"stereo calib cam{cam_a} | cam{cam_b} - c: capture, q: quit", combined)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("c") and n_common >= args.min_common_corners:
                ts = int(time.time() * 1000)
                fa = os.path.join(save_dir, f"a_{captured:03d}_{ts}.png")
                fb = os.path.join(save_dir, f"b_{captured:03d}_{ts}.png")
                cv2.imwrite(fa, frame_a)
                cv2.imwrite(fb, frame_b)
                captured += 1
                print(f"캡처된 쌍: {captured} (공통 코너 {n_common}개)")
            elif key == ord("c"):
                print(f"[건너뜀] 공통 코너가 {n_common}개뿐 (최소 {args.min_common_corners}개 필요)")
            elif key == ord("q"):
                break

        cap_a.release()
        cap_b.release()
        cv2.destroyAllWindows()

        if captured < args.min_pairs:
            print(f"[경고] 캡처된 쌍이 {captured}개로 권장치({args.min_pairs})보다 적습니다.")

    files_a = sorted(glob.glob(os.path.join(save_dir, "a_*.png")))
    files_b = sorted(glob.glob(os.path.join(save_dir, "b_*.png")))
    if len(files_a) != len(files_b) or not files_a:
        print("[오류] a/b 이미지 쌍이 맞지 않습니다.", file=sys.stderr)
        sys.exit(1)

    objpoints, imgpoints_a, imgpoints_b, frame_names = [], [], [], []
    n_dropped = 0
    for fa, fb in zip(files_a, files_b):
        ga = cv2.cvtColor(cv2.imread(fa), cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(cv2.imread(fb), cv2.COLOR_BGR2GRAY)
        if img_shape is None:
            img_shape = ga.shape[::-1]

        ids_a, corners_a = detect_charuco(detector_a, ga)
        ids_b, corners_b = detect_charuco(detector_b, gb)
        if ids_a is None or ids_b is None:
            n_dropped += 1
            continue

        matched = match_common_ids(ids_a, corners_a, ids_b, corners_b)
        if matched is None:
            n_dropped += 1
            continue
        common_ids, pts_a, pts_b = matched
        if len(common_ids) < args.min_common_corners:
            n_dropped += 1
            print(f"  [버림] {os.path.basename(fa)} <-> {os.path.basename(fb)}: "
                  f"공통 코너 {len(common_ids)}개 (최소 {args.min_common_corners}개 필요)")
            continue

        obj_pts = board_corners_3d[common_ids].astype(np.float32).reshape(-1, 1, 3)
        objpoints.append(obj_pts)
        imgpoints_a.append(pts_a)
        imgpoints_b.append(pts_b)
        frame_names.append(f"{os.path.basename(fa)} <-> {os.path.basename(fb)}")

    print(f"사용된 쌍: {len(objpoints)}개 / 버려진 쌍: {n_dropped}개 (전체 {len(files_a)}개 중)")

    if len(objpoints) < 5:
        print(f"[오류] 유효한 쌍이 {len(objpoints)}개뿐입니다 (최소 5개 필요).", file=sys.stderr)
        sys.exit(1)

    flags = cv2.CALIB_FIX_INTRINSIC  # 이미 구한 K, dist를 고정하고 R, T만 추정
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)

    for round_i in range(args.max_outlier_rounds + 1):
        print(f"[{round_i+1}회차] {len(objpoints)}개 쌍으로 스테레오 캘리브레이션 중...")
        rms, K0_, dist0_, K1_, dist1_, R, T, E, F, rvecs, tvecs, per_view_errors = \
            cv2.stereoCalibrateExtended(
                objpoints, imgpoints_a, imgpoints_b,
                K0, dist0, K1, dist1,
                img_shape, np.eye(3), np.zeros((3, 1)),
                flags=flags, criteria=criteria,
            )
        # per_view_errors: (N,2) — 카메라별 프레임당 재투영 오차. 두 값의 평균을 프레임 오차로 사용.
        per_frame = per_view_errors.mean(axis=1)
        order = np.argsort(-per_frame)
        print(f"  전체 RMS: {rms:.4f}px  (프레임별 오차 중앙값 {np.median(per_frame):.2f}px, "
              f"최대 {per_frame.max():.2f}px, 최소 {per_frame.min():.2f}px)")
        print("  오차가 큰 프레임 Top 5:")
        for i in order[:5]:
            print(f"    {per_frame[i]:6.2f}px  {frame_names[i]}")

        worst_idx = order[0]
        if per_frame[worst_idx] <= args.outlier_threshold_px:
            break
        if len(objpoints) <= max(args.min_pairs, 8):
            print(f"  더 제거하면 쌍이 너무 적어져서({len(objpoints)}개) 중단합니다.")
            break
        if round_i == args.max_outlier_rounds:
            print("  이상치 제거 반복 횟수를 다 썼습니다.")
            break

        print(f"  [이상치 제거] {frame_names[worst_idx]} (오차 {per_frame[worst_idx]:.2f}px > "
              f"임계값 {args.outlier_threshold_px}px) 제외하고 재계산합니다.")
        for lst in (objpoints, imgpoints_a, imgpoints_b, frame_names):
            del lst[worst_idx]

    print(f"최종 스테레오 재투영 오차(RMS): {rms:.4f}  (사용된 쌍: {len(objpoints)}개)")
    print("R (cam_a -> cam_b 회전):\n", R)
    print("T (cam_a -> cam_b 이동, mm):\n", T.ravel())

    if rms > 2.0:
        print(
            "[경고] RMS가 여전히 높습니다(2px 초과). 이상치 제거로도 해결되지 않는다면 아마 개별\n"
            "  프레임 오류가 아니라 구조적인 문제일 가능성이 높습니다. 다음을 확인해보세요:\n"
            "  - 두 카메라 중 하나의 영상이 좌우 반전(미러링)되어 있지는 않은지 (일부 노트북\n"
            "    내장캠/웹캠 소프트웨어가 기본적으로 미러링을 적용합니다)\n"
            "  - 캡처할 때 보드가 완전히 멈춘 상태였는지 (두 카메라는 하드웨어 동기화가 안 되어\n"
            "    있어서, 보드가 움직이는 중에 캡처하면 두 카메라가 실제로는 살짝 다른 순간의\n"
            "    보드 위치를 보게 됩니다)\n"
            "  - --intr0/--intr1 파일이 올바른 카메라의 것인지 (cam0/cam1을 뒤바꿔 넣지 않았는지)",
            file=sys.stderr,
        )

    np.savez(
        args.out,
        cam_a=cam_a, cam_b=cam_b,
        K0=K0, dist0=dist0, K1=K1, dist1=dist1,
        R=R, T=T, E=E, F=F, rms=rms,
        image_size=np.array(img_shape),
    )
    print(f"저장 완료: {args.out}")


if __name__ == "__main__":
    main()
