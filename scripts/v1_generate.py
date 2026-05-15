#!/usr/bin/env python
"""CLI entry: Generate V1 B&W QR code canvases (fixed ver 32)."""

import sys

from qrcast.bw.v1.generator import generate_qr_images

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate V1 B&W QR code canvases (fixed ver 32)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    parser.add_argument("--save-chunks", action="store_true", help="Save individual QR chunk images")
    args = parser.parse_args()
    generate_qr_images(
        file_path=args.file_path,
        base_dir=args.output_dir,
        compress=args.compress,
        save_chunks=args.save_chunks,
    )
