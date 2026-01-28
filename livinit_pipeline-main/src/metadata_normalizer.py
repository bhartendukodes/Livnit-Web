import json
import os
import re


def normalize_uid(root_dir: str):
    """
    Walk through all data.json files under root_dir and:
    - Set 'annotations.uid' = folder name (e.g., 'sofa', 'accent_chair'), removing -1/_2 suffixes.
    - Remove escape sequences and normalize whitespace in 'annotations.description'.
    """

    def clean_description(desc: str) -> str:
        """Remove escape characters, normalize spaces, unify quotes."""
        if not desc:
            return ""
        desc = desc.replace("\r", " ").replace("\n", " ")
        desc = desc.replace("\\n", " ").replace("\\r", " ")
        desc = re.sub(r"\s+", " ", desc)
        desc = desc.replace('"', "'")
        desc = desc.encode("utf-8", "ignore").decode("utf-8")
        return desc.strip()

    for root, _, files in os.walk(root_dir):
        for fn in files:
            if fn == "data.json":
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"[ERROR] Cannot open {path}: {e}")
                    continue

                # Derive UID from folder name (strip trailing number suffix)
                folder_name = os.path.basename(os.path.dirname(path))
                uid_base = re.sub(r"[-_]\d+$", "", folder_name)

                # Ensure annotations section exists
                if "annotations" not in data:
                    data["annotations"] = {}

                # Clean description text if present
                if "description" in data["annotations"]:
                    data["annotations"]["description"] = clean_description(
                        data["annotations"]["description"]
                    )

                # Set UID inside annotations only
                data["annotations"]["uid"] = uid_base
                data["annotations"]["category"] = uid_base

                # Remove top-level uid if it exists
                if "uid" in data:
                    del data["uid"]

                # Save file
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print(f"[UPDATED] {path} → uid='{uid_base}' (description cleaned)")
                except Exception as e:
                    print(f"[ERROR] Failed to save {path}: {e}")

    print("[INFO] UID + description normalization complete.")




def convert_to_utf8(root_dir):
    for root, _, files in os.walk(root_dir):
        for fn in files:
            if fn.endswith(".json"):
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = f.read()
                except UnicodeDecodeError:
                    with open(path, "r", encoding="cp1252", errors="ignore") as f:
                        data = f.read()
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(data)
                    print(f"[FIXED] Converted to UTF-8 → {path}")
