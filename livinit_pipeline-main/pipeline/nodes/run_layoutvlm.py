"""
Self-contained layout solver with gradient-based optimization.
"""
import io
import logging
import math
import time
from typing import Any, List, Optional
import copy

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from pydantic import BaseModel, Field
from shapely.geometry import Point, Polygon

logger = logging.getLogger(__name__)
logging.getLogger("PIL").setLevel(logging.WARNING)

def _get_device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def _point_to_segment_batch_loss(points, segments):
    px, py = points[:, 0].unsqueeze(1), points[:, 1].unsqueeze(1)
    x1, y1, x2, y2 = segments[:, 0], segments[:, 1], segments[:, 2], segments[:, 3]
    x1, y1, x2, y2 = x1.unsqueeze(0), y1.unsqueeze(0), x2.unsqueeze(0), y2.unsqueeze(0)
    dpx, dpy = px - x1, py - y1
    dx, dy = x2 - x1, y2 - y1
    projection = torch.clamp((dpx * dx + dpy * dy) / (dx * dx + dy * dy + 1e-8), 0, 1)
    closest_x, closest_y = x1 + projection * dx, y1 + projection * dy
    return (closest_x - px) ** 2 + (closest_y - py) ** 2


def _cosine_distance_loss(v1, v2):
    return 1 - torch.sum(F.normalize(v1, p=2, dim=-1) * F.normalize(v2, p=2, dim=-1), dim=-1).mean()


def _distance_loss(c1, c2, min_d=1.0, max_d=3.0):
    min_d, max_d = (0 if min_d is None else min_d), (1e6 if max_d is None else max_d)
    sq = torch.sum((c1 - c2) ** 2)
    return F.relu(min_d**2 - sq) + F.relu(sq - max_d**2)


class SandboxAssetInstance(BaseModel):
    optimize: int = Field(default=1)
    position: List[float] = Field(default=[0, 0, 0])
    rotation: List[float] = Field(default=[0, 0, 0])
    instance_id: Optional[str] = Field(default=None)
    size: Optional[List[float]] = Field(default=None)
    model_config = {"extra": "allow"}

    def __init__(self, **data):
        if "position" in data and len(data["position"]) == 2:
            data["position"] = list(data["position"]) + [0]
        super().__init__(**data)


class Assets(BaseModel):
    description: str = Field(default="")
    placements: List[SandboxAssetInstance] = Field(default_factory=list)
    size: Optional[List[float]] = Field(default=None)
    onCeiling: bool = Field(default=False)
    model_config = {"extra": "allow"}

    @property
    def instance_id(self) -> Optional[str]:
        return self.placements[0].instance_id if len(self.placements) == 1 else None

    @instance_id.setter
    def instance_id(self, value: str):
        if self.placements:
            self.placements[0].instance_id = value

    @property
    def position(self) -> List[float]:
        return self.placements[0].position if self.placements else [0, 0, 0]

    @property
    def rotation(self) -> List[float]:
        return self.placements[0].rotation if self.placements else [0, 0, 0]

    def __getitem__(self, idx: int) -> SandboxAssetInstance:
        return self.placements[idx]

    def __len__(self) -> int:
        return len(self.placements)


class SandboxWall:
    def __init__(self, corner1, corner2, instance_id):
        self.corner1, self.corner2, self.instance_id = corner1, corner2, instance_id


class SandboxConstraint:
    def __init__(self, name, **params):
        self.constraint_name, self.params = name, params


