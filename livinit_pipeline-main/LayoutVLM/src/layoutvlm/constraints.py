import math
import warnings

import numpy as np
import torch
from shapely.geometry import Polygon

from .constraint_utils import *
from .device_utils import get_device_with_index, to_device

# Try to import oriented_iou_loss - prefer CPU version for portability
try:
    from third_party.Rotated_IoU import oriented_iou_loss_cpu as oriented_iou_loss
    ORIENTED_IOU_AVAILABLE = True
except ImportError:
    try:
        from third_party.Rotated_IoU import oriented_iou_loss
        ORIENTED_IOU_AVAILABLE = True
    except ImportError as e:
        ORIENTED_IOU_AVAILABLE = False
        warnings.warn(f"Could not import oriented_iou_loss: {e}")


class Constraint:
    def __init__(self, constraint_name, constraint_func, description="", **params):
        self.constraint_name = constraint_name
        self.constraint_func = constraint_func
        self.description = description.format(**params)
        self.params = params

    def evaluate(self, assets: list, device=None):
        if device is None:
            device = get_device_with_index()
        # Ensure device is available
        if device.startswith("cuda") and not torch.cuda.is_available():
            device = "cpu"
        return self.constraint_func(assets, **self.params, device=device)


def get_bounding_box(obj):
    position = obj.position
    size = obj.size
    return (
        position[0] - size[0] / 2,
        position[0] + size[0] / 2,
        position[1] - size[1] / 2,
        position[1] + size[1] / 2,
        position[2] - size[2] / 2,
        position[2] + size[2] / 2,
    )


def get_center_position(obj):
    min_x, max_x, min_y, max_y, min_z, max_z = get_bounding_box(obj)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    center_z = (min_z + max_z) / 2
    return center_x, center_y, center_z


