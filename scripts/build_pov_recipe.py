"""Author an original six-scene POV recipe as M4 data, never runtime code."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.motion_contracts.models import MotionRecipe  # noqa: E402
from apps.api.motion_contracts.registry import recipe_digest  # noqa: E402

RECIPE_ID = "pov.first-sale"
VERSION = "1.2.0"
OUTPUT = ROOT / "contracts/motion/recipes" / f"{RECIPE_ID}.{VERSION}.json"
INDEX = OUTPUT.parent / "index.json"


def animation(property_name, first, last, end=4500):
    return {"property": property_name, "keyframes": [
        {"time": {"kind": "ms", "at_ms": 0}, "value": first, "easing": "cubic_in_out"},
        {"time": {"kind": "ms", "at_ms": end}, "value": last, "easing": "cubic_in_out"},
    ]}


def node(node_id, kind, position, *, parent=None, space="world", animations=None,
         params=None, opacity=1.0):
    value = {"id": node_id, "type": kind, "parent_id": parent, "space": space,
             "position": position, "scale": [1.0, 1.0], "rotate_z": 0.0,
             "opacity": opacity, "animations": animations or [], "z_index": 0,
             "anchor": [0.0, 0.0], "active_ms": None}
    if params is not None:
        value["params"] = params
    return value


def shape(node_id, position, width, height, color, *, parent=None,
          kind="rect", animations=None, space="world"):
    return node(node_id, "shape", position, parent=parent, space=space,
                animations=animations, params={
                    "geometry": {"kind": kind, "width": width, "height": height},
                    "fill": {"kind": "dna_palette", "index": color},
                })


def scene(index):
    signs = (1, -1, 1, -1, 1, -1)
    shift = signs[index] * 75
    nodes = [
        shape("background", [0.0, 0.0, 0.0], 1080, 1920, 0, space="screen"),
        shape("rule", [94.0, 150.0, 0.0], 112, 8, 2, space="screen"),
        node("heading", "text", [94.0, 260.0, 0.0], space="screen",
             animations=[animation("opacity", 0.0, 1.0, 650)], params={
                 "text": {"kind": "shot_field", "field": "on_screen_text"},
                 "font": {"kind": "dna_font", "index": 0},
                 "fill": {"kind": "dna_palette", "index": 1},
                 "size": 82.0, "max_width": 875.0, "line_height": 1.12,
                 "max_lines": 3, "align": "left", "method": "fade_slide",
             }),
        node("device", "group", [278.0, 730.0, 160.0],
             animations=[animation("position", [278.0+shift, 730.0, 120.0],
                                   [278.0-shift, 700.0, 240.0])]),
        shape("body", [0.0, 0.0, 0.0], 510, 810, 1, parent="device"),
        shape("display", [28.0, 32.0, 10.0], 454, 690, 0, parent="device"),
        shape("camera", [239.0, 754.0, 12.0], 32, 32, 2,
              parent="device", kind="ellipse"),
    ]
    if index == 0:  # Incoming listing, before the journey starts.
        nodes += [shape("alert", [84.0, 125.0, 20.0], 342, 128, 2, parent="device"),
                  shape("alert-line", [112.0, 168.0, 22.0], 255, 12, 0, parent="device")]
    elif index == 1:  # A table and cup beside the handset.
        nodes += [shape("table", [40.0, 1500.0, 10.0], 1000, 80, 2),
                  shape("cup", [50.0, 1150.0, 180.0], 230, 230, 1, kind="ellipse"),
                  shape("coffee", [82.0, 1182.0, 185.0], 166, 166, 0, kind="ellipse")]
    elif index == 2:  # Camera framing the item.
        nodes += [shape("viewfinder", [85.0, 115.0, 20.0], 330, 330, 2,
                        parent="device"),
                  shape("subject", [180.0, 195.0, 25.0], 140, 180, 1,
                        parent="device")]
    elif index == 3:  # Message response.
        nodes += [shape("reply", [78.0, 160.0, 20.0], 350, 160, 2,
                        parent="device"),
                  shape("reply-line", [106.0, 215.0, 22.0], 260, 14, 0,
                        parent="device")]
    elif index == 4:  # Close inspection of the used screen.
        nodes += [node("crack", "shape", [82.0, 80.0, 20.0], parent="device",
                       params={"geometry": {"kind": "polyline", "points": [
                           [10.0, 10.0], [120.0, 180.0], [80.0, 310.0],
                           [270.0, 470.0]]},
                           "stroke": {"kind": "dna_palette", "index": 2},
                           "stroke_width": 8.0})]
    else:  # Closing signal; still a fictional sale until editorial review.
        nodes += [shape("resolve-ring", [128.0, 195.0, 25.0], 250, 250, 2,
                        parent="device", kind="ellipse",
                        animations=[animation("opacity", 0.15, 1.0)]),
                  shape("resolve-dot", [221.0, 288.0, 28.0], 64, 64, 1,
                        parent="device", kind="ellipse")]
    return {"shot_slot": f"shot-{index+1}", "required_duration_ms": 5000,
            "graph": {"schema_version": "motion_scene_v1",
                      "safe_area": {"left": 72, "right": 72, "top": 120, "bottom": 180},
                      "camera": {"position": [0.0, 0.0, -80.0], "rotate_z": 0.0,
                                 "focal_length": 1500.0,
                                 "animations": [animation("position", [0.0, 0.0, -80.0],
                                                          [shift, -25.0, 50.0])]},
                      "nodes": nodes,
                      "cues": [{"id": "score", "at_ms": 0,
                                "sound": {"asset_binding": "score",
                                          "source_in_ms": index*5000,
                                          "duration_ms": 5000, "gain": 0.65,
                                          "fade_in_ms": 120, "fade_out_ms": 120}}]}}


def main():
    data = {"schema_version": "motion_recipe_v1", "id": RECIPE_ID,
            "version": VERSION, "sha256": "0" * 64,
            "canvas": {"width": 1080, "height": 1920, "fps_num": 30, "fps_den": 1},
            "asset_slots": {"score": "audio"},
            "scenes": [scene(index) for index in range(6)]}
    validated = MotionRecipe.model_validate(data)
    data = validated.model_dump(mode="json")
    data["sha256"] = recipe_digest(validated)
    MotionRecipe.model_validate(data)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index["recipes"] = [ref for ref in index["recipes"]
                        if (ref["id"], ref["version"]) != (RECIPE_ID, VERSION)]
    index["recipes"].append({"id": RECIPE_ID, "version": VERSION,
                             "sha256": data["sha256"]})
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Registered {RECIPE_ID}@{VERSION}: {data['sha256']}")


if __name__ == "__main__":
    main()
