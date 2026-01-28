"""Mock data for API testing and development."""

MOCK_SELECTED_ASSETS = [
    {"uid": "sofa_16", "description": "A classic living room staple, this Chase sofa brings contemporary charm and comfort to any living space.", "category": "Furniture", "width": 2.74, "depth": 0.76, "height": 0.91, "materials": ["Wood", "Foam", "Polyester"], "path": "dataset/blobs/sofa_16/sofa.glb", "price": 325, "asset_color": "dark grey", "asset_style": "modern", "asset_shape": "rectangular"},
    {"uid": "coffee_table_30", "description": "JOINICE Round Coffee Table with Storage and Sliding Door, Mid Century Modern Wooden Center Table, for Living Room, Walnut", "category": "coffee_tables", "width": 0.8, "depth": 0.8, "height": 0.5, "materials": ["wood"], "path": "dataset/blobs/coffee_table_30/coffee_table.glb", "price": 258, "asset_color": "light grey", "asset_style": "minimalist", "asset_shape": "round"},
    {"uid": "tv_stand_47", "description": "Update your entertainment experience with the Mainstays Parsons TV Stand for TVs up to 50\" wide.", "category": "tv_stands", "width": 1.157, "depth": 0.4, "height": 0.5, "materials": [], "path": "dataset/blobs/tv_stand_47/tv_stand.glb", "price": 338, "asset_color": "light grey", "asset_style": "minimalist", "asset_shape": "rectangular"},
    {"uid": "rug_8", "description": "Shaggy Area Rug for Bedroom Living Room", "category": "Rug", "width": 1.524, "depth": 2.4384, "height": 0.0381, "materials": ["polyester fiber"], "path": "dataset/blobs/rug_8/rug.glb", "price": 190, "asset_color": "grey", "asset_style": "minimalist", "asset_shape": "rectangular"},
    {"uid": "floor_lamps_1", "description": "Modern Design: This 62-inch tall floor lamp features a contemporary mid-century modern style with a sleek matte black finish.", "category": "Lighting", "width": 0.381, "depth": 0.254, "height": 1.5748, "materials": [], "path": "dataset/blobs/floor_lamps_1/floor_lamps.glb", "price": 141, "asset_color": "grey", "asset_style": "minimalist", "asset_shape": "rectangular"},
    {"uid": "book_shelves_38", "description": "Better Homes & Gardens 8-Cube Storage Organizer with eight compartments for displaying books and collectibles.", "category": "bookshelves", "width": 0.7658, "depth": 0.39, "height": 1.444, "materials": ["MDF", "particle board", "paperboard", "iron"], "path": "dataset/blobs/book_shelves_38/book_shelves.glb", "price": 190, "asset_color": "light gray", "asset_style": "minimalist", "asset_shape": "rectangular"},
    {"uid": "accent_chair_12", "description": "Bezseller Modern Accent Chair, Upholstered Armchair for Living Room, Bedroom, Office, Beige", "category": "Furniture", "width": 0.775, "depth": 0.762, "height": 0.829, "materials": ["Terry fabric", "Wood", "Sponge", "Chenille"], "path": "dataset/blobs/accent_chair_12/accent_chair.glb", "price": 231, "asset_color": "light gray", "asset_style": "modern", "asset_shape": "rectangular"},
    {"uid": "side_tables_100", "description": "Mainstays Parsons End Table with black oak woodgrain finish.", "category": "side_tables", "width": 0.508, "depth": 0.508, "height": 0.4445, "materials": ["PVC laminated hollow core"], "path": "dataset/blobs/side_tables_100/side_tables.glb", "price": 275, "asset_color": "charcoal grey", "asset_style": "minimalist", "asset_shape": "rectangular"},
]

