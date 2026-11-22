"""W0 - Environment snapshot: OS build, CPU, RAM, GPU/driver, monitors and DPI, tool versions.

    uv run python scripts/windows_tests/W0_env_snapshot.py

Records facts only. The few checks are objective (Python >= 3.11, Windows, a monitor exists).
Whether the machine matches the target (Ryzen 7 8745H, 16 GB, RTX 4050 6 GB) is for the owner to
confirm from the report, so no check pretends to decide it.
"""

import ctypes
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from ctypes import wintypes

from _common import IS_WINDOWS, Recorder

KEY_PACKAGES = (
    "pydantic",
    "pytest",
    "ruff",
    "numpy",
    "opencv-python",
    "pillow",
    "paddlepaddle",
    "paddleocr",
    "rapidfuzz",
    "imagehash",
    "scikit-image",
    "torch",
    "transformers",
    "sentencepiece",
    "openai",
    "pyside6",
    "dxcam",
    "psutil",
)


def run(cmd: list[str], timeout: float = 15.0) -> str | None:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return (done.stdout or done.stderr).strip() or None


def total_ram_gib() -> float | None:
    if IS_WINDOWS:

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / 2**30
        return None
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:
            return int(handle.readline().split()[1]) / 2**20
    except (OSError, ValueError):
        return None


def monitors() -> list[dict[str, object]]:
    """Physical-pixel monitor rectangles and DPI scale (per-monitor DPI aware)."""
    if not IS_WINDOWS:
        return []
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        pass

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    found: list[dict[str, object]] = []

    @ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    def callback(hmon, _hdc, _rect, _lparam):
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        dpi_x, dpi_y = ctypes.c_uint(0), ctypes.c_uint(0)
        try:
            ctypes.windll.shcore.GetDpiForMonitor(
                hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            )  # MDT_EFFECTIVE_DPI
        except (AttributeError, OSError):
            pass
        rect = info.rcMonitor
        found.append(
            {
                "device": info.szDevice,
                "primary": bool(info.dwFlags & 1),
                "left": rect.left,
                "top": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
                "dpi": dpi_x.value or None,
                "scale_percent": round(dpi_x.value / 96 * 100) if dpi_x.value else None,
            }
        )
        return True

    user32.EnumDisplayMonitors(None, None, callback, 0)
    return found


def installed(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    rec = Recorder("W0", "Environment snapshot")
    print("W0 - environment snapshot")

    rec.measure("python", sys.version.replace("\n", " "))
    rec.measure("python_executable", sys.executable)
    rec.measure("platform", platform.platform())
    rec.measure("machine", platform.machine())
    rec.measure("processor_string", platform.processor())
    rec.measure("logical_cpus", os.cpu_count())
    if IS_WINDOWS:
        v = sys.getwindowsversion()
        rec.measure("windows_build", f"{v.major}.{v.minor}.{v.build}")
    ram = total_ram_gib()
    rec.measure("ram_total", round(ram, 2) if ram else None, "GiB")

    cpu_name = run(
        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"]
    )
    rec.measure("cpu_name", cpu_name)

    smi = shutil.which("nvidia-smi")
    gpu = None
    if smi:
        gpu = run([smi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
    rec.measure("gpu_nvidia_smi", gpu)

    rec.measure("uv_version", run(["uv", "--version"]))
    if IS_WINDOWS:
        rec.measure("power_plan", run(["powercfg", "/getactivescheme"]))

    versions = {name: installed(name) for name in KEY_PACKAGES}
    rec.measure("installed_packages", versions)

    mons = monitors()
    rec.measure("monitors", mons)

    rec.check("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
    rec.check("running on Windows", IS_WINDOWS, platform.system())
    rec.check("at least one monitor reported", bool(mons) if IS_WINDOWS else None)
    rec.check("nvidia-smi available (GPU/VRAM sampling for W8)", bool(smi) if IS_WINDOWS else None)

    rec.note(
        "Owner to record by hand (cannot be read reliably from here): Windows power mode, "
        "Game Mode on/off, Hardware-accelerated GPU scheduling on/off, laptop plugged in or on "
        "battery, GPU mode (hybrid/discrete), and which monitor the game runs on."
    )
    rec.note("Compare cpu_name / ram_total / gpu_nvidia_smi with the target machine by eye.")
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
