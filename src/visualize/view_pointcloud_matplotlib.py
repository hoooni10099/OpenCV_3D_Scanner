"""
Open3D 없이 matplotlib만으로 포인트 클라우드(.ply)를 확인하는 대체 스크립트.

Open3D가 Python 3.13/3.14를 아직 지원하지 않을 때(2026-09-15 기준) 임시로 결과를
빠르게 확인하는 용도입니다. 노이즈 제거/다운샘플링 같은 후처리는 지원하지 않으며,
정식 후처리가 필요하면 Python 3.11/3.12 환경에서 view_pointcloud.py(Open3D)를 쓰세요.

triangulate.py가 만드는 ASCII PLY 포맷(x y z red green blue)만 지원합니다.

사용 예:
    python view_pointcloud_matplotlib.py --ply ../../data/output/pointcloud.ply
    python view_pointcloud_matplotlib.py --ply ../../data/output/pointcloud.ply --save preview.png --no-show
"""

import argparse
import sys

import matplotlib
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="matplotlib 기반 포인트 클라우드 미리보기 (Open3D 대체)")
    p.add_argument("--ply", type=str, required=True, help="입력 .ply 경로 (ASCII, x y z r g b)")
    p.add_argument("--max-points", type=int, default=50000,
                    help="화면에 그릴 최대 점 개수 (많으면 무작위로 줄여서 그림, 속도 위해)")
    p.add_argument("--point-size", type=float, default=2.0)
    p.add_argument("--save", type=str, default=None, help="결과를 이미지 파일로 저장 (예: preview.png)")
    p.add_argument("--no-show", action="store_true", help="화면 창을 띄우지 않음 (--save와 함께 사용)")
    return p.parse_args()


def read_ascii_ply(path):
    with open(path, "r") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "ply":
        raise ValueError("PLY 헤더가 아닙니다. ASCII PLY 파일인지 확인하세요.")

    n_vertex = None
    header_end = None
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("element vertex"):
            n_vertex = int(line.split()[-1])
        if line == "end_header":
            header_end = i
            break

    if n_vertex is None or header_end is None:
        raise ValueError("PLY 헤더를 파싱하지 못했습니다 (element vertex / end_header 없음).")

    data = np.loadtxt(lines[header_end + 1: header_end + 1 + n_vertex])
    if data.ndim == 1:
        data = data.reshape(1, -1)

    points = data[:, :3]
    if data.shape[1] >= 6:
        colors = data[:, 3:6] / 255.0
    else:
        colors = np.full((len(points), 3), 0.3)

    return points, colors


def main():
    args = parse_args()

    if args.no_show:
        matplotlib.use("Agg")  # 화면 없는 환경에서도 저장은 가능하도록
    import matplotlib.pyplot as plt  # noqa: E402  (backend 설정 이후 import)

    try:
        points, colors = read_ascii_ply(args.ply)
    except (OSError, ValueError) as e:
        print(f"[오류] {args.ply} 읽기 실패: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"불러온 점 개수: {len(points)}")

    if len(points) > args.max_points:
        idx = np.random.choice(len(points), args.max_points, replace=False)
        points, colors = points[idx], colors[idx]
        print(f"미리보기를 위해 {args.max_points}개로 무작위 샘플링")

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               c=colors, s=args.point_size, depthshade=True)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title(f"{args.ply}  ({len(points)} points)")

    # 세 축의 스케일을 맞춰서 형태가 왜곡되지 않도록 함
    max_range = (points.max(axis=0) - points.min(axis=0)).max() / 2.0
    mid = (points.max(axis=0) + points.min(axis=0)) / 2.0
    ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
    ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
    ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

    if args.save:
        fig.savefig(args.save, dpi=150)
        print(f"이미지 저장 완료: {args.save}")

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
