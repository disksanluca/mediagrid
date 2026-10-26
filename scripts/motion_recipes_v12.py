"""M4.D authored recipe data. No per-film React components or executable recipe fields."""

import math

from apps.api.motion_contracts.models import MotionRecipe
from apps.api.motion_contracts.registry import recipe_digest
from scripts.build_motion_recipes import animation as anim
from scripts.build_motion_recipes import color, ellipse, path, rect, shape, text

PRODUCTIONS_V12 = {
    "sports": dict(
        id="sports.depth-impact",
        format="vertical",
        durations=[2000, 3000, 4000, 3000],
        titles=["ACENDA\nO JOGO", "CADA MOVIMENTO\nUMA DECISÃO", "MUDE\nA ROTA", "FAÇA\nACONTECER"],
        palette=["#071217", "#FFF4DA", "#F4BE4E", "#25423C", "#78918A", "#B76D28"],
        fonts=["Barlow Condensed", "Barlow Condensed"],
    ),
    "music": dict(
        id="music.orbital-sleeve",
        format="square",
        durations=[4000, 6000],
        titles=["Órbita\nESTUDO SONORO", "Escute o espaço\nSESSÃO ORIGINAL"],
        palette=["#100D1B", "#F5EEFF", "#91DCE8", "#8C75DC", "#EA9BAC", "#292137"],
        fonts=["Space Grotesk", "Space Grotesk"],
    ),
    "geo": dict(
        id="geo.route-explainer",
        format="horizontal",
        durations=[5000] * 3,
        titles=[
            "Vale Aurora\nREGIÃO FICCIONAL",
            "Pelo vale\nROTA DEMONSTRATIVA",
            "Norte Luminar\nCHEGADA ILUSTRADA",
        ],
        palette=["#091820", "#F5ECD8", "#F4AD70", "#29454A", "#43615B", "#7DA397", "#63BAC6"],
        fonts=["IBM Plex Sans", "IBM Plex Sans"],
    ),
}


def grad(stops, kind="linear", start=(0, 0), end=(1, 1), radius=0.7):
    return dict(
        kind=kind,
        start=list(start),
        end=list(end),
        radius=radius,
        stops=[dict(offset=o, color=color(c), opacity=a) for o, c, a in stops],
    )


def material(id_, geometry, gradient=None, stroke_gradient=None, glow=0, **kwargs):
    n = shape(id_, geometry, **kwargs)
    if gradient:
        n["params"]["fill_gradient"] = gradient
    if stroke_gradient:
        n["params"]["stroke_gradient"] = stroke_gradient
    if glow:
        n["params"]["glow"] = glow
    return n


def typography(
    id_, line, size, width, x, y, duration, *, delay=0, align="left", tracking=0, fill=1
):
    n = text(
        id_,
        size,
        width,
        max_lines=1,
        space="screen",
        position=[x, y, 0],
        z_index=30,
        animations=[
            anim("position", [0, delay + 650, duration], [[x, y + 28, 0], [x, y, 0], [x, y, 0]]),
            anim(
                "opacity",
                [0, delay, delay + 500] if delay else [0, 500],
                [0, 0, 1] if delay else [0, 1],
            ),
        ],
    )
    n["params"].update(
        text=dict(kind="shot_field", field="on_screen_text", line_index=line),
        align=align,
        letter_spacing=tracking,
        fill=color(fill),
    )
    return n


