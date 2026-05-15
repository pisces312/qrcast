#!/usr/bin/env python
"""CLI entry: Display QR canvas images via OpenCV fullscreen window.

Works with both B&W and RGB QR canvases.
"""

import sys

from qrcast.common import display_canvases

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Display QR canvas images at a configurable interval")
    parser.add_argument("image_dir", nargs="?", default="./tmp", help="Directory containing canvas images")
    parser.add_argument("-i", "--interval", type=float, default=2, help="Display interval in seconds (default: 2)")
    parser.add_argument("-p", "--pattern", default="qrcode_*.png", help="Glob pattern for canvas files")
    args = parser.parse_args()

    display_canvases(args.image_dir, display_sec=args.interval, pattern=args.pattern)
