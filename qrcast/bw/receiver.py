"""Generic receiver for B&W QR code file transfer (v1 & v2 compatible).

Captures camera frames, decodes all QR codes using whole-image detection
(no grid splitting), filters false positives, and reconstructs the original file.
"""

import zxingcpp
import cv2
import os
from PIL import Image

from qrcast.common import parse_payload

received_chunks = {}
total_chunks = None


# ===================== Decode whole frame =====================
def decode_whole_frame(frame):
    """Decode all QR codes from the full frame without grid splitting."""
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    barcodes = zxingcpp.read_barcodes(pil_img)

    raw = []
    for barcode in barcodes:
        data = barcode.bytes
        if data:
            seq, total, payload = parse_payload(data)
            if seq is not None:
                raw.append((seq, total, payload))

    if not raw:
        return []
    totals = [t for _, t, _ in raw]
    consensus_total = max(set(totals), key=totals.count)
    results = []
    for seq, total, payload in raw:
        if total == consensus_total and seq < consensus_total:
            results.append((seq, total, payload))
    return results


# ===================== Assemble and extract =====================
def assemble_and_extract(output_dir="./output"):
    """Assemble received chunks and write to file.

    Returns True if successful, False otherwise.
    """
    global received_chunks, total_chunks

    if len(received_chunks) != total_chunks:
        return False

    print("\n[OK] All chunks received, assembling...")
    full_data = b""
    for i in sorted(received_chunks.keys()):
        full_data += received_chunks[i]

    print(f"[OK] Assembled data: {len(full_data)} bytes")

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "output.7z")
    with open(output_file, "wb") as f:
        f.write(full_data)

    print(f"[OK] File saved to: {output_file} ({len(full_data)} bytes)")
    return True


# ===================== Main receive loop =====================
def receive_loop(camera_index=0):
    """Start the camera receive loop.

    Args:
        camera_index: OpenCV camera index (default 0).
    """
    global total_chunks, received_chunks
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    print(f"[INFO] Camera {camera_index} opened. Waiting for QR codes... Press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = decode_whole_frame(frame)

        for seq, total, payload in results:
            if total_chunks is None:
                total_chunks = total
                print(f"\n[INFO] Total chunks expected: {total_chunks}")

            if seq in received_chunks:
                continue

            received_chunks[seq] = payload
            print(f"  [RECV] Chunk {seq + 1}/{total_chunks} ({len(payload)} bytes)")

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
    import argparse
    parser = argparse.ArgumentParser(description="Receive file via B&W QR codes")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()
    receive_loop(camera_index=args.camera)
