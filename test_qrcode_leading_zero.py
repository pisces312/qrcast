#!/usr/bin/env python3
"""Test qrcode library for leading-zero polynomial bug (ValueError: glog(0)).

This script constructs a payload that reliably triggers the bug in qrcode <= 8.2
when encoding certain binary data patterns. Use it to verify whether a qrcode
version upgrade fixes the issue.

Usage:
    python test_qrcode_leading_zero.py

Exit codes:
    0 - Bug is FIXED (no error)
    1 - Bug STILL PRESENT (ValueError: glog(0))
    2 - Other unexpected error
"""

import sys

from qrcode.constants import ERROR_CORRECT_M
from qrcode.main import QRCode


def make_mono_qr(data_bytes, version=32):
    """Generate a mono QR code from raw bytes."""
    qr = QRCode(
        version=version,
        error_correction=ERROR_CORRECT_M,
        box_size=3,
        border=4,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    img = qr.make_image()
    return img


def build_problematic_payload():
    """Build a payload that triggers glog(0) in unpatched qrcode 8.2.

    The bug is triggered when the Reed-Solomon polynomial gets a leading-zero
    coefficient during encoding. This happens with certain binary data patterns,
    especially PE/exe file headers which contain many 0x00 bytes.

    This payload mimics the structure that caused the crash:
    [seq(4B)][total(4B)][data_len(2B)][chunk_data]
    where chunk_data starts with a PE-like header (MZ + zeros).
    """
    seq = (0).to_bytes(4, "big")
    total = (11).to_bytes(4, "big")
    data_len = (4604).to_bytes(2, "big")

    # PE-like header: starts with MZ followed by many zeros
    pe_header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    chunk_data = pe_header + b"\x00" * (4604 - len(pe_header))

    payload = seq + total + data_len + chunk_data

    # Pad to multiple of 3 for RGB split
    pad_len = (3 - len(payload) % 3) % 3
    padded = payload + b"\x00" * pad_len
    chunk_size = len(padded) // 3

    # The first channel gets the bytes most likely to trigger the bug
    r_data = padded[:chunk_size]
    return r_data


def main():
    print("Testing qrcode library for leading-zero polynomial bug...")
    print(f"qrcode module: {QRCode.__module__}")

    test_data = build_problematic_payload()
    print(f"Test data size: {len(test_data)} bytes")
    print(f"First 32 bytes: {test_data[:32]}")

    try:
        img = make_mono_qr(test_data)
        print(f"\nResult: SUCCESS - QR code generated ({img.size[0]}x{img.size[1]})")
        print("The bug is FIXED in this qrcode version.")
        return 0

    except ValueError as e:
        if "glog(0)" in str(e):
            print(f"\nResult: FAIL - ValueError: {e}")
            print("The bug is STILL PRESENT in this qrcode version.")
            return 1
        raise

    except Exception as e:
        print(f"\nResult: UNEXPECTED ERROR - {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