def ball():
    nodes = [
        dict(id="ball-paint", type="group", parent_id="ball"),
        dict(
            id="ball-clip",
            type="mask",
            parent_id="ball",
            position=[-220, -220, 0],
            params=dict(target_id="ball-paint", geometry=ellipse(440, 440)),
        ),
        material(
            "sphere",
            ellipse(440, 440),
            grad(
                [(0, 1, 1), (0.42, 1, 1), (0.73, 4, 1), (1, 0, 1)],
                "radial",
                (0.27, 0.2),
                radius=0.9,
            ),
            parent_id="ball-paint",
            position=[-220, -220, 0],
        ),
    ]
    pent = [
        (
            math.cos(i * math.tau / 5 - math.pi / 2) * 88,
            math.sin(i * math.tau / 5 - math.pi / 2) * 88,
        )
        for i in range(5)
    ]
    nodes.append(
        material(
            "center-panel",
            path(pent, True),
            grad([(0, 3, 1), (1, 0, 1)]),
            parent_id="ball-paint",
            stroke=0,
        )
    )
    for j in range(5):
        a = j * math.tau / 5 - math.pi / 2
        x, y = math.cos(a) * 210, math.sin(a) * 210
        poly = [
            (x + math.cos(a + k * math.tau / 5) * 75, y + math.sin(a + k * math.tau / 5) * 75)
            for k in range(5)
        ]
        nodes.append(
            material(
                f"panel-{j}",
                path(poly, True),
                grad([(0, 3, 1), (1, 0, 1)]),
                parent_id="ball-paint",
                stroke=0,
            )
        )
        nodes.append(
            shape(
                f"seam-{j}",
                path([pent[j], (x * 0.78, y * 0.78)]),
                stroke=0,
                parent_id="ball-paint",
                opacity=0.7,
            )
        )
    nodes.append(
        material(
            "specular",
            ellipse(340, 260),
            grad([(0, 1, 0.3), (0.7, 1, 0.06), (1, 1, 0)], "radial", (0.3, 0.2), radius=0.7),
            parent_id="ball-paint",
            position=[-190, -210, 0],
        )
    )
    return nodes


