#!/usr/bin/env python
"""CLI entry: V3 RGB QR verifier (raw binary payload)."""

import sys
sys.path.insert(0, "..")

from qrcast.v3.verifier_bin import verify_qrgb_bin

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V3 RGB QR verifier (raw binary)")
    parser.add_argument("input_dir", nargs="?", default="./tmp", help="Input directory")
    parser.add_argument("output_dir", nargs="?", default="./tmp/qrgb_bin_verify_output", help="Output directory")
    args = parser.parse_args()

    print("=" * 50)
    print("QRCast V3 RGB QR Verifier (raw binary)")
    print("=" * 50)
    print(f"Input:  {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print("=" * 50)

    success = verify_qrgb_bin(args.input_dir, args.output_dir)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
