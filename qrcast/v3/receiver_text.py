"""V3 RGB QR code receiver (base64 text payload).

Captures camera frames, decodes RGB QR grid cells via channel separation,
and reconstructs the original file.

Uses zxingcpp for QR decoding of individual color channels.
"""

import base64
import os

import cv2
import numpy as np
import zxingcpp
from PIL import Image

from qrgb.qrgb import PAD_CHAR

# ===================== Grid Config (must match generator) =====================
MAX_QR_VER = 32
BOX_SIZE = 3
BORDER = 4
CELL_SIZE = (4 * MAX_QR_VER + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE  # 555

R_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (255, 0, 255), (255, 0, 0)])
G_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (0, 255, 255), (0, 255, 0)])
B_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 0, 255), (0, 255, 255), (0, 0, 255)])

# ===================== Global state =====================
received_chunks = {}
total_chunks = None


def extract_channel(img_array, channel_colors, tolerance=50):
    """Extract a single color channel as a binary image (vectorized numpy)."""
    h, w = img_array.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    img_int = img_array.astype(np.int16)

    for color in channel_colors:
        diff = np.abs(img_int - color.astype(np.int16))
        dist = diff.sum(axis=2)
        mask |= dist <= tolerance

    return np.where(mask, 0, 255).astype(np.uint8)


def decode_channel(binary_img):
    """Decode a binary channel image as a standard QR code using zxingcpp."""
    pil_img = Image.fromarray(binary_img, mode="L")
    results = zxingcpp.read_barcodes(pil_img)
    if results:
        return results[0].text
    return None


def decode_rgb_qr_cell(cell_rgb, tolerance=50):
    """Decode a single RGB QR cell. Returns combined text or None."""
    r_binary = extract_channel(cell_rgb, R_CHANNEL_COLORS, tolerance)
    g_binary = extract_channel(cell_rgb, G_CHANNEL_COLORS, tolerance)
    b_binary = extract_channel(cell_rgb, B_CHANNEL_COLORS, tolerance)

    r_text = decode_channel(r_binary)
    g_text = decode_channel(g_binary)
    b_text = decode_channel(b_binary)

    if r_text is None or g_text is None or b_text is None:
        return None

    combined = r_text + g_text + b_text
    combined = combined.rstrip(PAD_CHAR)
    return combined


def parse_text_payload(text):
    parts = text.split(":", 2)
    if len(parts) != 3:
        return None, None, None
    try:
        seq = int(parts[0])
        total = int(parts[1])
        raw_bytes = base64.b64decode(parts[2])
        return seq, total, raw_bytes
    except (ValueError, Exception):
        return None, None, None


def decode_frame(frame, tolerance=50):
    """Decode all RGB QR cells from a camera frame."""
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

            text = decode_rgb_qr_cell(cell, tolerance)
            if text is None:
                continue

            seq, total, payload = parse_text_payload(text)
            if seq is not None:
                results.append((seq, total, payload))

    return results


def assemble_and_save(output_dir="./qrgb_receive_output"):
    """Assemble received chunks and write to file."""
    global received_chunks, total_chunks

    if len(received_chunks) != total_chunks:
        return False

    print("\n[OK] All chunks received, assembling...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]

    print(f"[OK] Assembled data: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "output.bin")
    with open(output_file, "wb") as f:
        f.write(full_data)

    print(f"[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


def receive_loop(camera_index=0):
    """Start the camera receive loop for RGB QR (base64 text)."""
    global total_chunks, received_chunks
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    print(f"[INFO] CELL_SIZE: {CELL_SIZE}")
    print("[INFO] Waiting for RGB QR codes... Press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = decode_frame(frame)

        for seq, total, payload in results:
            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                continue

            if seq >= total_chunks:
                print(f"  [!] seq {seq} >= total {total_chunks}, ignoring")
                continue

            received_chunks[seq] = payload
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(payload)} bytes)")

            if assemble_and_save():
                cap.release()
                cv2.destroyAllWindows()
                return

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    if total_chunks and len(received_chunks) < total_chunks:
        missing = set(range(total_chunks)) - set(received_chunks.keys())
        print(f"\n[!] Incomplete: {len(received_chunks)}/{total_chunks}")
        print(f"Missing chunks: {sorted(missing)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Receive file via RGB QR codes (base64 text)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()
    receive_loop(camera_index=args.camera)