class ConstraintSolver:
    def __init__(self):
        self.constraints = []
        self._fixed = Assets(placements=[])

    def _id(self, a):
        if hasattr(a, "instance_id") and a.instance_id:
            return a.instance_id
        if isinstance(a, tuple):
            idx = len(self._fixed.placements)
            self._fixed.placements.append(SandboxAssetInstance(position=list(a), instance_id=f"fixed_point_{idx}", optimize=0))
            return f"fixed_point_{idx}"
        return None

    def _asset(self, a):
        if isinstance(a, tuple):
            idx = len(self._fixed.placements)
            self._fixed.placements.append(SandboxAssetInstance(position=list(a), instance_id=f"fixed_point_{idx}", optimize=0))
            return self._fixed.placements[-1]
        return a

    def point_towards(self, a1, a2, angle=0):
        a1.instance_id = self._id(a1) or a1.instance_id
        a2 = self._asset(a2)
        a2.instance_id = self._id(a2) or a2.instance_id
        self.constraints.append([SandboxConstraint("point_towards", angle=angle), [a1.instance_id, a2.instance_id]])

    def distance_constraint(self, a1, a2, min_distance=0, max_distance=10000, weight=1):
        a1.instance_id = self._id(a1) or a1.instance_id
        a2 = self._asset(a2)
        a2.instance_id = self._id(a2) or a2.instance_id
        self.constraints.append([SandboxConstraint("distance_constraint", min_distance=min_distance, max_distance=max_distance, weight=weight), [a1.instance_id, a2.instance_id]])

    def against_wall(self, a1, wall):
        a1.instance_id = self._id(a1) or a1.instance_id
        wid = wall.instance_id if hasattr(wall, "instance_id") else f"walls_{wall}" if isinstance(wall, int) else str(wall)
        self.constraints.append([SandboxConstraint("against_wall"), [a1.instance_id, wid]])

    def on_top_of(self, a1, a2):
        a1.instance_id = self._id(a1) or a1.instance_id
        a2 = self._asset(a2)
        a2.instance_id = self._id(a2) or a2.instance_id
        self.constraints.append([SandboxConstraint("on_top_of"), [a1.instance_id, a2.instance_id]])

    def skip_overlap(self, a1, a2):
        a1.instance_id = self._id(a1) or a1.instance_id
        a2 = self._asset(a2)
        a2.instance_id = self._id(a2) or a2.instance_id
        self.constraints.append([SandboxConstraint("skip_overlap"), [a1.instance_id, a2.instance_id]])

    def align_with(self, a1, a2, angle=0):
        a1.instance_id = self._id(a1) or a1.instance_id
        if hasattr(a2, "instance_id"):
            a2.instance_id = self._id(a2) or a2.instance_id
            a2id = a2.instance_id
        else:
            a2id = f"walls_{a2}" if isinstance(a2, int) else str(a2)
        self.constraints.append([SandboxConstraint("align_with", angle=angle), [a1.instance_id, a2id]])


class TorchWall:
    def __init__(self, wid, c1, c2, device="cpu"):
        self.id, self.device, self.corner1, self.corner2, self.optimize, self.size = wid, device, c1, c2, 0, None
        self.position = torch.tensor([(c1[0]+c2[0])/2, (c1[1]+c2[1])/2, 0], dtype=torch.float32, device=device, requires_grad=False)
        self.rotation = torch.tensor([0, 0], dtype=torch.float32, device=device, requires_grad=False)

    def get_2dvector(self, add_radian=0):
        vec = F.normalize(torch.tensor([self.corner2[0]-self.corner1[0], self.corner2[1]-self.corner1[1]], dtype=torch.float32, device=self.device), p=2, dim=-1)
        if add_radian:
            c, s = torch.cos(torch.tensor(add_radian)), torch.sin(torch.tensor(add_radian))
            vec = torch.matmul(torch.tensor([[c, -s], [s, c]], dtype=torch.float32, device=self.device), vec)
        return vec


