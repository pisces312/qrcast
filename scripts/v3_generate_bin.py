#!/usr/bin/env python
"""CLI entry: Generate V3 RGB QR canvases (raw binary payload)."""

import sys

from qrcast.v3.generator_bin import generate_qrgb_bin_images

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases (raw binary)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    args = parser.parse_args()
    generate_qrgb_bin_images(args.file_path, base_dir=args.output_dir)
