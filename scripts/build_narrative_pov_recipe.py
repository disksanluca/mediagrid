"""Build the original eight-scene declarative webtoon/cutout M4 recipe."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.motion_contracts.models import MotionRecipe  # noqa: E402
from apps.api.motion_contracts.registry import REGISTRY_ROOT, recipe_digest  # noqa: E402

RECIPE_ID = "pov.webtoon-cutout"
VERSION = "1.3.0"
OUTPUT = REGISTRY_ROOT / f"{RECIPE_ID}.{VERSION}.json"
INDEX = REGISTRY_ROOT / "index.json"
DURATION = 7000


def color(index):
    return {"kind": "dna_palette", "index": index}


def key(at_ms, value, easing="cubic_in_out"):
    return {"time": {"kind": "ms", "at_ms": at_ms}, "value": value, "easing": easing}


def animation(prop, start, end, *, at=0, until=DURATION):
    return {"property": prop, "keyframes": [key(at, start), key(until, end)]}


def group(identifier, position, *, parent=None, scale=None, animations=None, z=0):
    result = {
        "id": identifier, "type": "group", "position": position,
        "parent_id": parent, "z_index": z,
    }
    if scale:
        result["scale"] = scale
    if animations:
        result["animations"] = animations
    return result


def shape(identifier, position, width, height, fill, *, parent=None, kind="rect",
          stroke=None, stroke_width=1, points=None, opacity=1, animations=None, z=0,
          gradient=None, glow=0):
    geometry = {"kind": kind, "width": width, "height": height}
    if points is not None:
        geometry = {"kind": kind, "points": points}
    params = {"geometry": geometry}
    if fill is not None:
        params["fill"] = color(fill)
    if stroke is not None:
        params["stroke"] = color(stroke)
        params["stroke_width"] = stroke_width
    if gradient:
        params["fill_gradient"] = {
            "kind": "linear", "start": [0, 0], "end": [1, 1],
            "stops": [{"offset": stop, "color": color(value)}
                      for stop, value in gradient],
        }
    if glow:
        params["glow"] = glow
    node = {
        "id": identifier, "type": "shape", "position": position,
        "parent_id": parent, "params": params, "opacity": opacity, "z_index": z,
    }
    if animations:
        node["animations"] = animations
    return node


def text(identifier, position, *, literal=None, shot=False, size=74, width=900,
         fill=1, font=0, align="left", parent=None, animations=None, z=0):
    binding = (
        {"kind": "shot_field", "field": "on_screen_text"}
        if shot else {"kind": "literal", "value": literal}
    )
    result = {
        "id": identifier, "type": "text", "position": position,
        "parent_id": parent, "z_index": z,
        "params": {
            "text": binding, "font": {"kind": "dna_font", "index": font},
            "fill": color(fill), "size": size, "max_width": width,
            "line_height": 1.05, "max_lines": 3, "align": align,
            "method": "fade_slide",
        },
        "animations": animations or [
            {"property": "opacity", "keyframes": [
                key(0, 0, "linear"), key(420, 1, "cubic_out"),
                key(DURATION-380, 1, "linear"), key(DURATION, 0, "cubic_in_out"),
            ]},
        ],
    }
    return result


def character(prefix, x, y, scale, *, mood, pose, mirror=False):
    # Mirroring is expressed through pose/placement; M4 scale intentionally forbids
    # negative values so recipes cannot invert coordinate systems.
    sx = scale
    nodes = [
        group(prefix, [x, y, 90], scale=[sx, scale],
              animations=[animation("position", [x, y+10, 90], [x, y-8, 140])]),
        shape(prefix+"-shadow", [45, 575, 0], 250, 55, 0, parent=prefix, kind="ellipse",
              opacity=.22),
        shape(prefix+"-leg-back", [78, 485, 8], 78, 235, 6, parent=prefix,
              animations=[animation("rotate_z", -2, 3)]),
        shape(prefix+"-leg-front", [178, 485, 12], 78, 235, 6, parent=prefix,
              animations=[animation("rotate_z", 2, -3)]),
        shape(prefix+"-shoe-back", [56, 676, 16], 120, 48, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-shoe-front", [166, 676, 18], 120, 48, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-torso", [48, 275, 24], 246, 270, 2, parent=prefix,
              gradient=[(0, 2), (1, 5)]),
        shape(prefix+"-hood", [75, 250, 30], 190, 110, 2, parent=prefix, kind="ellipse",
              stroke=0, stroke_width=8),
        shape(prefix+"-neck", [132, 220, 34], 76, 80, 7, parent=prefix),
        shape(prefix+"-head", [77, 55, 38], 186, 210, 7, parent=prefix, kind="ellipse",
              gradient=[(0, 7), (1, 2)]),
        shape(prefix+"-ear", [62, 132, 36], 35, 58, 7, parent=prefix, kind="ellipse"),
        shape(prefix+"-hair", [72, 38, 46], 198, 105, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-curl-1", [72, 78, 48], 66, 75, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-curl-2", [124, 64, 49], 70, 70, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-curl-3", [180, 67, 49], 72, 68, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-eye-left", [117, 148, 52], 16, 20, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-eye-right", [198, 148, 52], 16, 20, 0, parent=prefix, kind="ellipse"),
        shape(prefix+"-nose", [165, 164, 54], 8, 24, 4, parent=prefix),
    ]
    mouth_points = {
        "curious": [[0, 8], [18, 2], [36, 8]],
        "worried": [[0, 2], [18, 10], [36, 2]],
        "frustrated": [[0, 8], [18, 1], [36, 8]],
        "focused": [[0, 5], [36, 5]],
        "confident": [[0, 2], [18, 12], [36, 2]],
    }[mood]
    nodes.append(shape(prefix+"-mouth", [150, 207, 54], 0, 0, None, parent=prefix,
                       kind="polyline", points=mouth_points, stroke=0, stroke_width=6))
    left_angle, right_angle = {
        "browse": (-18, 22), "hold": (-48, 45), "inspect": (-72, 72),
        "argue": (-25, -64), "learn": (-15, 40), "celebrate": (-55, 55),
    }[pose]
    for side, base_x, angle in (("left", 28, left_angle), ("right", 264, right_angle)):
        arm = prefix+"-arm-"+side
        nodes.extend([
            group(arm, [base_x, 295, 28], parent=prefix,
                  animations=[animation("rotate_z", angle-4, angle+4)]),
            shape(arm+"-sleeve", [0, 0, 0], 64, 220, 2, parent=arm),
            shape(arm+"-hand", [7, 194, 5], 50, 70, 7, parent=arm, kind="ellipse"),
        ])
    return nodes


def bedroom(prefix, *, rainy=False):
    nodes = [
        shape(prefix+"-wall", [0, 0, 850], 1080, 1920, 6,
              gradient=[(0, 6), (1, 0)]),
        shape(prefix+"-window", [590, 190, 650], 360, 600, 0, stroke=3, stroke_width=18),
        shape(prefix+"-sky", [614, 218, 660], 312, 544, 5),
        shape(prefix+"-moon", [780, 270, 670], 90, 90, 1, kind="ellipse", opacity=.72),
        shape(prefix+"-desk", [540, 1190, 280], 500, 70, 0),
        shape(prefix+"-desk-leg", [880, 1250, 260], 54, 520, 0),
        shape(prefix+"-bed", [-80, 1380, 210], 680, 340, 5),
        shape(prefix+"-blanket", [-40, 1450, 180], 600, 220, 3,
              gradient=[(0, 3), (1, 5)]),
        shape(prefix+"-lamp", [710, 930, 300], 150, 150, 2, kind="ellipse", glow=12),
        shape(prefix+"-rug", [160, 1710, 70], 760, 160, 5, kind="ellipse", opacity=.45),
    ]
    if rainy:
        for index, x in enumerate((640, 700, 760, 820, 880)):
            nodes.append(shape(prefix+f"-rain-{index}", [x, 260, 680], 0, 0, None,
                               kind="polyline", points=[[0, 0], [-35, 180]],
                               stroke=3, stroke_width=7, opacity=.7,
                               animations=[animation("position", [x, 240, 680],
                                                     [x-80, 590, 680])]))
    return nodes


def bus():
    nodes = [
        shape("bus-sky", [0, 0, 900], 1080, 1920, 3,
              gradient=[(0, 3), (1, 5)]),
        group("city", [0, 0, 700],
              animations=[animation("position", [0, 0, 700], [-300, 0, 700])]),
    ]
    for i, (x, h) in enumerate(((0, 620), (210, 850), (450, 700), (690, 930), (900, 760))):
        nodes.append(shape(f"building-{i}", [x, 720-h/2, 0], 170, h, 6, parent="city"))
    nodes += [
        shape("bus-window", [70, 160, 380], 940, 980, None, stroke=0, stroke_width=36),
        shape("bus-bar", [120, 1180, 180], 840, 42, 2),
        shape("seat", [-100, 1370, 100], 1280, 620, 5,
              gradient=[(0, 5), (1, 0)]),
    ]
    return nodes


def cafe(prefix="cafe"):
    return [
        shape(prefix+"-wall", [0, 0, 900], 1080, 1920, 1,
              gradient=[(0, 1), (1, 7)]),
        shape(prefix+"-window", [90, 180, 650], 420, 630, 0, stroke=2, stroke_width=18),
        shape(prefix+"-outside", [112, 202, 670], 376, 586, 3),
        shape(prefix+"-awning", [610, 170, 620], 350, 110, 4),
        shape(prefix+"-menu", [650, 350, 610], 270, 390, 0, stroke=1, stroke_width=10),
        shape(prefix+"-table", [120, 1160, 170], 840, 110, 0),
        shape(prefix+"-table-leg", [495, 1260, 160], 90, 500, 0),
        shape(prefix+"-cup", [730, 1030, 210], 145, 150, 2),
        shape(prefix+"-coffee", [742, 1010, 220], 120, 45, 0, kind="ellipse"),
        shape(prefix+"-light", [430, 40, 500], 220, 220, 2, kind="ellipse", glow=14,
              opacity=.8),
    ]


def repair_shop():
    nodes = [
        shape("shop-wall", [0, 0, 900], 1080, 1920, 6,
              gradient=[(0, 6), (1, 0)]),
        shape("pegboard", [100, 180, 650], 880, 680, 5, stroke=3, stroke_width=14),
        shape("counter", [-40, 1210, 140], 1160, 240, 0),
        shape("counter-edge", [-40, 1190, 150], 1160, 45, 2),
        shape("shelf", [110, 520, 670], 850, 35, 1),
    ]
    for index, x in enumerate((180, 350, 520, 690, 850)):
        nodes.append(shape(f"tool-{index}", [x, 280+(index%2)*90, 680], 32, 170, 3,
                           animations=[animation("rotate_z", -4, 4)]))
    return nodes


def phone(prefix, x, y, scale=1.0, *, parent=None, alert=False, messages=False):
    root = prefix+"-phone"
    nodes = [
        group(root, [x, y, 40], parent=parent, scale=[scale, scale],
              animations=[animation(
                  "scale", [round(scale*.96, 6), round(scale*.96, 6)], [scale, scale]
              )]),
        shape(root+"-body", [0, 0, 0], 320, 610, 0, parent=root),
        shape(root+"-screen", [18, 28, 8], 284, 530, 1, parent=root,
              gradient=[(0, 1), (1, 3)]),
        shape(root+"-camera", [138, 12, 12], 45, 14, 6, parent=root, kind="ellipse"),
        shape(root+"-home", [132, 572, 12], 55, 18, 6, parent=root, kind="ellipse"),
    ]
    if messages:
        nodes += [
            shape(root+"-bubble-a", [42, 95, 16], 205, 92, 3, parent=root),
            shape(root+"-bubble-b", [70, 220, 17], 190, 105, 5, parent=root),
            shape(root+"-bubble-c", [42, 365, 18], 220, 92, 3, parent=root,
                  animations=[animation("opacity", 0, 1, at=2500, until=3300)]),
        ]
    if alert:
        nodes += [
            shape(root+"-alert", [48, 180, 20], 220, 170, 4, parent=root,
                  animations=[animation("scale", [.82, .82], [1.06, 1.06],
                                        at=1200, until=2600)]),
            shape(root+"-warning", [141, 215, 24], 34, 76, 1, parent=root),
            shape(root+"-warning-dot", [141, 305, 24], 34, 34, 1,
                  parent=root, kind="ellipse"),
        ]
    return nodes


def labels(scene_index, chapter):
    return [
        text(f"chapter-{scene_index}", [72, 92, 20], literal=chapter, size=34,
             width=700, fill=3, font=1),
        text(f"title-{scene_index}", [72, 1420, 24], shot=True, size=82,
             width=900, fill=1),
        shape(f"progress-{scene_index}", [72, 1760, 20], 936, 8, 3),
        shape(f"progress-fill-{scene_index}", [72, 1760, 22],
              117*(scene_index+1), 8, 2),
    ]


def scene(index):
    nodes = []
    chapter = (
        "01 · O ACHADO", "02 · A PRESSA", "03 · O ENCONTRO", "04 · O DEFEITO",
        "05 · A CONSEQUÊNCIA", "06 · A CONVERSA", "07 · A CHECAGEM",
        "08 · A LIÇÃO",
    )[index]
    camera = {"position": [0, 0, -80], "rotate_z": 0.0, "focal_length": 1500.0}
    if index == 0:
        nodes += bedroom("intro")
        nodes += character("caio", 210, 730, .9, mood="curious", pose="browse")
        nodes += phone("listing", 640, 720, .82, messages=True)
        nodes += [shape("listing-price", [675, 810, 68], 250, 75, 2)]
        camera["animations"] = [animation("position", [-50, 20, -120], [35, -25, 70])]
    elif index == 1:
        nodes += bus()
        nodes += character("caio", 360, 660, 1.02, mood="curious", pose="hold")
        nodes += phone("chat", 110, 870, .62, messages=True)
        nodes += [text("bus-status", [690, 360, 30], literal="ENCONTRO\nEM 10 MIN", size=46,
                       width=300, fill=1, align="center")]
        camera["animations"] = [animation("position", [70, 0, -80], [-50, -20, 40])]
    elif index == 2:
        nodes += cafe()
        nodes += character("caio", 95, 680, .84, mood="focused", pose="hold")
        nodes += character("seller", 700, 690, .82, mood="confident", pose="hold", mirror=True)
        nodes += phone("deal", 430, 980, .52)
        nodes += [shape("handshake", [410, 1120, 90], 260, 95, 7, kind="ellipse")]
        camera["animations"] = [animation("position", [-70, 0, -50], [35, -35, 100])]
    elif index == 3:
        nodes += [
            shape("inspection-bg", [0, 0, 850], 1080, 1920, 6,
                  gradient=[(0, 6), (1, 0)]),
            shape("hand-left", [-120, 940, 80], 470, 660, 7, kind="ellipse",
                  animations=[animation("rotate_z", -8, 4)]),
            shape("hand-right", [750, 930, 82], 470, 660, 7, kind="ellipse",
                  animations=[animation("rotate_z", 8, -4)]),
        ]
        nodes += phone("inspect", 255, 330, 1.78, alert=True)
        nodes += [
            shape("crack", [410, 620, 100], 0, 0, None, kind="polyline",
                  points=[[0, 0], [90, 130], [40, 270], [170, 430], [120, 600]],
                  stroke=4, stroke_width=12,
                  animations=[animation("draw_progress", 0, 1, at=1700, until=3500)]),
            text("diagnostic", [90, 1170, 110], literal="TOQUE FALHANDO\nBATERIA INSTÁVEL",
                 size=48, width=900, fill=4, align="center"),
        ]
        camera["animations"] = [animation("position", [0, 80, -100], [0, -60, 140])]
    elif index == 4:
        nodes += bedroom("after", rainy=True)
        nodes += character("caio", 320, 720, 1.08, mood="frustrated", pose="inspect")
        nodes += phone("broken", 655, 920, .66, alert=True)
        nodes += [text("thought", [610, 520, 60], literal="EU DEVIA\nTER TESTADO", size=50,
                       width=380, fill=4, align="center")]
        camera["animations"] = [animation("position", [80, -20, -60], [-20, 25, 110])]
    elif index == 5:
        nodes += [
            shape("split-left", [0, 0, 850], 540, 1920, 6),
            shape("split-right", [540, 0, 850], 540, 1920, 5),
            shape("divider", [532, 0, 100], 16, 1920, 2),
        ]
        nodes += character("caio", 70, 740, .9, mood="focused", pose="argue")
        nodes += phone("negotiation", 610, 450, 1.12, messages=True)
        nodes += [
            shape("photo-proof-a", [620, 1160, 60], 180, 220, 1, stroke=3, stroke_width=8,
                  animations=[animation("position", [620, 1300, 60], [620, 1160, 90])]),
            shape("photo-proof-b", [825, 1110, 62], 180, 220, 1, stroke=3, stroke_width=8,
                  animations=[animation("position", [825, 1300, 62], [825, 1110, 92])]),
            text("message-status", [600, 300, 80], literal="FATOS, NÃO BRIGA", size=43,
                 width=410, fill=1, align="center"),
        ]
        camera["animations"] = [animation("position", [-30, 0, -60], [30, -15, 60])]
    elif index == 6:
        nodes += repair_shop()
        nodes += character("caio", 80, 710, .86, mood="focused", pose="learn")
        nodes += character("tech", 690, 650, .86, mood="confident", pose="inspect", mirror=True)
        nodes += phone("tested", 405, 940, .65)
        nodes += [
            shape("check-card", [560, 870, 90], 390, 330, 1, stroke=3, stroke_width=10),
            shape("check-one", [610, 930, 100], 35, 35, 3, kind="ellipse"),
            shape("check-two", [610, 1010, 100], 35, 35, 3, kind="ellipse"),
            shape("check-three", [610, 1090, 100], 35, 35, 3, kind="ellipse"),
            text("check-label", [665, 920, 104], literal="TELA\nBATERIA\nCÂMERAS",
                 size=36, width=240, fill=0),
        ]
        camera["animations"] = [animation("position", [-40, 20, -80], [50, -30, 100])]
    else:
        nodes += [
            shape("final-bg", [0, 0, 900], 1080, 1920, 0,
                  gradient=[(0, 0), (1, 5)]),
            shape("halo", [240, 360, 300], 600, 600, 3, kind="ellipse", glow=16,
                  opacity=.32, animations=[animation("scale", [.8, .8], [1.2, 1.2])]),
        ]
        nodes += character("caio", 360, 620, 1.05, mood="confident", pose="celebrate")
        nodes += phone("final", 100, 920, .65)
        for i, (label, y) in enumerate((("TESTE", 460), ("REGISTRE", 580), ("NEGOCIE", 700))):
            nodes += [
                shape(f"rule-dot-{i}", [720, y, 80], 44, 44, 3, kind="ellipse",
                      animations=[animation("opacity", 0, 1, at=500+i*600,
                                            until=1100+i*600)]),
                text(f"rule-{i}", [790, y-8, 82], literal=label, size=42, width=230,
                     fill=1, animations=[animation("opacity", 0, 1, at=500+i*600,
                                                   until=1100+i*600)]),
            ]
        camera["animations"] = [animation("position", [0, 40, -100], [0, -45, 140])]
    nodes += labels(index, chapter)
    return {
        "shot_slot": f"shot-{index+1}",
        "required_duration_ms": DURATION,
        "graph": {
            "schema_version": "motion_scene_v1",
            "safe_area": {"left": 72, "right": 72, "top": 80, "bottom": 120},
            "camera": camera,
            "nodes": nodes,
            "cues": [{
                "id": "mix", "at_ms": 0,
                "sound": {
                    "asset_binding": "mix", "source_in_ms": index*DURATION,
                    "duration_ms": DURATION, "gain": 1.0,
                    "fade_in_ms": 80, "fade_out_ms": 80,
                },
            }],
        },
    }


def main():
    data = {
        "schema_version": "motion_recipe_v1", "id": RECIPE_ID,
        "version": VERSION, "sha256": "0"*64,
        "canvas": {"width": 1080, "height": 1920, "fps_num": 30, "fps_den": 1},
        "asset_slots": {"mix": "audio"},
        "scenes": [scene(index) for index in range(8)],
    }
    recipe = MotionRecipe.model_validate(data)
    data = recipe.model_dump(mode="json")
    data["sha256"] = recipe_digest(recipe)
    MotionRecipe.model_validate(data)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index["recipes"] = [
        item for item in index["recipes"]
        if (item["id"], item["version"]) != (RECIPE_ID, VERSION)
    ]
    index["recipes"].append(
        {"id": RECIPE_ID, "version": VERSION, "sha256": data["sha256"]}
    )
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Registered {RECIPE_ID}@{VERSION}: {data['sha256']}")


if __name__ == "__main__":
    main()
