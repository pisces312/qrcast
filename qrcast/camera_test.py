"""Test script for camera image capture.

Usage:
    python -m qrcast.camera_test              # default camera index 0
    python -m qrcast.camera_test --camera 1   # specify camera index
    python -m qrcast.camera_test --save       # save captured frames to disk

Controls:
    S - save current frame as PNG
    Q / ESC - quit
"""

import cv2
import argparse
import os
import time


def test_camera_open(camera_index=0):
    """Test whether the camera can be opened."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[FAIL] Cannot open camera {camera_index}")
        return None
    print(f"[OK] Camera {camera_index} opened")
    return cap


def test_camera_properties(cap):
    """Read and print camera properties."""
    props = {
        "Width": cv2.CAP_PROP_FRAME_WIDTH,
        "Height": cv2.CAP_PROP_FRAME_HEIGHT,
        "FPS": cv2.CAP_PROP_FPS,
        "Backend": cv2.CAP_PROP_BACKEND,
        "Brightness": cv2.CAP_PROP_BRIGHTNESS,
        "Contrast": cv2.CAP_PROP_CONTRAST,
        "Auto Exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
    }
    print("\n[INFO] Camera properties:")
    for name, prop_id in props.items():
        val = cap.get(prop_id)
        print(f"  {name}: {val}")


def test_single_capture(cap):
    """Test capturing a single frame."""
    ret, frame = cap.read()
    if not ret or frame is None:
        print("[FAIL] Failed to capture frame")
        return None
    h, w = frame.shape[:2]
    channels = frame.shape[2] if len(frame.shape) == 3 else 1
    print(f"[OK] Captured frame: {w}x{h}, channels={channels}, dtype={frame.dtype}")
    return frame


def test_continuous_capture(cap, duration_sec=3):
    """Test continuous capture for a few seconds and report FPS."""
    print(f"\n[INFO] Testing continuous capture for {duration_sec}s...")
    count = 0
    failures = 0
    start = time.time()

    while time.time() - start < duration_sec:
        ret, frame = cap.read()
        if ret and frame is not None:
            count += 1
        else:
            failures += 1

    elapsed = time.time() - start
    fps = count / elapsed if elapsed > 0 else 0
    print(f"[OK] Captured {count} frames in {elapsed:.2f}s ({fps:.1f} FPS)")
    if failures:
        print(f"[WARN] {failures} failed reads during capture")
    return fps


def test_save_frame(frame, output_dir="./test_capture_output"):
    """Test saving a frame to disk."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"capture_{timestamp}.png")
    ok = cv2.imwrite(path, frame)
    if ok:
        size_kb = os.path.getsize(path) / 1024
        print(f"[OK] Frame saved: {path} ({size_kb:.1f} KB)")
    else:
        print(f"[FAIL] Could not write image to {path}")
    return ok


def interactive_preview(cap, auto_save=False, output_dir="./test_capture_output"):
    """Live preview window. Press S to save, Q/ESC to quit."""
    print("\n[INFO] Live preview - press S to save, Q/ESC to quit")
    save_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame read failed, retrying...")
            continue

        h, w = frame.shape[:2]
        info = f"{w}x{h}"
        cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow("Camera Capture Test", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break
        elif key == ord("s"):
            test_save_frame(frame, output_dir)
            save_count += 1

    print(f"[INFO] Preview ended. Saved {save_count} frame(s).")


def main():
    parser = argparse.ArgumentParser(description="Test camera image capture")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--save", action="store_true", help="Auto-save a test frame")
    parser.add_argument("--no-preview", action="store_true", help="Skip live preview")
    parser.add_argument("--duration", type=float, default=3, help="Continuous capture test duration in seconds")
    args = parser.parse_args()

    print("=" * 50)
    print("  Camera Capture Test")
    print("=" * 50)

    cap = test_camera_open(args.camera)
    if cap is None:
        return

    try:
        test_camera_properties(cap)

        print()
        frame = test_single_capture(cap)
        if frame is None:
            return

        test_continuous_capture(cap, duration_sec=args.duration)

        if args.save:
            print()
            test_save_frame(frame)

        if not args.no_preview:
            interactive_preview(cap)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n[OK] Camera released. Done.")


if __name__ == "__main__":
    main()
