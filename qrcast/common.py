"""Common utilities shared across all qrcast modules.

Includes:
- Canvas display (OpenCV fullscreen)
- 7z compression helper
- Payload parsing (seq/total/header)
- Constants shared by all versions
"""

import glob
import os

import cv2
import py7zr

# ===================== qrcode library bug fix =====================
# qrcode >=8.2 has a bug where Polynomial.__mod__ doesn't handle leading
# zero coefficients in Reed-Solomon encoding, causing ValueError: glog(0)
# when encoding certain binary data patterns. This patch strips leading zeros
# before the Galois field division, which is the mathematically correct behavior.
try:
    from qrcode import base as _qrcode_base

    _orig_mod = _qrcode_base.Polynomial.__mod__

    def _patched_mod(self, other):
        num = self.num[:]
        while len(num) > 0 and num[0] == 0:
            num.pop(0)
        if len(num) == 0:
            return _qrcode_base.Polynomial([0], 0)
        if len(num) < len(other):
            return _qrcode_base.Polynomial(num, 0)
        self = _qrcode_base.Polynomial(num, 0)

        difference = len(self) - len(other)
        if difference < 0:
            return self
        ratio = _qrcode_base.glog(self[0]) - _qrcode_base.glog(other[0])
        new_num = [
            item ^ _qrcode_base.gexp(_qrcode_base.glog(other_item) + ratio)
            for item, other_item in zip(self, other)
        ]
        if difference:
            new_num.extend(self[-difference:])
        return _qrcode_base.Polynomial(new_num, 0) % other

    _qrcode_base.Polynomial.__mod__ = _patched_mod
except Exception:
    pass  # If qrcode isn't installed or API changes, ignore silently

# ===================== Shared Constants =====================
CANVAS_W = 1850
CANVAS_H = 1000
BOX_SIZE = 3
BORDER = 4
HEADER_LEN = 8  # seq(4B) + total(4B)

# ===================== Display =====================
DEFAULT_DISPLAY_SEC = 2


def display_canvases(image_dir, display_sec=DEFAULT_DISPLAY_SEC, pattern="qrcode_*.png", window_name="QRCast Sender"):
    """Display saved canvas PNGs via OpenCV fullscreen window.

    Args:
        image_dir: Directory containing canvas images.
        display_sec: Seconds to show each image.
        pattern: Glob pattern for canvas files.
        window_name: Title of the OpenCV window.
    """
    files = sorted(glob.glob(os.path.join(image_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' found in {image_dir}")
        return

    print(f"Found {len(files)} canvas images in {image_dir}")
    print(f"Display interval: {display_sec} seconds")
    print("Press 'q' to quit, any other key to advance immediately.\n")

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    for idx, filepath in enumerate(files):
        img = cv2.imread(filepath)
        if img is None:
            print(f"Warning: could not read {filepath}, skipping")
            continue

        print(f"Displaying {idx + 1}/{len(files)}: {os.path.basename(filepath)}")
        cv2.imshow(window_name, img)
        key = cv2.waitKey(int(display_sec * 1000)) & 0xFF
        if key == ord("q"):
            print("Quit by user.")
            break

    cv2.destroyAllWindows()
    print("\n[OK] Display finished.")


# ===================== Compression =====================

def file_to_7z_bytes(file_path):
    """Compress a file with 7z (LZMA2 preset 9) and return bytes.

    Args:
        file_path: Path to the file to compress.

    Returns:
        Compressed file bytes.
    """
    print(f"Compressing file: {file_path} (max compression)")
    temp_path = file_path + ".7z"
    with py7zr.SevenZipFile(
        file=temp_path,
        mode="w",
        filters=[{"id": py7zr.FILTER_LZMA2, "preset": 9}],
        password=None,
    ) as archive:
        archive.write(file_path, arcname=os.path.basename(file_path))
    with open(temp_path, "rb") as f:
        result = f.read()
    os.unlink(temp_path)
    return result


# ===================== Payload Parsing =====================

def parse_payload(data_bytes):
    """Parse QR code payload: [seq(4B big-endian)][total(4B big-endian)][payload].

    Args:
        data_bytes: Raw bytes decoded from a QR code.

    Returns:
        (seq, total, payload) or (None, None, None) if too short.
    """
    if len(data_bytes) < 8:
        return None, None, None
    seq = int.from_bytes(data_bytes[0:4], "big", signed=False)
    total = int.from_bytes(data_bytes[4:8], "big", signed=False)
    payload = data_bytes[8:]
    return seq, total, payload


if __name__ == "__main__":
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Display QR canvas images via OpenCV fullscreen window")
    parser.add_argument("image_dir", nargs="?", default="./tmp", help="Directory containing canvas images")
    parser.add_argument("-i", "--interval", type=float, default=2, help="Display interval in seconds (default: 2)")
    parser.add_argument("-p", "--pattern", default="qrcode_*.png", help="Glob pattern for canvas files")
    args = parser.parse_args()
    display_canvases(args.image_dir, display_sec=args.interval, pattern=args.pattern)
