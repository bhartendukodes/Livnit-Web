import argparse
import collections
import json
import os

import numpy as np

from src.layoutvlm.layoutvlm import LayoutVLM
from src.layoutvlm.scene import Scene
from utils.placement_utils import get_random_placement


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scene_json_file", help="Path to scene JSON file", required=True
    )
    parser.add_argument(
        "--save_dir", help="Directory to save results", default="./results/test_run"
    )
    parser.add_argument(
        "--model", help="Model to use for layout generation", default="gpt-4"
    )
    parser.add_argument("--openai_api_key", help="OpenAI API key", required=True)
    parser.add_argument(
        "--asset_dir",
        help="Directory to load assets from.",
        default="./objaverse_processed",
    )
    return parser.parse_args()


def prepare_task_assets(task, asset_dir):
    """
    Prepare assets for the task by processing their metadata and annotations.
    This is a minimal version that assumes assets are already downloaded and processed.
    """
    if "layout_criteria" not in task:
        task[
            "layout_criteria"
        ] = "the layout should follow the task description and adhere to common sense"

    all_data = collections.defaultdict(list)
    for original_uid in task["assets"].keys():
        # Remove the idx number from the uid
        uid = "-".join(original_uid.split("-")[:-1])

        # Load asset data
        data_path = os.path.join(asset_dir, uid, "data.json")
        if not os.path.exists(data_path):
            print(f"Warning: Asset data not found for {uid}")
            continue

        with open(data_path, "r") as f:
            data = json.load(f)
        data["path"] = os.path.join(asset_dir, uid, f"{uid}.glb")
        all_data[uid].append(data)

    # Process categories and create asset entries
    category_count = collections.defaultdict(int)
    for uid, duplicated_assets in all_data.items():
        category_var_name = duplicated_assets[0]["annotations"]["category"]
        category_var_name = (
            category_var_name.replace("-", "_")
            .replace(" ", "_")
            .replace("'", "_")
            .replace("/", "_")
            .replace(",", "_")
            .lower()
        )
        category_count[category_var_name] += 1

    category_idx = collections.defaultdict(int)

    for uid, duplicated_assets in all_data.items():
        category_var_name = duplicated_assets[0]["annotations"]["category"]
        category_var_name = (
            category_var_name.replace("-", "_")
            .replace(" ", "_")
            .replace("'", "_")
            .replace("/", "_")
            .replace(",", "_")
            .lower()
        )
        category_idx[category_var_name] += 1

        for instance_idx, data in enumerate(duplicated_assets):
            # Create category name with suffix if needed
            category_var_name = (
                f"{category_var_name}_{chr(ord('A') + category_idx[category_var_name]-1)}"
                if category_count[category_var_name] > 1
                else category_var_name
            )

            # Create instance name
            var_name = (
                f"{category_var_name}_{instance_idx}"
                if len(duplicated_assets) > 1
                else category_var_name
            )
            # Create asset entry
            task["assets"][f"{category_var_name}-{instance_idx}"] = {
                "uid": uid,
                "count": len(duplicated_assets),
                "instance_var_name": var_name,
                "asset_var_name": category_var_name,
                "instance_idx": instance_idx,
                "annotations": data["annotations"],
                "category": data["annotations"]["category"],
                "description": data["annotations"]["description"],
                "path": data["path"],
                "onCeiling": data["annotations"]["onCeiling"],
                "onFloor": data["annotations"]["onFloor"],
                "onWall": data["annotations"]["onWall"],
                "onObject": data["annotations"]["onObject"],
                "frontView": data["annotations"]["frontView"],
                "assetMetadata": {
                    "boundingBox": {
                        "x": float(
                            data["assetMetadata"]["boundingBox"]["y"]
                        ),  # SWAP x and y
                        "y": float(data["assetMetadata"]["boundingBox"]["x"]),
                        "z": float(data["assetMetadata"]["boundingBox"]["z"]),
                    },
                },
                "placements": task["assets"][f"{category_var_name}-{instance_idx}"].get(
                    "placements",
                    [
                        {
                            "position": [0.0, 0.0, 0.0],
                            "rotation": [0.0, 0.0, 0.0],
                            "optimize": 1,
                        }
                    ],
                ),
            }

    for void_key, void_data in task.get("void_assets", {}).items():
        if void_key not in task["assets"]:
            task["assets"][void_key] = {}

        task["assets"][void_key]["category"] = "void"
        task["assets"][void_key][
            "description"
        ] = "This is a void space that other assets can't fill."
        task["assets"][void_key]["count"] = 1
        task["assets"][void_key]["asset_var_name"] = "void"
        task["assets"][void_key]["instance_var_name"] = "void"
        task["assets"][void_key]["instance_idx"] = 0
        task["assets"][void_key]["annotations"] = {
            "category": "void",
            "description": "This is a void space that other assets can't fill and it can't move.",
            "width": void_data["width"],
            "depth": void_data["depth"],
            "volume": void_data["width"] * void_data["depth"] * 5,
            "mass": 1000.0,
            "onCeiling": False,
            "onFloor": True,
            "onWall": True,
            "onObject": False,
            "frontView": False,
            "uid": void_key,
            "scale": 1.0,
        }
        task["assets"][void_key]["onCeiling"] = False
        task["assets"][void_key]["onFloor"] = True
        task["assets"][void_key]["onWall"] = True
        task["assets"][void_key]["onObject"] = False
        task["assets"][void_key]["frontView"] = False

        center = void_data["center"]
        if len(center) == 2:
            center = [center[0], center[1], 2.5]

        task["assets"][void_key]["assetMetadata"] = {
            "boundingBox": {
                "x": float(void_data["width"]),
                "y": float(void_data["depth"]),
                "z": 5,
            },
        }
        task["assets"][void_key]["placements"] = [
            {"position": center, "rotation": [0.0, 0.0, 0.0], "optimize": 0}
        ]
    del task["void_assets"]
    return task


