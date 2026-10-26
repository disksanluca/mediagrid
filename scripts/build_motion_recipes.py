"""Original local recipe data for M4; all visual differences live in these graphs."""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.motion_contracts.models import MotionRecipe  # noqa: E402
from apps.api.motion_contracts.registry import REGISTRY_ROOT, recipe_digest  # noqa: E402

PRODUCTIONS = {
    "sports": {
        "id": "sports.depth-impact",
        "format": "vertical",
        "durations": [2000, 3000, 4000, 3000],
        "titles": ["ENTRE\nEM JOGO", "SINTA\nO CAMPO", "MUDE\nA ROTA", "É AGORA."],
        "palette": ["#101A21", "#F4F0E6", "#D7FF3F", "#29434A"],
    },
    "music": {
        "id": "music.orbital-sleeve",
        "format": "square",
        "durations": [4000, 6000],
        "titles": ["ÓRBITA\nSESSÃO 01", "OUÇA\nO MOVIMENTO"],
        "palette": ["#171426", "#F2E8FF", "#98EADA", "#A790F5"],
    },
    "geo": {
        "id": "geo.route-explainer",
        "format": "horizontal",
        "durations": [5000] * 3,
        "titles": [
            "ROTA AURORA\nGEOGRAFIA FICCIONAL",
            "SIGA O VALE\nMAPA SINTÉTICO",
            "CHEGADA AO NORTE\nESTUDO ORIGINAL",
        ],
        "palette": ["#0A1B27", "#F1E9CE", "#5ADBC5", "#314C60"],
    },
}


def color(i):
    return {"kind": "dna_palette", "index": i}


def animation(prop, times, values, easing="cubic_in_out"):
    return {
        "property": prop,
        "keyframes": [
            {"time": {"kind": "ms", "at_ms": t}, "value": v, "easing": easing}
            for t, v in zip(times, values, strict=True)
        ],
    }


def shape(id_, geometry, *, fill=None, stroke=None, **kwargs):
    return {
        "id": id_,
        "type": "shape",
        "params": {
            "geometry": geometry,
            "fill": color(fill) if fill is not None else None,
            "stroke": color(stroke) if stroke is not None else None,
            "stroke_width": 3,
        },
        **kwargs,
    }


def rect(w, h):
    return {"kind": "rect", "width": w, "height": h}


def ellipse(w, h):
    return {"kind": "ellipse", "width": w, "height": h}


def path(points, closed=False):
    return {
        "kind": "polygon" if closed else "polyline",
        "points": [[round(x, 3), round(y, 3)] for x, y in points],
    }


def text(id_, size, width, max_lines=3, **kwargs):
    return {
        "id": id_,
        "type": "text",
        "params": {
            "text": {"kind": "shot_field", "field": "on_screen_text"},
            "font": {"kind": "dna_font", "index": 0},
            "fill": color(1),
            "size": size,
            "max_width": width,
            "max_lines": max_lines,
            "line_height": 1.03,
        },
        **kwargs,
    }


