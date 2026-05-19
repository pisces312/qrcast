"""V3 RGB QR code receiver v2 (raw binary, no base64).

Captures camera frames, decodes RGB QR grid cells via channel separation,
and reconstructs the original file with filename and CRC32 verification.

Payload format v2:
  Fixed Header (12B): [seq(4B)][total(4B)][data_len(2B)][proto_ver(1B)][flags(1B)]
  Data Segment:
    - seq==0: [filename_len(1B)][filename(N B)][file_crc32(4B)][file_size(4B)][chunk_data(M B)]
    - seq>0:  [chunk_data(M B)]

Uses zxingcpp .bytes for reliable binary data recovery.
"""

import os
import tempfile
import zlib

import cv2
import numpy as np
import py7zr
import zxingcpp
from PIL import Image

# ===================== Grid Config (must match generator) =====================
MAX_QR_VER = 20
BOX_SIZE = 3
BORDER = 4
CELL_SIZE = (4 * MAX_QR_VER + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE

R_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (255, 0, 255), (255, 0, 0)])
G_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 255, 0), (0, 255, 255), (0, 255, 0)])
B_CHANNEL_COLORS = np.array([(0, 0, 0), (255, 0, 255), (0, 255, 255), (0, 0, 255)])

# ===================== Global state =====================
received_chunks = {}
total_chunks = None
meta_info = {}  # filename, file_crc32, file_size, flags


def extract_channel(img_array, channel_colors, tolerance=50):
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


def decode_rgb_qr_cell(cell_rgb, tolerance=50):
    """Decode a single RGB QR cell. Returns combined raw bytes or None."""
    r_binary = extract_channel(cell_rgb, R_CHANNEL_COLORS, tolerance)
    g_binary = extract_channel(cell_rgb, G_CHANNEL_COLORS, tolerance)
    b_binary = extract_channel(cell_rgb, B_CHANNEL_COLORS, tolerance)

    r_bytes = decode_channel_bytes(r_binary)
    g_bytes = decode_channel_bytes(g_binary)
    b_bytes = decode_channel_bytes(b_binary)

    if r_bytes is None or g_bytes is None or b_bytes is None:
        return None

    return r_bytes + g_bytes + b_bytes


def parse_payload_v2(data_bytes):
    """Parse v2 binary payload.

    Returns dict with keys:
      seq, total, data_len, proto_ver, flags,
      filename, file_crc32, file_size, chunk_data
    or None if invalid.
    """
    if len(data_bytes) < 12:
        return None

    seq = int.from_bytes(data_bytes[0:4], "big", signed=False)
    total = int.from_bytes(data_bytes[4:8], "big", signed=False)
    data_len = int.from_bytes(data_bytes[8:10], "big", signed=False)
    proto_ver = data_bytes[10]
    flags = data_bytes[11]

    if proto_ver != 0x02:
        return None

    if len(data_bytes) < 12 + data_len:
        return None

    data_segment = data_bytes[12:12 + data_len]

    result = {
        "seq": seq,
        "total": total,
        "data_len": data_len,
        "proto_ver": proto_ver,
        "flags": flags,
        "filename": None,
        "file_crc32": None,
        "file_size": None,
        "chunk_data": b"",
    }

    if seq == 0:
        if len(data_segment) < 9:
            return None
        filename_len = data_segment[0]
        if len(data_segment) < 1 + filename_len + 8:
            return None
        filename = data_segment[1:1 + filename_len].decode("utf-8", errors="replace")
        file_crc32 = int.from_bytes(data_segment[1 + filename_len:5 + filename_len], "big", signed=False)
        file_size = int.from_bytes(data_segment[5 + filename_len:9 + filename_len], "big", signed=False)
        chunk_data = data_segment[9 + filename_len:]

        result["filename"] = filename
        result["file_crc32"] = file_crc32
        result["file_size"] = file_size
        result["chunk_data"] = chunk_data
    else:
        result["chunk_data"] = data_segment

    return result


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

            raw = decode_rgb_qr_cell(cell, tolerance)
            if raw is None:
                continue

            parsed = parse_payload_v2(raw)
            if parsed is not None:
                results.append(parsed)

    return results


def assemble_and_save(output_dir="./qrgb_bin_receive_output"):
    """Assemble received chunks and write to file."""
    global received_chunks, total_chunks, meta_info

    if total_chunks is None or len(received_chunks) != total_chunks:
        return False

    if not meta_info.get("filename"):
        print("[!] Missing meta info (seq=0), cannot save")
        return False

    print("\n[OK] All chunks received, assembling...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]

    print(f"[OK] Assembled data: {len(full_data)} bytes")

    # Optional 7z decompression
    if meta_info.get("flags", 0) & 0x01:
        print("[INFO] Decompressing 7z data...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".7z") as tmp:
            tmp.write(full_data)
            tmp_path = tmp.name
        try:
            with py7zr.SevenZipFile(tmp_path, mode="r") as archive:
                # Extract to a temp dir, then read the single file
                extract_dir = tempfile.mkdtemp()
                archive.extractall(path=extract_dir)
                # Find the extracted file
                extracted_files = [f for f in os.listdir(extract_dir) if os.path.isfile(os.path.join(extract_dir, f))]
                if not extracted_files:
                    print("[!] No file found in 7z archive")
                    return False
                with open(os.path.join(extract_dir, extracted_files[0]), "rb") as f:
                    full_data = f.read()
            print(f"[OK] Decompressed: {len(full_data)} bytes")
        finally:
            os.unlink(tmp_path)

    # CRC32 verification
    if meta_info.get("file_crc32") is not None:
        computed_crc = zlib.crc32(full_data) & 0xFFFFFFFF
        expected_crc = meta_info["file_crc32"]
        if computed_crc != expected_crc:
            print(f"[!] CRC32 mismatch! Expected {expected_crc:08X}, got {computed_crc:08X}")
        else:
            print(f"[OK] CRC32 verified: {computed_crc:08X}")

    # File size verification
    if meta_info.get("file_size") is not None:
        if len(full_data) != meta_info["file_size"]:
            print(f"[!] File size mismatch! Expected {meta_info['file_size']}, got {len(full_data)}")
        else:
            print(f"[OK] File size verified: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, meta_info["filename"])
    with open(output_file, "wb") as f:
        f.write(full_data)

    print(f"[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


def receive_loop(camera_index=0):
    """Start the camera receive loop for RGB QR v2 (raw binary)."""
    global total_chunks, received_chunks, meta_info
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

        for parsed in results:
            seq = parsed["seq"]
            total = parsed["total"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                continue

            if seq >= total_chunks:
                print(f"  [!] seq {seq} >= total {total_chunks}, ignoring")
                continue

            # Store meta info from seq=0
            if seq == 0:
                meta_info = {
                    "filename": parsed.get("filename"),
                    "file_crc32": parsed.get("file_crc32"),
                    "file_size": parsed.get("file_size"),
                    "flags": parsed.get("flags", 0),
                }
                print(f"  [META] filename={meta_info['filename']}, "
                      f"size={meta_info['file_size']}, crc32={meta_info['file_crc32']:08X}")

            received_chunks[seq] = parsed["chunk_data"]
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(parsed['chunk_data'])} bytes)")

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
    parser = argparse.ArgumentParser(description="Receive file via RGB QR codes v2 (raw binary + CRC)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--output-dir", default="./qrgb_bin_receive_output", help="Output directory")
    args = parser.parse_args()
    receive_loop(camera_index=args.camera)
