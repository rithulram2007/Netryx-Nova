import math

import numpy as np
import torch
from PIL import Image


def haversine(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    r = 6371.0
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def haversine_np(lat1: float, lon1: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    r = 6371.0
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = np.radians(lats)
    lon2_r = np.radians(lons)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def grid_points(
    center: tuple[float, float], radius: float, resolution: int
) -> list[tuple[float, float]]:
    import itertools

    lat, lon = center
    top_left = (lat - radius / 70, lon + radius / 70)
    bottom_right = (lat + radius / 70, lon - radius / 70)
    lat_diff = top_left[0] - bottom_right[0]
    lon_diff = top_left[1] - bottom_right[1]
    raw = list(itertools.product(range(resolution + 1), range(resolution + 1)))
    pts = [
        (bottom_right[0] + x * lat_diff / resolution, bottom_right[1] + y * lon_diff / resolution)
        for (x, y) in raw
    ]
    return [p for p in pts if haversine(p, center) <= radius]


def generate_circle_points(
    center_lat: float, center_lon: float, radius_km: float, num_points: int = 36
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    r = 6371.0
    lat_rad = math.radians(center_lat)
    lon_rad = math.radians(center_lon)
    angular_dist = radius_km / r
    for i in range(num_points):
        bearing = math.radians(i * (360 / num_points))
        new_lat = math.asin(
            math.sin(lat_rad) * math.cos(angular_dist)
            + math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing)
        )
        new_lon = lon_rad + math.atan2(
            math.sin(bearing) * math.sin(angular_dist) * math.cos(lat_rad),
            math.cos(angular_dist) - math.sin(lat_rad) * math.sin(new_lat),
        )
        points.append((math.degrees(new_lat), math.degrees(new_lon)))
    return points


def get_projection_base_dirs(
    fov_deg: float, out_hw: tuple[int, int], device: torch.device | None = None
) -> torch.Tensor:
    if device is None:
        has_mps = torch.backends.mps.is_available()
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if has_mps else "cpu")
    fov = math.radians(fov_deg)
    out_h, out_w = out_hw
    cx, cy = out_w / 2.0, out_h / 2.0
    fx = fy = (out_w / 2.0) / math.tan(fov / 2.0)
    xx, yy = torch.meshgrid(
        torch.arange(out_w, device=device, dtype=torch.float32),
        torch.arange(out_h, device=device, dtype=torch.float32),
        indexing="xy",
    )
    x = (xx - cx) / fx
    y = (yy - cy) / fy
    z = torch.ones_like(x)
    dirs = torch.stack([x, -y, z], dim=-1)
    dirs = dirs / torch.norm(dirs, dim=-1, keepdim=True)
    return dirs.reshape(-1, 3).T


def equirectangular_to_rectilinear_torch(
    pano_tensor: torch.Tensor,
    fov_deg: float = 90,
    out_hw: tuple[int, int] = (400, 400),
    yaw_deg: float | list[float] | torch.Tensor = 0,
    pitch_deg: float = 0,
    base_dirs: torch.Tensor | None = None,
) -> torch.Tensor:
    device = pano_tensor.device
    _, _, h, w = pano_tensor.shape
    out_h, out_w = out_hw

    if isinstance(yaw_deg, (float, int)):
        yaws = torch.tensor([yaw_deg], device=device, dtype=torch.float32)
    elif isinstance(yaw_deg, list):
        yaws = torch.tensor(yaw_deg, device=device, dtype=torch.float32)
    else:
        yaws = yaw_deg.to(device).float()
    b = len(yaws)

    yaws_rad = torch.deg2rad(yaws)
    cos_vals = torch.cos(yaws_rad)
    sin_vals = torch.sin(yaws_rad)
    zeros = torch.zeros_like(cos_vals)
    ones = torch.ones_like(cos_vals)

    row1 = torch.stack([cos_vals, zeros, sin_vals], dim=1)
    row2 = torch.stack([zeros, ones, zeros], dim=1)
    row3 = torch.stack([-sin_vals, zeros, cos_vals], dim=1)
    rot = torch.stack([row1, row2, row3], dim=1)

    if base_dirs is None:
        base_dirs = get_projection_base_dirs(fov_deg, out_hw, device=device)

    dirs = torch.matmul(rot, base_dirs.unsqueeze(0))
    dirs = dirs.permute(0, 2, 1)
    x = dirs[:, :, 0]
    y = dirs[:, :, 1]
    z = dirs[:, :, 2]

    lon = torch.atan2(x, z)
    lat = torch.asin(y.clamp(-1 + 1e-7, 1 - 1e-7))
    grid_x = lon / math.pi
    grid_y = -lat / (math.pi / 2.0)
    grid = torch.stack([grid_x, grid_y], dim=-1).reshape(b, out_h, out_w, 2)

    pano_batch = pano_tensor.expand(b, -1, -1, -1)
    out = torch.nn.functional.grid_sample(pano_batch, grid, mode="bilinear", align_corners=True)
    return out


def equirectangular_to_rectilinear(
    pano_img: Image.Image,
    fov_deg: float = 90,
    out_hw: tuple[int, int] = (400, 400),
    yaw_deg: float = 0,
    pitch_deg: float = 0,
) -> Image.Image:
    import numpy as np

    has_mps = torch.backends.mps.is_available()
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if has_mps else "cpu")
    arr = np.array(pano_img.convert("RGB"))
    pano_tensor = (
        torch.from_numpy(arr).float().permute(2, 0, 1).unsqueeze(0).div(255.0).to(device)
    )
    out_tensor = equirectangular_to_rectilinear_torch(
        pano_tensor, fov_deg, out_hw, yaw_deg, pitch_deg
    )
    out_t = (
        out_tensor.squeeze(0).cpu().clamp(0, 1).mul(255).add_(0.5)
        .to(torch.uint8).permute(1, 2, 0).numpy()
    )
    return Image.fromarray(out_t)


def pil_to_tensor(pil_img: Image.Image, device: torch.device | str | None = None) -> torch.Tensor:
    if device is None:
        has_mps = torch.backends.mps.is_available()
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if has_mps else "cpu")
    return (
        torch.from_numpy(np.array(pil_img.convert("RGB")))
        .float().permute(2, 0, 1).unsqueeze(0).div(255.0).to(device)
    )


def tensor_to_pil(t: torch.Tensor) -> Image.Image:
    arr = (
        t.squeeze(0).cpu().clamp(0, 1).mul(255).add_(0.5)
        .to(torch.uint8).permute(1, 2, 0).numpy()
    )
    return Image.fromarray(arr)
