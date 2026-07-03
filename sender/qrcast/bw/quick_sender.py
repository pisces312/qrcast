"""Quick single-file QR sender (configurable QR version 1-40).

Designed for small files like Python scripts. Only produces a single QR code.
Truncates data if it exceeds capacity. Optionally minifies Python scripts first.
"""

import os
import cv2
import numpy as np
import argparse
from qrcode.main import QRCode
from qrcode.constants import ERROR_CORRECT_L

from qrcast.pyminify import minify_python
from qrcast.bw.generator import calc_qr_max_bytes

# ===================== Config =====================
BOX_SIZE = 3
BORDER = 4
DEFAULT_VER = 40


def make_qr(data_bytes, ver):
    qr = QRCode(
        version=ver,
        error_correction=ERROR_CORRECT_L,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    print(f"  QR version: {qr.version}, modules: {qr.modules_count}x{qr.modules_count}")
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def send_file(file_path, minify=False, ver=DEFAULT_VER):
    """Display a single QR code for a small file.

    Args:
        file_path: Path to the file to send.
        minify: If True and file is .py, minify before encoding.
        ver: QR version (1-40). Higher = larger QR = more bytes per frame.
    """
    if not 1 <= ver <= 40:
        raise ValueError(f"QR version must be 1-40, got {ver}")

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    file_size = len(file_bytes)
    print(f"File: {file_path} ({file_size} bytes)")

    if minify and file_path.endswith(".py"):
        minified = minify_python(file_bytes.decode("utf-8")).encode("utf-8")
        saved = file_size - len(minified)
        print(f"Minified: {len(minified)} bytes (saved {saved} bytes, {saved * 100 // file_size}%)")
        file_bytes = minified
        file_size = len(file_bytes)

    qr_max_bytes = calc_qr_max_bytes(ver)
    print(f"QR version {ver} max capacity: {qr_max_bytes} bytes")

    if file_size > qr_max_bytes:
        print(f"Warning: data ({file_size} bytes) exceeds capacity ({qr_max_bytes} bytes), truncating.")
        file_bytes = file_bytes[:qr_max_bytes]

    qr_img = make_qr(file_bytes, ver)
    qr_cv = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)

    cv2.namedWindow("QRCast Quick Sender", cv2.WINDOW_AUTOSIZE)
    cv2.imshow("QRCast Quick Sender", qr_cv)
    print("Displaying — press any key to close.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    print("[OK] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quick single-file QR sender (small files only)")
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--minify", action="store_true", help="Minify .py files before encoding")
    parser.add_argument("--ver", type=int, default=DEFAULT_VER, help="QR version (1-40, default: 40)")
    args = parser.parse_args()
    send_file(args.file_path, minify=args.minify, ver=args.ver)
