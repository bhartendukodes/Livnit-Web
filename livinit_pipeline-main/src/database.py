print("[DEBUG] supabase_data module loaded")

import os
import json
import shutil
import requests
import random
import re
from collections import defaultdict
from supabase import create_client, Client
from dotenv import load_dotenv
from src.scene_multiple_lines import llm


# ===============================================================
#  Environment Setup
# ===============================================================
load_dotenv()
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = os.getenv("SUPABASE_ASSETS_TABLE", "assets")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ===============================================================
#  Constants
# ===============================================================

# Category configuration with min/max limits per room size
CATEGORY_RULES = {
    # Format: "category": {min, max_small, max_medium, max_large, priority}
    "sofa": {
        "min": 1, "max_small": 1, "max_medium": 2, "max_large": 2, 
        "priority": 1, "essential": True
    },
    "coffee_table": {
        "min": 1, "max_small": 1, "max_medium": 1, "max_large": 2, 
        "priority": 1, "essential": True
    },
    "tv_stand": {
        "min": 1, "max_small": 1, "max_medium": 1, "max_large": 1, 
        "priority": 1, "essential": True
    },
    "tv": {
        "min": 1, "max_small": 1, "max_medium": 1, "max_large": 1, 
        "priority": 1, "essential": True
    },
    "rug": {
        "min": 1, "max_small": 1, "max_medium": 1, "max_large": 2, 
        "priority": 1, "essential": True
    },
    "accent_chair": {
        "min": 0, "max_small": 1, "max_medium": 2, "max_large": 3, 
        "priority": 2, "essential": False
    },
    "side_table": {
        "min": 0, "max_small": 1, "max_medium": 2, "max_large": 3, 
        "priority": 2, "essential": False
    },
    "floor_lamp": {
        "min": 0, "max_small": 1, "max_medium": 1, "max_large": 2, 
        "priority": 2, "essential": False
    },
    "book_shelf": {
        "min": 0, "max_small": 0, "max_medium": 1, "max_large": 1, 
        "priority": 3, "essential": False
    },
    "storage_unit": {
        "min": 0, "max_small": 0, "max_medium": 1, "max_large": 2, 
        "priority": 3, "essential": False
    },
    "ottoman": {
        "min": 0, "max_small": 0, "max_medium": 1, "max_large": 2, 
        "priority": 3, "essential": False
    },
    "plant": {
        "min": 0, "max_small": 1, "max_medium": 2, "max_large": 3, 
        "priority": 3, "essential": False
    },
    "decor": {
        "min": 0, "max_small": 1, "max_medium": 2, "max_large": 3, 
        "priority": 3, "essential": False
    },
    "wall_art": {
        "min": 0, "max_small": 0, "max_medium": 1, "max_large": 2, 
        "priority": 3, "essential": False
    },
    "throw_pillow": {
        "min": 0, "max_small": 0, "max_medium": 2, "max_large": 3, 
        "priority": 4, "essential": False
    }
}

# Room size thresholds
ROOM_SIZE_CONFIG = {
    "small": {"max_sqft": 140, "asset_range": (6, 8)},
    "medium": {"max_sqft": 220, "asset_range": (9, 12)},
    "large": {"max_sqft": float('inf'), "asset_range": (13, 18)}
}

# Style mapping for graceful fallback
STYLE_HIERARCHY = {
    "modern": ["modern", "contemporary", "minimalist", "industrial"],
    "contemporary": ["contemporary", "modern", "transitional"],
    "traditional": ["traditional", "classic", "vintage"],
    "minimalist": ["minimalist", "modern", "scandinavian"],
    "industrial": ["industrial", "modern", "rustic"],
    "scandinavian": ["scandinavian", "minimalist", "modern"],
    "bohemian": ["bohemian", "eclectic", "vintage"],
    "rustic": ["rustic", "farmhouse", "traditional"]
}

# Enhanced color similarity with neutrals
COLOR_SIMILARITY = {
    "black": ["black", "dark gray", "charcoal", "graphite", "slate", "ebony"],
    "white": ["white", "off white", "cream", "ivory", "alabaster", "pearl"],
    "gray": ["gray", "grey", "light gray", "dark gray", "charcoal", "silver", "ash", "slate"],
    "beige": ["beige", "tan", "sand", "taupe", "cream", "light brown", "khaki"],
    "brown": ["brown", "walnut", "espresso", "chocolate", "mahogany", "oak"],
    "blue": ["blue", "navy", "sky blue", "teal", "azure", "cobalt"],
    "green": ["green", "olive", "sage", "mint", "emerald", "forest"],
    "neutral": ["white", "black", "gray", "beige", "cream", "tan", "taupe"]
}


