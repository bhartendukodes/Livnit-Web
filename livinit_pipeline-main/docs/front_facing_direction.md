# Front-Facing Direction Convention

## Overview

All assets in the pipeline follow a consistent front-facing direction convention. This ensures assets are oriented correctly during layout optimization and final rendering.

## Coordinate System

```
        +Y (up)
         ^
         |
         |
-X <-----+-----> +X (right)
         |
         |
         v
        -Y (down)
```

- **Origin**: Bottom-left of room at (0, 0)
- **X axis**: Rightward (+)
- **Y axis**: Upward (+)
- **Z axis**: Height above floor

## frontView Field

Each asset has a `frontView` field in `dataset/blobs/<asset_id>/data.json` under `annotations.frontView`.

| frontView | Native Direction | Meaning |
|-----------|------------------|---------|
| 0 | -Y | Asset faces toward y=0 (default) |
| 1 | +X | Asset faces toward x=max |
| 2 | +Y | Asset faces toward y=max |
| 3 | -X | Asset faces toward x=0 |

## Rotation Convention

Rotation is specified in **radians** around the Z-axis:

| Rotation | Facing Direction |
|----------|------------------|
| 0 | -Y (toward y=0) |
| π/2 (1.57) | +X (toward x=max) |
| π (3.14) | +Y (toward y=max) |
| 3π/2 (4.71) | -X (toward x=0) |

## Front-View Correction

The pipeline automatically applies a rotation correction based on `frontView` to normalize all assets to face -Y when rotation=0.

```python
# Correction applied to normalize asset orientation
FRONT_VIEW_ROTATIONS = {
    0: 0,           # Already faces -Y, no correction
    1: -π/2,        # Faces +X, rotate -90°
    2: -π,          # Faces +Y, rotate -180°
    3: π/2          # Faces -X, rotate +90°
}
```

## Where Correction is Applied

1. **render_topdown.py** - Top-down asset preview images
2. **render_scene.py** - Final 3D scene rendering
3. **run_layoutvlm.py** - Layout optimization

## Example

An asset with:
- `frontView: 2` (natively faces +Y)
- Layout rotation: `π/2` (should face +X)

Final rotation = `π/2 + (-π)` = `-π/2` = faces +X ✓

## Updating frontView

To correct an asset's front-facing direction:

1. Open `dataset/blobs/<asset_id>/data.json`
2. Find `annotations.frontView`
3. Set to 0, 1, 2, or 3 based on which direction the 3D model natively faces
4. Re-render top-down images: delete `dataset/render/<asset_id>.png` and run pipeline

## Visual Reference

```
frontView=0        frontView=1        frontView=2        frontView=3
    ^                  |                  |                  |
    |                  |                  v                  |
    |                  +-->                                <--+
  FRONT              FRONT              FRONT              FRONT
```
