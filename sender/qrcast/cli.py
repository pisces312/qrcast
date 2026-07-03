"""qrcast CLI — unified command-line interface."""

import argparse
import sys


def cmd_generate(args):
    mode = args.mode
    if mode == "v2":
        from qrcast.bw.generator import generate_qr_images
        generate_qr_images(
            file_path=args.file,
            ver=args.ver,
            base_dir=args.output_dir,
            compress=args.compress,
            save_chunks=args.save_chunks,
        )
    elif mode == "v3":
        if args.v3_mode == "bin":
            from qrcast.rgb.generator_bin import generate_qr_images
        else:
            from qrcast.rgb.generator_text import generate_qr_images
        generate_qr_images(
            file_path=args.file,
            base_dir=args.output_dir,
            compress=args.compress,
        )


def cmd_display(args):
    # Default pattern and interval based on mode
    if args.display_mode == "individual":
        if args.interval == 2:  # still at default, switch to 0.5 for individual
            args.interval = 0.5
        if args.pattern is None:
            args.pattern = "qr_*.png"
    else:
        if args.pattern is None:
            args.pattern = "qrcode_*.png"

    if args.display_mode == "canvas":
        from qrcast.common import display_canvases
        display_canvases(args.image_dir, display_sec=args.interval, pattern=args.pattern)
    else:
        from qrcast.bw.display import display_individual_qr
        display_individual_qr(args.image_dir, interval=args.interval, pattern=args.pattern,
                              fullscreen=not args.no_fullscreen, end_pause=args.end_pause)


def cmd_verify(args):
    if args.version == "v2":
        from qrcast.bw.verifier import verify
        verify(args.image_dir, args.output_dir)
    elif args.version == "v3":
        if args.v3_mode == "bin":
            from qrcast.rgb.verifier_bin import verify
        else:
            from qrcast.rgb.verifier_text import verify
        verify(args.image_dir, args.output_dir)


def cmd_receive(args):
    if args.version == "v2":
        from qrcast.bw.receiver import receive_loop
        receive_loop(camera_index=args.camera)
    elif args.version == "v3":
        if args.v3_mode == "bin":
            from qrcast.rgb.receiver_bin import receive_loop
        else:
            from qrcast.rgb.receiver_text import receive_loop
        receive_loop(camera_index=args.camera)


def cmd_quick_send(args):
    from qrcast.bw.quick_sender import send_file
    send_file(args.file, minify=args.minify)


def main():
    parser = argparse.ArgumentParser(
        prog="qrcast",
        description="qrcast — File transfer via QR codes. No network required.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── generate ──────────────────────────────────────
    p_gen = subparsers.add_parser("generate", help="Generate QR code canvases from a file")
    p_gen.add_argument("mode", choices=["v2", "v3"], help="QR version mode")
    p_gen.add_argument("file", help="File to encode")
    p_gen.add_argument("--output-dir", default="./tmp", help="Output directory (default: ./tmp)")
    p_gen.add_argument("--compress", action="store_true", help="Compress with 7z before encoding")
    p_gen.add_argument("--save-chunks", action="store_true", help="Save individual QR chunk images (v1/v2)")
    p_gen.add_argument("--ver", type=int, default=32, help="QR version for v2 (1-40, default: 32)")
    p_gen.add_argument("--v3-mode", choices=["text", "bin"], default="bin",
                       help="V3 encoding mode: text (base64) or bin (raw binary, recommended) (default: bin)")
    p_gen.set_defaults(func=cmd_generate)

    # ── display ───────────────────────────────────────
    p_disp = subparsers.add_parser("display", help="Display QR images fullscreen")
    p_disp.add_argument("image_dir", nargs="?", default="./tmp", help="Directory with QR images")
    p_disp.add_argument("-i", "--interval", type=float, default=2, help="Seconds per image (default: 2 for canvas, 0.5 for individual)")
    p_disp.add_argument("-p", "--pattern", default=None, help="Glob pattern (default: qrcode_*.png for canvas, qr_*.png for individual)")
    p_disp.add_argument("--mode", choices=["canvas", "individual"], default="canvas",
                        dest="display_mode",
                        help="Display mode: canvas (grid images via HDMI) or individual (single QR for phone) (default: canvas)")
    p_disp.add_argument("--no-fullscreen", action="store_true",
                        help="Display at original image size instead of fullscreen (individual mode only)")
    p_disp.add_argument("--end-pause", type=float, default=3,
                        help="Seconds to hold the last image after playback (individual mode, default: 3)")
    p_disp.set_defaults(func=cmd_display)

    # ── verify ────────────────────────────────────────
    p_verify = subparsers.add_parser("verify", help="Verify/extract file from saved canvas images")
    p_verify.add_argument("image_dir", help="Directory with canvas images")
    p_verify.add_argument("output_dir", help="Output directory for reconstructed file")
    p_verify.add_argument("--version", choices=["v2", "v3"], default="v2",
                          help="QR version of the canvases (default: v2)")
    p_verify.add_argument("--v3-mode", choices=["text", "bin"], default="bin",
                          help="V3 mode: text or bin (default: bin)")
    p_verify.set_defaults(func=cmd_verify)

    # ── receive ───────────────────────────────────────
    p_recv = subparsers.add_parser("receive", help="Receive file via camera")
    p_recv.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    p_recv.add_argument("--version", choices=["v2", "v3"], default="v2",
                        help="QR version to decode (default: v2)")
    p_recv.add_argument("--v3-mode", choices=["text", "bin"], default="bin",
                        help="V3 mode: text or bin (default: bin)")
    p_recv.set_defaults(func=cmd_receive)

    # ── quick-send ───────────────────────────────────
    p_qs = subparsers.add_parser("quick-send", help="Quick single-QR send for small files (V2 ver40)")
    p_qs.add_argument("file", help="File to encode (small files only)")
    p_qs.add_argument("--minify", action="store_true", help="Minify .py files before encoding")
    p_qs.set_defaults(func=cmd_quick_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
