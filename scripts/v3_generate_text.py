#!/usr/bin/env python
"""CLI entry: Generate V3 RGB QR canvases (base64 text payload)."""

import sys

from qrcast.v3.generator_text import generate_qrgb_images

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases (base64 text)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress file with 7z before encoding")
    args = parser.parse_args()
    generate_qrgb_images(args.file_path, base_dir=args.output_dir, compress=args.compress)
