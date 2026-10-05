"""Local hardware measurements for the Windows setup wizard and system doctor."""

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from .config import get_settings


class HardwareProfile(BaseModel):
    cpu: str
    logical_cores: int
    ram_gb: float | None
    gpu: str | None
    vram_gb: float | None
    cuda_available: bool
    disk_free_gb: float
    windows_version: str | None
    recommended_profile: str


def _windows_inventory() -> dict[str, object]:
    if platform.system() != "Windows" or not shutil.which("powershell.exe"):
        return {}
    command = (
        "$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "$os=Get-CimInstance Win32_OperatingSystem; "
        "$gpu=Get-CimInstance Win32_VideoController | Sort-Object AdapterRAM -Descending | "
        "Select-Object -First 1; "
        "[pscustomobject]@{cpu=$cpu.Name;ram_kb=$os.TotalVisibleMemorySize;"
        "gpu=$gpu.Name;vram_bytes=$gpu.AdapterRAM;windows=$os.Caption} | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        value = json.loads(result.stdout)
        return value if isinstance(value, dict) else {}
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return {}


def _nvidia_inventory() -> tuple[str | None, float | None, bool]:
    if not shutil.which("nvidia-smi"):
        return None, None, False
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        first = result.stdout.splitlines()[0]
        name, memory_mib = first.rsplit(",", 1)
        return name.strip(), round(float(memory_mib.strip()) / 1024, 1), True
    except (
        OSError,
        IndexError,
        ValueError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        return None, None, False


def _ram_gb() -> float | None:
    if platform.system() == "Linux":
        try:
            match = re.search(r"MemTotal:\s+(\d+) kB", Path("/proc/meminfo").read_text())
            return round(int(match.group(1)) / 1024 / 1024, 1) if match else None
        except (OSError, ValueError):
            return None
    return None


def choose_profile(ram_gb: float | None, vram_gb: float | None) -> str:
    if not vram_gb or not ram_gb or ram_gb < 12 or vram_gb < 6:
        return "LIGHT"
    if vram_gb >= 24 and ram_gb >= 32:
        return "HIGH_PERFORMANCE"
    if vram_gb >= 12 and ram_gb >= 24:
        return "QUALITY"
    return "BALANCED"


def profile_hardware() -> HardwareProfile:
    inventory = _windows_inventory()
    nvidia_name, nvidia_vram, cuda = _nvidia_inventory()
    ram_kb = inventory.get("ram_kb")
    ram = round(float(ram_kb) / 1024 / 1024, 1) if ram_kb else _ram_gb()
    raw_vram = inventory.get("vram_bytes")
    # WMI AdapterRAM is a 32-bit value; large GPU memory is taken from nvidia-smi.
    wmi_vram = round(float(raw_vram) / 1024**3, 1) if raw_vram else None
    vram = nvidia_vram or wmi_vram
    data_dir = get_settings().mediagrid_data_dir
    ancestor = data_dir.resolve()
    while not ancestor.exists() and ancestor.parent != ancestor:
        ancestor = ancestor.parent
    free = round(shutil.disk_usage(ancestor).free / 1024**3, 1)
    return HardwareProfile(
        cpu=str(inventory.get("cpu") or platform.processor() or "Unknown CPU"),
        logical_cores=os.cpu_count() or 1,
        ram_gb=ram,
        gpu=nvidia_name or (str(inventory["gpu"]) if inventory.get("gpu") else None),
        vram_gb=vram,
        cuda_available=cuda,
        disk_free_gb=free,
        windows_version=str(inventory["windows"]) if inventory.get("windows") else None,
        recommended_profile=choose_profile(ram, vram),
    )