def sports(i, d):
    n = [
        material(
            "ambient",
            rect(1080, 1920),
            grad([(0, 3, 0.85), (0.6, 0, 1), (1, 0, 1)], "radial", (0.45, 0.4), radius=0.85),
            space="screen",
        ),
        dict(
            id="field-group",
            type="group",
            position=[540, 1130, 420],
            rotate_z=-13,
            z_index=2,
            animations=[anim("rotate_z", [0, d], [-13 + i * 3, -10 + i * 3])],
        ),
        material(
            "turf",
            rect(1080, 1420),
            grad([(0, 3, 0.95), (0.65, 0, 0.65), (1, 0, 0.2)]),
            parent_id="field-group",
            position=[-540, -710, 0],
        ),
        shape(
            "field-line",
            rect(980, 1320),
            stroke=4,
            parent_id="field-group",
            position=[-490, -660, 0],
            opacity=0.4,
        ),
        shape(
            "mid-line", path([[-490, 0], [490, 0]]), stroke=4, parent_id="field-group", opacity=0.4
        ),
        shape(
            "field-circle",
            ellipse(300, 300),
            stroke=4,
            parent_id="field-group",
            position=[-150, -150, 0],
            opacity=0.4,
        ),
        shape(
            "goal-a",
            rect(400, 220),
            stroke=4,
            parent_id="field-group",
            position=[-200, -660, 0],
            opacity=0.4,
        ),
        shape(
            "goal-b",
            rect(400, 220),
            stroke=4,
            parent_id="field-group",
            position=[-200, 440, 0],
            opacity=0.4,
        ),
        dict(
            id="dust",
            type="particle",
            position=[540, 960, 700],
            opacity=0.38,
            params=dict(seed=76, count=20, velocity=[-9, -23], radius=2, fill=color(1)),
        ),
    ]
    for j in range(3):
        n.append(
            material(
                f"near-band-{j}",
                rect(100, 2400),
                grad([(0, 2, 0), (0.5, 2, 0.12), (1, 2, 0)]),
                position=[-180 + j * 240, -200, -160],
                rotate_z=-23,
                z_index=12,
                animations=[
                    anim(
                        "position",
                        [0, d],
                        [[-180 + j * 240, -200, -160], [-310 + j * 240, -200, -160]],
                    )
                ],
            )
        )
    start = [[780, 1220, 200], [600, 950, -180], [220, 1450, 40], [810, 900, -60]][i]
    end = [[600, 950, -180], [750, 1000, 180], [810, 900, -60], [770, 1330, 80]][i]
    n.append(
        dict(
            id="ball",
            type="group",
            position=start,
            z_index=9,
            animations=[
                anim("position", [0, d], [start, end]),
                anim("rotate_z", [0, d], [-20 + i * 25, 5 + i * 25]),
            ],
        )
    )
    n += ball()
    n.append(
        material(
            "ground-shadow",
            ellipse(450, 100),
            grad([(0, 0, 0.7), (1, 0, 0)], "radial", (0.5, 0.5)),
            position=[end[0] - 210, end[1] + 260, 80],
            z_index=3,
            animations=[anim("scale", [0, d], [[0.6, 0.6], [1.1, 1.1]])],
        )
    )
    if i == 2:
        route = [(220, 1450), (440, 1270), (620, 1420), (810, 900)]
        line = material(
            "route",
            path(route),
            stroke_gradient=grad([(0, 2, 0.1), (0.7, 2, 1), (1, 1, 1)]),
            glow=5,
            z_index=7,
            animations=[anim("draw_progress", [0, d], [0, 1])],
        )
        line["params"]["stroke_width"] = 6
        n.append(line)
    if i == 3:
        for j in range(2):
            n.append(
                shape(
                    f"impact-ring-{j}",
                    ellipse(700, 700),
                    stroke=2,
                    anchor=[0.5, 0.5],
                    position=[810, 900, -60],
                    z_index=6,
                    opacity=0.35,
                    animations=[
                        anim("scale", [0, 500 + j * 200, d], [[0.15, 0.15], [1, 1], [2, 2]]),
                        anim("opacity", [0, 400, d], [0.6, 0.4, 0]),
                    ],
                )
            )
        n.append(
            material(
                "finish-ribbon",
                rect(1300, 260),
                grad([(0, 5, 1), (0.5, 2, 1), (1, 2, 0.65)]),
                space="screen",
                position=[-100, 1490, 0],
                rotate_z=-7,
                z_index=15,
                animations=[
                    anim(
                        "position",
                        [0, 1200, d],
                        [[-1400, 1490, 0], [-100, 1490, 0], [-100, 1490, 0]],
                    )
                ],
            )
        )
    y = 330 if i != 1 else 1290
    sizes = [(220, 270), (114, 170), (230, 265), (230, 178)][i]
    n += [
        typography("type-first", 0, sizes[0], 920, 80, y, d, tracking=1),
        typography("type-second", 1, sizes[1], 920, 80, y + sizes[0] * 0.94, d, delay=180, fill=2),
    ]
    if i in (0, 2):
        for title in n[-2:]:
            title["parent_id"] = "title-group"
        n += [
            dict(id="title-group", type="group", space="screen", z_index=30),
            dict(
                id="title-mask",
                type="mask",
                space="screen",
                z_index=30,
                params=dict(target_id="title-group", geometry=rect(1080, 1920)),
                animations=[anim("progress", [0, 650], [0.05, 1])],
            ),
        ]
    n.append(
        dict(
            id="light",
            type="light_sweep",
            position=[-600, -100, 0],
            z_index=20,
            space="screen",
            params=dict(width=240, angle=-20, intensity=0.22, blur=12, fill=color(1)),
            animations=[
                anim("position", [0, 600, d], [[-600, -100, 0], [1400, -100, 0], [1700, -100, 0]])
            ],
        )
    )
    return dict(
        nodes=n,
        camera=dict(
            position=[0, 0, -20],
            animations=[anim("position", [0, d], [[0, 0, -20], [25, -15, 10]])],
        ),
        safe_area=dict(left=72, right=72, top=120, bottom=180),
    )


