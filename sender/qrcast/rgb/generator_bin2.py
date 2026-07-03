"""V3 RGB QR code generator v2 (configurable version 1-40).

File -> optional 7z compress -> chunk -> raw binary into 3 QR channels -> RGB canvases (PNG).

Uses qrgb's color rendering to encode raw bytes into 3 color channels (R, G, B).
Each channel carries raw binary via QR byte mode — no base64 overhead.

Payload format v2:
  Fixed Header (12B): [seq(4B)][total(4B)][data_len(2B)][proto_ver(1B)][flags(1B)]
  Data Segment:
    - seq==0: [filename_len(1B)][filename(N B)][file_crc32(4B)][file_size(4B)][chunk_data(M B)]
    - seq>0:  [chunk_data(M B)]

proto_ver = 0x02, flags bit0 = 7z compressed.
"""

import argparse
import math
import os
import zlib

import numpy as np
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M
from qrcode.main import QRCode

from qrcast.common import CANVAS_W, CANVAS_H, BOX_SIZE, BORDER, file_to_7z_bytes

# qrgb is required for generation
try:
    from qrgb.qrgb import render_color, QR_CAPACITIES
except ImportError as e:
    raise ImportError("qrgb library is required for V3 generation. Install: pip install qrgb") from e

ERROR_M = ERROR_CORRECT_M


