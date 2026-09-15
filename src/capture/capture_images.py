"""
카메라 3대(또는 2대 이상)에서 동기화된 스캔 대상 이미지를 촬영합니다.

스페이스바(또는 'c')를 누르면 모든 카메라에서 거의 동시에 프레임을 저장합니다.
grab()을 모든 카메라에 대해 먼저 호출한 뒤 retrieve()하는 방식으로 시간차를 최소화합니다
(완벽한 하드웨어 동기화는 아니므로, 정지된 물체를 스캔하는 것을 권장합니다).

사용 예:
    python capture_images.py --cams 0 1 2 --out ../../data/captures/session1
"""

import argparse
import os
import sys

import cv2

# 기본값 640x480: 2026-09-15 카메라 점검 결과 cam0/cam1이 최대 640x480까지만 지원함
# (cam2는 1920x1080까지 가능하나, 3대 공통 해상도로 통일해 계산을 단순화함).
# 나중에 카메라를 교체하거나 해상도를 다르게 쓰고 싶다면 --width/--height로 덮어쓰세요.
TARGET_WIDTH = 640
TARGET_HEIGHT = 480
TARGET_FPS = 30


def parse_args():
    p = argparse.ArgumentParser(description="다중 카메라 동시 촬영")
    p.add_argument("--cams", type=int, nargs="+", required=True,
                    help="사용할 카메라 인덱스 목록, 예: --cams 0 1 2")
    p.add_argument("--out", type=str, required=True, help="촬영 이미지를 저장할 폴더")
    p.add_argument("--width", type=int, default=TARGET_WIDTH)
    p.add_argument("--height", type=int, default=TARGET_HEIGHT)
    p.add_argument("--fps", type=int, default=TARGET_FPS)
    p.add_argument("--manual-exposure", action="store_true",
                    help="자동 노출을 끄고 값을 고정 (카메라 기종이 다를 때 밝기 차이를 줄이는 데 도움)")
    return p.parse_args()


def open_camera(index, width, height, fps, manual_exposure):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if manual_exposure:
        # 참고: 값의 의미(0.25=manual, 0.75=auto 등)는 드라이버/OS마다 다릅니다.
        # 카메라별로 실제 동작을 확인 후 조정하세요.
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    return cap


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)

    caps = {}
    for idx in args.cams:
        cap = open_camera(idx, args.width, args.height, args.fps, args.manual_exposure)
        if cap is None:
            print(f"[오류] 카메라 {idx} 를 열 수 없습니다.", file=sys.stderr)
            sys.exit(1)
        caps[idx] = cap

    print("스페이스바(또는 'c')로 모든 카메라에서 동시 촬영, 'q'로 종료.")
    shot = 0

    try:
        while True:
            frames = {}
            # 1단계: 모든 카메라에서 최대한 동시에 grab
            grabbed = {idx: cap.grab() for idx, cap in caps.items()}
            if not all(grabbed.values()):
                print("[경고] 일부 카메라 grab 실패, 재시도")
                continue
            # 2단계: retrieve로 디코딩
            for idx, cap in caps.items():
                ok, frame = cap.retrieve()
                if not ok:
                    frame = None
                frames[idx] = frame

            if any(f is None for f in frames.values()):
                continue

            previews = [cv2.resize(frames[idx], (426, 240)) for idx in args.cams]
            combined = cv2.hconcat(previews)
            cv2.putText(combined, f"shots: {shot}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("capture (space/c: shoot, q: quit)", combined)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord(" "), ord("c")):
                shot_dir = os.path.join(args.out, f"shot_{shot:03d}")
                os.makedirs(shot_dir, exist_ok=True)
                for idx in args.cams:
                    fname = os.path.join(shot_dir, f"cam{idx}.png")
                    cv2.imwrite(fname, frames[idx])
                print(f"저장됨: {shot_dir}")
                shot += 1
            elif key == ord("q"):
                break
    finally:
        for cap in caps.values():
            cap.release()
        cv2.destroyAllWindows()

    print(f"총 {shot}개 샷 촬영 완료 -> {args.out}")


if __name__ == "__main__":
    main()