class TorchAsset:
    def __init__(self, aid, pos, rot, size, onCeiling=False, optimize=1, device="cpu"):
        self.id, self.onCeiling, self.device, self.optimize = aid, onCeiling, device, optimize
        pos = list(pos) + [0] if len(pos) == 2 else list(pos)
        rot = rot or [0, 0, 0]
        self.position = torch.nn.Parameter(torch.tensor(pos, dtype=torch.float32, device=device), requires_grad=(optimize > 0))
        rz = rot[-1] - math.pi/2
        self.rotation = torch.nn.Parameter(torch.tensor([math.cos(rz), math.sin(rz)], dtype=torch.float32, device=device), requires_grad=(optimize > 0))
        size = [size]*3 if isinstance(size, (int, float)) else (size*3)[:3] if len(size) < 3 else size
        self.size = size
        self.dimensions = torch.tensor(size, dtype=torch.float32, device=device, requires_grad=False)

    def get_theta(self):
        return math.atan2(self.rotation[1].item(), self.rotation[0].item()) + math.pi/2

    def get_2dvector(self, add_radian=0):
        rot = F.normalize(self.rotation, p=2, dim=-1)
        if add_radian:
            c, s = torch.cos(torch.tensor(add_radian)), torch.sin(torch.tensor(add_radian))
            rot = torch.matmul(torch.tensor([[c, -s], [s, c]], dtype=torch.float32, device=self.device), rot)
        return rot

    def get_2dpolygon(self):
        rot = F.normalize(self.rotation, p=2, dim=-1)
        # Rotate by (rz - π/2) so local +Y (front) aligns with facing direction [cos(rz), sin(rz)]
        rm = torch.stack([torch.stack([rot[1], -rot[0]]), torch.stack([rot[0], rot[1]])])
        d = self.dimensions
        corners = torch.tensor([[-d[0]/2, -d[1]/2], [-d[0]/2, d[1]/2], [d[0]/2, d[1]/2], [d[0]/2, -d[1]/2]], dtype=rm.dtype, device=self.device)
        return torch.matmul(corners, rm) + self.position[:2]


class GradConstraint:
    def __init__(self, name, func, **params):
        self.name, self.func, self.params = name, func, params

    def evaluate(self, assets, device="cpu"):
        return self.func(assets, **self.params, device=device)


def _c_distance(assets, min_distance, max_distance, weight=1.0, device="cpu"):
    return weight * torch.clamp(_distance_loss(assets[0].position[:2].to(device), assets[1].position[:2].to(device).detach(), min_distance, max_distance), max=1)


def _c_point_towards(assets, angle=0, device="cpu"):
    a1, a2 = assets
    v1 = a1.get_2dvector(add_radian=-math.radians(angle)).to(device)
    target_dir = (a2.position[:2] - a1.position[:2]).to(device).detach()
    return _cosine_distance_loss(v1, target_dir)


def _c_align_with(assets, angle=0, device="cpu"):
    return _cosine_distance_loss(assets[0].get_2dvector(add_radian=-math.radians(angle)).to(device), assets[1].get_2dvector().to(device).detach())


def _c_against_wall(assets, device="cpu"):
    a, w = assets
    # Side of asset should be parallel to wall (so back faces wall)
    vec, corners = a.get_2dvector(add_radian=-math.pi/2).to(device), a.get_2dpolygon().to(device)
    seg = torch.tensor([[w.corner1[0], w.corner1[1], w.corner2[0], w.corner2[1]]], dtype=corners.dtype, device=device)
    # Use back corners [0] and [3] for distance to wall
    back_corners = corners[[0, 3]]
    return torch.clamp(torch.sum(_point_to_segment_batch_loss(back_corners, seg)[:, 0]), max=10) + 10 * _cosine_distance_loss(vec, w.get_2dvector())


def _c_on_top_of(assets, device="cpu"):  # noqa: ARG001
    # z-positioning handled separately in project_back, no xy gradient needed
    del assets  # unused, z-positioning in project_back
    return torch.tensor(0.0, device=device)