def music(i, d):
    start = i * 4000
    n = [
        material(
            "ambient",
            rect(1080, 1080),
            grad([(0, 5, 1), (0.65, 0, 1), (1, 0, 1)], "radial", (0.5, 0.47), radius=0.7),
            space="screen",
        ),
        dict(
            id="dust",
            type="particle",
            position=[540, 540, 650],
            opacity=0.5,
            params=dict(seed=156, count=24, velocity=[3, -7], radius=1.8, fill=color(1)),
        ),
        dict(
            id="sleeve",
            type="group",
            position=[540, 520, 0],
            z_index=5,
            animations=[
                anim("rotate_z", [0, d], [-6 + i * 8, 2 + i * 8]),
                anim("scale", [0, 700, d], [[0.88, 0.88], [0.95, 0.95], [1.02, 1.02]]),
            ],
        ),
        dict(
            id="cover",
            type="image",
            parent_id="sleeve",
            anchor=[0.5, 0.5],
            params=dict(asset_binding="cover", width=430, height=430),
            animations=[anim("opacity", [0, 650], [0.1, 1])],
        ),
        shape(
            "cover-line",
            rect(450, 450),
            stroke=3,
            parent_id="sleeve",
            anchor=[0.5, 0.5],
            opacity=0.5,
        ),
    ]
    for j, angle in enumerate((-32, 38, 88)):
        n.append(
            dict(
                id=f"orbit-{j}",
                type="group",
                position=[540, 520, 70],
                rotate_z=angle,
                z_index=3,
                animations=[anim("rotate_z", [0, d], [angle + i * 10, angle + (i + 1) * 10])],
            )
        )
        for half in (0, 1):
            pts = [
                (
                    math.cos((k / 40 + half) * math.pi) * 355,
                    math.sin((k / 40 + half) * math.pi) * 155,
                )
                for k in range(41)
            ]
            ribbon = material(
                f"ribbon-{j}-{half}",
                path(pts),
                stroke_gradient=grad(
                    [(0, 3, 0.15), (0.3, 2, 1), (0.55, 1, 1), (0.8, 4, 1), (1, 3, 0.2)]
                ),
                glow=5 if half else 0,
                parent_id=f"orbit-{j}",
                z_index=10 if half else 0,
                animations=[anim("draw_progress", [0, 900, d], [0.05, 1, 1])],
            )
            ribbon["params"]["stroke_width"] = 16 if j != 2 else 11
            n.append(ribbon)
        # Separate foreground path uses the same transform but sorts over the sleeve.
        front = n[-1]
        front["parent_id"] = None
        front["position"] = [540, 520, -10]
        front["rotate_z"] = angle
        front["z_index"] = 10
        front["animations"].append(anim("rotate_z", [0, d], [angle + i * 10, angle + (i + 1) * 10]))
    n += [
        typography(
            "headline", 0, 76 if i == 0 else 62, 920, 80, 100, d, align="center", tracking=1.5
        ),
        typography(
            "edition", 1, 32, 920, 80, 934, d, delay=200, align="center", tracking=4, fill=2
        ),
        dict(
            id="wave",
            type="video",
            space="screen",
            position=[280, 866, 0],
            z_index=2,
            opacity=0.42,
            params=dict(
                asset_binding="waveform", width=520, height=60, source_in_ms=start, muted=True
            ),
        ),
    ]
    return dict(
        nodes=n,
        camera=dict(
            position=[0, 0, -50],
            animations=[anim("position", [0, d], [[0, 0, -50 + i * 25], [0, 0, -25 + i * 25]])],
        ),
        safe_area=dict(left=72, right=72, top=72, bottom=72),
    )


