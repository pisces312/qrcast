#!/usr/bin/env python
"""CLI entry: Generic B&W QR verifier (V1 & V2 compatible, whole-image decode)."""

import sys
sys.path.insert(0, "..")

from qrcast.bw.verifier import verify

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generic B&W QR verifier (whole-image decode)")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./tmp/verify_output", help="Output directory")
    args = parser.parse_args()

    print("=" * 50)
    print("QRCast Verifier - Whole Image Decode")
    print("=" * 50)
    print(f"Input:  {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print("=" * 50)

    success = verify(args.input_dir, args.output_dir)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
