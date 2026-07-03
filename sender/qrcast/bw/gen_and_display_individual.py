"""Gen + Display Individual QR codes with producer-consumer threading.

Reads a file, generates individual QR code images (one per chunk),
saves them to disk, and simultaneously displays them via OpenCV.

Producer thread: chunk → encode QR → save to disk → put into queue.
Consumer thread: pull from queue → display with cv2 (fullscreen) at fixed interval.

Usage:
    python -m qrcast.bw.gen_and_display_individual myfile.zip
    python -m qrcast.bw.gen_and_display_individual myfile.zip --ver 30 --interval 0.5
"""

import argparse
import os
import queue
import threading
import time
import zlib

import cv2
import numpy as np
from PIL import Image

from qrcast.bw.generator2 import (
    QRConfig,
    build_payload,
    make_qr,
    file_to_7z_bytes,
)


def _producer(file_path, ver, base_dir, compress, q, stop_event, done_event):
    """Generate QR images and feed them into the queue.

    Puts (chunk_idx, total, pil_image, save_path) tuples into q.
    Puts None when done or stopped.
    Sets done_event when finished (even if stopped early).
    """
    try:
        if not os.path.exists(file_path):
            print(f"[X] File not found: {file_path}")
            q.put(None)
            done_event.set()
            return

        qr_cfg = QRConfig(ver)
        qr_cfg.print_config()

        with open(file_path, "rb") as f:
            original_bytes = f.read()

        original_size = len(original_bytes)
        original_crc = zlib.crc32(original_bytes) & 0xFFFFFFFF
        filename = os.path.basename(file_path)
        filename_base = os.path.splitext(filename)[0]

        if compress:
            file_bytes = file_to_7z_bytes(file_path)
        else:
            file_bytes = original_bytes

        data_per_qr = qr_cfg.data_per_qr
        filename_bytes = filename.encode("utf-8")
        if len(filename_bytes) > 255:
            filename_bytes = filename_bytes[:255]
        meta_overhead = 1 + len(filename_bytes) + 4 + 4

        # Build chunks
        chunks = []
        offset = 0
        seq = 0
        while offset < len(file_bytes):
            if seq == 0:
                chunk_size = data_per_qr - meta_overhead
            else:
                chunk_size = data_per_qr
            chunks.append(file_bytes[offset:offset + chunk_size])
            offset += chunk_size
            seq += 1

        total_chunks = len(chunks)
        flags = 0x01 if compress else 0x00

        output_dir = os.path.join(base_dir, f"{filename_base}-individual")
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n{'Compressed' if compress else 'Raw'} total size: {len(file_bytes)} bytes")
        print(f"Original size: {original_size} bytes, CRC32: {original_crc:08X}")
        print(f"Total chunks: {total_chunks}")
        print(f"Output dir: {output_dir}")
        print(f"Display interval: 0.5s (press 'q' to quit)\n")

        for chunk_idx in range(total_chunks):
            if stop_event.is_set():
                print(f"\n[!] Producer stopped early at chunk {chunk_idx}/{total_chunks}")
                break

            payload = build_payload(
                seq=chunk_idx,
                total=total_chunks,
                flags=flags,
                chunk_data=chunks[chunk_idx],
                filename=filename if chunk_idx == 0 else None,
                file_crc32=original_crc if chunk_idx == 0 else None,
                file_size=original_size if chunk_idx == 0 else None,
            )

            print(f"[Gen] Chunk {chunk_idx + 1}/{total_chunks}: {len(chunks[chunk_idx])} bytes → payload {len(payload)} bytes")

            qr_pil = make_qr(payload, qr_cfg)
            save_path = os.path.join(output_dir, f"qr_{chunk_idx:04d}.png")
            qr_pil.save(save_path)

            # Block until consumer takes it (back-pressure via maxsize=5)
            q.put((chunk_idx, total_chunks, qr_pil, save_path))

        # Signal consumer: no more items
        q.put(None)
        print("\n[OK] All QR images generated and saved.")

    except Exception as e:
        print(f"[X] Producer error: {e}")
        try:
            q.put(None)
        except Exception:
            pass
    finally:
        done_event.set()


