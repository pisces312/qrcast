#!/usr/bin/env python
"""CLI entry: Quick single-file QR sender (small files, V2 ver40)."""

import sys
sys.path.insert(0, "..")

from qrcast.bw.v2.quick_sender import send_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Quick single-file QR sender (small files only)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--minify", action="store_true", help="Minify .py files before encoding")
    args = parser.parse_args()
    send_file(args.file_path, minify=args.minify)