def bbox_overlap_loss(
    assets: list,
    skipped_asset_pairs: list = [],
    only_consider_overlapping_assets=False,
    detach_asset2=False,
    consider_z_axis=True,
    epsilon=1e-5,
    device=None,
):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    """
    This function calculates the loss for the 3D bounding boxes of the assets to not overlap
    """

    def segment_overlap(x1, y1, x2, y2):
        max_start = max(x1, x2)
        min_end = min(y1, y2)
        overlap_length = max(0, min_end - max_start)
        return overlap_length

    num_assets = len(assets)
    if num_assets < 2:
        return torch.tensor(0.0, requires_grad=True).to(device), torch.tensor(
            0.0, requires_grad=True
        ).to(device)

    overlap_coefs = []
    corners1 = []
    corners2 = []
    area1 = []
    area2 = []
    for i in range(num_assets):
        asset_i = assets[i]

        # Handle size robustly
        if hasattr(asset_i, "dimensions"):
            size_i = asset_i.dimensions
        elif isinstance(asset_i.size, (int, float)):
            size_i = [asset_i.size, asset_i.size, asset_i.size]
        else:
            size_i = asset_i.size

        area_i = size_i[0] * size_i[1]

        for j in range(i + 1, num_assets):
            asset_j = assets[j]

            # Handle size robustly
            if hasattr(asset_j, "dimensions"):
                size_j = asset_j.dimensions
            elif isinstance(asset_j.size, (int, float)):
                size_j = [asset_j.size, asset_j.size, asset_j.size]
            else:
                size_j = asset_j.size

            area_j = size_j[0] * size_j[1]
            if (
                (asset_i.id, asset_j.id) in skipped_asset_pairs
                or (asset_j.id, asset_i.id) in skipped_asset_pairs
                or (asset_i.id.startswith("void") and asset_j.id.startswith("void"))
            ):
                continue
            if only_consider_overlapping_assets:
                with torch.no_grad():
                    corner_i = asset_i.get_2dpolygon().detach().cpu().numpy()
                    corner_j = asset_j.get_2dpolygon().detach().cpu().numpy()
                    poly_i = Polygon(corner_i)
                    poly_j = Polygon(corner_j)
                    if not poly_i.intersects(poly_j):
                        continue
            if consider_z_axis:
                # Handle tensor vs float for size
                h_i = (
                    size_i[-1].item()
                    if isinstance(size_i, torch.Tensor)
                    else size_i[-1]
                )
                h_j = (
                    size_j[-1].item()
                    if isinstance(size_j, torch.Tensor)
                    else size_j[-1]
                )

                overlap_coef = segment_overlap(
                    asset_i.position[-1].item() - h_i / 2,
                    asset_i.position[-1].item() + h_i / 2,
                    asset_j.position[-1].item() - h_j / 2,
                    asset_j.position[-1].item() + h_j / 2,
                )
                if overlap_coef < 0.05:
                    overlap_coef = 0
                overlap_coefs.append(overlap_coef)

            if detach_asset2:
                corners1.append(asset_i.get_2dpolygon())
                corners2.append(asset_j.get_2dpolygon())
                area1.append(area_i)
                area2.append(area_j)
            else:
                if abs(area_i - area_j) < epsilon:
                    corners1.append(asset_i.get_2dpolygon())
                    corners2.append(asset_j.get_2dpolygon())
                    area1.append(area_i)
                    area2.append(area_j)

                    corners1.append(asset_j.get_2dpolygon())
                    corners2.append(asset_i.get_2dpolygon())
                    area1.append(area_j)
                    area2.append(area_i)

                    if consider_z_axis:
                        overlap_coefs.append(overlap_coef)
                else:
                    small_asset, bigger_asset = (
                        (asset_i, asset_j) if area_i < area_j else (asset_j, asset_i)
                    )
                    corners1.append(small_asset.get_2dpolygon())
                    corners2.append(bigger_asset.get_2dpolygon())
                    area1.append(min(area_i, area_j))
                    area2.append(max(area_i, area_j))

    if len(corners1) == 0:
        return torch.tensor(0.0, requires_grad=False), torch.tensor(
            0.0, requires_grad=False
        )

    corners1 = torch.stack(corners1, dim=0).unsqueeze(0)
    corners2 = torch.stack(corners2, dim=0).unsqueeze(0)
    area1 = torch.tensor(area1, dtype=torch.float32, requires_grad=False).unsqueeze(0)
    area2 = torch.tensor(area2, dtype=torch.float32, requires_grad=False).unsqueeze(0)

    if not ORIENTED_IOU_AVAILABLE:
        return torch.tensor(0.0, requires_grad=False), torch.tensor(0.0, requires_grad=False)

    def corners_to_box(corners):
        center = torch.mean(corners, dim=2)
        edge1 = corners[..., 1, :] - corners[..., 0, :]
        w = torch.norm(edge1, dim=-1)
        edge2 = corners[..., 2, :] - corners[..., 1, :]
        h = torch.norm(edge2, dim=-1)
        alpha = torch.atan2(edge1[..., 1], edge1[..., 0]) - math.pi
        return torch.stack([center[..., 0], center[..., 1], w, h, alpha], dim=-1)

    box1 = corners_to_box(corners1)
    box2 = corners_to_box(corners2)
    giou_loss, iou = oriented_iou_loss.cal_giou(box1, box2)

    if consider_z_axis:
        overlap_coefs = (
            torch.tensor(overlap_coefs, dtype=torch.float32, requires_grad=False)
            .unsqueeze(0)
            .to(device)
        )
        giou_loss = giou_loss * overlap_coefs
        iou = iou * overlap_coefs
    return -torch.mean(giou_loss), torch.sum(iou)


################################
### distance-based
################################
def distance_constraint(
    assets: list, min_distance, max_distance, weight=1.0, device=None
):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    coord1 = assets[0].position[:2].to(device)
    coord2 = assets[1].position[:2].to(device).detach()
    loss = distance_loss(
        coord1, coord2, min_distance=min_distance, max_distance=max_distance
    )
    return weight * torch.clamp(loss, max=1)


def distance_constraint_deterministic(
    assets: list, min_distance, max_distance, weight=1.0, device=None
):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    distance = torch.linalg.norm(assets[0].position[:2] - assets[1].position[:2])
    if min_distance < distance < max_distance:
        return (torch.tensor(0.0), distance)
    else:
        return (torch.tensor(100000.0), distance)


################################
### top-bottom based
################################
def on_top_of_deterministic(assets: list, device=None):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    min_x1, max_x1, min_y1, max_y1, min_z1, max_z1 = get_bounding_box(assets[0])
    min_x2, max_x2, min_y2, max_y2, min_z2, max_z2 = get_bounding_box(assets[1])

    coord1 = torch.tensor(min_z1, dtype=torch.float32)
    coord2 = torch.tensor(max_z2, dtype=torch.float32)

    vertical_loss = coord1 - coord2
    if vertical_loss < 0.1:
        return torch.tensor(10)
    else:
        giou_loss, iou = bbox_overlap_loss(
            assets, detach_asset2=True, consider_z_axis=False, device=device
        )
        return -10 * iou


def on_top_of(assets: list, device=None):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    giou_loss, iou = bbox_overlap_loss(
        assets, detach_asset2=True, consider_z_axis=False, device=device
    )
    return torch.clamp(-10 * iou, min=-10, max=10)


