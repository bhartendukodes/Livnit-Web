#!/usr/bin/env python3
"""
Re-categorize assets in processed.json based on descriptions.

Categories (5 total):
- Seating: sofas, chairs, recliners
- Sleeping: beds
- Tables: side tables, coffee tables, dining tables, desks
- Storage: bookshelves, storage units, tv stands
- Utility: lamps, lighting, decor, plants, rugs, pillows, throws, wall art
"""

import json
import re
from pathlib import Path


def categorize_by_description(item: dict) -> str:
    """Categorize item into one of 5 categories based on uid prefix and description."""
    uid = item['uid'].lower()
    desc = item['description'].lower()

    # Check uid prefix first (most reliable)
    # Utility: lamps, lighting, decor, plants, rugs - check BEFORE tables to avoid "table_lamps" matching "table"
    if uid.startswith(('table_lamp', 'floor_lamp', 'lamp', 'light', 'decor', 'plant', 'rug', 'art', 'pillow', 'throw')):
        return 'utility'

    # Seating: sofas, chairs, recliners
    if uid.startswith(('sofa', 'sectional', 'recliner', 'accent_chair', 'dining_chair', 'chair')):
        return 'seating'

    # Sleeping: beds
    if uid.startswith('bed'):
        return 'sleeping'

    # Tables: side tables, coffee tables, dining tables, desks
    if uid.startswith(('side_table', 'coffee_table', 'dining_table', 'table', 'desk')):
        return 'tables'

    # Storage: bookshelves, storage units, tv stands
    if uid.startswith(('book_shelves', 'bookshelf', 'storage', 'tv_stand', 'cabinet', 'shelf')):
        return 'storage'

    # Fallback: check description keywords
    # Utility keywords
    if any(kw in desc for kw in ['lamp', 'lighting', 'light fixture', 'decor', 'plant', 'rug', 'carpet', 'artwork', 'pillow', 'throw', 'blanket']):
        return 'utility'

    # Seating keywords (use word boundaries to avoid "rechargeable" matching "chair")
    if re.search(r'\b(sofa|couch|recliner|chair|loveseat|settee|seating)\b', desc):
        return 'seating'

    # Sleeping keywords
    if re.search(r'\b(bed|mattress|headboard)\b', desc):
        return 'sleeping'

    # Tables keywords
    if re.search(r'\b(table|desk|nightstand)\b', desc) and 'lamp' not in desc:
        return 'tables'

    # Storage keywords
    if any(kw in desc for kw in ['bookshelf', 'bookcase', 'storage', 'organizer', 'cabinet', 'tv stand', 'media console', 'shelving']):
        return 'storage'

    # Default to utility for everything else
    return 'utility'


def main():
    # Find processed.json relative to script location
    script_dir = Path(__file__).resolve().parent
    dataset_path = script_dir.parent / 'dataset' / 'processed.json'

    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found")
        return

    # Load data
    with open(dataset_path) as f:
        data = json.load(f)

    print(f"Loaded {len(data)} items from {dataset_path}")

    # Show current distribution
    old_cats = {}
    for item in data:
        cat = item['category']
        old_cats[cat] = old_cats.get(cat, 0) + 1

    print("\nCurrent category distribution:")
    for cat, count in sorted(old_cats.items()):
        print(f"  {cat}: {count}")

    # Re-categorize all items
    for item in data:
        item['category'] = categorize_by_description(item)

    # Show new distribution
    new_cats = {}
    for item in data:
        cat = item['category']
        new_cats[cat] = new_cats.get(cat, 0) + 1

    print("\nNew category distribution:")
    for cat, count in sorted(new_cats.items()):
        print(f"  {cat}: {count}")

    # Save updated file
    with open(dataset_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {dataset_path}")


if __name__ == '__main__':
    main()
