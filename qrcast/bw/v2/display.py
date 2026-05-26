"""Display individual QR code images for phone-side receiving.

Reads QR images from the {filename_base}-individual/ output directory
and displays them one by one at a specified interval in a fullscreen window.

Usage:
    python -m qrcast.bw.v2.display <image_dir> [options]
    python -m qrcast.bw.v2.display ./tmp/myfile-individual -i 0.5
"""

import argparse
import glob
import os
import time

import cv2
import numpy as np
from PIL import Image


def _make_countdown_frame(text, width, height):
    """Create a black frame with centered white text."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = min(width, height) / 200
    thickness = max(1, int(font_scale * 3))
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = (width - tw) // 2
    y = (height + th) // 2
    cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return frame


def display_individual_qr(image_dir, interval=0.5, pattern="qr_*.png", window_name="QRCast Sender", fullscreen=True, end_pause=3):
    """Display individual QR images one by one.

    Args:
        image_dir: Directory containing individual QR images.
        interval: Seconds to show each image.
        pattern: Glob pattern for QR image files.
        window_name: Title of the OpenCV window.
        fullscreen: If True, display fullscreen; if False, display at original image size.
        end_pause: Seconds to keep the last image after playback finishes.
    """
    files = sorted(glob.glob(os.path.join(image_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' found in {image_dir}")
        return

    total = len(files)
    print(f"Found {total} QR images in {image_dir}")
    print(f"Display interval: {interval}s per image (~{total * interval:.1f}s total)")
    print("Press 'q' to quit, any other key to advance immediately.\n")

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    if fullscreen:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    else:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)

    # Countdown 3-2-1 before starting
    screen_w = cv2.getWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN)  # just to get window
    # Use a reasonable canvas size for countdown text
    first_img = cv2.imread(files[0])
    if first_img is not None:
        ch, cw = first_img.shape[:2]
    else:
        cw, ch = 800, 600

    for count in range(3, 0, -1):
        frame = _make_countdown_frame(str(count), cw, ch)
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1000) & 0xFF
        if key == ord("q"):
            cv2.destroyAllWindows()
            print("Quit by user during countdown.")
            return

    start_time = time.monotonic()
    last_idx = 0

    for idx, filepath in enumerate(files):
        img = cv2.imread(filepath)
        if img is None:
            print(f"Warning: could not read {filepath}, skipping")
            continue

        last_idx = idx
        elapsed = time.monotonic() - start_time
        print(f"[{idx + 1}/{total}] {os.path.basename(filepath)}  (elapsed: {elapsed:.1f}s)")

        cv2.imshow(window_name, img)
        key = cv2.waitKey(int(interval * 1000)) & 0xFF
        if key == ord("q"):
            print("Quit by user.")
            break
    else:
        # Finished all images normally — pause on last frame
        if end_pause > 0:
            print(f"\nHolding last image for {end_pause}s...")
            cv2.waitKey(int(end_pause * 1000))

    cv2.destroyAllWindows()
    total_elapsed = time.monotonic() - start_time
    print(f"\n[OK] Display finished. {last_idx + 1}/{total} images shown in {total_elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display individual QR images for phone-side receiving")
    parser.add_argument("image_dir", help="Directory containing QR images (e.g. ./tmp/myfile-individual)")
    parser.add_argument("-i", "--interval", type=float, default=0.5,
                        help="Seconds per image (default: 0.5)")
    parser.add_argument("-p", "--pattern", default="qr_*.png",
                        help="Glob pattern for QR files (default: qr_*.png)")
    parser.add_argument("--no-fullscreen", action="store_true",
                        help="Display at original image size instead of fullscreen")
    parser.add_argument("--end-pause", type=float, default=3,
                        help="Seconds to hold the last image after playback (default: 3)")
    args = parser.parse_args()

    display_individual_qr(args.image_dir, interval=args.interval, pattern=args.pattern,
                          fullscreen=not args.no_fullscreen, end_pause=args.end_pause)