################################
### orientation-based
################################
def point_towards(assets: list, angle=0, device=None):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    asset1, asset2 = assets
    vector1 = asset1.get_2dvector(add_radian=-math.radians(angle)).to(device)
    corners2 = asset2.get_2dpolygon().to(device)

    with torch.no_grad():
        intersects = ray_intersects_polygon(
            origin=asset1.position[:2].detach().cpu().numpy(),
            direction=vector1.detach().cpu().numpy(),
            polygon=corners2.detach().cpu().numpy(),
        )

    if intersects:
        return torch.tensor(0.0, requires_grad=True, device=device)
    else:
        vector2 = (asset2.position[:2] - asset1.position[:2]).to(device).detach()
        return cosine_distance_loss(vector1, vector2)


def align_with(assets: list, angle=0, device=None):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    asset1, asset2 = assets
    vector1 = asset1.get_2dvector(add_radian=-math.radians(angle)).to(device)
    vector2 = asset2.get_2dvector().to(device).detach()
    return cosine_distance_loss(vector1, vector2)


################################
### others
################################
def against_wall(assets: list, device=None):
    if device is None:
        device = get_device_with_index()
    # Ensure device is available
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    assert len(assets) == 2
    asset, wall = assets
    vector = asset.get_2dvector(add_radian=-math.radians(90)).to(device)
    corners = asset.get_2dpolygon().to(device)
    segment = torch.tensor(
        [[wall.corner1[0], wall.corner1[1], wall.corner2[0], wall.corner2[1]]],
        dtype=corners.dtype,
        requires_grad=False,
    ).to(device)
    distances = point_to_segment_batch_loss(corners[:4, ...], segment)
    angle_difference = cosine_distance_loss(vector, wall.get_2dvector())
    return torch.clamp(torch.sum(distances[:2, 0]), max=10) + 10 * angle_difference


################################
### deprecated
################################
# visual mark / boundary-based
# def locate_grid(assets):
#   asset1, grid = assets
#   coord1 = asset1.position[:2]
#   coord2 = grid.position[:2]
#   assert coord1.requires_grad, "coord1 does not require gradients"
#   assert coord2.requires_grad, "coord2 does not require gradients"
#   #assert len(assets) == 2
#   return 0.01  * distance_loss(coord1, coord2, min_distance=0, max_distance=1)

# def align_x(assets):
#    assert len(assets) == 2
#    asset1, asset2 = assets
#    # Calculate the Mean Squared Error (MSE) between the x-coordinates
#    return torch.nn.functional.mse_loss(asset1.position[0], asset2.position[0])
#
# def align_y(assets):
#    assert len(assets) == 2
#    asset1, asset2 = assets
#    # Calculate the Mean Squared Error (MSE) between the x-coordinates
#    return torch.nn.functional.mse_loss(asset1.position[0], asset2.position[0])


ALL_CONSTRAINTS = {
    "distance": Constraint(
        constraint_name="distance_constraint",
        constraint_func=distance_constraint,
        description="the distance between the two objects should be within the specified range",
    ),
    "close_to": Constraint(
        constraint_name="close_to",
        constraint_func=distance_constraint,
        description="",
        min_distance=0,
        max_distance=1,
    ),
    "close_to_deterministic": Constraint(
        constraint_name="close_to",
        constraint_func=distance_constraint_deterministic,
        description="",
        min_distance=0,
        max_distance=1,
    ),
    "moderate_distance": Constraint(
        constraint_name="moderate_distance",
        constraint_func=distance_constraint,
        description="",
        min_distance=1,
        max_distance=3,
    ),
    "moderate_distance_deterministic": Constraint(
        constraint_name="moderate_distance",
        constraint_func=distance_constraint_deterministic,
        description="",
        min_distance=1,
        max_distance=3,
    ),
    "point_towards": Constraint(
        constraint_name="point_towards",
        constraint_func=point_towards,
        description="the oriented bounding box of first object should be pointing towards the second object",
    ),
    "against_wall": Constraint(
        constraint_name="against_wall",
        constraint_func=against_wall,
        description="the bounding box of the first object should overlap with the bounding box of the second object",
    ),
    "on_top_of_deterministic": Constraint(
        constraint_name="on_top_of_deterministic",
        constraint_func=on_top_of_deterministic,
        description="the first object should be on the second object within the specified distance range",
    ),
    "on_top_of": Constraint(
        constraint_name="on_top_of",
        constraint_func=on_top_of,
        description="the first object should be on the second object within the specified distance range",
    ),
    "align_with": Constraint(
        constraint_name="align_with",
        constraint_func=align_with,
        description="the first object should be aligned with the second object both in orientation and distance",
    ),
}
