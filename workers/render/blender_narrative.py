"""Original, versioned Migo 3D rig and stage. Executed only by Blender.

The input is a validated JSON story, never generated Python or a .blend from
an untrusted source. Each shot rebuilds the same rig and world IDs so the
character and palette remain continuous across camera cuts.
"""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

RIG_VERSION = "migo_3d_v1"
WORLD_VERSION = "atelier_stage_v1"


def material(name: str, rgb: tuple[float, float, float], *, roughness: float = 0.35):
    item = bpy.data.materials.new(name)
    item.diffuse_color = (*rgb, 1.0)
    item.use_nodes = True
    node = item.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*rgb, 1.0)
    node.inputs["Roughness"].default_value = roughness
    return item


def cube(name: str, location: tuple[float, float, float], scale: tuple[float, float, float],
         surface, *, bevel: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    item = bpy.context.object
    item.name = name
    item.scale = scale
    item.data.materials.append(surface)
    if bevel:
        modifier = item.modifiers.new("Soft original geometry", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        item.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return item


def sphere(name: str, location: tuple[float, float, float],
           scale: tuple[float, float, float], surface):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1,
                                        location=location)
    item = bpy.context.object
    item.name = name
    item.scale = scale
    item.data.materials.append(surface)
    bpy.ops.object.shade_smooth()
    return item


def animate(item, frames: tuple[int, int, int], poses: list[tuple[float, float, float]],
            *, rotation: bool = False) -> None:
    for frame, coordinates in zip(frames, poses, strict=True):
        if rotation:
            item.rotation_euler = coordinates
            item.keyframe_insert(data_path="rotation_euler", frame=frame)
        else:
            item.location = coordinates
            item.keyframe_insert(data_path="location", frame=frame)


def build(shot: dict, frames: int, aspect: str, quality: str, output: Path) -> dict:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    dark = material("migo-shell-v1", (0.023, 0.072, 0.094))
    lime = material("migo-lime-v1", (0.66, 0.91, 0.20))
    white = material("migo-eye-v1", (0.91, 0.97, 0.88))
    black = material("migo-pupil-v1", (0.012, 0.018, 0.026))
    floor = material("atelier-floor-v1", (0.045, 0.091, 0.095), roughness=0.55)
    orb = material("atelier-orb-v1", (0.23, 0.68, 0.75), roughness=0.18)
    cube("atelier-floor-v1", (0, 0, -0.18), (14, 14, 0.30), floor, bevel=0.10)
    cube("atelier-plinth-v1", (0, 0, 0.05), (4.4, 3.5, 0.18), dark, bevel=0.16)
    for index in range(4):
        cube(f"atelier-column-{index}", ((-3.5 if index % 2 else 3.5),
             (-2.2 if index < 2 else 2.2), 1.4), (0.14, 0.14, 2.8), lime, bevel=0.06)

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.2))
    actor = bpy.context.object
    actor.name = RIG_VERSION

    def part(item):
        item.parent = actor
        item.matrix_parent_inverse = actor.matrix_world.inverted()
        return item

    part(cube("migo-body", (0, 0, 1.05), (1.15, 0.68, 1.30), lime, bevel=0.28))
    head = part(cube("migo-head", (0, -0.03, 2.0), (1.54, 0.83, 1.06), dark,
                     bevel=0.36))
    for side in (-1, 1):
        part(sphere(f"migo-eye-{side}", (side * 0.37, -0.49, 2.13),
                    (0.19, 0.08, 0.22), white))
        part(sphere(f"migo-pupil-{side}", (side * 0.36, -0.56, 2.11),
                    (0.08, 0.04, 0.09), black))
        part(cube(f"migo-brow-{side}", (side * 0.36, -0.53, 2.43),
                  (0.42, 0.09, 0.055), lime, bevel=0.02))
        part(cube(f"migo-foot-{side}", (side * 0.32, -0.18, 0.34),
                  (0.40, 0.70, 0.25), dark, bevel=0.08))
    part(cube("migo-mouth", (0, -0.53, 1.78), (0.43, 0.06, 0.055), white,
              bevel=0.02))
    part(sphere("migo-antenna", (0, -0.03, 2.79), (0.15, 0.15, 0.15), lime))
    part(cube("migo-antenna-stem", (0, -0.03, 2.67), (0.07, 0.07, 0.22), lime))
    left = part(cube("migo-arm-left", (-0.76, 0, 1.32), (0.29, 0.35, 0.92), dark,
                     bevel=0.11))
    right = part(cube("migo-arm-right", (0.76, 0, 1.32), (0.29, 0.35, 0.92), dark,
                      bevel=0.11))
    sphere("atelier-orb-v1", (1.65, -0.66, 1.1), (0.32, 0.32, 0.32), orb)
    prop = bpy.context.object

    start, mid, end = 1, max(2, frames // 2), frames
    action = shot["action"]
    if action == "notice":
        positions = [(0, 0, 0.2), (0.10, 0, 0.23), (0.16, 0, 0.2)]
        right_angles = [(0, 0, 0), (0, -0.16, -0.34), (0, -0.18, -0.42)]
        head_angles = [(0, 0, 0), (0, 0, -0.12), (0, 0, -0.18)]
    elif action == "reach":
        positions = [(0.16, 0, 0.2), (0.42, 0, 0.22), (0.65, 0, 0.2)]
        right_angles = [(0, -0.18, -0.42), (0, -0.25, -0.95),
                        (0, -0.30, -1.18)]
        head_angles = [(0, 0, -0.18), (0, 0, -0.14), (0, 0, 0)]
    elif action == "react":
        positions = [(0.65, 0, 0.2), (0.45, 0, 0.40), (0.45, 0, 0.2)]
        right_angles = [(0, -0.30, -1.18), (0, -0.2, -0.62), (0, 0, -0.2)]
        head_angles = [(0, 0, 0), (0, 0, 0.22), (0, 0, 0.06)]
    else:  # celebrate
        positions = [(0.45, 0, 0.2), (0.45, 0, 0.50), (0.45, 0, 0.2)]
        right_angles = [(0, 0, -0.2), (0, 0, -1.5), (0, 0, -1.25)]
        head_angles = [(0, 0, 0.06), (0, 0, 0), (0, 0, -0.06)]
    animate(actor, (start, mid, end), positions)
    animate(right, (start, mid, end), right_angles, rotation=True)
    animate(left, (start, mid, end), [(0, 0, 0), (0, 0, 0.4 if action == "celebrate" else 0.1),
                                      (0, 0, 0.3 if action == "celebrate" else 0)],
            rotation=True)
    animate(head, (start, mid, end), head_angles, rotation=True)
    animate(prop, (start, mid, end), [(1.65, -0.66, 1.1),
            (1.65, -0.66, 1.32 if action in {"react", "celebrate"} else 1.1),
            (1.65, -0.66, 1.1)])

    camera_positions = {"wide": (5.8, -9.0, 4.0), "medium": (4.0, -6.5, 3.4),
                        "close": (2.8, -4.6, 3.0)}
    bpy.ops.object.camera_add(location=camera_positions[shot["camera"]])
    camera = bpy.context.object
    camera.name = "atelier-camera-v1"
    direction = Vector((0, 0, 1.8)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = {"wide": 7.4, "medium": 5.8, "close": 5.8}[shot["camera"]]
    bpy.context.scene.camera = camera
    for name, location, energy, color in (
        ("key", (1.0, -4.0, 6.0), 850, (0.84, 1.0, 0.85)),
        ("rim", (-3.0, 2.0, 4.5), 1100, (0.35, 0.78, 1.0)),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = f"atelier-{name}-v1"
        multiplier = {"bright": 1.3, "tense": 0.7, "calm": 1.0}[shot["lighting"]]
        light.data.energy = energy * multiplier
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
    scene = bpy.context.scene
    scene.world.color = (0.04, 0.065, 0.075)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    dimensions = {
        ("blocking", "horizontal"): (480, 270),
        ("blocking", "vertical"): (270, 480),
        ("final", "horizontal"): (1280, 720),
        ("final", "vertical"): (720, 1280),
    }
    scene.render.resolution_x, scene.render.resolution_y = dimensions[quality, aspect]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.fps = 12 if quality == "blocking" else 24
    scene.render.filepath = str(output / "frame_")
    scene.render.image_settings.color_mode = "RGB"
    scene.camera.data.lens = 50
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(animation=True)
    return {"rig_version": RIG_VERSION, "world_version": WORLD_VERSION,
            "frames": frames, "fps": scene.render.fps, "camera": shot["camera"],
            "objects": ["migo-body", "migo-head", "atelier-floor-v1", "atelier-orb-v1"]}


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--shot", type=int, required=True)
    parser.add_argument("--quality", choices=("blocking", "final"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    values = parser.parse_args(args)
    story = json.loads(values.story.read_text(encoding="utf-8"))
    if story.get("rig_version") != RIG_VERSION or story.get("world_version") != WORLD_VERSION:
        raise ValueError("Unsupported character or world version")
    shot = story["shots"][values.shot]
    fps = 12 if values.quality == "blocking" else 24
    frames = max(1, round(shot["duration_ms"] * fps / 1000))
    metadata = build(shot, frames, story["aspect"], values.quality, values.output)
    (values.output / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")


if __name__ == "__main__":
    main()