def sports(index, duration):
    n = [
        shape(
            "field",
            rect(1160, 1700),
            stroke=3,
            position=[-40, 40, 550],
            rotate_z=-12,
            animations=[animation("position", [0, duration], [[-40, 40, 550], [100, -70, 500]])],
        ),
        shape(
            "center-circle",
            ellipse(650, 650),
            stroke=3,
            position=[200, 600, 450],
            animations=[animation("scale", [0, duration], [[1, 1], [1.15, 1.15]])],
        ),
        {
            "id": "atmosphere",
            "type": "particle",
            "position": [540, 960, 800],
            "params": {
                "seed": 84,
                "count": 18,
                "velocity": [-14, -34],
                "radius": 3,
                "fill": color(1),
            },
            "opacity": 0.35,
        },
    ]
    # Near/far planes move differently under the same camera.
    n += [
        shape(
            f"stripe-{j}",
            rect(65, 2300),
            fill=2,
            position=[-160 + j * 100, -120, -100],
            rotate_z=-25,
            opacity=0.12,
            animations=[
                animation(
                    "position",
                    [0, duration],
                    [[-160 + j * 100, -120, -100], [-350 + j * 100, -80, -100]],
                )
            ],
        )
        for j in range(3)
    ]
    ball_start = [[800, 1250, 400], [780, 850, 220], [260, 1050, 140], [720, 920, 100]][index]
    ball_end = [[780, 1050, 250], [640, 1050, -20], [830, 920, -40], [680, 1150, 180]][index]
    n.append(
        {
            "id": "ball",
            "type": "group",
            "position": ball_start,
            "animations": [
                animation("position", [0, duration], [ball_start, ball_end]),
                animation("rotate_z", [0, duration], [-20, 35]),
            ],
            "z_index": 4,
        }
    )
    n += [
        shape(
            "shadow",
            ellipse(340, 80),
            fill=0,
            position=[-170, 170, 0],
            parent_id="ball",
            opacity=0.6,
        ),
        shape("sphere", ellipse(310, 310), fill=1, position=[-155, -155, 0], parent_id="ball"),
        shape(
            "sphere-shade",
            ellipse(310, 310),
            fill=3,
            position=[-155, -155, 0],
            parent_id="ball",
            opacity=0.12,
        ),
        shape(
            "panel",
            path([[0, -60], [56, -18], [35, 52], [-35, 52], [-56, -18]], True),
            fill=0,
            parent_id="ball",
        ),
        shape(
            "shine",
            ellipse(95, 35),
            fill=1,
            position=[-105, -120, 0],
            parent_id="ball",
            opacity=0.8,
        ),
    ]
    for j in range(5):
        angle = (j * 72 - 90) * math.pi / 180
        n.append(
            shape(
                f"seam-{j}",
                path(
                    [
                        [math.cos(angle) * 60, math.sin(angle) * 60],
                        [math.cos(angle) * 148, math.sin(angle) * 148],
                    ]
                ),
                stroke=0,
                parent_id="ball",
                opacity=0.65,
            )
        )
    n.append({"id": "type", "type": "group", "space": "screen", "z_index": 8})
    y = [450, 1210, 340, 450][index]
    title = text(
        "headline",
        [232, 205, 224, 235][index],
        920,
        space="screen",
        parent_id="type",
        position=[80, y, 0],
        animations=[
            animation(
                "position", [0, 430, duration], [[80, y + 90, 0], [80, y, 0], [80, y - 22, 0]]
            ),
            animation("opacity", [0, 260, duration - 180, duration], [0, 1, 1, 0.5]),
        ],
    )
    n.append(title)
    if index in (0, 2):
        n.append(
            {
                "id": "title-reveal",
                "type": "mask",
                "space": "screen",
                "params": {"target_id": "type", "geometry": rect(1080, 1920)},
                "animations": [animation("progress", [0, 420], [0, 1], "cubic_out")],
            }
        )
    if index == 2:
        n += [
            shape(
                "route",
                path([[100, 1200], [450, 1000], [540, 1300], [880, 800]]),
                stroke=2,
                position=[0, 0, 80],
                animations=[animation("draw_progress", [0, 2600, duration], [0, 1, 1])],
            ),
            {
                "id": "route-marker",
                "type": "path_follower",
                "position": [0, 0, 80],
                "anchor": [0.5, 0.5],
                "params": {"path_ref": "route", "marker": ellipse(28, 28), "fill": color(1)},
                "animations": [animation("progress", [0, 2600, duration], [0, 1, 1])],
            },
        ]
    if index == 3:
        n.append(
            shape(
                "climax",
                ellipse(900, 900),
                stroke=2,
                position=[540, 960, 0],
                anchor=[0.5, 0.5],
                opacity=0.5,
                z_index=3,
                animations=[
                    animation("scale", [0, 700, duration], [[0.15, 0.15], [1, 1], [1.8, 1.8]])
                ],
            )
        )
    n.append(
        {
            "id": "flash",
            "type": "light_sweep",
            "space": "screen",
            "z_index": 12,
            "position": [-500, -250, 0],
            "params": {"width": 260, "angle": -24, "intensity": 0.16, "blur": 8, "fill": color(1)},
            "animations": [
                animation(
                    "position",
                    [0, 700, duration],
                    [[-500, -250, 0], [1600, -250, 0], [1900, -250, 0]],
                )
            ],
        }
    )
    return {
        "nodes": n,
        "camera": {
            "position": [-22, 0, -30],
            "animations": [animation("position", [0, duration], [[-22, 0, -30], [40, -25, 80]])],
        },
    }