# ===============================================================
#  Helper Functions
# ===============================================================
def calculate_room_area(floor_vertices: list) -> float:
    """Calculate room area using shoelace formula."""
    if not floor_vertices or len(floor_vertices) < 3:
        return 150.0
    
    vertices = []
    for v in floor_vertices:
        if len(v) >= 2:
            vertices.append((v[0], v[1]))
    
    if len(vertices) < 3:
        return 150.0
    
    area = 0.0
    n = len(vertices)
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    
    area = abs(area) / 2.0
    area*= 10.7639
    return area


def classify_room_size(area_sqft: float) -> dict:
    """Classify room and return size info."""
    for size, config in ROOM_SIZE_CONFIG.items():
        if area_sqft <= config["max_sqft"]:
            return {"size": size, "area": area_sqft, **config}
    return {"size": "large", "area": area_sqft, **ROOM_SIZE_CONFIG["large"]}


def get_category_max(category: str, room_size: str) -> int:
    """Get maximum allowed items for a category based on room size."""
    if category not in CATEGORY_RULES:
        return 1  # Default for unknown categories
    
    rules = CATEGORY_RULES[category]
    max_key = f"max_{room_size}"
    return rules.get(max_key, rules.get("min", 1))


def match_with_fallback(value: str, target: str, hierarchy: dict) -> int:
    """Return match score (higher = better match)."""
    if not value or not target:
        return 0
    
    value_lower = value.lower()
    target_lower = target.lower()
    
    if target_lower in value_lower:
        return 100
    
    similar_styles = hierarchy.get(target_lower, [target_lower])
    for idx, style in enumerate(similar_styles):
        if style in value_lower:
            return 100 - (idx * 10)
    
    return 0


def match_color_with_fallback(asset_color: str, target_color: str) -> int:
    """Return color match score."""
    if not asset_color or not target_color:
        return 50
    
    asset_lower = asset_color.lower()
    target_lower = target_color.lower()
    
    if target_lower in asset_lower:
        return 100
    
    similar_colors = COLOR_SIMILARITY.get(target_lower, [target_lower])
    for idx, color in enumerate(similar_colors):
        if color in asset_lower:
            return 100 - (idx * 5)
    
    if any(neutral in asset_lower for neutral in ["white", "black", "gray", "grey", "beige"]):
        return 40
    
    return 0


# ===============================================================
#  Smart Asset Fetching with Scoring
# ===============================================================
def fetch_and_score_assets(style: str = None, color_palette: str = None) -> list:
    """Fetch all assets and score them based on style/color match."""
    print(f"[INFO] Fetching and scoring assets (style={style}, color={color_palette})")
    
    try:
        resp = supabase.table(SUPABASE_TABLE).select("name,category,style,color,cost").execute()
        assets = resp.data or []
    except Exception as e:
        print(f"[ERROR] Failed to fetch assets from Supabase: {e}")
        return []

    print(f"[INFO] Total assets in database: {len(assets)}")
    
    if not assets:
        print("[ERROR] No assets found in database!")
        return []
    
    scored_assets = []
    for asset in assets:
        score = 0
        
        if style:
            style_score = match_with_fallback(
                asset.get("style", ""), 
                style, 
                STYLE_HIERARCHY
            )
            score += style_score * 0.6
        else:
            score += 50
        
        if color_palette:
            color_score = match_color_with_fallback(
                asset.get("color", ""), 
                color_palette
            )
            score += color_score * 0.4
        else:
            score += 40
        
        asset["match_score"] = score
        scored_assets.append(asset)
    
    scored_assets.sort(key=lambda x: x["match_score"], reverse=True)
    
    print(f"[INFO] Assets scored. Top score: {scored_assets[0]['match_score']:.1f}, "
          f"Lowest score: {scored_assets[-1]['match_score']:.1f}")
    
    return scored_assets


