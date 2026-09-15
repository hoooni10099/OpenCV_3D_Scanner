"""
ChArUco 보드(체커보드 + ArUco 마커 조합) 이미지를 생성합니다.

*** 왜 일반 체커보드 대신 ChArUco를 쓰는가 (2026-09-15 발견한 문제) ***
일반 체커보드는 180도 회전해도 똑같이 생겨서, 서로 많이 다른 각도에 있는 두 카메라가
동시에 같은 체커보드를 보면 OpenCV가 두 이미지에서 코너를 반대 순서로 인식하는 경우가
생깁니다. 이러면 두 카메라의 같은 인덱스 코너가 실제로는 다른 물리적 점을 가리키게 되어
스테레오 캘리브레이션이 완전히 틀어집니다(RMS 수십 px). ChArUco 보드는 각 칸 사이에
고유 ID를 가진 ArUco 마커가 있어서, 각 코너가 "몇 번 코너인지"를 어느 각도에서 봐도
명확하게 알 수 있습니다 — 이 모호함 자체가 원천적으로 없어집니다.

화면에 띄워서 쓰는 방법은 기존 체커보드와 동일합니다: 화면에 띄우고 자로 정사각형
한 칸을 실측해서 calibrate_stereo.py의 --square 에 입력하세요.

사용 예:
    python generate_charuco_board.py --out ../../data/charuco_10x7.png
"""

import argparse

import cv2
import numpy as np
from PIL import Image

# calibrate_stereo.py 와 반드시 같은 값을 써야 함
DEFAULT_SQUARES_X = 10
DEFAULT_SQUARES_Y = 7
DEFAULT_DICT = cv2.aruco.DICT_4X4_50


def parse_args():
    p = argparse.ArgumentParser(description="ChArUco 보드 이미지 생성 (화면 표시/인쇄용)")
    p.add_argument("--squares-x", type=int, default=DEFAULT_SQUARES_X, help="가로 정사각형 개수")
    p.add_argument("--squares-y", type=int, default=DEFAULT_SQUARES_Y, help="세로 정사각형 개수")
    p.add_argument("--square-px", type=int, default=150, help="정사각형 한 칸의 픽셀 크기")
    p.add_argument("--marker-ratio", type=float, default=0.7,
                    help="마커 크기 / 정사각형 크기 비율 (0~1, ArUco 표준 마커용)")
    p.add_argument("--margin-px", type=int, default=60, help="테두리 여백 픽셀")
    p.add_argument("--out", type=str, required=True, help="출력 이미지 경로 (.png)")
    return p.parse_args()


def main():
    args = parse_args()

    dictionary = cv2.aruco.getPredefinedDictionary(DEFAULT_DICT)
    # squareLength/markerLength는 이미지 생성 자체에는 비율만 영향을 줌 (실제 mm 값은
    # calibrate_stereo.py 실행 시 --square 로 따로 지정)
    board = cv2.aruco.CharucoBoard(
        (args.squares_x, args.squares_y),
        1.0, args.marker_ratio,
        dictionary,
    )

    img_w = args.squares_x * args.square_px + 2 * args.margin_px
    img_h = args.squares_y * args.square_px + 2 * args.margin_px
    img = board.generateImage((img_w, img_h), marginSize=args.margin_px, borderBits=1)

    Image.fromarray(img).save(args.out)

    print(f"ChArUco 보드 이미지 저장 완료: {args.out}")
    print(f"  - 정사각형 개수: {args.squares_x} x {args.squares_y} (내부 코너 {args.squares_x - 1} x {args.squares_y - 1})")
    print(f"  - 이미지 픽셀 크기: {img_w} x {img_h}")
    print("  - 화면에 띄운 뒤, 자로 정사각형 한 칸의 실제 길이(mm)를 측정해서")
    print("    calibrate_stereo.py 의 --square 옵션에 그 값을 입력하세요.")


if __name__ == "__main__":
    main()