def music(index, duration):
    n = [
        {
            "id": "orbits",
            "type": "group",
            "position": [540, 560, 160],
            "animations": [
                animation("rotate_z", [0, duration], [-14 + index * 35, 35 + index * 35])
            ],
        }
    ]
    for j in range(4):
        radius = 260 + j * 55
        points = [
            [math.cos(i * math.pi / 24) * radius, math.sin(i * math.pi / 24) * radius * 0.8]
            for i in range(49)
        ]
        n.append(
            shape(
                f"orbit-{j}",
                path(points),
                stroke=3 if j % 2 else 2,
                parent_id="orbits",
                opacity=0.5,
                rotate_z=j * 25,
                animations=[animation("draw_progress", [0, 900, duration], [0.1, 1, 1])],
            )
        )
        n.append(
            {
                "id": f"orbiter-{j}",
                "type": "path_follower",
                "parent_id": "orbits",
                "anchor": [0.5, 0.5],
                "params": {
                    "path_ref": f"orbit-{j}",
                    "marker": ellipse(14 + j * 3, 14 + j * 3),
                    "fill": color(2 if j % 2 else 1),
                },
                "animations": [animation("progress", [0, duration], [0, 1], "linear")],
            }
        )
    n += [
        {
            "id": "sleeve",
            "type": "group",
            "position": [540, 560, -20],
            "z_index": 5,
            "animations": [
                animation("rotate_z", [0, duration], [-6, 5]),
                animation("scale", [0, 400, duration], [[0.9, 0.9], [1, 1], [1.04, 1.04]]),
            ],
        },
        shape("sleeve-border", rect(464, 464), stroke=2, parent_id="sleeve", anchor=[0.5, 0.5]),
        {
            "id": "cover",
            "type": "image",
            "parent_id": "sleeve",
            "anchor": [0.5, 0.5],
            "params": {"asset_binding": "cover", "width": 440, "height": 440},
        },
        text(
            "headline",
            116,
            900,
            position=[90, 100, 0],
            space="screen",
            z_index=10,
            animations=[
                animation(
                    "position", [0, 600, duration], [[90, 150, 0], [90, 100, 0], [110, 100, 0]]
                ),
                animation("opacity", [0, 400], [0, 1]),
            ],
        ),
        {
            "id": "waveform",
            "type": "video",
            "space": "screen",
            "position": [90, 865, 0],
            "z_index": 2,
            "params": {
                "asset_binding": "waveform",
                "width": 900,
                "height": 134,
                "source_in_ms": 0 if index == 0 else 4000,
                "muted": True,
            },
            "opacity": 0.6,
        },
        {
            "id": "dust",
            "type": "particle",
            "position": [540, 540, 650],
            "params": {
                "seed": 156,
                "count": 28,
                "velocity": [12, -18],
                "radius": 2,
                "fill": color(2),
            },
        },
    ]
    return {
        "nodes": n,
        "camera": {
            "animations": [animation("position", [0, duration], [[-25, 0, -20], [25, 12, 100]])]
        },
        "safe_area": {"left": 72, "right": 72, "top": 72, "bottom": 72},
    }


