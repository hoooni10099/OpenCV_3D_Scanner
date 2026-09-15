"""
체커보드 캘리브레이션 패턴 이미지를 생성합니다.

프린터가 없을 때: 이 이미지를 모니터/태블릿/휴대폰 화면에 '실제 크기(확대/축소 없음)'로
띄워서 종이 체커보드 대신 사용할 수 있습니다. 화면마다 실제 픽셀 밀도(PPI)가 달라서,
화면에 띄운 뒤 자로 정사각형 한 칸의 실제 길이(mm)를 재서 그 값을 캘리브레이션 스크립트의
--square 옵션에 입력해야 합니다 (이 스크립트가 생성하는 "정사각형 픽셀 크기"는 참고용일 뿐,
화면에 표시될 실제 물리 크기는 화면마다 다릅니다).

내부 코너 개수는 calibrate_single.py / calibrate_stereo.py의 기본값(--cols 9 --rows 6)과
반드시 맞춰야 합니다. 기본값을 바꾸지 않았다면 이 스크립트도 기본값 그대로 실행하세요.

사용 예:
    # 기본 설정(내부 코너 9x6, 정사각형 150px)으로 PNG 생성
    python generate_checkerboard.py --out ../../data/checkerboard_9x6.png

    # 더 큰 화면/고해상도 모니터에 맞게 정사각형을 크게
    python generate_checkerboard.py --square-px 220 --out ../../data/checkerboard_9x6_large.png
"""

import argparse

import numpy as np
from PIL import Image


def parse_args():
    p = argparse.ArgumentParser(description="체커보드 패턴 이미지 생성 (화면 표시/인쇄용)")
    p.add_argument("--cols", type=int, default=9, help="내부 코너 가로 개수 (calibrate_*.py와 동일해야 함)")
    p.add_argument("--rows", type=int, default=6, help="내부 코너 세로 개수 (calibrate_*.py와 동일해야 함)")
    p.add_argument("--square-px", type=int, default=150, help="정사각형 한 칸의 픽셀 크기")
    p.add_argument("--margin-squares", type=float, default=1.0,
                    help="테두리 여백 (정사각형 몇 개 크기만큼 흰 여백을 둘지, 코너 검출 안정성에 도움)")
    p.add_argument("--out", type=str, required=True, help="출력 이미지 경로 (.png)")
    return p.parse_args()


def main():
    args = parse_args()

    # 내부 코너가 cols x rows 이려면 정사각형은 (cols+1) x (rows+1)개 필요
    n_cols_sq = args.cols + 1
    n_rows_sq = args.rows + 1
    s = args.square_px
    margin = int(round(args.margin_squares * s))

    board_w = n_cols_sq * s
    board_h = n_rows_sq * s
    img_w = board_w + 2 * margin
    img_h = board_h + 2 * margin

    # 흰 배경
    img = np.full((img_h, img_w), 255, dtype=np.uint8)

    for r in range(n_rows_sq):
        for c in range(n_cols_sq):
            if (r + c) % 2 == 0:
                y0 = margin + r * s
                y1 = y0 + s
                x0 = margin + c * s
                x1 = x0 + s
                img[y0:y1, x0:x1] = 0

    Image.fromarray(img).save(args.out)

    print(f"체커보드 이미지 저장 완료: {args.out}")
    print(f"  - 정사각형 개수: {n_cols_sq} x {n_rows_sq} (내부 코너 {args.cols} x {args.rows})")
    print(f"  - 이미지 픽셀 크기: {img_w} x {img_h}")
    print("  - 화면에 '실제 크기(100%, 확대/축소 없음)'로 띄운 뒤, 자로 정사각형 한 칸의")
    print("    실제 길이(mm)를 측정해서 calibrate_single.py / calibrate_stereo.py 의")
    print("    --square 옵션에 그 값을 입력하세요.")


if __name__ == "__main__":
    main()