def main():
    args = parse_args()
    if args.openai_api_key:
        os.environ["OPENAI_API_KEY"] = args.openai_api_key

    # Create save directory
    os.makedirs(args.save_dir, exist_ok=True)

    # Initialize constraint solver
    layout_solver = LayoutVLM(
        mode="one_shot",
        save_dir=args.save_dir,
        asset_source="objaverse",  # Default to objaverse
    )

    # Load scene configuration
    with open(args.scene_json_file, 'r') as f:
        scene_config = json.load(f)
    # Prepare assets
    scene_config = prepare_task_assets(scene_config, args.asset_dir)
    scene_path = os.path.join(args.save_dir, "scene_processed.json")
    with open(scene_path, "w") as f:
        json.dump(scene_config, f, indent=4)
    print(f"Prepared scene configuration saved to {scene_path}")

    layout = layout_solver.solve(scene_config)


#     layout = layout_solver.solve_manual_with_sandbox_program(
#         scene_config,
#         """
#         ```python
# from math import cos, sin, radians
# import uuid
# from pydantic import BaseModel, Field, conint
# from typing import List, Optional, Union


# class Wall(BaseModel):
#     optimize: int = Field(description="Whether to optimize the position and rotation of the asset", default=0)
#     corner1: List[float] = Field(description="2d coordinates of the first corner of this wall")
#     corner2: List[float] = Field(description="2d coordinates of the second corner of this wall")
#     instance_id: Optional[str] = Field(description="Unique identifier for the wall", default=None)

# class AssetInstance(BaseModel):
#     optimize: int = Field(description="Whether to optimize the position and rotation of the asset", default=1)
#     position: List[float] = Field(description="Position of the asset", default=[0,0,0])
#     rotation: List[float] = Field(description="Rotation of the asset in degrees", default=[0,0,0])
#     instance_id: Optional[str] = Field(description="Unique identifier for the asset instance", default=None)
#     size: Optional[List[float]] = Field(description="Bounding box size of the asset instance", default=0.01)

#     # if the position is 2d, add a zero z-coordinate
#     def __init__(self, **data):
#         if 'position' in data and len(data['position']) == 2:
#             data['position'].append(0)
#         super().__init__(**data)

#     # Method to set size from the parent Assets class if not provided
#     def set_size_from_parent(self, parent_size: Optional[List[float]]):
#         if self.size is None and parent_size is not None:
#             self.size = parent_size


# class Assets(BaseModel):
#     description: str = Field(description="Description of the asset")
#     placements: List[AssetInstance] = Field(description="List of asset instances of this 3D asset", default=None)
#     size: Optional[List[float]] = Field(description="Bounding box size of the asset (z-axis up)", default=None)
#     onCeiling: bool = Field(description="Whether the asset is on the ceiling", default=False)

#     def __getitem__(self, index: int) -> AssetInstance:
#         "Allow indexing into placements."
#         return self.placements[index]

#     def __len__(self) -> int:
#         "Allow using len() to get the number of placements."
#         return len(self.placements)