def _bbox_overlap_loss(assets, skipped=[], device="cpu"):
    """Compute overlap loss with gradients to push assets apart. Rugs can be under other assets."""
    if len(assets) < 2:
        return torch.tensor(0.0, device=device)
    # Build set of skipped IDs for fast lookup
    skipped_set = {pair for pair in skipped} | {(b, a) for a, b in skipped}
    total = torch.tensor(0.0, device=device)
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            id_i, id_j = assets[i].id, assets[j].id
            if (id_i, id_j) in skipped_set:
                continue
            # Skip rugs (can be under furniture)
            if "rug" in id_i.lower() or "rug" in id_j.lower():
                continue
            # Check overlap using shapely (non-differentiable)
            with torch.no_grad():
                pi = Polygon(assets[i].get_2dpolygon().detach().cpu().numpy())
                pj = Polygon(assets[j].get_2dpolygon().detach().cpu().numpy())
                overlaps = pi.intersects(pj)
            # If overlapping, add differentiable distance loss to push apart
            if overlaps:
                dist_sq = torch.sum((assets[i].position[:2] - assets[j].position[:2]) ** 2)
                min_dist = (assets[i].dimensions[0] + assets[j].dimensions[0]) / 2
                total = total + F.relu(min_dist ** 2 - dist_sq)
    return total


def _boundary_loss(assets, boundary, device="cpu"):
    """Push assets inside room boundary using differentiable loss."""
    poly = Polygon(boundary)
    centroid = poly.centroid
    center = torch.tensor([centroid.x, centroid.y], dtype=torch.float32, device=device)
    total = torch.tensor(0.0, device=device)
    for a in assets:
        if not a.optimize or a.id.startswith("walls") or a.id.startswith("fixed_point"):
            continue
        corners = a.get_2dpolygon()
        for c in corners:
            with torch.no_grad():
                pt = Point(c[0].item(), c[1].item())
                outside = not poly.buffer(0.01).contains(pt)
            if outside:
                # Push corner toward room center
                total = total + torch.sum((c - center) ** 2) * 0.1
    return total


def _rotate_point(x, y, radians):
    """Rotate point around origin - matches layout_preview.py"""
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def _capture_frame(assets, boundary):
    """Capture current layout state as PIL Image."""
    fig, ax = plt.subplots(figsize=(8, 8))
    bx = [b[0] for b in boundary] + [boundary[0][0]]
    by = [b[1] for b in boundary] + [boundary[0][1]]
    ax.plot(bx, by, "k-", linewidth=2)
    ax.fill(bx, by, alpha=0.1, color="gray")
    for iid, a in assets.items():
        if iid.startswith("walls") or iid.startswith("fixed_point"):
            continue
        # Use same polygon calculation as layout_preview.py
        pos_x, pos_y = a.position[0].item(), a.position[1].item()
        dim_x, dim_y = a.dimensions[0].item(), a.dimensions[1].item()
        rotation_z = a.get_theta()
        local_corners = [(-dim_x/2, -dim_y/2), (dim_x/2, -dim_y/2), (dim_x/2, dim_y/2), (-dim_x/2, dim_y/2)]
        corners = [(_rotate_point(cx, cy, rotation_z)[0] + pos_x, _rotate_point(cx, cy, rotation_z)[1] + pos_y) for cx, cy in local_corners]
        xs = [c[0] for c in corners] + [corners[0][0]]
        ys = [c[1] for c in corners] + [corners[0][1]]
        color = "blue" if a.optimize else "red"
        ax.fill(xs, ys, alpha=0.4, color=color)
        ax.plot(xs, ys, color=color, linewidth=1)
        # Direction arrow using same convention as layout_preview.py
        ax.arrow(pos_x, pos_y, math.sin(rotation_z) * 0.3, -math.cos(rotation_z) * 0.3, head_width=0.1, color=color)
        ax.text(pos_x, pos_y, iid.split("_")[0][:6], fontsize=6, ha="center")
    ax.set_aspect("equal")
    ax.set_title("Layout Optimization")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).copy()


