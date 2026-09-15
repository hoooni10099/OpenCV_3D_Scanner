"""
캡처된 이미지(cam0/cam1/cam2)와 스테레오 캘리브레이션 결과로 포인트 클라우드를 생성합니다.

절차:
  1) cam0-cam1, cam0-cam2 각각에서 SIFT 특징점을 매칭
  2) Fundamental Matrix + RANSAC으로 잘못된 매칭 제거
  3) cv2.triangulatePoints로 3D 좌표 계산 (카메라0 좌표계 기준)
  4) 두 쌍의 결과를 합쳐 하나의 포인트 클라우드로 저장 (.ply)

주의: 이 방식은 "성긴(sparse)" 포인트 클라우드를 만듭니다 (특징점이 있는 곳만).
      더 촘촘한 결과가 필요하면 --dense 옵션(스테레오 정합 기반)을 사용하세요.

사용 예:
    python triangulate.py --session ../../data/captures/session1 \
        --stereo01 ../../data/output/stereo_0_1.npz \
        --stereo02 ../../data/output/stereo_0_2.npz \
        --out ../../data/output/pointcloud.ply
"""

import argparse
import glob
import os
import sys

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="삼각측량으로 포인트 클라우드 생성")
    p.add_argument("--session", type=str, required=True,
                    help="capture_images.py로 촬영한 세션 폴더 (shot_000, shot_001, ... 포함)")
    p.add_argument("--stereo01", type=str, required=True, help="cam0-cam1 스테레오 캘리브레이션 .npz")
    p.add_argument("--stereo02", type=str, required=True, help="cam0-cam2 스테레오 캘리브레이션 .npz")
    p.add_argument("--out", type=str, required=True, help="출력 .ply 경로")
    p.add_argument("--ratio", type=float, default=0.75, help="Lowe's ratio test 임계값")
    p.add_argument("--max-reproj-error", type=float, default=4.0,
                    help="이 값(px)보다 재투영 오차가 큰 점은 버림")
    return p.parse_args()


def load_projection_matrices(stereo_npz_path):
    d = np.load(stereo_npz_path)
    K0, dist0 = d["K0"], d["dist0"]
    K1, dist1 = d["K1"], d["dist1"]
    R, T = d["R"], d["T"]
    # cam0을 world 원점으로: P0 = K0 [I | 0], P1 = K1 [R | T]
    P0 = K0 @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P1 = K1 @ np.hstack([R, T.reshape(3, 1)])
    return K0, dist0, K1, dist1, P0, P1


