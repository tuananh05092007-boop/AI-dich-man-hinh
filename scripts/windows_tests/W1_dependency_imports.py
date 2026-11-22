"""W1 - Dependency import and CPU-only check for the approved stack.

    uv run python scripts/windows_tests/W1_dependency_imports.py

Imports every candidate package, records version and import time. It installs nothing. Install
the candidates first in a separate virtual environment (see README.md) so the repository lockfile
is not touched before M0-09.

``dxcam`` is only a *candidate* DXGI binding (DEPENDENCIES.md risk 2), so a missing ``dxcam``
does not fail W1; it is reported as a note.
"""

import importlib
import importlib.metadata
import sys
import time

from _common import Recorder

# (import name, distribution name, required)
CANDIDATES = (
    ("numpy", "numpy", True),
    ("cv2", "opencv-python", True),
    ("PIL", "pillow", True),
    ("pydantic", "pydantic", True),
    ("yaml", "pyyaml", True),
    ("paddle", "paddlepaddle", True),
    ("paddleocr", "paddleocr", True),
    ("rapidfuzz", "rapidfuzz", True),
    ("imagehash", "imagehash", True),
    ("skimage", "scikit-image", True),
    ("torch", "torch", True),
    ("transformers", "transformers", True),
    ("sentencepiece", "sentencepiece", True),
    ("openai", "openai", True),
    ("PySide6", "pyside6", True),
    ("psutil", "psutil", False),
    ("dxcam", "dxcam", False),
)


def version_of(dist: str, module: object) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return getattr(module, "__version__", None)


def main() -> int:
    rec = Recorder("W1", "Dependency imports (approved stack, CPU-only)")
    print("W1 - dependency imports")
    print(f"  python {sys.version.split()[0]}")
    loaded: dict[str, object] = {}
    rows = {}
    for module_name, dist, required in CANDIDATES:
        start = time.perf_counter()
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - any import failure is a finding
            rows[module_name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
            if required:
                rec.check(f"import {module_name}", False, rows[module_name]["error"])
            else:
                error = rows[module_name]["error"]
                rec.note(f"optional/candidate '{module_name}' not importable: {error}")
            continue
        elapsed = round((time.perf_counter() - start) * 1000)
        loaded[module_name] = module
        rows[module_name] = {"ok": True, "version": version_of(dist, module), "import_ms": elapsed}
        rec.check(f"import {module_name}", True, f"{rows[module_name]['version']} ({elapsed} ms)")
    rec.extra["imports"] = rows

    paddle = loaded.get("paddle")
    if paddle is not None:
        try:
            compiled_cuda = bool(paddle.is_compiled_with_cuda())
            rec.measure("paddle_compiled_with_cuda", compiled_cuda)
            rec.measure("paddle_device", str(paddle.device.get_device()))
            rec.check(
                "PaddlePaddle is a CPU build (approved OCR backend is CPU)",
                not compiled_cuda,
                "a CUDA build was installed" if compiled_cuda else "CPU build",
            )
        except Exception as exc:  # noqa: BLE001
            rec.check("PaddlePaddle device query", False, f"{type(exc).__name__}: {exc}")

    torch = loaded.get("torch")
    if torch is not None:
        try:
            rec.measure("torch_cuda_available", bool(torch.cuda.is_available()))
            rec.measure("torch_num_threads", int(torch.get_num_threads()))
            rec.note(
                "NLLB is approved for CPU. torch_cuda_available is informational: W4 forces CPU "
                "so the game keeps the GPU."
            )
        except Exception as exc:  # noqa: BLE001
            rec.check("torch device query", False, f"{type(exc).__name__}: {exc}")

    qt = loaded.get("PySide6")
    if qt is not None:
        try:
            from PySide6 import QtCore  # noqa: PLC0415

            rec.measure("qt_version", QtCore.qVersion())
        except Exception as exc:  # noqa: BLE001
            rec.check("PySide6 QtCore import", False, f"{type(exc).__name__}: {exc}")

    rec.note(
        "Pins are NOT decided here. M0-09 pins versions only after W2-W8 pass on this machine."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
