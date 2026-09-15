"""
연결된 카메라를 탐색하고, 각 인덱스가 지원하는 해상도/FPS를 점검하는 유틸리티.

물리적으로 어떤 카메라가 어떤 인덱스에 매핑되는지 확인하려면, 카메라를 하나씩만 연결한 채로
실행하거나 --preview 옵션으로 미리보기 창을 띄워 렌즈를 손으로 가려보며 확인하세요.

사용 예:
    # 인덱스 0~5까지 스캔, 열리는 카메라만 보고
    python list_cameras.py

    # 인덱스 0~9까지 스캔
    python list_cameras.py --max-index 9

    # 각 카메라 미리보기 (스페이스바로 다음 카메라, q로 종료)
    python list_cameras.py --preview
"""

import argparse

import cv2

# 확인해볼 후보 해상도 (가로, 세로)
CANDIDATE_RESOLUTIONS = [
    (640, 480),
    (1280, 720),
    (1920, 1080),
]


def parse_args():
    p = argparse.ArgumentParser(description="연결된 카메라 탐색")
    p.add_argument("--max-index", type=int, default=5, help="탐색할 최대 카메라 인덱스")
    p.add_argument("--preview", action="store_true", help="각 카메라의 미리보기 창을 띄움")
    return p.parse_args()


def probe_camera(index):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None

    info = {"index": index, "supported": []}
    for w, h in CANDIDATE_RESOLUTIONS:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        info["supported"].append(f"{w}x{h} -> 실제 {actual_w}x{actual_h}")

    info["fps"] = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return info


def preview_camera(index):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"[cam {index}] 열기 실패")
        return
    print(f"[cam {index}] 미리보기 중... 스페이스바: 다음 카메라, q: 종료")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cv2.putText(frame, f"camera index: {index}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imshow("camera preview", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            break
        if key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            raise SystemExit
    cap.release()


def main():
    args = parse_args()

    print(f"인덱스 0 ~ {args.max_index} 탐색 중...\n")
    found = []
    for i in range(args.max_index + 1):
        info = probe_camera(i)
        if info is None:
            continue
        found.append(info)
        print(f"[cam {i}] 열림. FPS={info['fps']:.1f}")
        for s in info["supported"]:
            print(f"   - {s}")

    if not found:
        print("열리는 카메라가 없습니다. USB 연결/권한을 확인하세요.")
        return

    print(f"\n총 {len(found)}대 발견: 인덱스 {[f['index'] for f in found]}")

    if args.preview:
        print("\n미리보기를 시작합니다. 각 카메라 렌즈를 손으로 가려보며 어떤 물리 카메라인지 확인하세요.")
        for info in found:
            preview_camera(info["index"])
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
