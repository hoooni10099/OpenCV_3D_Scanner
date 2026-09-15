"""
포인트 클라우드(.ply)를 Open3D로 시각화하고, 선택적으로 노이즈를 제거해 다시 저장합니다.

사용 예:
    python view_pointcloud.py --ply ../../data/output/pointcloud.ply
    python view_pointcloud.py --ply ../../data/output/pointcloud.ply --denoise --save-clean ../../data/output/pointcloud_clean.ply
"""

import argparse
import sys

try:
    import open3d as o3d
except ImportError:
    print(
        "[오류] open3d가 설치되어 있지 않습니다.\n"
        "  - Open3D는 Python 3.12 이하에서만 설치 가능합니다 (2026-09-15 기준 3.13/3.14 미지원).\n"
        "  - 해결 방법: Python 3.11 또는 3.12로 별도 가상환경을 만들고\n"
        "      pip install -r requirements-viz.txt\n"
        "    를 실행하세요.\n"
        "  - 지금 바로 결과만 확인하고 싶다면 open3d 없이 동작하는 대체 스크립트를 쓰세요:\n"
        "      python src/visualize/view_pointcloud_matplotlib.py --ply <파일.ply>",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description="포인트 클라우드 시각화 / 후처리")
    p.add_argument("--ply", type=str, required=True, help="입력 .ply 경로")
    p.add_argument("--denoise", action="store_true",
                    help="통계적 이상치 제거(statistical outlier removal) 적용")
    p.add_argument("--nb-neighbors", type=int, default=20)
    p.add_argument("--std-ratio", type=float, default=2.0)
    p.add_argument("--voxel-size", type=float, default=0.0,
                    help="0보다 크면 다운샘플링 (단위: 캘리브레이션과 동일, 기본 mm)")
    p.add_argument("--save-clean", type=str, default=None,
                    help="후처리 결과를 저장할 경로 (지정하지 않으면 저장 안 함)")
    p.add_argument("--no-gui", action="store_true", help="화면 출력 없이 후처리/저장만 수행")
    return p.parse_args()


def main():
    args = parse_args()
    pcd = o3d.io.read_point_cloud(args.ply)
    print(f"불러온 점 개수: {len(pcd.points)}")

    if args.voxel_size > 0:
        pcd = pcd.voxel_down_sample(args.voxel_size)
        print(f"다운샘플링 후: {len(pcd.points)}")

    if args.denoise:
        pcd, _ = pcd.remove_statistical_outlier(
            nb_neighbors=args.nb_neighbors, std_ratio=args.std_ratio
        )
        print(f"이상치 제거 후: {len(pcd.points)}")

    if args.save_clean:
        o3d.io.write_point_cloud(args.save_clean, pcd)
        print(f"저장 완료: {args.save_clean}")

    if not args.no_gui:
        coord = o3d.geometry.TriangleMesh.create_coordinate_frame(size=20.0)
        o3d.visualization.draw_geometries([pcd, coord])


if __name__ == "__main__":
    main()