class QRConfig:
    """QR generation config derived from a given QR version."""

    def __init__(self, ver=20):
        if not 1 <= ver <= 40:
            raise ValueError(f"QR version must be 1-40, got {ver}")
        if ver not in QR_CAPACITIES:
            raise ValueError(f"QR version {ver} not supported by qrgb (available: {list(QR_CAPACITIES.keys())})")
        self.ver = ver
        self.channel_capacity = QR_CAPACITIES[ver]
        self.cell_size = (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE
        self.rows = math.floor(CANVAS_H / self.cell_size)
        self.cols = math.floor(CANVAS_W / self.cell_size)
        self.qr_per_image = self.rows * self.cols
        self.header_len = 12  # seq(4) + total(4) + data_len(2) + proto_ver(1) + flags(1)
        self.data_per_qr = self.channel_capacity * 3 - self.header_len

    def print_config(self):
        print(f"QR version: {self.ver}")
        print(f"CELL_SIZE: {self.cell_size}, ROWS: {self.rows}, COLS: {self.cols}, QR_PER_IMAGE: {self.qr_per_image}")
        print(f"CHANNEL_CAPACITY: {self.channel_capacity}, DATA_PER_QR: {self.data_per_qr}")


def make_mono_qr(data_bytes, version):
    """Generate a mono (black/white) QR code image from raw bytes."""
    qr = QRCode(
        version=version,
        error_correction=ERROR_M,
        box_size=BOX_SIZE,
        border=BORDER,
    )
    qr.add_data(data_bytes)
    qr.make(fit=True)
    img = qr.make_image()
    img = img.convert("L").point(lambda p: 0 if p < 128 else 255)
    return img


def make_rgb_qr_image(payload_bytes, version):
    """Create an RGB QR code PIL image from raw binary payload."""
    pad_len = (3 - len(payload_bytes) % 3) % 3
    padded = payload_bytes + b"\x00" * pad_len
    chunk_size = len(padded) // 3

    r_data = padded[:chunk_size]
    g_data = padded[chunk_size:2 * chunk_size]
    b_data = padded[2 * chunk_size:]

    r_img = make_mono_qr(r_data, version)
    g_img = make_mono_qr(g_data, version)
    b_img = make_mono_qr(b_data, version)

    r_arr = np.array(r_img)
    g_arr = np.array(g_img)
    b_arr = np.array(b_img)

    height, width = r_arr.shape
    color_img = np.zeros((height, width, 3), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            color_img[y, x] = render_color(r_arr[y, x], g_arr[y, x], b_arr[y, x])

    print(f"  RGB QR: version={version}, size={width}x{height}, payload={len(payload_bytes)} bytes")
    return Image.fromarray(color_img)


def make_canvas(qr_images, qr_cfg):
    """Tile RGB QR images into a canvas."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    for idx, img in enumerate(qr_images):
        row = idx // qr_cfg.cols
        col = idx % qr_cfg.cols
        x = col * qr_cfg.cell_size
        y = row * qr_cfg.cell_size
        canvas.paste(img, (x, y))
    return canvas


def build_payload(seq, total, flags, chunk_data, filename=None, file_crc32=None, file_size=None):
    """Build v2 payload bytes."""
    seq_b = seq.to_bytes(4, "big", signed=False)
    total_b = total.to_bytes(4, "big", signed=False)
    proto_ver_b = b"\x02"
    flags_b = flags.to_bytes(1, "big", signed=False)

    if seq == 0:
        # meta segment: [filename_len(1B)][filename][crc32(4B)][size(4B)][chunk_data]
        filename_bytes = filename.encode("utf-8") if filename else b""
        if len(filename_bytes) > 255:
            filename_bytes = filename_bytes[:255]
        meta = (
            len(filename_bytes).to_bytes(1, "big", signed=False)
            + filename_bytes
            + file_crc32.to_bytes(4, "big", signed=False)
            + file_size.to_bytes(4, "big", signed=False)
        )
        data_segment = meta + chunk_data
    else:
        data_segment = chunk_data

    data_len = len(data_segment)
    data_len_b = data_len.to_bytes(2, "big", signed=False)

    payload = seq_b + total_b + data_len_b + proto_ver_b + flags_b + data_segment
    return payload


def generate_qrgb_bin_images(file_path, ver=20, base_dir="./tmp", compress=False):
    if not os.path.exists(file_path):
        print("File not found!")
        return

    qr_cfg = QRConfig(ver)
    qr_cfg.print_config()

    os.makedirs(base_dir, exist_ok=True)

    # Read original file
    with open(file_path, "rb") as f:
        original_bytes = f.read()

    original_size = len(original_bytes)
    original_crc = zlib.crc32(original_bytes) & 0xFFFFFFFF
    filename = os.path.basename(file_path)

    # Optional 7z compression
    if compress:
        file_bytes = file_to_7z_bytes(file_path)
    else:
        file_bytes = original_bytes

    # Chunk size for seq>0
    data_per_qr = qr_cfg.data_per_qr

    # seq=0 meta overhead: filename_len(1) + filename(N) + crc32(4) + file_size(4)
    filename_bytes = filename.encode("utf-8")
    if len(filename_bytes) > 255:
        filename_bytes = filename_bytes[:255]
    meta_overhead = 1 + len(filename_bytes) + 4 + 4

    # Split file into chunks
    chunks = []
    offset = 0
    seq = 0
    while offset < len(file_bytes):
        if seq == 0:
            chunk_size = data_per_qr - meta_overhead
        else:
            chunk_size = data_per_qr
        chunk = file_bytes[offset:offset + chunk_size]
        chunks.append(chunk)
        offset += chunk_size
        seq += 1

    total_chunks = len(chunks)
    total_images = math.ceil(total_chunks / qr_cfg.qr_per_image)

    print(f"{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
    print(f"Original size: {original_size} bytes, CRC32: {original_crc:08X}")
    print(f"Total chunks: {total_chunks}, total canvases: {total_images}")

    flags = 0x01 if compress else 0x00

    for img_idx in range(total_images):
        print(f"\nGenerating canvas {img_idx + 1}/{total_images}")
        current_qrs = []

        for qr_idx_in_img in range(qr_cfg.qr_per_image):
            chunk_idx = img_idx * qr_cfg.qr_per_image + qr_idx_in_img
            if chunk_idx >= total_chunks:
                break

            chunk_data = chunks[chunk_idx]
            payload = build_payload(
                seq=chunk_idx,
                total=total_chunks,
                flags=flags,
                chunk_data=chunk_data,
                filename=filename if chunk_idx == 0 else None,
                file_crc32=original_crc if chunk_idx == 0 else None,
                file_size=original_size if chunk_idx == 0 else None,
            )

            print(f"Chunk {chunk_idx}: {len(chunk_data)} raw bytes, "
                  f"payload: {len(payload)} bytes (max {qr_cfg.channel_capacity * 3})")

            qr_img = make_rgb_qr_image(payload, qr_cfg.ver)
            current_qrs.append(qr_img)

        canvas = make_canvas(current_qrs, qr_cfg)
        output_path = os.path.join(base_dir, f"qrcode_{img_idx + 1:03d}.png")
        canvas.save(output_path)
        print(f"Saved: {output_path}")

    print(f"\n[OK] All {total_images} canvas images generated in {base_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate V3 RGB QR code canvases v2 (with filename + CRC)")
    parser.add_argument("file_path", help="Path to file to encode")
    parser.add_argument("--ver", type=int, default=20, help="QR version (1-40, default: 20)")
    parser.add_argument("--output-dir", default="./tmp", help="Output directory")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    args = parser.parse_args()
    generate_qrgb_bin_images(
        file_path=args.file_path,
        ver=args.ver,
        base_dir=args.output_dir,
        compress=args.compress,
    )
