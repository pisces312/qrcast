#!/usr/bin/env python
"""CLI entry: V1 grid-based verifier (fixed ver 32 layout)."""

import sys
sys.path.insert(0, "..")

from qrcast.bw.v1.verifier_grid import verify_qr_codes

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V1 grid-based QR verifier")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./verify_output", help="Output directory")
    args = parser.parse_args()
    verify_qr_codes(args.input_dir, args.output_dir)
