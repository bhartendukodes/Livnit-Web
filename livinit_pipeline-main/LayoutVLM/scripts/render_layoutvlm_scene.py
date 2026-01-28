"""Blender script for rendering LayoutVLM scenes via subprocess."""
import argparse
import json
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.blender_render import render_existing_scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        with open(args.input) as f:
            data = json.load(f)

        task_data = data["task_data"]
        params = data["params"]

        output_images, visual_marks = render_existing_scene(
            placed_assets=task_data["placed_assets"],
            task=task_data["task"],
            save_dir=data["save_dir"],
            **params,
        )

        # Convert tuple keys to strings for JSON serialization
        visual_marks_json = {f"{k[0]},{k[1]}": v for k, v in visual_marks.items()}

        with open(args.output, "w") as f:
            json.dump({"success": True, "output_images": output_images, "visual_marks": visual_marks_json}, f)

    except Exception as e:
        with open(args.output, "w") as f:
            json.dump({"success": False, "error": str(e)}, f)
        sys.exit(1)


if __name__ == "__main__":
    main()