# ===============================================================
#  Balanced Asset Selection with Category Limits
# ===============================================================
def select_assets_for_room(
    scored_assets: list, 
    room_info: dict, 
    user_prompt: str = ""
) -> list:
    """
    Intelligently select assets with proper category limits.
    """
    room_size = room_info["size"]
    min_assets, max_assets = room_info["asset_range"]
    
    print(f"\n[INFO] Room: {room_size.upper()} ({room_info['area']:.1f} sq ft)")
    print(f"[INFO] Target asset count: {min_assets}-{max_assets}")
    
    # Group assets by category
    by_category = defaultdict(list)
    for asset in scored_assets:
        cat = (asset.get("category") or asset["name"].split("_")[0]).lower()
        by_category[cat].append(asset)
    
    selected = []
    category_counts = defaultdict(int)
    
    # Get categories sorted by priority
    categories_by_priority = sorted(
        CATEGORY_RULES.items(), 
        key=lambda x: (x[1]["priority"], -x[1]["min"])
    )
    
    # Phase 1: Add essential items (priority 1)
    print("\n[PHASE 1] Adding essential furniture...")
    for cat, rules in categories_by_priority:
        if not rules["essential"]:
            continue
        
        if cat not in by_category:
            print(f"  ⚠ {cat}: No assets available in database")
            continue
        
        max_for_room = get_category_max(cat, room_size)
        min_required = rules["min"]
        
        # Add minimum required
        items_to_add = min(min_required, len(by_category[cat]), max_for_room)
        
        for i in range(items_to_add):
            asset = by_category[cat][i]
            selected.append(asset)
            category_counts[cat] += 1
            print(f"  ✓ {cat}: {asset['name']} (score: {asset['match_score']:.1f})")
    
    # Phase 2: Add important furniture (priority 2)
    print("\n[PHASE 2] Adding important furniture...")
    for cat, rules in categories_by_priority:
        if rules["priority"] != 2:
            continue
        
        if len(selected) >= max_assets:
            break
        
        if cat not in by_category:
            continue
        
        max_for_room = get_category_max(cat, room_size)
        current_count = category_counts[cat]
        
        # Determine how many to add
        if room_size == "small":
            items_to_add = min(1, max_for_room - current_count)
        elif room_size == "medium":
            items_to_add = min(2, max_for_room - current_count)
        else:  # large
            items_to_add = min(2, max_for_room - current_count)
        
        # Add items respecting max limits
        for i in range(items_to_add):
            if len(selected) >= max_assets:
                break
            if current_count + i >= len(by_category[cat]):
                break
            if category_counts[cat] >= max_for_room:
                break
            
            asset = by_category[cat][current_count + i]
            selected.append(asset)
            category_counts[cat] += 1
            print(f"  ✓ {cat}: {asset['name']} (score: {asset['match_score']:.1f})")
    
    # Phase 3: Add decorative items (priority 3) - with diversity
    print("\n[PHASE 3] Adding decorative items...")
    priority_3_cats = [cat for cat, rules in categories_by_priority if rules["priority"] == 3]
    
    # Round-robin to ensure variety
    while len(selected) < min_assets:
        added_this_round = False
        
        for cat in priority_3_cats:
            if len(selected) >= min_assets:
                break
            
            if cat not in by_category:
                continue
            
            max_for_room = get_category_max(cat, room_size)
            current_count = category_counts[cat]
            
            if current_count >= max_for_room:
                continue
            if current_count >= len(by_category[cat]):
                continue
            
            asset = by_category[cat][current_count]
            selected.append(asset)
            category_counts[cat] += 1
            print(f"  ✓ {cat}: {asset['name']} (score: {asset['match_score']:.1f})")
            added_this_round = True
        
        if not added_this_round:
            break  # No more items can be added
    
    # Phase 4: Fill to max for large rooms (priority 4 + extras)
    if room_size == "large" and len(selected) < max_assets:
        print("\n[PHASE 4] Adding final touches for large room...")
        
        # First try priority 4 items
        priority_4_cats = [cat for cat, rules in categories_by_priority if rules["priority"] == 4]
        
        for cat in priority_4_cats:
            if len(selected) >= max_assets:
                break
            
            if cat not in by_category:
                continue
            
            max_for_room = get_category_max(cat, room_size)
            current_count = category_counts[cat]
            
            for i in range(max_for_room - current_count):
                if len(selected) >= max_assets:
                    break
                if current_count + i >= len(by_category[cat]):
                    break
                
                asset = by_category[cat][current_count + i]
                selected.append(asset)
                category_counts[cat] += 1
                print(f"  ✓ {cat}: {asset['name']} (score: {asset['match_score']:.1f})")
        
        # Then add more from flexible categories if still under max
        flexible_cats = ["plant", "decor", "side_table", "accent_chair"]
        
        while len(selected) < max_assets:
            added = False
            for cat in flexible_cats:
                if len(selected) >= max_assets:
                    break
                
                if cat not in by_category:
                    continue
                
                max_for_room = get_category_max(cat, room_size)
                current_count = category_counts[cat]
                
                if current_count >= max_for_room:
                    continue
                if current_count >= len(by_category[cat]):
                    continue
                
                asset = by_category[cat][current_count]
                selected.append(asset)
                category_counts[cat] += 1
                print(f"  ✓ {cat}: {asset['name']} (score: {asset['match_score']:.1f})")
                added = True
                break
            
            if not added:
                break
    
    return selected


