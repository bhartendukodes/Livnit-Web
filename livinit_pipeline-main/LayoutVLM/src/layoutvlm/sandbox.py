import os
import random
import re
from typing import Any

import numpy as np
import torch

from utils.placement_utils import get_random_placement

from .constraints import (Constraint, against_wall, align_with,
                          distance_constraint, on_top_of, point_towards)
from .device_utils import get_device_with_index, to_device
from .grad_solver import GradSolver
from .scene import AssetInstance, Wall


class SandBoxEnv:
    def __init__(self, task, mode="default", save_dir=None):
        self.task = task
        self.mode = mode
        self.boundary = task["boundary"]["floor_vertices"]
        self.save_dir = save_dir
        self.grad_solver = GradSolver(self.boundary, "default")
        self.local_vars = {"np": np}
        self.all_code = ""
        self.all_constraints = []
        self.solver_step = 0

    def execute_code(self, code):
        self.all_code += code + "\n"
        self.export_code()
        exec(code, self.local_vars)

    def export_code(self, save_dir=None):
        if save_dir is None:
            save_dir = self.save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        with open(f"{self.save_dir}/complete_sandbox_program.py", "w") as f:
            f.write(self.all_code)

    def _get_asset_indices(self):
        # Helper to map original_uid to (var_name, index)
        # Groups assets by var_name and assigns 0-based indices
        var_groups = {}
        for original_uid, asset in self.task["assets"].items():
            var_name = asset["asset_var_name"]
            if var_name not in var_groups:
                var_groups[var_name] = []
            var_groups[var_name].append(original_uid)
        
        uid_to_index = {}
        for var_name, uids in var_groups.items():
            # Sort uids to ensure deterministic assignment. 
            # Assuming format name-index, sort by index.
            def get_idx(u):
                parts = u.split("-")
                return int(parts[-1]) if parts[-1].isdigit() else 0
            
            sorted_uids = sorted(uids, key=get_idx)
            
            for i, uid in enumerate(sorted_uids):
                uid_to_index[uid] = i
        return uid_to_index

    def initialize_variables(self):
        uid_to_index = self._get_asset_indices()
        setup_code = ""
        for original_uid, asset in self.task["assets"].items():
            var_name = asset["asset_var_name"]
            
            # Use computed index
            target_idx = uid_to_index.get(original_uid, 0)
            if var_name == original_uid.replace("-", "_"):
                target_idx = 0

            # Check if the asset is fixed (optimize == 0)
            is_fixed = False
            position = [0,0,0]
            rotation = [0,0,0]

            if "placements" in asset and len(asset["placements"]) > 0:
                p = asset["placements"][0]
                if p.get("optimize") == 0:
                    is_fixed = True
                    position = p.get("position")
                    rotation = p.get("rotation", [0, 0, 0])

            if is_fixed:
                if len(position) == 2:
                    position = list(position) + [0.0]
                setup_code += f"{var_name}[{target_idx}].position = {position}\n"
                setup_code += f"{var_name}[{target_idx}].rotation = {rotation}\n"
                setup_code += f"{var_name}[{target_idx}].optimize = 0\n"
            else:
                if "placements" in asset and len(asset["placements"]) > 0:
                    position = list(asset["placements"][0]["position"])
                    rotation = asset["placements"][0].get("rotation", [0, 0, 0])
                else:
                    position = get_random_placement(self.task["boundary"]["floor_vertices"], add_z=True)
                    if isinstance(position, np.ndarray):
                        position = position.tolist()
                    rotation = [0, 0, 0]

                if len(position) < 3: position = list(position) + [0.0]
                
                position[-1] = asset["assetMetadata"]["boundingBox"]["z"] / 2
                if asset.get("onCeiling"):
                    position[-1] = 3
                    setup_code += f"{var_name}.onCeiling = True\n"

                setup_code += f"{var_name}[{target_idx}].position = {position}\n"
                setup_code += f"{var_name}[{target_idx}].rotation = {rotation}\n"

        # self.all_code += setup_code
        # self.export_code()
        self.execute_code(setup_code)
        # Validate
        for var_name, asset in self.local_vars.items():
            if type(asset).__name__ == "Assets":
                for instance in asset.placements:
                    assert instance.position is not None
                    assert instance.rotation is not None

    def assign_instance_ids(self):
        uid_to_index = self._get_asset_indices()
        code = ""
        for original_uid, asset in self.task["assets"].items():
            var_name = asset["asset_var_name"]
            
            target_idx = uid_to_index.get(original_uid, 0)
            if var_name == original_uid.replace("-", "_"):
                target_idx = 0

            instance_id = original_uid.replace("-", "_")
            code += f"{var_name}[{target_idx}].instance_id = '{instance_id}'\n"

        # self.all_code += code
        self.execute_code(code)

    def setup_initial_assets(self):
        num_walls = len(self.boundary)
        wall_assets = {}
        for idx in range(num_walls):
            vertices = np.array(
                [self.boundary[idx], self.boundary[(idx + 1) % num_walls]]
            ).astype(np.float32)
            wall_id = f"walls_{idx}"
            wall_assets[wall_id] = Wall(
                wall_id,
                vertices=[vertices[0], vertices[1]],
            )
        return wall_assets

    def sanity_check(self, group_assets, entire_program, constraint_for_all=False):
        _local_vars = self.local_vars.copy()

        def _hyphen_to_underscore_ids(s: str) -> str:
            return re.sub(r"\b([a-zA-Z_]\w*)-(\d+)\b", r"\1_\2", s)

        def _is_scaffolding_line(line: str) -> bool:
            if re.match(r"^\s*(from\s+\S+\s+import\s+|import\s+\S+)", line):
                return True
            if re.match(r"^\s*(class|def)\s+[A-Za-z_]\w*\s*(\(|:)", line):
                return True
            if re.match(r"^\s*@", line):
                return True
            if re.match(r"^\s*(try|except|finally|with)\b", line):
                return True
            if re.match(r'^\s*(\"\"\"|\'\'\')', line):
                return True
            return False

        def _track_defined_vars(stripped: str) -> None:
            assign_match = re.match(r"^\s*([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)\s*=", stripped)
            if assign_match and not re.match(r"^\s*[a-zA-Z_]\w*\s*=\s*Assets\s*\(", stripped):
                for v in assign_match.group(1).split(","):
                    _local_vars.setdefault(v.strip(), None)

            for_match = re.match(r"^\s*for\s+([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)\s+in\b", stripped)
            if for_match:
                for v in for_match.group(1).split(","):
                    _local_vars.setdefault(v.strip(), None)

        def _register_assets_ctor(stripped: str) -> bool:
            ctor_match = re.match(r"^\s*([a-zA-Z_]\w*)\s*=\s*Assets\s*\(", stripped)
            if not ctor_match:
                return False

            var_name = ctor_match.group(1)

            class DummyAssets:
                def __init__(self):
                    self.placements = [0]

            _local_vars[var_name] = DummyAssets()
            return True

        def _rewrite_array_accesses(line_text: str, stripped_masked: str) -> tuple[str, bool]:
            new_line = line_text
            array_accesses = re.findall(r"\b([a-zA-Z_]\w*)\[(\d+)\]", stripped_masked)
            for base_var, idx_str in array_accesses:
                idx = int(idx_str)
                candidate_iid = f"{base_var}_{idx}"
                var_name_res, idx_res, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(candidate_iid)

                if var_name_res is None or instance_obj is None:
                    if base_var in _local_vars:
                        obj = _local_vars[base_var]
                        if hasattr(obj, "placements"):
                            plen = len(obj.placements)
                            if plen == 1:
                                new_line = re.sub(rf"\b{base_var}\[{idx}\]", f"{base_var}[0]", new_line)
                                continue
                            if plen == 0:
                                obj.placements.append(
                                    AssetInstance(
                                        id=f"{base_var}_0",
                                        position=[0.0, 0.0, 0.0],
                                        rotation=[0.0, 0.0, 0.0],
                                        optimize=1,
                                    )
                                )
                                new_line = re.sub(rf"\b{base_var}\[{idx}\]", f"{base_var}[0]", new_line)
                                continue
                            print(
                                f"Warning: Skipping line due to out-of-bounds index '{base_var}[{idx}]' (len={plen}): {line_text}"
                            )
                            return line_text, False
                    continue

                has_placements = hasattr(asset_obj, "placements") and bool(getattr(asset_obj, "placements", []))
                if has_placements:
                    new_line = re.sub(rf"\b{base_var}\[{idx}\]", f"{var_name_res}[{idx_res}]", new_line)
                else:
                    new_line = re.sub(rf"\b{base_var}\[{idx}\]", f"{var_name_res}", new_line)

            return new_line, True

        def _rewrite_instance_tokens(line_text: str, stripped_masked: str) -> str:
            new_line = line_text
            instance_tokens = re.findall(r"\b([a-zA-Z_]\w*_\d+)\b", stripped_masked)
            for tok in instance_tokens:
                var_name_res, idx_res, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(tok)
                if var_name_res is None or instance_obj is None:
                    continue
                has_placements = hasattr(asset_obj, "placements") and bool(getattr(asset_obj, "placements", []))
                repl = f"{var_name_res}[{idx_res}]" if has_placements else f"{var_name_res}"
                new_line = re.sub(rf"\b{re.escape(tok)}\b", repl, new_line)
            return new_line

        def _normalize_solver_line(line_text: str) -> str:
            if "solver." not in line_text:
                return line_text

            def _normalize_arg_token(tok: str) -> str:
                s = tok.strip()
                if s.startswith("AssetInstance("):
                    return tok
                if re.match(r"^[a-zA-Z_]\w*\s*\[\s*\d+\s*\]$", s):
                    return tok
                m_attr = re.match(r"^\s*([a-zA-Z_]\w*)\s*\.\s*placements\s*$", s)
                if m_attr:
                    return f"{m_attr.group(1)}[0]"

                base = s
                obj = _local_vars.get(base)
                if obj is None:
                    return tok
                if type(obj).__name__ == "AssetInstance":
                    return base
                if hasattr(obj, "placements") or isinstance(obj, list):
                    return f"{base}[0]"
                return base

            def _rewrite_solver_args(line_in: str) -> str:
                def repl(m):
                    func = m.group(1)
                    args_str = m.group(2)

                    tmp = re.sub(r"AssetInstance\s*\(.*?\)", "AssetInstance()", args_str)
                    parts = [p.strip() for p in tmp.split(",")]
                    orig_parts = [p.strip() for p in args_str.split(",")]

                    rebuilt = []
                    for i, p in enumerate(parts):
                        if "=" in p:
                            name, value = p.split("=", 1)
                            name, value = name.strip(), value.strip()
                            if re.match(r"^\[.*\]$", value):
                                rebuilt.append(f"{name}={value}")
                                continue
                            if re.match(r"^[a-zA-Z_]\w*(?:\[\s*\d+\s*\])?$", value) or re.match(
                                r"^[a-zA-Z_]\w*\s*\.\s*placements$", value
                            ):
                                value = _normalize_arg_token(value)
                            rebuilt.append(f"{name}={value}")
                        else:
                            if re.match(r"^\[.*\]$", p):
                                rebuilt.append(orig_parts[i])
                            elif re.match(r"^[a-zA-Z_]\w*(?:\[\s*\d+\s*\])?$", p) or re.match(
                                r"^[a-zA-Z_]\w*\s*\.\s*placements$", p
                            ):
                                rebuilt.append(_normalize_arg_token(p))
                            else:
                                rebuilt.append(orig_parts[i])
                    return f"solver.{func}({', '.join(rebuilt)})"

                return re.sub(r"solver\.([a-zA-Z_]\w*)\((.*?)\)", repl, line_in, flags=re.S)

            return _rewrite_solver_args(line_text)

        def _solver_call_has_list_arg(line_text: str) -> bool:
            if "solver." not in line_text:
                return False

            def _arg_resolves_to_list(arg: str) -> bool:
                s = arg.strip()
                if s.startswith("AssetInstance("):
                    return False
                if re.match(r"^\[.*\]$", s):
                    return True
                if re.match(r"^[a-zA-Z_]\w*\s*\[\s*\d+\s*\]$", s):
                    return False
                if re.match(r"^[a-zA-Z_]\w*\s*\.\s*placements$", s):
                    return True
                base = s.split("[")[0].split(".")[0]
                obj = _local_vars.get(base)
                return isinstance(obj, list)

            mcall = re.search(r"solver\.[a-zA-Z_]\w*\((.*?)\)", line_text, flags=re.S)
            if not mcall:
                return False

            args_str = mcall.group(1)
            tmp = re.sub(r"AssetInstance\s*\(.*?\)", "AssetInstance()", args_str)
            parts = [p.strip() for p in tmp.split(",")]
            for p in parts:
                if "=" in p:
                    _, value = p.split("=", 1)
                    if _arg_resolves_to_list(value):
                        return True
                else:
                    if _arg_resolves_to_list(p):
                        return True
            return False

        def _validate_solver_args(line_text: str) -> bool:
            if "solver." not in line_text:
                return True

            match = re.search(r"solver\.[a-zA-Z0-9_]+\((.*)\)", line_text)
            if not match:
                return True

            args_content = match.group(1)
            tmp = re.sub(r"AssetInstance\s*\(.*?\)", "AssetInstance()", args_content)
            args = [a.strip() for a in tmp.split(",")]

            allowed_solver_funcs = {"against_wall", "on_top_of", "align_with", "distance_constraint", "point_towards"}
            allowed_builtins = {"True", "False", "None", "solver", "AssetInstance", "Assets", "Wall", "walls", "center_x", "center_y"} | allowed_solver_funcs
            group_allowed = {ga.split("_")[0] for ga in group_assets} | set(group_assets)

            for arg in args:
                if "=" in arg:
                    _, value = arg.split("=", 1)
                    value = value.strip()
                    m = re.match(r"^\s*([a-zA-Z_]\w*)\s*\[\s*\d+\s*\]\s*$", value)
                    if m:
                        base_var = m.group(1)
                        if base_var not in _local_vars and base_var not in group_allowed:
                            return False
                    continue

                base_var = arg.split("[")[0]
                if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", base_var):
                    if base_var in allowed_builtins:
                        continue
                    if base_var not in _local_vars and base_var not in group_allowed:
                        return False

            return True

        def _strip_indices_on_instances(code_text: str) -> str:
            def strip_line(ln: str) -> str:
                def repl_local(m):
                    base = m.group(1)
                    obj = _local_vars.get(base)
                    if obj is not None and type(obj).__name__ == "AssetInstance":
                        return base
                    return m.group(0)

                ln2 = re.sub(r"\b([a-zA-Z_]\w*)\s*\[\s*(\d+)\s*\]", repl_local, ln)

                tokens = set(re.findall(r"\b([a-zA-Z_]\w*_\d+)\b", ln2))
                for tok in tokens:
                    var_name_res, _, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(tok)
                    if instance_obj is not None and not (hasattr(asset_obj, "placements") and asset_obj.placements):
                        ln2 = re.sub(rf"\b{re.escape(tok)}\s*\[\s*\d+\s*\]", var_name_res, ln2)
                        ln2 = re.sub(rf"\b{re.escape(tok)}\b", var_name_res, ln2)
                return ln2

            return "\n".join(strip_line(ln) for ln in code_text.split("\n"))

        def _coerce_instance(x):
            if x is None:
                return None
            if type(x).__name__ == "AssetInstance":
                return x
            if hasattr(x, "placements"):
                try:
                    pls = getattr(x, "placements")
                    if pls and len(pls) > 0:
                        return pls[0]
                except Exception:
                    pass
            if isinstance(x, (list, tuple)):
                cur = x
                while isinstance(cur, (list, tuple)):
                    if len(cur) == 0:
                        return None
                    cur = cur[0]
                return _coerce_instance(cur)
            return x

        filtered_lines = []
        for line in entire_program.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or _is_scaffolding_line(line):
                filtered_lines.append(line)
                continue

            _track_defined_vars(stripped)

            if _register_assets_ctor(stripped):
                filtered_lines.append(line)
                continue

            new_line = _hyphen_to_underscore_ids(line)
            stripped_masked = _hyphen_to_underscore_ids(stripped)

            new_line, ok = _rewrite_array_accesses(new_line, stripped_masked)
            if not ok:
                indent = line[: len(line) - len(stripped)]
                filtered_lines.append(f"{indent}pass # Skipped: {stripped}")
                continue

            new_line = _rewrite_instance_tokens(new_line, _hyphen_to_underscore_ids(new_line.strip()))
            new_line = _normalize_solver_line(new_line)

            if _solver_call_has_list_arg(new_line):
                indent = line[: len(line) - len(stripped)]
                filtered_lines.append(f"{indent}pass # Skipped: {stripped}")
                continue

            if not _validate_solver_args(_hyphen_to_underscore_ids(new_line.strip())):
                indent = line[: len(line) - len(stripped)]
                if stripped.endswith(":"):
                    filtered_lines.append(f"{indent}if False: # Skipped invalid block: {stripped}")
                else:
                    filtered_lines.append(f"{indent}pass # Skipped: {stripped}")
                continue

            filtered_lines.append(new_line)

        filtered_program = "\n".join(filtered_lines)
        filtered_program = _strip_indices_on_instances(filtered_program)
        filtered_program = re.sub(r"(\[\s*\d+\s*\])\s*\[\s*\d+\s*\]", r"\1", filtered_program)

        if "solver" in _local_vars:
            _solver = _local_vars["solver"]
            for _fname in ("against_wall", "on_top_of", "align_with", "distance_constraint", "point_towards"):
                if hasattr(_solver, _fname):
                    _orig = getattr(_solver, _fname)

                    def _make_wrapper(orig_func):
                        def _wrapped(*args, **kwargs):
                            args2 = tuple(_coerce_instance(a) for a in args)
                            for k in ("asset", "asset1", "asset2", "target", "reference", "obj"):
                                if k in kwargs:
                                    kwargs[k] = _coerce_instance(kwargs[k])
                            return orig_func(*args2, **kwargs)

                        return _wrapped

                    setattr(_solver, _fname, _make_wrapper(_orig))

        exec(filtered_program, _local_vars)
        with open(f"{self.save_dir}/filtered_sandbox_program.py", "w") as f:
            f.write(filtered_program)

        # for _, asset in _local_vars.items():
        #     if type(asset).__name__ == "Assets":
        #         for instance in asset.placements:
        #             assert instance.instance_id is not None
        #             assert instance.position is not None
        #             assert instance.rotation is not None
        #     if type(asset).__name__ == "Walls":
        #         for wall in asset.walls:
        #             assert wall.instance_id is not None
        #             assert wall.corner1 is not None
        #             assert wall.corner2 is not None

        if constraint_for_all:
            all_instance_ids = []
            for constraint in _local_vars["solver"].constraints:
                all_instance_ids.extend(constraint[1])
            for instance_var_name in group_assets:
                if instance_var_name not in all_instance_ids:
                    print(f"Instance {instance_var_name} is not specified in the constraints")
                    assert False

    def setup_optimization_param(
        self, placed_instance_ids, new_instance_ids, new_constraints
    ):
        all_instance_ids = placed_instance_ids + new_instance_ids
        for constraint, instance_ids in self.all_constraints + new_constraints:
            all_instance_ids.extend(instance_ids)
        solver_assets = self.setup_initial_assets()
        for instance_id in all_instance_ids:
            if instance_id.startswith("walls_") or instance_id == "room_0":
                continue

            var_name, instance_idx, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(instance_id)
            if instance_obj is None or asset_obj is None:
                # Unresolved/phantom id; skip
                continue

            # Normalize rotation
            if hasattr(instance_obj, "rotation") and len(instance_obj.rotation) == 1:
                instance_obj.rotation = [0, 0, instance_obj.rotation[0]]

            on_ceiling = getattr(asset_obj, "onCeiling", False)
            optimize_flag = getattr(instance_obj, "optimize", 1)
            if instance_id.startswith("fixed_point"):
                optimize_flag = 0

            if self.mode == "no_initialization":
                random_pos = get_random_placement(self.boundary, add_z=True)
                solver_assets[instance_id] = AssetInstance(
                    id=instance_id,
                    position=random_pos,
                    rotation=[0, 0, random.uniform(0, 360)],
                    size=asset_obj.size,
                    onCeiling=on_ceiling,
                    optimize=optimize_flag,
                )
            else:
                solver_assets[instance_id] = AssetInstance(
                    id=instance_id,
                    position=instance_obj.position,
                    rotation=instance_obj.rotation,
                    size=asset_obj.size,
                    onCeiling=on_ceiling,
                    optimize=optimize_flag,
                )
        return solver_assets

    def self_consistency_filtering(self, solver_assets, new_constraints):
        existing_constraint_str = ""
        for constraint, instance_ids in self.all_constraints:
            params_str = ", ".join([f"{k}={v}" for k, v in constraint.params.items()])
            existing_constraint_str += f"solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {params_str})\n"

        filtered_new_constraints = []
        new_constraint_str = ""
        for constraint, instance_ids in new_constraints:
            if constraint.constraint_name == "on_top_of":
                if instance_ids[0].startswith("fixed_point") or instance_ids[
                    1
                ].startswith("fixed_point"):
                    continue
                if not any(
                    pair[0] == instance_ids[0]
                    for pair in self.grad_solver.on_top_of_assets
                ):
                    self.grad_solver.on_top_of_assets.append(
                        (instance_ids[0], instance_ids[1])
                    )
                    filtered_new_constraints.append((constraint, instance_ids))
                    new_constraint_str += (
                        f"solver.on_top_of({instance_ids[0]}, {instance_ids[1]})\n"
                    )

        for constraint, instance_ids in new_constraints:
            if instance_ids[0].startswith("fixed_point") or instance_ids[1].startswith(
                "fixed_point"
            ):
                continue

            existing_constraints_count = sum(
                1
                for c in self.all_constraints + filtered_new_constraints
                if c[0].constraint_name == constraint.constraint_name
                and c[1][0] == instance_ids[0]
            )

            if constraint.constraint_name == "against_wall":
                if existing_constraints_count > 0:
                    new_constraint_str += f"constraint {constraint.constraint_name} with instance_ids {instance_ids} is already specified\n"
                    new_constraint_str += f"==> (rejected) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]})\n"
                    continue
                asset_pos = (
                    solver_assets[instance_ids[0]]
                    .position.detach()
                    .clone()
                    .cpu()
                    .numpy()
                )

                def get_distance_to_wall(asset_pos, wall_id):
                    wall_start = np.array(solver_assets[wall_id].corner1[:2])
                    wall_end = np.array(solver_assets[wall_id].corner2[:2])
                    # Calculate the vector from wall_start to wall_end
                    wall_vector = wall_end - wall_start
                    # Calculate the vector from wall_start to the asset
                    asset_vector = asset_pos[:2] - wall_start
                    # Project asset_vector onto wall_vector
                    projection = np.dot(asset_vector, wall_vector) / np.dot(
                        wall_vector, wall_vector
                    )
                    # Calculate the closest point on the wall
                    closest_point = wall_start + projection * wall_vector
                    # Calculate the distance from the asset to the closest point
                    distance = np.linalg.norm(asset_pos[:2] - closest_point)
                    return distance

                # get the wall_id with the minimum distance
                min_distance = float("inf")
                min_wall_id = None
                for wall_id in solver_assets.keys():
                    if wall_id.startswith("walls_"):
                        distance = get_distance_to_wall(asset_pos, wall_id)
                        if distance < min_distance:
                            min_distance = distance
                            min_wall_id = wall_id
                instance_ids = [instance_ids[0], min_wall_id]
                filtered_new_constraints.append((constraint, instance_ids))
                if min_wall_id != instance_ids[1]:
                    new_constraint_str += f"==> (updated) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]})\n"
                else:
                    new_constraint_str += f"solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]})\n"
                    continue

                filtered_new_constraints.append((constraint, instance_ids))
                new_constraint_str += f"solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]})\n"

            elif constraint.constraint_name == "distance_constraint":
                if existing_constraints_count > 2 and not instance_ids[1].startswith("void"):
                    print(
                        f"constraint {constraint.constraint_name} with instance_ids {instance_ids} is already specified"
                    )
                    new_constraint_str += f"==> (rejected) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['min_distance']}, {constraint.params['max_distance']})\n"
                    continue
                if (
                    solver_assets[instance_ids[0]].onCeiling
                    or solver_assets[instance_ids[1]].onCeiling
                ):
                    print(
                        f"constraint {constraint.constraint_name} with instance_ids {instance_ids} is not "
                    )
                    new_constraint_str += f"==> (rejected as distance to wall not supported) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['min_distance']}, {constraint.params['max_distance']})\n"
                    continue
                # Calculate the distance between two assets using self.local_vars
                with torch.no_grad():
                    pos1 = solver_assets[instance_ids[0]].position.detach().clone()
                    pos2 = solver_assets[instance_ids[1]].position.detach().clone()
                    distance = torch.norm(pos1 - pos2).item()

                    def _size_wh(s):
                        # normalize size to (w, h)
                        if isinstance(s, (list, tuple)):
                            if len(s) >= 2:
                                return float(s[0]), float(s[1])
                            elif len(s) == 1:
                                return float(s[0]), float(s[0])
                            else:
                                return 1.0, 1.0
                        elif isinstance(s, (int, float)):
                            return float(s), float(s)
                        else:
                            return 1.0, 1.0

                    w1, h1 = _size_wh(solver_assets[instance_ids[0]].size)
                    w2, h2 = _size_wh(solver_assets[instance_ids[1]].size)

                    min_distance = min(w1, h1) / 2 + min(w2, h2) / 2

                    if constraint.params["min_distance"] is not None:
                        constraint.params["min_distance"] = min(
                            distance, constraint.params["min_distance"]
                        )
                        if constraint.params["min_distance"] < min_distance:
                            constraint.params["min_distance"] = min_distance
                    if constraint.params["max_distance"] is not None:
                        constraint.params["max_distance"] = max(
                            distance, constraint.params["max_distance"]
                        )
                        ### NOTE: (added heuristics) max distance should not be too tight
                        if constraint.params["max_distance"] < min_distance * 1.5:
                            constraint.params["max_distance"] = min_distance * 1.5

                filtered_new_constraints.append((constraint, instance_ids))
                new_constraint_str += f"solver.distance_constraint({instance_ids[0]}, {instance_ids[1]}, {constraint.params['min_distance']}, {constraint.params['max_distance']})\n"

            elif constraint.constraint_name == "point_towards":
                # check if instance_ids[0] already has a point_towards or align_with constraint
                has_existing_orientation_constraint = any(
                    (
                        c[0].constraint_name in ["point_towards", "against_wall"]
                        and c[1][0] == instance_ids[0]
                    )
                    for c in self.all_constraints + filtered_new_constraints
                )
                if has_existing_orientation_constraint:
                    print(
                        f"constraint {constraint.constraint_name} with instance_ids {instance_ids} conflicts with existing constraint"
                    )
                    new_constraint_str += f"==> (rejected) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['angle']})\n"
                    continue

                filtered_new_constraints.append((constraint, instance_ids))
                new_constraint_str += f"solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['angle']})\n"

            elif constraint.constraint_name == "align_with":
                # check if instance_ids[0] already has a point_towards or align_with constraint
                has_existing_orientation_constraint = any(
                    (
                        c[0].constraint_name in ["align_with", "against_wall"]
                        and c[1][0] == instance_ids[0]
                    )
                    for c in self.all_constraints + filtered_new_constraints
                )
                if has_existing_orientation_constraint:
                    print(
                        f"constraint {constraint.constraint_name} with instance_ids {instance_ids} conflicts with existing constraint"
                    )
                    new_constraint_str += f"==> (rejected) solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['angle']})\n"
                    continue

                filtered_new_constraints.append((constraint, instance_ids))
                new_constraint_str += f"solver.{constraint.constraint_name}({instance_ids[0]}, {instance_ids[1]}, {constraint.params['angle']})\n"

            elif constraint.constraint_name == "on_top_of":
                pass

            else:
                assert (
                    False
                ), f"constraint {constraint.constraint_name} is not supported"

        return filtered_new_constraints, [existing_constraint_str, new_constraint_str]

    def build_constraint_functions(self):
        constraints_for_solver = []
        for constraint in self.local_vars["solver"].constraints:
            function_name = constraint[0].constraint_name
            # skip fixed_point constraints
            if constraint[1][0].startswith("fixed_point"):
                continue

            if function_name == "against_wall":
                constraints_for_solver.append(
                    (
                        Constraint(
                            constraint_name=function_name,
                            constraint_func=against_wall,
                        ),
                        constraint[1],
                    )
                )
            elif function_name == "distance_constraint":
                constraints_for_solver.append(
                    (
                        Constraint(
                            constraint_name=function_name,
                            constraint_func=distance_constraint,
                            min_distance=constraint[0].params["min_distance"],
                            max_distance=constraint[0].params["max_distance"],
                            weight=constraint[0].params["weight"],
                        ),
                        constraint[1],
                    )
                )
                # constraint
            elif function_name == "on_top_of":
                constraints_for_solver.append(
                    (
                        Constraint(
                            constraint_name=function_name,
                            constraint_func=on_top_of,
                        ),
                        constraint[1],
                    )
                )
            elif function_name == "align_with":
                constraints_for_solver.append(
                    (
                        Constraint(
                            constraint_name=function_name,
                            constraint_func=align_with,
                            angle=constraint[0].params["angle"],
                        ),
                        constraint[1],
                    )
                )
            elif function_name == "point_towards":
                constraints_for_solver.append(
                    (
                        Constraint(
                            constraint_name=function_name,
                            constraint_func=point_towards,
                            angle=constraint[0].params["angle"],
                        ),
                        constraint[1],
                    )
                )
            elif function_name == "align_x":
                assert False, "align_x should not be used"
                # constraints_for_solver.append(
                #    (
                #        Constraint(
                #            constraint_name=function_name,
                #            constraint_func=align_x,
                #        ),
                #        constraint[1]
                #    )
                # )
            elif function_name == "align_y":
                assert False, "align_y should not be used"
                # constraints_for_solver.append(
                #    (
                #        Constraint(
                #            constraint_name=function_name,
                #            constraint_func=align_y,
                #        ),
                #        constraint[1]
                #    )
                # )
            else:
                assert False

        return constraints_for_solver

    def export_layout(self, incomplete_scene=False, use_degree=False):
        layout = {}

        uid_to_index = self._get_asset_indices()

        for original_uid, asset in self.task["assets"].items():
            var_name = asset["asset_var_name"]
            iid_underscore = original_uid.replace("-", "_")

            # 1) Prefer resolving by instance_id set in sanity/program
            var_name_res, idx_res, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(iid_underscore)

            if instance_obj is None or asset_obj is None:
                # 2) Fallback to var_name + computed index
                if var_name not in self.local_vars:
                    continue
                asset_obj = self.local_vars[var_name]

                # Compute target index deterministically, then clamp/fallback
                target_idx = uid_to_index.get(original_uid, 0)
                if hasattr(asset_obj, "placements") and asset_obj.placements:
                    if target_idx >= len(asset_obj.placements):
                        # If only one placement, use index 0; otherwise skip
                        if len(asset_obj.placements) == 1:
                            target_idx = 0
                        else:
                            continue
                    instance_obj = asset_obj.placements[target_idx]
                else:
                    instance_obj = asset_obj

            # Include if optimized or when exporting incomplete scene
            is_optimized = getattr(instance_obj, "optimize", 1) == 2
            if is_optimized or incomplete_scene:
                rotation = instance_obj.rotation
                if use_degree:
                    rotation = [float(np.rad2deg(r)) for r in rotation]
                layout[original_uid] = {
                    "position": instance_obj.position,
                    "rotation": rotation,
                    "scale": getattr(asset_obj, "size", None),
                }

        return layout

    def _resolve_var_and_index_from_instance_id(self, instance_id):
        """
        Resolve (var_name, index, instance_obj, asset_obj) for a given instance_id:
        1) Exact match by scanning all Assets placements.
        2) Fallback to base_var + numeric suffix if valid.
        3) Fallback to var named base_var_suffix (e.g., void_0) with index 0.
        """
        # 1) Scan for exact placement id match
        for var_name, obj in self.local_vars.items():
            if hasattr(obj, "placements") and obj.placements:
                for i, p in enumerate(obj.placements):
                    if getattr(p, "instance_id", None) == instance_id:
                        return var_name, i, p, obj

        # 2) Fallbacks based on naming
        parts = instance_id.split("_")
        if len(parts) > 1:
            base_var = "_".join(parts[:-1])
            idx_str = parts[-1]

            # base_var[index]
            if base_var in self.local_vars:
                obj = self.local_vars[base_var]
                if hasattr(obj, "placements") and obj.placements:
                    if len(obj.placements) == 1:
                        return base_var, 0, obj.placements[0], obj
                    if idx_str.isdigit():
                        idx = int(idx_str)
                        if 0 <= idx < len(obj.placements):
                            return base_var, idx, obj.placements[idx], obj
                else:
                    return base_var, 0, obj, obj

            # var named base_var_idx (e.g., void_0)
            cand = f"{base_var}_{idx_str}"
            if cand in self.local_vars:
                obj = self.local_vars[cand]
                if hasattr(obj, "placements") and obj.placements:
                    return cand, 0, obj.placements[0], obj
                else:
                    return cand, 0, obj, obj

        return None, None, None, None

    def solve(
        self,
        placed_assets,
        group_assets,
        program_segment,
        save_dir,
        only_initialize=False,
    ):
        ### replace '-' with '_' in the instance ids (for correspondence to variable names)
        placed_instance_ids = [
            _instance.replace("-", "_") for _instance in list(placed_assets.keys())
        ]
        group_assets = [_instance_id.replace("-", "_") for _instance_id in group_assets]
        # initialize the asset positions/rotations
        self.execute_code(program_segment)
        ### Create a sandbox environment to safely execute the code
        # sandbox_globals = {}
        # sandbox_locals = self.local_vars.copy()
        # try:
        #    # Execute the code in the sandbox environment
        #    exec(program_segment, sandbox_globals, sandbox_locals)
        #    # If execution succeeds, update the actual environment
        #    self.local_vars.update(sandbox_locals)
        # except Exception as e:
        #    print(f"Error executing code in sandbox: {e}")
        #    # Handle the error appropriately, maybe log it or raise a custom exception
        #    return

        # After successful initialization
        new_constraints = self.build_constraint_functions()
        solver_assets = self.setup_optimization_param(
            placed_instance_ids, group_assets, new_constraints
        )
        print("assets given to grad_solver", solver_assets.keys())
        for k in solver_assets:
            print(solver_assets[k])

        if only_initialize:
            return self.export_layout(incomplete_scene=True)

        if "no_self_consistency" not in self.mode:
            new_constraints, [
                existing_constraint_str,
                new_constraint_str,
            ] = self.self_consistency_filtering(solver_assets, new_constraints)
            with open(f"{save_dir}/new_constraints.txt", "w") as f:
                f.write(existing_constraint_str)
                f.write("\n=================================\n")
                f.write(new_constraint_str)

        ### no constraint optimization mode (ablation)
        if len(new_constraints) == 0 or "no_constraint" in self.mode:
            solver_code = "solver.constraints = []\n"
            for instance_id in solver_assets.keys():
                if instance_id.startswith("fixed_point"):
                    continue

                var_name, instance_idx, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(instance_id)
                if var_name is None or instance_obj is None:
                    continue
                if hasattr(instance_obj, "optimize") and instance_obj.optimize == 0:
                    continue

                solver_code += f"{var_name}[{instance_idx}].optimize = 2\n"
        else:
            ### use constraints to further optimize the pose of assets
            results = self.grad_solver.optimize(
                assets=solver_assets,
                existing_constraints=self.all_constraints,
                new_constraints=new_constraints,
                temp_dir=f"{save_dir}/temp_{self.solver_step}",
                output_gif_path=f"{save_dir}/out.gif",
                iterations=400,
                learning_rate=0.05,
            )
            print("Results from grad_solver:", results)
            ##########################################################################
            ### merge these results back with self.local_vars
            ##########################################################################
            # NOTE: or keep the old constriants?
            solver_code = "solver.constraints = []\n"
            for instance_id in results.keys():
                if instance_id.startswith("fixed_point"):
                    continue

                var_name, instance_idx, instance_obj, asset_obj = self._resolve_var_and_index_from_instance_id(instance_id)
                if var_name is None or instance_obj is None:
                    continue
                if hasattr(instance_obj, "optimize") and instance_obj.optimize == 0:
                    continue

                solver_code += f"{var_name}[{instance_idx}].position = {results[instance_id]['position']}\n"
                solver_code += f"{var_name}[{instance_idx}].rotation = {results[instance_id]['rotation']}\n"
                solver_code += f"{var_name}[{instance_idx}].optimize = 2\n"

        # Execute solver_code in sandbox environment
        self.execute_code(solver_code)
        self.solver_step += 1
        self.all_constraints += new_constraints
        # export code to the specific save_dir for this solver call
        self.export_code(save_dir)
        return self.export_layout(incomplete_scene=True)