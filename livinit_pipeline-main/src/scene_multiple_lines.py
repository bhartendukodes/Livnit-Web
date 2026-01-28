import base64
import json
import mimetypes
import os
import random
import re
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, validator
from supabase import Client, create_client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

openai_client = OpenAI(api_key=OPENAI_API_KEY)


def llm(system: str, user: str, temp: float = 0.5) -> str:
    """Send system+user prompt to OpenAI and return plain text."""
    try:
        print(f"\n[LLM] Model: {OPENAI_MODEL}")
        print(f"[LLM] Temperature: {temp}")
        print(f"[LLM] System prompt (first 200 chars): {system[:200]}")
        print(f"[LLM] User prompt (first 400 chars): {user[:400]}...\n")

        r = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temp,
        )

        response_text = r.choices[0].message.content.strip()
        print("[LLM] Raw Response (first 400 chars):", response_text[:400], "...\n")
        return response_text

    except Exception as e:
        print("[LLM] Error during API call:", e)
        return ""




def encode_image_as_data_url(path: str) -> str:
    """Convert local image to base64 data:image/... URL."""
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        mime = "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def download_url_as_data_url(url: str) -> str:
    """Download remote image and return as data:image/... URL."""
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    mime = r.headers.get("Content-Type", "image/jpeg")
    b64 = base64.b64encode(r.content).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_task_and_criteria(
    user_prompt,
    cats,
    void_assets_dict,
    rect_vertices,
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:

    content_blocks = []

    # Find the room dimensions and longer walls from rect_vertices
    rect = np.array(rect_vertices)

    def distance(p1, p2):
        return np.linalg.norm(p1 - p2)

    wall_lengths = [distance(rect[i], rect[(i + 1) % 4]) for i in range(4)]
    length = max(wall_lengths)
    width = min(wall_lengths)
    room_dimensions = {"length": length, "width": width}
    longest_wall_idx = wall_lengths.index(length)
    shortest_wall_idx = wall_lengths.index(width)
    # ----------------------------------------------------
    # ADD IMAGE (ONLY CHANGE)
    # ----------------------------------------------------
    if image_path:
        try:
            data_url = encode_image_as_data_url(image_path)
            content_blocks.append({"type": "image_url", "image_url": {"url": data_url}})
        except Exception as e:
            print("[IMAGE ERROR] Could not read local image:", e)

    if image_url:
        try:
            data_url = download_url_as_data_url(image_url)
            content_blocks.append({"type": "image_url", "image_url": {"url": data_url}})
        except Exception as e:
            print("[IMAGE ERROR] Could not download remote image:", e)

    # ----------------------------------------------------
    # YOUR EXACT PROMPT (UNCHANGED)
    # ----------------------------------------------------
    user_msg = f"""{user_prompt}

Selected Asset:
{", ".join(cats)}

And positioning void assets:
{", ".join(void_assets_dict)}

Your task:
You are an expert of interior design and spatial-planning assistant for a 3D interior layout system.
create layout criteria with all the assets provided in the Selected Asset list.
Refer all the needed information about the interior design and spacial planning of the assets.

IMPORTANT (Image Instruction):
- If an image is provided above, treat it as an example reference of a living room.
- Study the spacing, distances, openness, walking paths, furniture proportions, and arrangement style.
- Use the image ONLY as inspiration — DO NOT replicate it exactly.
- Adapt the spacing, flow, and natural placement style to the room dimensions given by the floor rectangle vertices.

Use the following floor rectangle vertices for finding of room dimensions and create task description based on the room dimensions:
- Rectangle Vertices: {rect_vertices}
- Room Dimensions: Length = {room_dimensions['length']:.2f} meters, Width = {room_dimensions['width']:.2f} meters.
- The longest wall is wall[{longest_wall_idx}] with positions {rect[longest_wall_idx].tolist()} to {rect[(longest_wall_idx + 1) % 4].tolist()}.
- The shortest wall is wall[{shortest_wall_idx}] with positions {rect[shortest_wall_idx].tolist()} to {rect[(shortest_wall_idx + 1) % 4].tolist()}.

Layout criteria steps:
- Only use the assets provided in the Selected Asset list.
- Leave enough space for walking between all furniture pieces and around the room at least 0.1 meters.
- Avoid any overlap or collision between furniture and void spaces.

Assets placement should be done as per the layout criteria mentioned above to create a natural and open living room setup. Important notes for placement:
- Use the rectangle vertices provided to determine room layout and positioning void assets to avoid blocking them.
- Center room floor vertices at origin (0,0) for position calculations. All positions to be in meters.
- The position of wall[0] from {rect[0].tolist()} to {rect[(0 + 1) % 4].tolist()} is aligned along +x axis. Thus, wall[1] is +y axis, wall[2] is -x axis, wall[3] is -y axis.
- The rotation must be in degrees. If the object faces +x axis, rotation is [0, 0, 180], else [0, 0, 0]. If it faces +y axis, rotation is [0, 0, 270], else [0, 0, 90].
- All assets shouldn't overlap or collide with any void spaces (void-0, void_door-1) by at least 0.3 meters.
- Asset must be placed focus in the center and within the floor vertices.
- Asset MUST be straight (same axis-x or axis-y as per layout criteria) and not rotated at any odd angles.
- A zero degree rotation implies that the object faces +x axis. ([0, 0, 90] means that the object faces +y axis (counterclockwise rotation of 90 degrees).

OUTPUT of a layout:
{{{{
    "task_description": "User request: {user_prompt}. Arrange a simple living room about 4x6 meters with a couch, accent chairs, rug, two floor lamp, tv stand, and tv. The setup should look natural, open, and easy to move around in.",
    "layout_criteria": [
        'Place the sofa centered along the longer wall, facing the center of the room.',
        'Position the TV on top of the TV stand. TV and TV stand MUST be directly opposite the sofa (with same rotation), both facing and aligned with it.',
        'Place the coffee table in front of the sofa, centered and aligned with it. Ensure it is on top of the rug.',
        'Position the first accent chair to the right of the sofa, angled towards the coffee table.',
        'Place the second accent chair to the left of the sofa, also angled towards the coffee table.',
        'Position the storage unit along one of the shorter walls, ensuring it does not block any pathways.',
        'Ensure there is at least 0.1 meters of walking space between all furniture pieces and around the room.',
        'Ensure avoid any overlap or collision between furniture and void spaces at least 0.3 meters. (void_0, void_door-1)'
    ],
    "asset_placements": {{
        "sofa-0": [{{"position": [1.0, 0.5, 180.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
        "tv_stand-0": [{{"position": [-1.0, 0.5, 0.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
        "tv-0": [{{"position": [-1.0, 0.5, 1.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
        "coffee_table-0": [{{"position": [1.0, 1.0, 0.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
        "rug-0": [{{"position": [1.0, 1.0, 0.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
        "accent_chair-0": [{{"position": [0.5, 1.5, 0.0], "rotation": [0.0, 0.0, 90], "optimize": 1}}],
        "accent_chair-1": [{{"position": [0.5, 1.5, 0.0], "rotation": [0.0, 0.0, -90], "optimize": 1}}],
        "storage_unit-0": [{{"position": [-1.5, 1.5, 0.0], "rotation": [0.0, 0.0, 90.0], "optimize": 1}}],
        "floor_lamp-0": [{{"position": [-1.0, 0.5, 0.0], "rotation": [0.0, 0.0, 0.0], "optimize": 1}}],
    }}
}}}}

Output Format:
- Keep name of assets (asset-0) same as provided in the Selected Asset list in assets_placement.
- If there is multiple assets then reference it properly as <asset name>-0 and <asset_name>-1.
- Make such all the assets are placed inside the floor vertices.
- Do not miss out any assets placemets and explain each of the assets placement properly without any ambiguity in their description.
- Keep the task description and layout criteria concise and to the point.
- Make sure you give the layout criteria for all the assets properly and dont not miss any asset
- Do not give the same layout criteria and task description from the example provided.
- All the values to be in meters.
- Make the layout criteria as humanly natural as possible and in simple english.
- Mention ONLY categories listed above — do not invent new items and change names.
- Do NOT put arguments and ONLY put variable in the code block.
- Output ONLY the JSON — no commentary, markdown, or code fences.
"""

    # ADD TEXT TO THE CONTENT BLOCKS LAST
    content_blocks.append({"type": "text", "text": user_msg})

    # ----------------------------------------------------
    # GPT-4o MULTIMODAL CALL (correct endpoint)
    # ----------------------------------------------------
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",  # MUST be a vision-capable model
            messages=[
                {"role": "system", "content": "You are an interior layout model."},
                {"role": "user", "content": content_blocks},
            ],
            temperature=0.3,
            top_p=0.2,
        )

        raw = resp.choices[0].message.content.strip()
        print("[GPT-4o multimodal] Raw output:", raw[:1000], "...\n")
        return json.loads(raw)

    except Exception as e:
        print("[GPT-4o multimodal] Error:", e)
        return {}
