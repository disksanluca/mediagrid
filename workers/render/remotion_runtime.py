"""The shared Remotion CLI invocation for legacy and creative jobs."""

import os
import shutil
import subprocess
from pathlib import Path

from apps.api.config import get_settings
from workers.render.power import keep_system_awake


def render_remotion(
    props_path: Path,
    public_dir: Path,
    output: Path,
    *,
    timeline: bool,
    scale: float = 1,
    explicit_codecs: bool = False,
) -> None:
    settings = get_settings()
    root = settings.mediagrid_renderer_root.resolve() if settings.mediagrid_renderer_root else None
    node = settings.mediagrid_node_path
    if root and node:
        cli = root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        if not cli.is_file():
            cli = root.parents[1] / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        if not cli.is_file():
            raise ValueError("Remotion CLI not found in renderer runtime or workspace")
        command = [
            str(node),
            str(cli),
            "render",
            str(root / "src" / "index.ts"),
            "MediaGridTimelineV2" if timeline else "MediaGridVideo",
            str(output),
            "--props",
            str(props_path),
        ]
        browser = (
            str(settings.mediagrid_browser_path)
            if settings.mediagrid_browser_path
            else next(
                (
                    str(path)
                    for path in (root / "node_modules" / ".remotion").rglob(
                        "chrome-headless-shell.exe"
                    )
                ),
                None,
            )
        )
    else:
        command = [
            "npm",
            "run",
            "render:v2" if timeline else "render",
            "--workspace",
            "@mediagrid/renderer",
            "--",
            str(output),
            "--props",
            str(props_path),
        ]
        browser = shutil.which("chromium") or shutil.which("google-chrome")
    if browser:
        command.append(f"--browser-executable={browser}")
    command.extend(
        [
            f"--concurrency={min(settings.mediagrid_render_concurrency, os.cpu_count() or 1)}",
            "--disallow-parallel-encoding",
            f"--public-dir={public_dir}",
        ]
    )
    if explicit_codecs:
        command.extend(
            [
                "--codec=h264",
                "--audio-codec=aac",
                "--pixel-format=yuv420p",
                "--crf=18",
                "--audio-bitrate=192k",
                f"--scale={scale}",
            ]
        )
    with keep_system_awake():
        subprocess.run(command, check=True, cwd=root)
