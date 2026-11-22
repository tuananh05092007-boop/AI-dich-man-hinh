"""W2 - DXGI Desktop Duplication capture smoke test (candidate binding: ``dxcam``).

    uv run python scripts/windows_tests/W2_dxgi_capture.py --seconds 10
    uv run python scripts/windows_tests/W2_dxgi_capture.py --roi 200,800,1400,1000 --monitor 0

Keep something moving on screen while it runs (play a video or drag a window): DXGI Desktop
Duplication returns no new frame for a static screen, so a static desktop shows up here as many
``None`` grabs. That is expected behaviour, not an error, and is reported separately.

What is measured: grab latency (median/p95/max), delivered frames per second, None-frame ratio,
frame shape versus the requested size, an all-black check, and ROI versus full-frame cost.
Nothing is written to disk unless ``--save-sample`` is given (screens can contain private content).

Run it three ways and keep all three reports: desktop, a Windowed/Borderless game, and (separately)
a Fullscreen Exclusive game. Exclusive fullscreen is *not* assumed to work.
"""

import argparse
import sys
import time

from _common import Recorder, require_windows, stats


def parse_roi(text: str | None) -> tuple[int, int, int, int] | None:
    if not text:
        return None
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4 or parts[2] <= parts[0] or parts[3] <= parts[1]:
        raise SystemExit("--roi must be left,top,right,bottom with right>left and bottom>top")
    return (parts[0], parts[1], parts[2], parts[3])


def grab_loop(camera, seconds: float, region=None) -> dict:
    latencies: list[float] = []
    none_count = 0
    black = 0
    shapes: set[tuple[int, ...]] = set()
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        start = time.perf_counter()
        frame = camera.grab(region=region) if region else camera.grab()
        latencies.append((time.perf_counter() - start) * 1000)
        if frame is None:
            none_count += 1
            continue
        shapes.add(tuple(frame.shape))
        if int(frame.max()) == 0:
            black += 1
    frames = len(latencies) - none_count
    return {
        "calls": len(latencies),
        "frames": frames,
        "none": none_count,
        "black_frames": black,
        "shapes": sorted(shapes),
        "latency_ms": stats(latencies),
        "frames_per_second": round(frames / seconds, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--monitor", type=int, default=0, help="dxcam output index")
    parser.add_argument("--device", type=int, default=0, help="dxcam GPU adapter index")
    parser.add_argument("--roi", help="left,top,right,bottom in monitor pixels")
    parser.add_argument("--target-fps", type=int, default=30)
    parser.add_argument("--label", default="desktop", help="e.g. desktop, game-borderless")
    parser.add_argument("--save-sample", action="store_true", help="write one PNG (may be private)")
    args = parser.parse_args()

    rec = Recorder("W2", f"DXGI capture smoke test [{args.label}]")
    print(f"W2 - DXGI capture [{args.label}]")
    if not require_windows(rec):
        return rec.finish()
    try:
        import dxcam
    except Exception as exc:  # noqa: BLE001
        rec.check("import dxcam", False, f"{type(exc).__name__}: {exc}")
        rec.note("dxcam is a candidate binding only; another DXGI binding may be evaluated.")
        return rec.finish()

    rec.measure("label", args.label)
    try:
        rec.measure("dxcam_output_info", str(dxcam.output_info()))
        rec.measure("dxcam_device_info", str(dxcam.device_info()))
    except Exception as exc:  # noqa: BLE001
        rec.note(f"could not list outputs: {type(exc).__name__}: {exc}")

    roi = parse_roi(args.roi)
    camera = None
    try:
        camera = dxcam.create(device_idx=args.device, output_idx=args.monitor, output_color="BGR")
        rec.check("dxcam.create succeeded", camera is not None)
        if camera is None:
            return rec.finish()

        full = grab_loop(camera, args.seconds)
        rec.extra["full_frame"] = full
        rec.measure("full_frame_grab_latency_ms", full["latency_ms"])
        rec.measure("full_frame_frames_per_second", full["frames_per_second"], "fps")
        rec.measure("full_frame_none_ratio", round(full["none"] / max(full["calls"], 1), 3))
        rec.measure("full_frame_shapes", full["shapes"])
        rec.check("received at least one frame", full["frames"] > 0, f"{full['frames']} frames")
        rec.check(
            "frames are not all black",
            full["frames"] > 0 and full["black_frames"] < full["frames"],
            f"{full['black_frames']} of {full['frames']} frames all-zero",
        )
        if full["frames"] == 0:
            rec.note(
                "No frames: screen may be static (move something) or the target uses an "
                "unsupported mode (e.g. Fullscreen Exclusive). Record this as a finding."
            )

        if roi:
            region = grab_loop(camera, args.seconds, region=roi)
            rec.extra["roi"] = {"box": roi, **region}
            width, height = roi[2] - roi[0], roi[3] - roi[1]
            rec.measure("roi_grab_latency_ms", region["latency_ms"])
            rec.measure("roi_frames_per_second", region["frames_per_second"], "fps")
            rec.check(
                "ROI frame shape equals requested size",
                bool(region["shapes"]) and all(s[:2] == (height, width) for s in region["shapes"]),
                f"expected {(height, width)}, got {region['shapes']}",
            )
        else:
            rec.note("No --roi given; ROI cost versus full frame was not measured.")

        # Capture-thread mode: what a real pipeline would use (latest-frame semantics).
        try:
            if roi:
                camera.start(target_fps=args.target_fps, region=roi)
            else:
                camera.start(target_fps=args.target_fps)
            delivered = 0
            last = None
            end = time.perf_counter() + min(args.seconds, 5.0)
            while time.perf_counter() < end:
                frame = camera.get_latest_frame()
                if frame is not None and frame is not last:
                    delivered += 1
                    last = frame
                time.sleep(0.002)
            camera.stop()
            rec.measure("capture_thread_distinct_frames", delivered)
            rec.check("capture-thread mode delivered frames", delivered > 0)
        except Exception as exc:  # noqa: BLE001
            rec.check("capture-thread mode", False, f"{type(exc).__name__}: {exc}")

        if args.save_sample:
            try:
                import cv2

                frame = camera.grab(region=roi) if roi else camera.grab()
                if frame is not None:
                    cv2.imwrite(f"W2_sample_{args.label}.png", frame)
                    rec.note(f"saved W2_sample_{args.label}.png - may contain private content")
            except Exception as exc:  # noqa: BLE001
                rec.note(f"sample not saved: {type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001
        rec.check("capture run", False, f"{type(exc).__name__}: {exc}")
    finally:
        if camera is not None:
            try:
                camera.release()
            except Exception:  # noqa: BLE001, S110
                pass

    rec.note(
        "Not covered here (manual): device loss/reset after alt-tab or resolution change, "
        "multi-monitor capture of the second monitor (re-run with --monitor 1), and "
        "Fullscreen Exclusive (re-run with --label game-exclusive and report what happens)."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