def _show_countdown(window_name, seconds=3):
    """Show a 3-2-1 countdown before transmitting begins."""
    font = cv2.FONT_HERSHEY_DUPLEX
    for i in range(seconds, 0, -1):
        canvas = np.zeros((600, 800, 3), dtype=np.uint8)
        text = str(i)
        text_size = cv2.getTextSize(text, font, 6, 4)[0]
        text_x = (800 - text_size[0]) // 2
        text_y = (600 + text_size[1]) // 2
        cv2.putText(canvas, text, (text_x, text_y), font, 6, (255, 255, 255), 4)
        cv2.imshow(window_name, canvas)
        cv2.waitKey(1000)
    # "GO" flash
    canvas = np.zeros((600, 800, 3), dtype=np.uint8)
    text = "GO"
    text_size = cv2.getTextSize(text, font, 4, 3)[0]
    text_x = (800 - text_size[0]) // 2
    text_y = (600 + text_size[1]) // 2
    cv2.putText(canvas, text, (text_x, text_y), font, 4, (0, 255, 0), 3)
    cv2.imshow(window_name, canvas)
    cv2.waitKey(500)


def _get_screen_size():
    """Get primary screen resolution via ctypes (Windows)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080  # fallback


def _fit_square_to_screen(cv_img, screen_w, screen_h):
    """Scale image to 1:1 square filling screen height, centered on black bg."""
    img_h, img_w = cv_img.shape[:2]
    # Target: square filling height
    target_size = screen_h
    # Scale to target size preserving aspect ratio (source is already ~square)
    scale = target_size / max(img_h, img_w)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    resized = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

    # Black canvas, center the QR
    canvas = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
    x_off = (screen_w - new_w) // 2
    y_off = (screen_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def _consumer(q, stop_event, interval):
    """Pull QR images from queue and display them via OpenCV.

    Args:
        q: Queue of (chunk_idx, total, pil_image, save_path) or None sentinel.
        stop_event: Set by consumer itself on 'q' key to signal producer.
        interval: Seconds to display each frame.
    """
    screen_w, screen_h = _get_screen_size()
    window_name = "QRCast — Gen & Display"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    displayed = 0

    # ---- countdown before first frame ----
    first_frame = True

    while True:
        item = q.get()

        if item is None:
            # Producer finished
            print(f"\n[Display] Done. Total displayed: {displayed}")
            break

        chunk_idx, total, pil_img, save_path = item

        # Convert PIL to OpenCV format, fit as 1:1 square on screen
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        cv_img = _fit_square_to_screen(cv_img, screen_w, screen_h)

        if first_frame:
            _show_countdown(window_name)
            first_frame = False

        cv2.imshow(window_name, cv_img)
        print(f"[Display] {chunk_idx + 1}/{total} — {os.path.basename(save_path)}")

        # Frame timing: first=1s, last=3s, rest=interval
        is_first = (chunk_idx == 0)
        is_last = (chunk_idx == total - 1)
        if is_first:
            wait_ms = 1000
        elif is_last:
            wait_ms = 3000
        else:
            wait_ms = int(interval * 1000)

        key = cv2.waitKey(wait_ms) & 0xFF
        displayed += 1

        if key == ord("q"):
            print("\n[!] 'q' pressed — exiting.")
            cv2.destroyAllWindows()
            os._exit(0)

    cv2.destroyAllWindows()


def gen_and_display(file_path, ver=30, output_dir="./tmp", compress=False, interval=0.5):
    """Generate QR codes and display them simultaneously.

    Args:
        file_path: Path to the file to send.
        ver: QR version (1-40, default: 30).
        output_dir: Base output directory.
        compress: Whether to 7z-compress first.
        interval: Seconds to show each QR image (default: 0.5).
    """
    q = queue.Queue(maxsize=5)
    stop_event = threading.Event()
    done_event = threading.Event()

    producer = threading.Thread(
        target=_producer,
        args=(file_path, ver, output_dir, compress, q, stop_event, done_event),
        name="Producer",
    )
    consumer = threading.Thread(
        target=_consumer,
        args=(q, stop_event, interval),
        name="Consumer",
    )

    print("=" * 50)
    print("QRCast Gen & Display — Producer-Consumer Mode")
    print("=" * 50)

    t0 = time.time()

    consumer.start()
    producer.start()

    producer.join()
    consumer.join()

    elapsed = time.time() - t0
    print(f"Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate and display QR codes simultaneously (producer-consumer)"
    )
    parser.add_argument("file_path", help="File to encode")
    parser.add_argument("--ver", type=int, default=30, help="QR version (1-40, default: 30)")
    parser.add_argument("--output-dir", default="./tmp", help="Base output directory")
    parser.add_argument("--interval", type=float, default=0.2,
                        help="Display interval in seconds (default: 0.2)")
    parser.add_argument("--compress", action="store_true", help="Compress with 7z first")
    args = parser.parse_args()

    gen_and_display(
        file_path=args.file_path,
        ver=args.ver,
        output_dir=args.output_dir,
        compress=args.compress,
        interval=args.interval,
    )