MOCK_INITIAL_LAYOUT = {
    "rug_8": {"category": "Rug", "position": [1.85, 2.74, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "sofa_16": {"category": "Furniture", "position": [1.85, 4.1, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "tv_stand_47": {"category": "tv_stands", "position": [1.85, 0.6, 0.0], "rotation": [0.0, 0.0, 3.141592653589793]},
    "coffee_table_30": {"category": "coffee_tables", "position": [1.85, 2.5, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "accent_chair_12": {"category": "Furniture", "position": [0.6, 2.5, 0.0], "rotation": [0.0, 0.0, 1.5707963267948966]},
    "side_tables_100": {"category": "side_tables", "position": [3.3, 4.1, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "book_shelves_38": {"category": "bookshelves", "position": [0.4, 0.6, 0.0], "rotation": [0.0, 0.0, 3.141592653589793]},
    "floor_lamps_1": {"category": "Lighting", "position": [0.3, 4.1, 0.0], "rotation": [0.0, 0.0, 0.0]},
}

MOCK_REFINED_LAYOUT = {
    "rug_8": {"category": "Rug", "position": [1.85, 2.74, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "sofa_16": {"category": "Furniture", "position": [1.85, 4.1, 0.0], "rotation": [0, 0, 0.0]},
    "tv_stand_47": {"category": "tv_stands", "position": [1.85, 0.6, 0.0], "rotation": [0.0, 0.0, 3.141592653589793]},
    "coffee_table_30": {"category": "coffee_tables", "position": [1.85, 2.5, 0.0], "rotation": [0.0, 0.0, 0.0]},
    "accent_chair_12": {"category": "Furniture", "position": [0.6, 2.5, 0.0], "rotation": [0.0, 0.0, 1.5707963267948966]},
    "side_tables_100": {"category": "side_tables", "position": [3.45, 4.1, 0.0], "rotation": [0, 0, 0.0]},
    "book_shelves_38": {"category": "bookshelves", "position": [0.4, 0.6, 0.0], "rotation": [0.0, 0.0, 3.141592653589793]},
    "floor_lamps_1": {"category": "Lighting", "position": [0.25, 4.1, 0.0], "rotation": [0, 0, 0.0]},
}

MOCK_ROOM_GEOMETRY = {
    "room_area": (3.71, 5.49),
    "room_vertices": [[3.71, 0.0], [3.71, 5.49], [0.0, 5.49], [0.0, 0.0]],
    "room_doors": [{"center": [0.0, 5.01], "width": 0.82}],
    "room_windows": [
        {"center": [3.80, 4.83], "width": 0.08, "depth": 1.06},
        {"center": [1.80, 0.0], "width": 1.58, "depth": 0.08},
    ],
    "room_voids": [],
}

MOCK_CONSTRAINT_PROGRAM = """# Orientation and Basic Placement
solver.against_wall(sofa_16, walls[2])
solver.against_wall(tv_stand_47, walls[0])
solver.against_wall(book_shelves_38, walls[0])
solver.point_towards(sofa_16, tv_stand_47)
solver.align_with(tv_stand_47, walls[0], angle=180)

# Center furniture grouping
solver.distance_constraint(rug_8, sofa_16, 0.0, 0.5)
solver.on_top_of(coffee_table_30, rug_8)
solver.distance_constraint(sofa_16, coffee_table_30, 0.35, 0.55)

# Fix Overlaps and side placement
solver.distance_constraint(sofa_16, side_tables_100, 0.0, 0.1)
solver.distance_constraint(sofa_16, floor_lamps_1, 0.0, 0.1)

# Conversation area
solver.point_towards(accent_chair_12, coffee_table_30)
solver.distance_constraint(accent_chair_12, rug_8, 0.1, 0.6)

# Clearances
solver.distance_constraint(void_door_0, rug_8, 0.5, 5.0, weight=10)
solver.distance_constraint(void_door_0, sofa_16, 0.5, 5.0, weight=10)
solver.distance_constraint(void_door_0, floor_lamps_1, 0.5, 5.0, weight=10)
"""