def geo(index, duration):
    n = [{"id": "map", "type": "group", "position": [640, 80, 280], "z_index": 2}]
    for j in range(12):
        n.append(
            shape(
                f"longitude-{j}",
                path([[j * 105, 0], [j * 105, 1000]]),
                stroke=3,
                parent_id="map",
                opacity=0.35,
            )
        )
    for j in range(9):
        n.append(
            shape(
                f"latitude-{j}",
                path([[0, j * 110], [1200, j * 110]]),
                stroke=3,
                parent_id="map",
                opacity=0.35,
            )
        )
    coast = [
        [90, 100],
        [330, 40],
        [500, 150],
        [700, 80],
        [950, 180],
        [1020, 400],
        [920, 620],
        [780, 640],
        [700, 850],
        [480, 930],
        [300, 780],
        [120, 800],
        [30, 550],
        [160, 350],
    ]
    n.append(shape("region", path(coast, True), fill=3, stroke=2, parent_id="map", opacity=0.7))
    river = [[210, 130], [320, 260], [490, 300], [540, 470], [430, 600], [500, 750], [720, 840]]
    n.append(shape("river", path(river), stroke=2, parent_id="map", opacity=0.65))
    route = [[200, 750], [340, 620], [520, 590], [660, 440], [720, 320], [910, 210]]
    n += [
        shape(
            "route",
            path(route),
            stroke=1,
            parent_id="map",
            animations=[
                animation(
                    "draw_progress", [0, duration], [round(index / 3, 6), round((index + 1) / 3, 6)]
                )
            ],
        ),
        {
            "id": "traveller",
            "type": "path_follower",
            "parent_id": "map",
            "anchor": [0.5, 0.5],
            "params": {"path_ref": "route", "marker": ellipse(24, 24), "fill": color(2)},
            "animations": [
                animation(
                    "progress", [0, duration], [round(index / 3, 6), round((index + 1) / 3, 6)]
                )
            ],
        },
        shape("shade", rect(590, 1080), fill=0, space="screen", opacity=0.92, z_index=9),
        text(
            "headline",
            98,
            510,
            max_lines=4,
            position=[80, 220, 0],
            space="screen",
            z_index=10,
            animations=[
                animation("opacity", [0, 600], [0, 1]),
                animation(
                    "position", [0, 700, duration], [[80, 255, 0], [80, 220, 0], [80, 220, 0]]
                ),
            ],
        ),
        shape(
            "rule",
            rect(310, 5),
            fill=2,
            space="screen",
            position=[80, 160, 0],
            z_index=11,
            animations=[animation("scale", [0, 800], [[0.05, 1], [1, 1]])],
        ),
    ]
    return {
        "nodes": n,
        "camera": {
            "position": [0, 0, 0],
            "animations": [
                animation(
                    "position",
                    [0, duration],
                    [
                        [index * 35, -index * 15, index * 80],
                        [(index + 1) * 35, -(index + 1) * 15, (index + 1) * 80],
                    ],
                )
            ],
        },
        "safe_area": {"left": 72, "right": 72, "top": 72, "bottom": 72},
    }


def build(label):
    p = PRODUCTIONS[label]
    width, height = {"vertical": (1080, 1920), "square": (1080, 1080), "horizontal": (1920, 1080)}[
        p["format"]
    ]
    slots = {"score": "audio"}
    if label == "music":
        slots.update(cover="image", waveform="video")
    scenes, start = [], 0
    for i, duration in enumerate(p["durations"]):
        graph = {
            "schema_version": "motion_scene_v1",
            **globals()[label](i, duration),
            "cues": [
                {
                    "id": "score",
                    "at_ms": 0,
                    "sound": {
                        "asset_binding": "score",
                        "source_in_ms": start,
                        "duration_ms": duration,
                        "gain": 0.9,
                        "fade_in_ms": 40 if i == 0 else 0,
                        "fade_out_ms": 180 if i == len(p["durations"]) - 1 else 0,
                    },
                },
                {"id": "settle", "at_ms": 600},
            ],
        }
        scenes.append(
            {"shot_slot": f"shot-{i + 1}", "required_duration_ms": duration, "graph": graph}
        )
        start += duration
    recipe = MotionRecipe.model_validate(
        {
            "schema_version": "motion_recipe_v1",
            "id": p["id"],
            "version": "1.1.0",
            "sha256": "0" * 64,
            "canvas": {"width": width, "height": height},
            "asset_slots": slots,
            "scenes": scenes,
        }
    )
    return recipe.model_copy(update={"sha256": recipe_digest(recipe)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    index = json.loads((REGISTRY_ROOT / "index.json").read_text(encoding="utf-8"))
    refs = [r for r in index["recipes"] if r["version"] != "1.1.0"]
    outputs = {}
    for label in PRODUCTIONS:
        recipe = build(label)
        refs.append(recipe.model_dump(include={"id", "version", "sha256"}))
        outputs[f"{recipe.id}.{recipe.version}.json"] = recipe.model_dump(mode="json")
    outputs["index.json"] = {"schema_version": "motion_registry_v1", "recipes": refs}
    for filename, value in outputs.items():
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        target = REGISTRY_ROOT / filename
        if args.check:
            if target.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Recipe differs: {filename}")
        else:
            target.write_text(text, encoding="utf-8", newline="\n")
    print("Original M4 recipes: " + ", ".join(PRODUCTIONS))


if __name__ == "__main__":
    main()