class GradientSolver:
    def __init__(self, boundary):
        self.device, self.boundary, self.on_top_of, self.frames = _get_device(), boundary, [], []

    def project_back(self, assets):
        poly = Polygon(self.boundary)
        # Build lookup: which asset is on top of which
        on_top_base = {top: base for top, base in self.on_top_of}
        with torch.no_grad():
            for iid, a in assets.items():
                if iid.startswith("walls") or iid.startswith("fixed_point") or not a.optimize:
                    continue
                for _ in range(3):
                    corners, fixed = a.get_2dpolygon().cpu().numpy(), True
                    for c in corners:
                        if not poly.buffer(0.01).contains(Point(c)):
                            proj = poly.exterior.interpolate(poly.exterior.project(Point(c)))
                            a.position[:2] += torch.tensor([proj.x - c[0], proj.y - c[1]], dtype=torch.float32, device=self.device)
                            fixed = False
                            break
                    if fixed:
                        break
                # Set z-position based on on_top_of or floor
                if iid in on_top_base and on_top_base[iid] in assets:
                    base = assets[on_top_base[iid]]
                    a.position[2] = base.size[2] + a.size[2] / 2
                elif not a.onCeiling:
                    a.position[2] = a.size[2] / 2

    def optimize(self, assets, constraints, iterations=200, lr=0.01):
        self.frames = []
        if not assets:
            return {}
        self.project_back(assets)
        self.frames.append(_capture_frame(assets, self.boundary))
        params, target_ids = [], set()
        for iid, a in assets.items():
            if a.optimize and a.position.requires_grad:
                params.append(a.position)
                target_ids.add(iid)
            if a.optimize and a.rotation.requires_grad:
                params.append(a.rotation)
                target_ids.add(iid)
        if not params:
            return {}
        opt = torch.optim.Adam(params, lr=lr)
        sched = torch.optim.lr_scheduler.ExponentialLR(opt, gamma=0.96)
        best_loss, best = float("inf"), {}
        for i in range(iterations):
            opt.zero_grad()
            non_fixed = [a for a in assets.values() if not a.id.startswith("walls") and not a.id.startswith("fixed_point")]
            overlap = _bbox_overlap_loss(non_fixed, self.on_top_of, self.device)
            boundary = _boundary_loss(non_fixed, self.boundary, self.device)
            closs = torch.tensor(0.0, requires_grad=True, device=self.device)
            for c, iids in constraints:
                try:
                    # TODO: Temporarily skip distance/on_top_of constraints involving void points
                    include_void = any(id.startswith("void_") for id in iids)
                    if (c.name == "distance_constraint" or c.name == "on_top_of") and not include_void:
                        continue

                    objs = [assets[x] for x in iids if x in assets]
                    if len(objs) == 2:
                        closs = closs + c.evaluate(objs, self.device)
                except Exception:
                    pass
            loss = overlap * 1000 + boundary * 500 + closs
            if loss.requires_grad:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, max_norm=1.0)
                opt.step()
            if i % 10 == 0:
                if loss.item() < best_loss:
                    best_loss = loss.item()
                    best = {iid: {"position": assets[iid].position.data.clone(), "rotation": assets[iid].rotation.data.clone()} for iid in target_ids}
                self.frames.append(_capture_frame(assets, self.boundary))
            if i % 100 == 0:
                self.project_back(assets)
                sched.step()
        for iid, d in best.items():
            assets[iid].position.data, assets[iid].rotation.data = d["position"], d["rotation"]
        self.project_back(assets)
        self.frames.append(_capture_frame(assets, self.boundary))
        return {iid: {"position": assets[iid].position.cpu().detach().numpy().tolist(), "rotation": [0, 0, assets[iid].get_theta()]} for iid in target_ids}


