"""Receiver for B&W QR code file transfer (payload format v2).

Captures camera frames, detects the white canvas via contour analysis,
applies perspective correction, then decodes each QR cell via grid-based
scan. Extracts filename + CRC32 from seq=0 and reconstructs the file.
"""

import argparse
import os
import tempfile
import zlib

import cv2
import numpy as np
import py7zr
import zxingcpp
from PIL import Image

from qrcast.common import parse_payload_v2, CANVAS_W, CANVAS_H, BOX_SIZE, BORDER

received_chunks = {}
total_chunks = None
meta_info = {}


def calc_cell_size(ver):
    """Calculate cell size for a given QR version."""
    return (4 * ver + 17) * BOX_SIZE + 2 * BORDER * BOX_SIZE


def order_points(pts):
    """Order 4 points as [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left
    rect[1] = pts[np.argmin(diff)]   # top-right
    rect[2] = pts[np.argmax(s)]      # bottom-right
    rect[3] = pts[np.argmax(diff)]   # bottom-left
    return rect


def find_canvas_corners(frame):
    """Find the four corners of the white canvas in the frame.

    Returns (4,2) numpy array of corner points or None if not found.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Threshold: white canvas is bright
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Morphological close to connect nearby edges
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Sort by area, try largest first
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours[:3]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            return order_points(pts)

    return None


def perspective_transform(frame, corners, dst_w=CANVAS_W, dst_h=CANVAS_H):
    """Warp perspective to rectified canvas."""
    dst_pts = np.array(
        [[0, 0], [dst_w, 0], [dst_w, dst_h], [0, dst_h]], dtype=np.float32
    )
    M = cv2.getPerspectiveTransform(corners, dst_pts)
    warped = cv2.warpPerspective(frame, M, (dst_w, dst_h))
    return warped


def _parse_results(barcodes):
    """Parse barcodes into list of parsed payloads."""
    raw = []
    for barcode in barcodes:
        data = barcode.bytes
        if data:
            parsed = parse_payload_v2(data)
            if parsed is not None:
                raw.append(parsed)
    if not raw:
        return []
    totals = [r["total"] for r in raw]
    consensus_total = max(set(totals), key=totals.count)
    results = []
    for parsed in raw:
        if parsed["total"] == consensus_total and parsed["seq"] < consensus_total:
            results.append(parsed)
    return results


def decode_frame_grid(frame, ver=20):
    """Decode QR codes using grid-based scan after perspective correction.

    Returns list of parsed payloads.
    """
    corners = find_canvas_corners(frame)
    if corners is None:
        return []

    warped = perspective_transform(frame, corners)
    warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)

    cell_size = calc_cell_size(ver)
    h, w = warped_rgb.shape[:2]
    rows = h // cell_size
    cols = w // cell_size

    results = []

    for row in range(rows):
        for col in range(cols):
            x_start = col * cell_size
            x_end = (col + 1) * cell_size
            y_start = row * cell_size
            y_end = (row + 1) * cell_size
            cell = warped_rgb[y_start:y_end, x_start:x_end]

            # Skip mostly-white cells (empty slots)
            if np.mean(cell) > 250:
                continue

            cell_pil = Image.fromarray(cell)
            cell_barcodes = zxingcpp.read_barcodes(cell_pil)
            cell_results = _parse_results(cell_barcodes)
            results.extend(cell_results)

    return results


def assemble_and_extract(output_dir="./output"):
    """Assemble received chunks and write to file."""
    global received_chunks, total_chunks, meta_info

    if len(received_chunks) != total_chunks:
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
                extract_dir = tempfile.mkdtemp()
                archive.extractall(path=extract_dir)
                extracted_files = [
                    f for f in os.listdir(extract_dir)
                    if os.path.isfile(os.path.join(extract_dir, f))
                ]
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


def receive_loop(camera_index=0, ver=20):
    """Start the camera receive loop using grid-based scan."""
    global total_chunks, received_chunks, meta_info
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    print(f"[INFO] Camera {camera_index} opened.")
    print(f"[INFO] QR version: {ver}, cell_size: {calc_cell_size(ver)}")
    print("[INFO] Point camera at the QR canvas. Press Q to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = decode_frame_grid(frame, ver=ver)

        for parsed in results:
            seq = parsed["seq"]
            total = parsed["total"]

            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                continue

            if seq == 0:
                meta_info = {
                    "filename": parsed.get("filename"),
                    "file_crc32": parsed.get("file_crc32"),
                    "file_size": parsed.get("file_size"),
                    "flags": parsed.get("flags", 0),
                }
                print(
                    f"  [META] filename={meta_info['filename']}, "
                    f"size={meta_info['file_size']}, crc32={meta_info['file_crc32']:08X}"
                )

            received_chunks[seq] = parsed["chunk_data"]
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(parsed['chunk_data'])} bytes)")

            if assemble_and_extract():
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
    parser = argparse.ArgumentParser(description="Receive file via B&W QR codes v2 (grid-based)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--ver", type=int, default=20, help="QR version (default: 20)")
    args = parser.parse_args()
    receive_loop(camera_index=args.camera, ver=args.ver)