def match_and_triangulate(img0, img1, K0, dist0, K1, dist1, P0, P1, ratio, max_reproj_error):
    sift = cv2.SIFT_create()
    gray0 = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    kp0, des0 = sift.detectAndCompute(gray0, None)
    kp1, des1 = sift.detectAndCompute(gray1, None)

    if des0 is None or des1 is None or len(kp0) < 8 or len(kp1) < 8:
        return np.empty((0, 3)), np.empty((0, 3))

    bf = cv2.BFMatcher(cv2.NORM_L2)
    raw_matches = bf.knnMatch(des0, des1, k=2)
    good = [m for m, n in raw_matches if m.distance < ratio * n.distance]
    if len(good) < 8:
        return np.empty((0, 3)), np.empty((0, 3))

    pts0 = np.float32([kp0[m.queryIdx].pt for m in good])
    pts1 = np.float32([kp1[m.trainIdx].pt for m in good])

    F, mask = cv2.findFundamentalMat(pts0, pts1, cv2.FM_RANSAC, 2.0, 0.99)
    if mask is None:
        return np.empty((0, 3)), np.empty((0, 3))
    mask = mask.ravel().astype(bool)
    pts0_in, pts1_in = pts0[mask], pts1[mask]
    colors_bgr = np.array([img0[int(round(y)), int(round(x))]
                            for x, y in pts0_in if 0 <= int(y) < img0.shape[0] and 0 <= int(x) < img0.shape[1]])

    if len(pts0_in) < 8:
        return np.empty((0, 3)), np.empty((0, 3))

    # 렌즈 왜곡 보정 + 정규화 좌표로 undistort 후, 다시 픽셀 좌표로 (triangulatePoints는 픽셀 좌표 P와 함께 사용)
    pts0_u = cv2.undistortPoints(pts0_in.reshape(-1, 1, 2), K0, dist0, P=K0).reshape(-1, 2)
    pts1_u = cv2.undistortPoints(pts1_in.reshape(-1, 1, 2), K1, dist1, P=K1).reshape(-1, 2)

    pts4d = cv2.triangulatePoints(P0, P1, pts0_u.T, pts1_u.T)
    pts3d = (pts4d[:3] / pts4d[3]).T

    # 재투영 오차로 필터링
    proj0 = (P0 @ np.hstack([pts3d, np.ones((len(pts3d), 1))]).T).T
    proj0 = proj0[:, :2] / proj0[:, 2:3]
    err = np.linalg.norm(proj0 - pts0_u, axis=1)
    good_mask = err < max_reproj_error

    pts3d = pts3d[good_mask]
    colors = colors_bgr[good_mask][:, ::-1] if len(colors_bgr) == len(good_mask) else np.full((len(pts3d), 3), 200)

    return pts3d, colors


def write_ply(path, points, colors):
    assert len(points) == len(colors)
    with open(path, "w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        f.write("end_header\n")
        for (x, y, z), (r, g, b) in zip(points, colors):
            f.write(f"{x:.4f} {y:.4f} {z:.4f} {int(r)} {int(g)} {int(b)}\n")


def main():
    args = parse_args()

    shots = sorted(glob.glob(os.path.join(args.session, "shot_*")))
    if not shots:
        print(f"[오류] {args.session} 안에 shot_* 폴더가 없습니다.", file=sys.stderr)
        sys.exit(1)

    K0, dist0, K1, dist1, P01_0, P01_1 = load_projection_matrices(args.stereo01)
    K0b, dist0b, K2, dist2, P02_0, P02_2 = load_projection_matrices(args.stereo02)

    all_points, all_colors = [], []

    for shot_dir in shots:
        p0 = os.path.join(shot_dir, "cam0.png")
        p1 = os.path.join(shot_dir, "cam1.png")
        p2 = os.path.join(shot_dir, "cam2.png")
        if not (os.path.exists(p0) and os.path.exists(p1) and os.path.exists(p2)):
            print(f"[건너뜀] {shot_dir}: cam0/1/2.png 중 일부가 없습니다.")
            continue

        img0 = cv2.imread(p0)
        img1 = cv2.imread(p1)
        img2 = cv2.imread(p2)

        pts_01, col_01 = match_and_triangulate(
            img0, img1, K0, dist0, K1, dist1, P01_0, P01_1, args.ratio, args.max_reproj_error
        )
        pts_02, col_02 = match_and_triangulate(
            img0, img2, K0b, dist0b, K2, dist2, P02_0, P02_2, args.ratio, args.max_reproj_error
        )

        print(f"{os.path.basename(shot_dir)}: cam0-1 {len(pts_01)}점, cam0-2 {len(pts_02)}점")

        if len(pts_01):
            all_points.append(pts_01)
            all_colors.append(col_01)
        if len(pts_02):
            all_points.append(pts_02)
            all_colors.append(col_02)

    if not all_points:
        print("[오류] 생성된 3D 점이 없습니다. 캘리브레이션/촬영 상태를 확인하세요.", file=sys.stderr)
        sys.exit(1)

    points = np.vstack(all_points)
    colors = np.vstack(all_colors)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_ply(args.out, points, colors)
    print(f"총 {len(points)}개 점 -> {args.out}")


if __name__ == "__main__":
    main()