def geo(i, d):
    n = [
        material(
            "atmosphere",
            rect(1920, 1080),
            grad([(0, 3, 0.8), (0.8, 0, 1), (1, 0, 1)], "radial", (0.65, 0.45), radius=0.9),
            space="screen",
        )
    ]

    def vertex(x, y):
        height = 100 + 85 * math.sin(x * 0.007 + y * 0.004) + 50 * math.cos(y * 0.012 - x * 0.004)
        return (430 + x, 110 + y * 0.77 - height)

    for y in range(5):
        for x in range(8):
            points = [
                vertex(x * 240, y * 260),
                vertex((x + 1) * 240, y * 260),
                vertex((x + 1) * 240, (y + 1) * 260),
                vertex(x * 240, (y + 1) * 260),
            ]
            for tri, idx in enumerate(((0, 1, 2), (0, 2, 3))):
                n.append(
                    shape(
                        f"terrain-{x}-{y}-{tri}",
                        path([points[k] for k in idx], True),
                        fill=3 if (x + y + tri) % 3 else 4,
                        stroke=4,
                        opacity=0.35 + ((x * 17 + y * 13 + tri * 7) % 11) * 0.045,
                        position=[0, 0, 380],
                        z_index=1,
                    )
                )
    river = [vertex(700 + 80 * math.sin(y / 130), y) for y in range(0, 1301, 40)]
    line = shape("river", path(river), stroke=6, position=[0, 0, 370], opacity=0.65, z_index=3)
    line["params"]["stroke_width"] = 12
    n.append(line)
    route = [
        (760, 720),
        (950, 640),
        (1110, 460),
        (1280, 520),
        (1450, 340),
        (1650, 360),
        (1840, 140),
    ]
    trace = material(
        "route",
        path(route),
        stroke_gradient=grad([(0, 2, 0.5), (0.65, 2, 1), (1, 1, 1)]),
        glow=6,
        position=[0, 0, 300],
        z_index=6,
        animations=[anim("draw_progress", [0, d], [round(i / 3, 6), round((i + 1) / 3, 6)])],
    )
    trace["params"]["stroke_width"] = 7
    n.append(trace)
    for suffix, radius, opacity, fill in (("halo", 54, 0.17, 2), ("head", 14, 1, 1)):
        n.append(
            dict(
                id=f"marker-{suffix}",
                type="path_follower",
                anchor=[0.5, 0.5],
                position=[0, 0, 300],
                opacity=opacity,
                z_index=8,
                params=dict(path_ref="route", marker=ellipse(radius, radius), fill=color(fill)),
                animations=[anim("progress", [0, d], [round(i / 3, 6), round((i + 1) / 3, 6)])],
            )
        )
    for j, (x, y) in enumerate((route[0], route[3], route[-1])):
        n.append(
            shape(
                f"station-{j}",
                ellipse(32, 32),
                stroke=2,
                anchor=[0.5, 0.5],
                position=[x, y, 300],
                z_index=7,
                opacity=0.7,
                animations=[anim("scale", [0, d // 2, d], [[1, 1], [1.4, 1.4], [1, 1]])],
            )
        )
    n += [
        material(
            "editorial-shade",
            rect(770, 1080),
            grad([(0, 0, 1), (0.7, 0, 0.92), (1, 0, 0)]),
            space="screen",
            z_index=20,
        ),
        typography("place", 0, 74, 610, 92, 310, d, tracking=0.3),
        typography("source-label", 1, 32, 650, 92, 415, d, delay=160, tracking=2, fill=2),
        shape(
            "editorial-rule", rect(80, 4), fill=2, space="screen", position=[92, 270, 0], z_index=30
        ),
    ]
    cameras = [[0, 0, -80], [170, -35, 10], [330, -90, 100], [500, -140, 160]]
    return dict(
        nodes=n,
        camera=dict(
            position=cameras[i],
            animations=[anim("position", [0, d], [cameras[i], cameras[i + 1]], "linear")],
        ),
        safe_area=dict(left=72, right=72, top=72, bottom=72),
    )


def build_v12(label):
    def authored_precision(value):
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, list):
            return [authored_precision(v) for v in value]
        if isinstance(value, dict):
            return {k: authored_precision(v) for k, v in value.items()}
        return value

    p = PRODUCTIONS_V12[label]
    w, h = {"vertical": (1080, 1920), "square": (1080, 1080), "horizontal": (1920, 1080)}[
        p["format"]
    ]
    scenes = []
    start = 0
    for i, d in enumerate(p["durations"]):
        graph = {
            "schema_version": "motion_scene_v1",
            **{"sports": sports, "music": music, "geo": geo}[label](i, d),
            "cues": [
                dict(
                    id="score",
                    at_ms=0,
                    sound=dict(
                        asset_binding="score",
                        source_in_ms=start,
                        duration_ms=d,
                        gain=0.9,
                        fade_in_ms=40 if i == 0 else 0,
                        fade_out_ms=180 if i == len(p["durations"]) - 1 else 0,
                    ),
                ),
                dict(id="settle", at_ms=600),
            ],
        }
        scenes.append(dict(shot_slot=f"shot-{i + 1}", required_duration_ms=d, graph=graph))
        start += d
    recipe = MotionRecipe.model_validate(
        authored_precision(
            dict(
                schema_version="motion_recipe_v1",
                id=p["id"],
                version="1.2.0",
                sha256="0" * 64,
                canvas=dict(width=w, height=h),
                asset_slots={
                    "score": "audio",
                    **({"cover": "image", "waveform": "video"} if label == "music" else {}),
                },
                scenes=scenes,
            )
        )
    )
    return recipe.model_copy(update={"sha256": recipe_digest(recipe)})