# class Constraint:
#     def __init__(self, constraint_name, **params):
#         self.constraint_name = constraint_name
#         self.params = params

#     def evaluate(self, assets: list):
#         return self.constraint_func(assets, **self.params)


# fixed_pointtt = Assets(description="global absolute marks", size=[0.01, 0.01, 0.01], placements=[])
# def get_instance_id(asset):
#     global fixed_pointtt
#     if asset.instance_id is not None:
#         return asset.instance_id

#     if isinstance(asset, AssetInstance):
#         # fine the name of the variable that is an instance of AssetInstance
#         for var_name in globals():
#             var = globals()[var_name]
#             if isinstance(var, Assets):
#                 for instance_idx, placement in enumerate(var.placements):
#                     if id(placement) == id(asset):
#                         return f"{var_name}_{instance_idx}"

#         # new instantiation of AssetInstance, return random instance_id
#         instance_index = len(fixed_pointtt.placements)
#         fixed_pointtt.placements.append(
#             AssetInstance(
#                 position=asset.position,
#                 rotation=[0,0,0],
#                 optimize=False,
#                 instance_id=f"fixed_pointtt_{instance_index}"
#             )
#         )
#         return fixed_pointtt.placements[-1].instance_id

#     if isinstance(asset, Wall):
#         var = globals()['walls']
#         for instance_idx, wall_instance in enumerate(var):
#             if id(wall_instance) == id(asset):
#                 return f"walls_{instance_idx}"


# class ConstraintSolver:
#     def __init__(self):
#         self.constraints = []

#     def handle_fixed_pointtt(self, asset):
#         global fixed_pointtt
#         if isinstance(asset, tuple):
#             instance_index = len(fixed_pointtt.placements)
#             fixed_pointtt.placements.append(
#                 AssetInstance(
#                     position=list(asset),
#                     rotation=[0,0,0],
#                     optimize=False,
#                     instance_id=f"fixed_pointtt_{instance_index}"
#                 )
#             )
#             return fixed_pointtt.placements[-1]
#         return asset

#     def point_towards(self, asset1: AssetInstance, asset2: Union[AssetInstance, tuple], angle=0):
#         asset1.instance_id = get_instance_id(asset1)
#         asset2 = self.handle_fixed_pointtt(asset2)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("point_towards", angle=angle),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def distance_constraint(self, asset1: AssetInstance, asset2: Union[AssetInstance, tuple], min_distance=0, max_distance=10000, weight=1):
#         asset1.instance_id = get_instance_id(asset1)
#         asset2 = self.handle_fixed_pointtt(asset2)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("distance_constraint", min_distance=min_distance, max_distance=max_distance, weight=weight),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def against_wall(self, asset1: AssetInstance, wall: Wall):
#         asset1.instance_id = get_instance_id(asset1)
#         wall.instance_id = get_instance_id(wall)
#         self.constraints.append([
#             Constraint("against_wall"),
#             [asset1.instance_id, wall.instance_id]
#         ])

#     def on_top_of(self, asset1: AssetInstance, asset2: AssetInstance):
#         asset1.instance_id = get_instance_id(asset1)
#         asset2 = self.handle_fixed_pointtt(asset2)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("on_top_of"),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def align_with(self, asset1: AssetInstance, asset2: AssetInstance, angle=0):
#         asset1.instance_id = get_instance_id(asset1)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("align_with", angle=angle),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def align_x(self, asset1: AssetInstance, asset2: AssetInstance):
#         '''
#         Add a constraint that asset1 should have the same x-coordinate as asset2.
#         '''
#         asset1.instance_id = get_instance_id(asset1)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("align_x"),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def align_y(self, asset1: AssetInstance, asset2: AssetInstance):
#         '''
#         Add a constraint that asset1 should have the same y-coordinate as asset2.
#         '''
#         asset1.instance_id = get_instance_id(asset1)
#         asset2.instance_id = get_instance_id(asset2)
#         self.constraints.append([
#             Constraint("align_y"),
#             [asset1.instance_id, asset2.instance_id]
#         ])

#     def solve(self):
#         pass


# solver = ConstraintSolver()

# # Walls that define the boundary of the scene
# walls = [
#     Wall(corner1=[1.83, -2.74, 0.00], corner2=[1.83, 2.74, 0.00]),
#     Wall(corner1=[1.83, 2.74, 0.00], corner2=[-1.88, 2.74, 0.00]),
#     Wall(corner1=[-1.88, 2.74, 0.00], corner2=[-1.88, -2.74, 0.00]),
#     Wall(corner1=[-1.88, -2.74, 0.00], corner2=[1.83, -2.74, 0.00])
# ]

