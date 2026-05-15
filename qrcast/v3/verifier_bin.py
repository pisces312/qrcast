"""V3 RGB QR code verifier (raw binary, no base64).

Reads RGB QR canvas PNGs, decodes each cell via channel separation,
and reconstructs the original file.

Payload format: [seq(4B)][total(4B)][data_len(2B)][raw chunk bytes][padding]
data_len tells decoder exact chunk size so padding from 3-way split can be stripped.
Uses zxingcpp .bytes for reliable binary data recovery.
"""

import glob
import os
import sys

import cv2
import numpy as np
import zxingcpp
from PIL import Image

# ===================== Grid Config (must match generator) =====================
MAX_QR_VER = 32
BOX_SIZE = 3
BORDER = 4
CELL_SIZE = (4 * MAX_QR_VER + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE  # 555
print(f"CELL_SIZE: {CELL_SIZE}")

R_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (255, 0, 255), (255, 0, 0)])
G_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (0, 255, 255), (0, 255, 0)])
B_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 0, 255), (0, 255, 255), (0, 0, 255)])


def extract_channel(img_array, channel_colors, tolerance=30):
    """Extract a single color channel as a binary image (vectorized numpy)."""
    h, w = img_array.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    img_int = img_array.astype(np.int16)

    for color in channel_colors:
        diff = np.abs(img_int - color.astype(np.int16))
        dist = diff.sum(axis=2)
        mask |= (dist <= tolerance)

    return np.where(mask, 0, 255).astype(np.uint8)


def decode_channel_bytes(binary_img):
    """Decode a binary channel image as QR, returning raw bytes."""
    pil_img = Image.fromarray(binary_img, mode="L")
    results = zxingcpp.read_barcodes(pil_img)
    if results:
        return results[0].bytes
    return None


def decode_rgb_qr_cell(cell_img_array, tolerance=30):
    """Decode a single RGB QR cell by separating R, G, B channels.

    Returns the combined raw bytes (with padding), or None.
    """
    r_binary = extract_channel(cell_img_array, R_CHANNEL_COLORS, tolerance)
    g_binary = extract_channel(cell_img_array, G_CHANNEL_COLORS, tolerance)
    b_binary = extract_channel(cell_img_array, B_CHANNEL_COLORS, tolerance)

    r_bytes = decode_channel_bytes(r_binary)
    g_bytes = decode_channel_bytes(g_binary)
    b_bytes = decode_channel_bytes(b_binary)

    if r_bytes is None or g_bytes is None or b_bytes is None:
        failed = []
        if r_bytes is None:
            failed.append("R")
        if g_bytes is None:
            failed.append("G")
        if b_bytes is None:
            failed.append("B")
        print(f"    [!] Failed to decode channel(s): {', '.join(failed)}")
        return None

    return r_bytes + g_bytes + b_bytes


def parse_payload(data_bytes):
    """Parse binary payload: [seq(4B)][total(4B)][data_len(2B)][chunk bytes][padding]."""
    if len(data_bytes) < 10:
        return None, None, None
    seq = int.from_bytes(data_bytes[0:4], "big", signed=False)
    total = int.from_bytes(data_bytes[4:8], "big", signed=False)
    data_len = int.from_bytes(data_bytes[8:10], "big", signed=False)
    payload = data_bytes[10:10 + data_len]
    return seq, total, payload


def decode_canvas(image_path, tolerance=30):
    """Decode all RGB QR cells from a canvas image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] Could not read {image_path}")
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    rows = h // CELL_SIZE
    cols = w // CELL_SIZE

    results = []

    for row in range(rows):
        for col in range(cols):
            x_start = col * CELL_SIZE
            x_end = (col + 1) * CELL_SIZE
            y_start = row * CELL_SIZE
            y_end = (row + 1) * CELL_SIZE

            cell = img_rgb[y_start:y_end, x_start:x_end]

            if np.mean(cell) > 250:
                continue

            print(f"  Decoding cell [{row},{col}]...")
            raw = decode_rgb_qr_cell(cell, tolerance)
            if raw is None:
                continue

            seq, total, payload = parse_payload(raw)
            if seq is not None:
                results.append({"seq": seq, "total": total, "payload": payload})

    return results


def verify_qrgb_bin(base_dir, output_dir, tolerance=30):
    """Verify all RGB QR canvas PNGs and reconstruct the file."""
    received_chunks = {}
    total_chunks = None

    qr_files = sorted(glob.glob(os.path.join(base_dir, "qrcode_*.png")))
    if not qr_files:
        print(f"[X] No QR code files found in {base_dir}")
        return False

    print(f"[DIR] Found {len(qr_files)} canvas files")

    for qr_file in qr_files:
        print(f"\n[FILE] Processing: {os.path.basename(qr_file)}")
        results = decode_canvas(qr_file, tolerance)

        if not results:
            print(f"  [!] No RGB QR codes detected")
            continue

        print(f"  [OK] Detected {len(results)} RGB QR codes")

        for result in results:
            seq = result["seq"]
            total = result["total"]
            payload = result["payload"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                print(f"  [SKIP] Chunk {seq} already received")
                continue

            if seq >= total_chunks:
                print(f"  [!] seq {seq} >= total {total_chunks}, ignoring")
                continue

            received_chunks[seq] = payload
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(payload)} bytes)")

    if total_chunks is None:
        print("\n[X] No valid RGB QR codes found!")
        return False

    print(f"\n[INFO] Chunks received: {len(received_chunks)}/{total_chunks}")

    if len(received_chunks) != total_chunks:
        print("\n[!] Not all chunks received! Cannot reconstruct file.")
        missing = set(range(total_chunks)) - set(received_chunks.keys())
        print(f"Missing chunks: {sorted(missing)}")
        return False

    print("\n[INFO] Assembling chunks...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]

    print(f"[OK] Assembled data: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "output.bin")
    with open(output_file, "wb") as f:
        f.write(full_data)
    print(f"\n[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "./tmp"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./tmp/qrgb_bin_verify_output"

    print("=" * 50)
    print("QRCast V3 RGB QR Verifier (raw binary)")
    print("=" * 50)
    print(f"Input directory:  {base_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 50)

    success = verify_qrgb_bin(base_dir, output_dir)

    print("\n" + "=" * 50)
    if success:
        print("[OK] VERIFICATION SUCCESSFUL")
    else:
        print("[X] VERIFICATION FAILED")
    print("=" * 50)
