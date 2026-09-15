"""
단일 카메라 내부 파라미터(intrinsic) 캘리브레이션.

체커보드를 카메라 앞에서 여러 각도로 보여주며 'c' 키로 캡처하고,
'q' 키로 종료 후 자동으로 캘리브레이션을 수행해 .npz로 저장합니다.

카메라 인덱스를 모를 때는 아래처럼 먼저 확인하세요:

    python -c "
    import cv2
    for i in range(5):
        cap = cv2.VideoCapture(i)
        ok = cap.isOpened()
        print(i, 'OK' if ok else 'no device')
        cap.release()
    "

사용 예:
    python calibrate_single.py --cam 0 --out ../../data/output/cam0_intrinsics.npz
"""

import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="단일 카메라 캘리브레이션")
    p.add_argument("--cam", type=int, required=True, help="카메라 인덱스 (예: 0, 1, 2)")
    p.add_argument("--cols", type=int, default=9, help="체커보드 내부 코너 가로 개수")
    p.add_argument("--rows", type=int, default=6, help="체커보드 내부 코너 세로 개수")
    p.add_argument("--square", type=float, default=25.0, help="체커보드 정사각형 한 변 길이 (mm)")
    p.add_argument("--min-images", type=int, default=15, help="캘리브레이션에 사용할 최소 이미지 수")
    p.add_argument("--save-dir", type=str, default=None,
                    help="캡처한 체커보드 이미지를 저장할 폴더 (기본: data/calibration_images/camN)")
    p.add_argument("--out", type=str, required=True, help="결과 .npz 저장 경로")
    p.add_argument("--width", type=int, default=640,
                    help="캡처 해상도 가로 (기본 640: 2026-09-15 점검 결과 cam0/1의 최대 해상도)")
    p.add_argument("--height", type=int, default=480,
                    help="캡처 해상도 세로 (기본 480)")
    return p.parse_args()


def main():
    args = parse_args()
    board_size = (args.cols, args.rows)

    save_dir = args.save_dir or os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "calibration_images", f"cam{args.cam}"
    )
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # 체커보드의 3D 좌표 (z=0 평면, 단위: mm)
    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
    objp *= args.square

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    cap = cv2.VideoCapture(args.cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"[오류] 카메라 인덱스 {args.cam} 를 열 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    print("체커보드를 카메라에 다양한 각도/거리/위치로 보여주고 'c' 키로 캡처하세요.")
    print(f"최소 {args.min_images}장 이상 권장, 화면 가장자리도 포함해서 찍으세요. 'q'로 종료.")

    captured = 0
    img_shape = None

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[경고] 프레임을 읽지 못했습니다.")
            continue
        img_shape = frame.shape[:2][::-1]  # (w, h)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, board_size,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        display = frame.copy()
        if found:
            cv2.drawChessboardCorners(display, board_size, corners, found)

        cv2.putText(display, f"captured: {captured}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow(f"cam{args.cam} calibration - c: capture, q: quit", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("c") and found:
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            fname = os.path.join(save_dir, f"cam{args.cam}_{captured:03d}_{int(time.time())}.png")
            cv2.imwrite(fname, frame)
            captured += 1
            print(f"캡처됨: {fname} (총 {captured}장)")
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    if captured < args.min_images:
        print(f"[경고] 캡처된 이미지가 {captured}장으로 권장치({args.min_images})보다 적습니다. "
              f"정확도가 떨어질 수 있습니다. 계속 진행합니다.")

    # 저장된 모든 이미지로 캘리브레이션 (재실행 시 기존 이미지도 함께 사용됨)
    images = sorted(glob.glob(os.path.join(save_dir, "*.png")))
    if not images:
        print("[오류] 캘리브레이션에 사용할 이미지가 없습니다.", file=sys.stderr)
        sys.exit(1)

    objpoints = []
    imgpoints = []
    for fname in images:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, board_size)
        if not found:
            continue
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners2)
        img_shape = gray.shape[::-1]

    if len(objpoints) < 5:
        print(f"[오류] 체커보드가 검출된 이미지가 {len(objpoints)}장뿐입니다 (최소 5장 필요).", file=sys.stderr)
        sys.exit(1)

    print(f"{len(objpoints)}장의 이미지로 캘리브레이션 중...")
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_shape, None, None
    )

    print(f"재투영 오차(RMS): {rms:.4f}  (일반적으로 0.5 이하면 양호)")
    print("카메라 행렬 K:\n", K)
    print("왜곡 계수:\n", dist.ravel())

    np.savez(args.out, K=K, dist=dist, rms=rms, image_size=np.array(img_shape))
    print(f"저장 완료: {args.out}")


if __name__ == "__main__":
    main()