class SandboxEnv:
    def __init__(self, boundary):
        self.boundary, self.device = boundary, _get_device()
        walls = [SandboxWall(boundary[i], boundary[(i+1) % len(boundary)], f"walls_{i}") for i in range(len(boundary))]
        self.local_vars = {"np": np, "solver": ConstraintSolver(), "walls": walls}
        self.grad_solver = GradientSolver(boundary)

    def init_assets(self, cfg):
        counts, sizes = {}, {}
        for uid, c in cfg.items():
            vn = c["asset_var_name"]
            counts[vn] = counts.get(vn, 0) + 1
            bb = c.get("assetMetadata", {}).get("boundingBox", {})
            sizes[vn] = [bb.get("x", 1.0), bb.get("y", 1.0), bb.get("z", 1.0)]
        for vn, cnt in counts.items():
            self.local_vars[vn] = Assets(size=sizes.get(vn, [1, 1, 1]), placements=[SandboxAssetInstance() for _ in range(cnt)])
        idx_map = {}
        for uid, c in cfg.items():
            vn = c["asset_var_name"]
            idx = idx_map.get(vn, 0)
            idx_map[vn] = idx + 1
            inst = self.local_vars[vn].placements[idx]
            inst.instance_id = uid.replace("-", "_")
            if c.get("placements"):
                p = c["placements"][0]
                pos = list(p.get("position", [0, 0, 0]))
                if len(pos) == 2:
                    pos.append(c["assetMetadata"]["boundingBox"]["z"] / 2)
                inst.position, inst.rotation, inst.optimize = pos, p.get("rotation", [0, 0, 0]), p.get("optimize", 1)
            inst.size = sizes.get(vn, [1, 1, 1])

    def exec_constraints(self, program):
        self.local_vars["solver"].constraints = []
        try:
            exec(program, self.local_vars)
        except Exception as e:
            logger.warning(f"Constraint exec error: {e}")

    def build_assets(self):
        assets = {f"walls_{i}": TorchWall(f"walls_{i}", self.boundary[i], self.boundary[(i+1) % len(self.boundary)], self.device) for i in range(len(self.boundary))}
        for obj in self.local_vars.values():
            if isinstance(obj, Assets):
                for inst in obj.placements:
                    if inst.instance_id:
                        assets[inst.instance_id] = TorchAsset(inst.instance_id, inst.position, inst.rotation, inst.size or obj.size or [1, 1, 1], obj.onCeiling, inst.optimize, self.device)
        return assets

    def build_constraints(self):
        func_map = {"distance_constraint": _c_distance, "point_towards": _c_point_towards, "align_with": _c_align_with, "against_wall": _c_against_wall, "on_top_of": _c_on_top_of}
        constraints = []
        skip_overlap_pairs, on_top_of_pairs = [], []
        for c in self.local_vars["solver"].constraints:
            if c[0].constraint_name == "skip_overlap":
                skip_overlap_pairs.append(tuple(c[1]))
                continue
            if c[0].constraint_name not in func_map:
                continue
            if c[0].constraint_name == "on_top_of":
                skip_overlap_pairs.append(tuple(c[1]))
                on_top_of_pairs.append(tuple(c[1]))
            constraints.append((GradConstraint(c[0].constraint_name, func_map[c[0].constraint_name], **c[0].params), c[1]))
        return constraints, skip_overlap_pairs, on_top_of_pairs

    def solve(self, cfg, program):
        self.init_assets(cfg)
        self.exec_constraints(program)
        constraints, skip_overlap_pairs, on_top_of_pairs = self.build_constraints()
        self.grad_solver.on_top_of = skip_overlap_pairs
        self.on_top_of_pairs = on_top_of_pairs
        results = self.grad_solver.optimize(self.build_assets(), constraints)
        return results, self.grad_solver.frames