# # Longest wall is wall[0] with length 5.49 meters
# # Shortest wall is wall[1] with length 3.71 meters

# # Existing assets placed in the scene:

# # New assets to be placed
# sofa = Assets(description="Aiho 69' L Modern Loveseat Sofa with 3 Comfortable Pillows for Apartment, Dorm Room, Office, Bedroom - Dark Gray", size=[0.76, 1.75, 0.79], placements=[AssetInstance(position=[0.00, -2.00, 0.00], rotation=[1.57, 1.57, 1.57], optimize=1)])
# coffee_table = Assets(description="A minimalist & functional piece of furniture. Industrial X-shaped Design not only adds industrial style to your home, but also can prevent items from falling. 2-Tier Open Storage give you much space to store items and find them easily. The high-class thick boards feature excellent weight capacity, each shelf can hold up to 180 lbs. The scratch-proof, waterproof finish enables the tabletop is also easy to clean, helping you save time and effort on mundane cleaning.", size=[0.60, 1.20, 0.45], placements=[AssetInstance(position=[0.00, -1.00, 0.00], rotation=[1.57, 1.57, 1.57], optimize=1)])
# tv_stand = Assets(description="The Beautiful Fluted TV Stand is a stylish and functional addition to any living room or entertainment space.", size=[0.43, 1.52, 0.62], placements=[AssetInstance(position=[0.00, 2.00, 0.00], rotation=[1.57, 1.57, 4.71], optimize=1)])
# tv = Assets(description="onn 75” Class 4K UHD (2160P) LED Roku Smart Television", size=[0.38, 1.91, 0.10], placements=[AssetInstance(position=[0.00, 2.00, 1.00], rotation=[1.57, 1.57, 4.71], optimize=1)])
# rug = Assets(description="VUNATE 5'x5' Round Rugs for Living Room Washable Rugs Boho Moroccan Area Rug Soft Neutral Geometric Bohemian Carpet Distressed Indoor Rug for Bedroom Dining Room Office Foldable Nonslip Rug Coffee", size=[1.52, 1.52, 0.01], placements=[AssetInstance(position=[0.00, -1.00, 0.00], rotation=[1.57, 1.57, 1.57], optimize=1)])
# accent_chair = Assets(description="Introduce the Mainstays Swivel Chair to your living area, perfect for adding a touch of comfort and style to any living room, bedroom, or office. With its low-profile barrel back design, this chair serves as a modern accent piece, effortlessly adding a hint of luxury to your space without the need for complex assembly or tools. The chair's cream boucle fabric is versatile, harmonizing with both vibrant and muted color palettes for a classic, elegant look. Made with durable and easy-to-clean upholstery, the Mainstays Swivel Chair is not just an attractive piece, but also a practical choice for busy family homes, guaranteeing lasting appeal and easy maintenance.", size=[0.81, 0.84, 0.76], placements=[AssetInstance(position=[1.50, -1.50, 0.00], rotation=[1.57, 1.57, 6.28], optimize=1), AssetInstance(position=[-1.50, -1.50, 0.00], rotation=[1.57, 1.57, 3.14], optimize=1)])
# storage_unit = Assets(description="Sterilite Wide 3 Drawer Cart, Clear Plastic Storage Drawers, Wheels Included, Black", size=[0.56, 0.56, 0.65], placements=[AssetInstance(position=[-1.50, 0.00, 0.00], rotation=[1.57, 1.57, 3.14], optimize=1)])
# void_door_0 = Assets(description="This is a void space that other assets can't fill.", size=[0.08, 0.82, 5.00], placements=[AssetInstance(position=[-1.93, 2.27, 0.00], rotation=[0.00, 0.00, 0.00], optimize=0)])

# sofa[0].instance_id = 'sofa_0'
# coffee_table[0].instance_id = 'coffee_table_0'
# tv_stand[0].instance_id = 'tv_stand_0'
# tv[0].instance_id = 'tv_0'
# rug[0].instance_id = 'rug_0'
# accent_chair[0].instance_id = 'accent_chair_0'
# accent_chair[1].instance_id = 'accent_chair_1'
# storage_unit[0].instance_id = 'storage_unit_0'
# void_door_0[0].instance_id = 'void_door_0_0'

