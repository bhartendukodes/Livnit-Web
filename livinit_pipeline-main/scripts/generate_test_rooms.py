"""Generate synthetic USDZ room files matching iOS RoomPlan schema."""

from pathlib import Path
from pxr import Usd, UsdGeom, UsdShade, UsdUtils, Sdf, Gf

ROOM_CONFIGS = [
    {"name": "small", "width": 3.0, "depth": 3.5, "wall_height": 2.4},
    {"name": "medium", "width": 4.5, "depth": 5.0, "wall_height": 2.6},
    {"name": "large", "width": 6.0, "depth": 7.0, "wall_height": 2.8},
    {"name": "xlarge", "width": 8.0, "depth": 9.0, "wall_height": 3.0},
]

WALL_THICKNESS = 0.15
DOOR_WIDTH, DOOR_HEIGHT = 0.9, 2.1
WINDOW_WIDTH, WINDOW_HEIGHT = 1.2, 1.0
WINDOW_SILL_HEIGHT = 0.9


def create_box_mesh(stage, path, width, height, depth, color=(0.8, 0.8, 0.8)):
    """Create a box mesh with given dimensions centered at origin."""
    mesh = UsdGeom.Mesh.Define(stage, path)
    hw, hd = width / 2, depth / 2

    points = [
        (-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),  # bottom
        (-hw, -hd, height), (hw, -hd, height), (hw, hd, height), (-hw, hd, height),  # top
    ]
    mesh.GetPointsAttr().Set([Gf.Vec3f(*p) for p in points])
    mesh.GetFaceVertexCountsAttr().Set([4] * 6)
    mesh.GetFaceVertexIndicesAttr().Set([
        0, 3, 2, 1,  # bottom
        4, 5, 6, 7,  # top
        0, 1, 5, 4,  # front
        2, 3, 7, 6,  # back
        0, 4, 7, 3,  # left
        1, 2, 6, 5,  # right
    ])

    # Add material
    mat = UsdShade.Material.Define(stage, f"{path}_color")
    shader = UsdShade.Shader.Define(stage, f"{path}_color/surfaceShader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    mesh.GetPrim().ApplyAPI(UsdShade.MaterialBindingAPI)
    UsdShade.MaterialBindingAPI(mesh).Bind(mat)
    return mesh


def create_floor(stage, arch_grp, width, depth):
    """Create floor mesh as a flat quad."""
    floor_grp = UsdGeom.Xform.Define(stage, f"{arch_grp}/Floor_grp")
    mesh = UsdGeom.Mesh.Define(stage, f"{floor_grp.GetPath()}/Floor0")

    points = [(0, 0, 0), (width, 0, 0), (width, depth, 0), (0, depth, 0)]
    mesh.GetPointsAttr().Set([Gf.Vec3f(*p) for p in points])
    mesh.GetFaceVertexCountsAttr().Set([4])
    mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])

    mat = UsdShade.Material.Define(stage, f"{mesh.GetPath()}_color")
    shader = UsdShade.Shader.Define(stage, f"{mat.GetPath()}/surfaceShader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.9, 0.85, 0.8))
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    mesh.GetPrim().ApplyAPI(UsdShade.MaterialBindingAPI)
    UsdShade.MaterialBindingAPI(mesh).Bind(mat)
    return mesh


def create_wall_with_opening(stage, wall_grp_path, wall_idx, x, y, length, height, is_vertical, opening=None):
    """Create wall mesh, optionally with door/window opening."""
    UsdGeom.Xform.Define(stage, wall_grp_path)

    # Wall as a simple box
    if is_vertical:
        w, d = WALL_THICKNESS, length
    else:
        w, d = length, WALL_THICKNESS

    wall_mesh = create_box_mesh(stage, f"{wall_grp_path}/Wall{wall_idx}", w, height, d, (0.95, 0.95, 0.92))
    xform = UsdGeom.Xformable(wall_mesh)
    xform.AddTranslateOp().Set(Gf.Vec3d(x + w/2, y + d/2, 0))

    # Add opening (door or window) if specified
    if opening:
        op_type, op_x, op_y = opening["type"], opening["x"], opening["y"]
        if op_type == "door":
            op_w, op_h = DOOR_WIDTH, DOOR_HEIGHT
            op_z = 0  # door at floor level
            color = (0.55, 0.35, 0.2)
        else:  # window
            op_w, op_h = WINDOW_WIDTH, WINDOW_HEIGHT
            op_z = WINDOW_SILL_HEIGHT
            color = (0.7, 0.85, 0.95)

        if is_vertical:
            mesh_w, mesh_d = WALL_THICKNESS * 0.8, op_w
        else:
            mesh_w, mesh_d = op_w, WALL_THICKNESS * 0.8

        op_mesh = create_box_mesh(stage, f"{wall_grp_path}/{op_type.title()}0", mesh_w, op_h, mesh_d, color)
        xform = UsdGeom.Xformable(op_mesh)
        xform.AddTranslateOp().Set(Gf.Vec3d(op_x + mesh_w/2, op_y + mesh_d/2, op_z))

    return wall_mesh


def generate_room(config, output_dir: Path):
    """Generate a single room USDZ file."""
    name = config["name"]
    width, depth, wall_height = config["width"], config["depth"], config["wall_height"]

    # Create stage
    usda_path = output_dir / f"room_{name}.usda"
    usdz_path = output_dir / f"room_{name}.usdz"
    stage = Usd.Stage.CreateNew(str(usda_path))

    # Root structure matching RoomPlan schema
    root_name = f"Room_{name}"
    UsdGeom.Xform.Define(stage, f"/{root_name}")
    mesh_grp = UsdGeom.Xform.Define(stage, f"/{root_name}/Mesh_grp")
    arch_grp = UsdGeom.Xform.Define(stage, f"/{root_name}/Mesh_grp/Arch_grp")

    # Floor
    create_floor(stage, mesh_grp.GetPath().pathString, width, depth)

    # Walls: 4 walls forming rectangle, door on wall 2 (right), window on wall 0 (bottom)
    walls = [
        # (x, y, length, is_vertical, opening)
        (0, -WALL_THICKNESS, width, False, {"type": "window", "x": width/2 - WINDOW_WIDTH/2, "y": -WALL_THICKNESS/2}),  # bottom wall with window
        (width, 0, depth, True, None),  # right wall
        (0, depth, width, False, {"type": "door", "x": width/2 - DOOR_WIDTH/2, "y": depth}),  # top wall with door
        (-WALL_THICKNESS, 0, depth, True, None),  # left wall
    ]

    for i, (x, y, length, is_vert, opening) in enumerate(walls):
        create_wall_with_opening(
            stage,
            f"{arch_grp.GetPath()}/Wall_{i}_grp",
            i, x, y, length, wall_height, is_vert, opening
        )

    # Set up axis and meters
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    stage.GetRootLayer().Save()

    # Convert to USDZ
    UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(usda_path)), str(usdz_path))
    usda_path.unlink()  # remove intermediate usda

    print(f"Generated {usdz_path}: {width}m x {depth}m, height={wall_height}m")
    return usdz_path


def main():
    output_dir = Path(__file__).parent.parent / "dataset" / "room" / "synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)

    for config in ROOM_CONFIGS:
        generate_room(config, output_dir)

    print(f"\nGenerated {len(ROOM_CONFIGS)} rooms in {output_dir}")


if __name__ == "__main__":
    main()