def _generate_complete_program(cfg, boundary, program):
    """Generate a complete executable sandbox program with all variable definitions."""
    lines = ["# Complete Sandbox Program - Auto-generated", "# Includes all variable definitions and constraints", ""]
    lines.append(f"boundary = {boundary!r}")
    lines.append(f"walls = [type('Wall', (), {{'corner1': boundary[i], 'corner2': boundary[(i+1)%len(boundary)], 'instance_id': f'walls_{{i}}'}})() for i in range(len(boundary))]")
    lines.append("")
    lines.append("class AssetInstance:")
    lines.append("    def __init__(self, position=None, instance_id=None, size=None, optimize=1):")
    lines.append("        self.position = position or [0, 0, 0]")
    lines.append("        self.instance_id = instance_id")
    lines.append("        self.size = size or [1, 1, 1]")
    lines.append("        self.optimize = optimize")
    lines.append("")
    var_assets = {}
    for uid, c in cfg.items():
        vn = c["asset_var_name"]
        bb = c["assetMetadata"]["boundingBox"]
        pos = c["placements"][0]["position"]
        opt = c["placements"][0].get("optimize", 1)
        if vn not in var_assets:
            var_assets[vn] = []
        var_assets[vn].append({"uid": uid, "pos": pos, "size": [bb["x"], bb["y"], bb["z"]], "opt": opt})
    lines.append("# Asset definitions")
    for vn, instances in var_assets.items():
        insts = [f"AssetInstance(position={i['pos']}, instance_id='{i['uid'].replace('-', '_')}', size={i['size']}, optimize={i['opt']})" for i in instances]
        lines.append(f"{vn} = [{', '.join(insts)}]")
    lines.append("")
    lines.append("# Solver stub for standalone execution")
    lines.append("class Solver:")
    lines.append("    def against_wall(self, a, w): pass")
    lines.append("    def point_towards(self, a1, a2, angle=0): pass")
    lines.append("    def distance_constraint(self, a1, a2, min_d=0, max_d=10000, weight=1): pass")
    lines.append("    def align_with(self, a1, a2, angle=0): pass")
    lines.append("    def on_top_of(self, a1, a2): pass")
    lines.append("solver = Solver()")
    lines.append("")
    lines.append("# Constraints")
    lines.append(program)
    return "\n".join(lines)


def post_process_layout(layout: dict[str, Any], cfg: dict[str, Any], on_top_of_pairs: list) -> dict[str, Any]:
    """Post-process layout: fix z for stacked assets and snap rotations to π/4 increments."""
    fixed_layout = copy.deepcopy(layout)
    on_top_map = dict(on_top_of_pairs)

    def get_height(uid: str) -> float:
        return cfg.get(uid, {}).get("assetMetadata", {}).get("boundingBox", {}).get("z", 0.3)

    for uid, placement in fixed_layout.items():
        if uid.startswith("void_"):
            continue
        pos = list(placement.get("position", [0, 0, 0]))
        if uid in on_top_map:
            base_uid = on_top_map[uid]
            base_pos = fixed_layout.get(base_uid, {}).get("position", [0, 0, 0])
            pos[0], pos[1] = base_pos[0], base_pos[1]
            pos[2] = get_height(base_uid)
        else:
            pos[2] = 0
        rot = placement.get("rotation", [0, 0, 0])
        placement["position"] = pos
        placement["rotation"] = [round(r / (math.pi / 4)) * (math.pi / 4) for r in rot]
    return fixed_layout

MOCK_PROGRAM = """# Main seating and focal point
solver.against_wall(sectional_sofa[0], walls[2])
solver.against_wall(furniture[0], walls[0])
solver.point_towards(sectional_sofa[0], furniture[0])
solver.point_towards(furniture[0], sectional_sofa[0])

# Primary coffee table placement
solver.distance_constraint(coffee_tables[0], sectional_sofa[0], 0.35, 0.55)
solver.align_with(coffee_tables[0], sectional_sofa[0], 0)

# Secondary coffee table/bench near TV area
solver.distance_constraint(coffee_table[0], furniture[0], 0.8, 1.2)
solver.align_with(coffee_table[0], furniture[0], 0)

# Recliners positioned for conversation
solver.point_towards(recliners[0], coffee_tables[0])
solver.point_towards(recliners[1], coffee_tables[0])
solver.distance_constraint(recliners[0], walls[3], 0.3, 0.8)
solver.distance_constraint(recliners[1], walls[1], 0.3, 0.8)

# Rug centering the layout
solver.distance_constraint(area_rug[0], coffee_tables[0], 0, 0.1)

# Lighting placement
solver.on_top_of(table_lamp[0], coffee_tables[0])
solver.on_top_of(table_lamp[1], coffee_tables[0])
solver.on_top_of(table_lamp[2], coffee_table[0])
solver.distance_constraint(lighting[0], sectional_sofa[0], 0.1, 0.5)

# Door clearance for walkways (Weight=10)
for asset in [sectional_sofa[0], lighting[0], recliners[0]]:
    solver.distance_constraint(asset, void_door_0[0], 0.6, None, weight=10)

# Maintain symmetry for recliners relative to the room center
solver.distance_constraint(recliners[0], recliners[1], 2.0, 3.0)
# Room boundary constraints
for asset in [sectional_sofa[0], coffee_table[0], coffee_tables[0], furniture[0], lighting[0], table_lamp[0], table_lamp[1], table_lamp[2], area_rug[0], recliners[0], recliners[1]]:
    solver.distance_constraint(asset, AssetInstance(position=[1.86, 2.74, 0]), 0, 3.31, weight=10)
"""


