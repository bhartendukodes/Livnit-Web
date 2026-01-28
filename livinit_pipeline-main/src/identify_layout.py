import json
import numpy as np
import math
from shapely.geometry import Polygon, box, Point
from typing import Dict, List, Any

class LayoutGeometryEngine:
    def __init__(self, layout_json_path: str, sence_json_path: str = None):
        with open(layout_json_path, 'r') as f:
            self.data = json.load(f)
        
        self.scene_data = {}
        if sence_json_path:
            with open(sence_json_path, 'r') as f:
                self.scene_data = json.load(f)

        self.assets = self._parse_assets()

    def _parse_assets(self):
        """Flatten assets into a usable dictionary with Shapely polygons."""
        parsed = {}
        
        layout_assets = self.data
        scene_assets = self.scene_data.get("assets", {})
        
        # Process all assets found in either layout or scene
        all_keys = set(layout_assets.keys()) | set(scene_assets.keys())

        for key in all_keys:
            # Use layout asset for metadata if available, else scene asset
            asset_data = layout_assets.get(key, scene_assets.get(key))
            
            # Determine Position and Rotation
            pos = None
            rot = None

            # 1. Try layout JSON (Primary source)
            if key in layout_assets:
                placements = layout_assets[key]
                if placements:
                    pos = np.array(placements.get("position", [0,0,0]))
                    rot = placements.get("rotation", [0,0,0])

            # 2. Fallback to scene JSON (Secondary source)
            if (pos is None or rot is None) and key in scene_assets:
                placements = scene_assets[key].get("placements", [])
                if placements:
                    if pos is None:
                        pos = np.array(placements[0].get("position", [0,0,0]))
                    if rot is None:
                        rot = placements[0].get("rotation", [0,0,0])

            # 3. Defaults
            if pos is None: pos = np.array([0,0,0])
            if rot is None: rot = [0,0,0]

            meta = asset_data.get("assetMetadata", {}).get("boundingBox", {})
            w = meta.get("x", 1.0)
            d = meta.get("y", 1.0)

            half_w, half_d = w/2, d/2
            corners = np.array([
                [-half_w, -half_d], [half_w, -half_d], 
                [half_w, half_d], [-half_w, half_d]
            ])
            
            theta = rot[2] 
            c, s = math.cos(theta), math.sin(theta)
            R = np.array(((c, -s), (s, c)))
            rotated_corners = corners @ R.T
            
            final_corners = rotated_corners + pos[:2]
            
            parsed[key] = {
                "uid": key,
                "category": asset_data.get("category", "unknown"),
                "pos": pos,
                "rot_z_deg": math.degrees(theta),
                "poly": Polygon(final_corners),
                "front_vec": R @ np.array([1, 0])
            }
        return parsed

    def check_collisions(self) -> List[str]:
        collisions = []
        keys = list(self.assets.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                
                poly1 = self.assets[k1]['poly']
                poly2 = self.assets[k2]['poly']
                
                # Check intersection area
                intersection = poly1.intersection(poly2).area
                if intersection > 0.05: # Tolerance for tiny touches
                    collisions.append(f"CRITICAL: {k1} overlaps with {k2} by {intersection:.2f} m2")
        return collisions

    def analyze_relationships(self) -> str:
        """Generates a text report of all spatial relationships."""
        report = []
        keys = list(self.assets.keys())
        
        for i in range(len(keys)):
            for j in range(len(keys)):
                if i == j: continue
                k1, k2 = keys[i], keys[j]
                a1, a2 = self.assets[k1], self.assets[k2]

                dist = a1['poly'].distance(a2['poly'])
                center_dist = np.linalg.norm(a1['pos'] - a2['pos'])

                vec_to_target = (a2['pos'] - a1['pos'])
                vec_to_target /= (np.linalg.norm(vec_to_target) + 1e-6)
                facing_score = np.dot(a1['front_vec'], vec_to_target[:2])
                
                facing_status = "not facing"
                if facing_score > 0.8: facing_status = "directly facing"
                elif facing_score > 0.4: facing_status = "loosely facing"
                
                report.append(
                    f"- {k1} is {dist:.2f}m away from {k2} (edge-to-edge). "
                    f"It is {facing_status} {k2}."
                )
                
        return "\n".join(report)

    def get_summary(self):
        return {
            "asset_list": [f"{k} at {v['pos']}" for k,v in self.assets.items()],
            "collisions": self.check_collisions(),
            "relations": self.analyze_relationships()
        }


if __name__ == "__main__":
    engine = LayoutGeometryEngine(
        "outputs/20251216_102048/layout.json",
        "outputs/20251216_102048/scene_processed.json"
    )
    summary = engine.get_summary()
    print("Assets:")
    for asset in summary["asset_list"]:
        print(f"  - {asset}")
    print("\nCollisions:")
    for collision in summary["collisions"]:
        print(f"  - {collision}")
    print("\nRelationships:")
    print(summary["relations"])