# sofa[0].position = [0.0, -2.0, 0.395]
# sofa[0].rotation = [1.5707963267948966, 1.5707963267948966, 1.5707963267948966]
# coffee_table[0].position = [0.0, -1.0, 0.225]
# coffee_table[0].rotation = [1.5707963267948966, 1.5707963267948966, 1.5707963267948966]
# tv_stand[0].position = [0.0, 2.0, 0.3085]
# tv_stand[0].rotation = [1.5707963267948966, 1.5707963267948966, 4.71238898038469]
# tv[0].position = [0.0, 2.0, 0.0508]
# tv[0].rotation = [1.5707963267948966, 1.5707963267948966, 4.71238898038469]
# rug[0].position = [0.0, -1.0, 0.005]
# rug[0].rotation = [1.5707963267948966, 1.5707963267948966, 1.5707963267948966]
# accent_chair[0].position = [1.5, -1.5, 0.381]
# accent_chair[0].rotation = [1.5707963267948966, 1.5707963267948966, 6.283185307179586]
# accent_chair[1].position = [-1.5, -1.5, 0.381]
# accent_chair[1].rotation = [1.5707963267948966, 1.5707963267948966, 3.141592653589793]
# storage_unit[0].position = [-1.5, 0.0, 0.324]
# storage_unit[0].rotation = [1.5707963267948966, 1.5707963267948966, 3.141592653589793]
# void_door_0[0].position = [-1.9250861548253138, 2.2658127404214192, 0.0]
# void_door_0[0].rotation = [0.0, 0.0, 0.0]
# void_door_0[0].optimize = 0

# solver.constraints = []

# # Define the center of the room for alignment purposes
# center_x, center_y = 0.0, 0.0

# # Place the sofa centered along the longest wall, facing the center of the room
# solver.against_wall(sofa[0], walls[0])
# solver.point_towards(sofa[0], AssetInstance(position=[center_x, center_y, 0.0]))

# # Position the TV on top of the TV stand, directly opposite the sofa, both centered and facing it
# solver.on_top_of(tv[0], tv_stand[0])
# solver.align_with(tv_stand[0], sofa[0], angle=180)
# solver.align_with(tv[0], sofa[0], angle=180)

# # Place the coffee table in front of the sofa, centered and aligned with it, on top of the rug
# solver.on_top_of(coffee_table[0], rug[0])
# solver.align_with(coffee_table[0], sofa[0])

# # Position the first accent chair to the right of the sofa, angled towards the coffee table
# solver.distance_constraint(accent_chair[0], sofa[0], 0.5, 1.0)
# solver.point_towards(accent_chair[0], coffee_table[0])

# # Place the second accent chair to the left of the sofa, also angled towards the coffee table
# solver.distance_constraint(accent_chair[1], sofa[0], 0.5, 1.0)
# solver.point_towards(accent_chair[1], coffee_table[0])

# # Position the storage unit along one of the shorter walls, ensuring it does not block any pathways
# solver.against_wall(storage_unit[0], walls[1])
# solver.distance_constraint(storage_unit[0], AssetInstance(position=[center_x, center_y, 0.0]), 0.5, None)

# # Ensure there are at least 0.3 meters of walking space between all furniture pieces and around the room
# for asset1 in [sofa[0], coffee_table[0], tv_stand[0], accent_chair[0], accent_chair[1], storage_unit[0]]:
#     for asset2 in [sofa[0], coffee_table[0], tv_stand[0], accent_chair[0], accent_chair[1], storage_unit[0]]:
#         if asset1 != asset2:
#             solver.distance_constraint(asset1, asset2, 0.3, None)

# # Align all furniture parallel to the room walls
# for asset in [sofa[0], tv_stand[0], coffee_table[0], accent_chair[0], accent_chair[1], storage_unit[0]]:
#     solver.align_with(asset, AssetInstance(position=[center_x, center_y, 0.0]), angle=0)

# # Avoid any overlap or collision between furniture and void spaces
# for asset in [sofa[0], coffee_table[0], tv_stand[0], accent_chair[0], accent_chair[1], storage_unit[0]]:
#     for void in [void_door_0[0]]:
#         solver.distance_constraint(asset, void, 0.5, None)
# ```
#             """
#         )

    # Save results
    output_path = os.path.join(args.save_dir, "layout.json")
    with open(output_path, "w") as f:
        json.dump(layout, f, indent=4)

    print(f"Layout generated and saved to {output_path}")


if __name__ == "__main__":
    main()