def run_layoutvlm_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    program = state.get("constraint_program", "")
    if not program:
        logger.info("[LAYOUTVLM] No constraint program, using mock data")
        program = MOCK_PROGRAM

    room_area = state.get("room_area", (5.0, 5.0))
    verts = state.get("room_vertices")
    boundary = [[v[0], v[1], 0.0] for v in verts] if verts else [[0, 0, 0], [room_area[0], 0, 0], [room_area[0], room_area[1], 0], [0, room_area[1], 0]]

    initial = state.get("refined_layout") or state.get("initial_layout", {})
    cfg = {}
    for a in state.get("selected_assets", []):
        uid = a["uid"]
        p = initial.get(uid, {})
        cfg[uid] = {"asset_var_name": uid, "assetMetadata": {"boundingBox": {"x": a.get("width", 1.0), "y": a.get("depth", 1.0), "z": a.get("height", 1.0)}},
                    "placements": [{"position": p.get("position", [0, 0, 0]), "rotation": p.get("rotation", [0, 0, 0]), "optimize": 1}], "onCeiling": a.get("onCeiling", False)}

    for i, d in enumerate(state.get("room_doors", [])):
        c = d["center"] + [2.5] if len(d["center"]) == 2 else d["center"]
        cfg[f"void_door-{i}"] = {"asset_var_name": f"void_door_{i}", "assetMetadata": {"boundingBox": {"x": d["width"], "y": d["width"], "z": 5.0}}, "placements": [{"position": c, "rotation": [0, 0, 0], "optimize": 0}]}
    for i, w in enumerate(state.get("room_windows", [])):
        c = w["center"] + [2.5] if len(w["center"]) == 2 else w["center"]
        cfg[f"void_window-{i}"] = {"asset_var_name": f"void_window_{i}", "assetMetadata": {"boundingBox": {"x": w["width"], "y": w.get("depth", 0.1), "z": 5.0}}, "placements": [{"position": c, "rotation": [0, 0, 0], "optimize": 0}]}

    env = SandboxEnv(boundary)
    results, frames = env.solve(cfg, program)

    layout = dict(initial)
    for uid in cfg:
        iid = uid.replace("-", "_")
        if iid in results:
            layout[uid] = {"position": results[iid]["position"], "rotation": results[iid]["rotation"], "scale": None}

    final_layout = post_process_layout(layout, cfg, env.on_top_of_pairs)
    complete_program = _generate_complete_program(cfg, boundary, program)
    manager = state.get("asset_manager")
    if manager:
        manager.write_text("layoutvlm", "constraint_program.py", program)
        manager.write_text("layoutvlm", "complete_sandbox_program.py", complete_program)
        manager.write_json("layoutvlm", "final_layout.json", final_layout)
        if frames:
            buf = io.BytesIO()
            frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
            manager.write_bytes("layoutvlm", "optimization.gif", buf.getvalue())
    else:
        import pathlib
        runs_dir = pathlib.Path("runs")
        runs_dir.mkdir(exist_ok=True)
        (runs_dir / "complete_sandbox_program.py").write_text(complete_program)
        if frames:
            gif_path = runs_dir / "optimization.gif"
            frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    logger.info("[LAYOUTVLM] Time: %.2fs, optimized %d assets", time.perf_counter() - start, len(results))
    return {"layoutvlm_layout": final_layout}