# ===============================================================
#  Main List Creations Function
# ===============================================================
def list_creations(
    user_prompt: str, 
    floor_vertices: list, 
    style: str = None, 
    color_palette: str = None
) -> list:
    """
    Main function to generate optimal asset list for room layout.
    """
    print("\n" + "="*60)
    print("BALANCED ASSET SELECTION ALGORITHM")
    print("="*60)
    
    # Step 1: Calculate room info
    area = calculate_room_area(floor_vertices)
    room_info = classify_room_size(area)
    print(f"\n[ROOM INFO] Size: {room_info['size']}, Area: {room_info['area']:.1f} sq ft")
    print(f"[TARGET] {room_info['asset_range'][0]}-{room_info['asset_range'][1]} assets")
    
    # Step 2: Fetch and score all assets
    scored_assets = fetch_and_score_assets(style, color_palette)
    
    if not scored_assets:
        print("[ERROR] No assets available!")
        return []
    
    # Step 3: Smart selection with category limits
    selected = select_assets_for_room(scored_assets, room_info, user_prompt)
    
    # Step 4: Display results
    print("\n" + "="*60)
    print("FINAL SELECTION")
    print("="*60)
    print(f"Total assets selected: {len(selected)}")
    
    # Group by category for display
    by_cat = defaultdict(list)
    for asset in selected:
        cat = (asset.get("category") or asset["name"].split("_")[0]).lower()
        by_cat[cat].append(asset)
    
    # Show category breakdown with limits
    print(f"\n[CATEGORY BREAKDOWN]")
    for cat, items in sorted(by_cat.items()):
        max_allowed = get_category_max(cat, room_info['size'])
        print(f"\n{cat.upper()} ({len(items)}/{max_allowed} max):")
        for asset in items:
            print(f"  • {asset['name']:<30} | style: {asset.get('style','N/A'):<12} | "
                  f"color: {asset.get('color','N/A'):<15} | score: {asset['match_score']:.1f}")
    
    print("="*60 + "\n")
    
    return [asset["name"] for asset in selected]


# ===============================================================
#  Asset Downloader (unchanged)
# ===============================================================
def download_asset(asset_name: str) -> str:
    """Downloads an asset GLB and metadata."""
    print(f"[INFO] Downloading asset: {asset_name}")

    data = (
        supabase.table(SUPABASE_TABLE)
        .select("name, category, model_url, metadata_url")
        .eq("name", asset_name)
        .execute()
    )

    if not data.data:
        print(f"[WARN] Asset '{asset_name}' not found in Supabase.")
        return None

    asset_info = data.data[0]
    category = (asset_info.get("category") or asset_name.split("_")[0]).lower()
    model_url = asset_info.get("model_url")
    metadata_url = asset_info.get("metadata_url")

    if not model_url:
        print(f"[WARN] No model_url for {asset_name}")
        return None

    if "supabase" in model_url and "download=" not in model_url:
        sep = "&" if "?" in model_url else "?"
        model_url = f"{model_url}{sep}download=1"

    objaverse_root = os.path.join("assets", "objaverse_processed")
    asset_dir = os.path.join(objaverse_root, asset_name)
    os.makedirs(asset_dir, exist_ok=True)

    model_filename = f"{category}.glb"
    model_path = os.path.join(asset_dir, model_filename)
    metadata_path = os.path.join(asset_dir, "data.json")

    print(f"[INFO] → Downloading model from {model_url}")
    try:
        resp = requests.get(model_url, timeout=60)
        resp.raise_for_status()
        data = resp.content
    except Exception as e:
        print(f"[ERROR] Failed to download {asset_name}: {e}")
        return None

    if len(data) < 1000:
        print(f"[CORRUPT] {asset_name} too small ({len(data)} bytes) → skipped.")
        return None
    if not data.startswith(b"glTF"):
        text_head = data[:32]
        if text_head.strip().startswith(b"{") or text_head.strip().startswith(b"<"):
            print(f"[CORRUPT] {asset_name} looks like JSON/HTML → skipped.")
            return None
        try:
            import base64
            decoded = base64.b64decode(data, validate=True)
            if decoded.startswith(b"glTF"):
                data = decoded
                print(f"[FIX] {asset_name} decoded from base64 successfully.")
            else:
                print(f"[CORRUPT] {asset_name} invalid binary → skipped.")
                return None
        except Exception:
            print(f"[CORRUPT] {asset_name} missing 'glTF' header → skipped.")
            return None

    with open(model_path, "wb") as f:
        f.write(data)
    print(f"[OK] Saved GLB → {model_path}")

    if metadata_url:
        print(f"[INFO] → Downloading metadata from {metadata_url}")
        try:
            meta_resp = requests.get(metadata_url, timeout=30)
            meta_resp.raise_for_status()
            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write(meta_resp.text)
        except Exception as e:
            print(f"[WARN] Failed to download metadata for {asset_name}: {e}")

    print(f"[SUCCESS] {asset_name} → {asset_dir}")
    return model_path