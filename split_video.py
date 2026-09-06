#!/usr/bin/env python3
"""
split_video.py — Split a video into fixed-length sections.

Takes a path to a video file (iPhone .mov/HEVC and most other formats are
supported via FFmpeg) and divides it into consecutive sections. By default each
section is one minute long; the final section holds the remainder — e.g. a 4:10
video split at 1:00 yields 1:00, 1:00, 1:00, 1:00, 0:10.

Two cutting modes (see the drawing / project spec):
  * default  — stream copy. Instant and lossless, but cuts snap to the nearest
               keyframe, so a boundary may drift by up to a couple of seconds.
  * --exact  — re-encodes so every cut lands precisely on the interval. Slower
               and slightly recompresses, but section lengths are exact.

Usage:
    python split_video.py <video> [--interval 60] [--exact] [--output-dir DIR]

Examples:
    python split_video.py IMG_1234.mov
    python split_video.py clip.mp4 --interval 90
    python split_video.py clip.mp4 --interval 1:30 --exact
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


class ReadmeHelpAction(argparse.Action):
    """--help: print the full README instead of the terse argparse usage."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest,
                         default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        readme = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
        try:
            with open(readme, encoding="utf-8") as fh:
                print(fh.read())
        except OSError:
            # Fall back to the built-in usage if the README is missing.
            parser.print_help()
        parser.exit()


def require_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(
                f"'{tool}' not found on PATH. Install FFmpeg "
                "(https://ffmpeg.org/download.html) and try again."
            )


def parse_interval(text: str) -> float:
    """Accept plain seconds ('90', '90.5') or clock form ('1:30', '1:05:00')."""
    text = text.strip()
    try:
        if ":" in text:
            parts = [float(p) for p in text.split(":")]
            seconds = 0.0
            for p in parts:
                seconds = seconds * 60 + p
        else:
            seconds = float(text)
    except ValueError:
        die(f"could not understand interval '{text}'. Use seconds (90) or M:SS (1:30).")
    if seconds <= 0:
        die("interval must be greater than zero.")
    return seconds


def probe_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True,
    )
    out = result.stdout.strip()
    if result.returncode != 0 or not out or out == "N/A":
        die(f"could not read video duration.\n{result.stderr.strip()}")
    try:
        return float(out)
    except ValueError:
        die(f"unexpected duration from ffprobe: '{out}'")


def fmt_ts(seconds: float) -> str:
    """Format seconds as H:MM:SS (or M:SS under an hour)."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        die(f"ffmpeg failed (exit {result.returncode}).")


def split_fast(src: str, out_pattern: str, interval: float) -> None:
    """Lossless stream-copy split via FFmpeg's segment muxer (keyframe cuts)."""
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-stats",
        "-i", src,
        "-c", "copy", "-map", "0",
        "-f", "segment",
        "-segment_time", str(interval),
        "-reset_timestamps", "1",
        "-segment_start_number", "1",
        out_pattern,
    ])


def split_exact(src: str, base: str, ext: str, outdir: str,
                interval: float, duration: float) -> None:
    """Frame-accurate split by re-encoding each section (H.264 / AAC)."""
    count = max(1, math.ceil(duration / interval))
    width = max(2, len(str(count)))
    for i in range(count):
        start = i * interval
        length = min(interval, duration - start)
        if length <= 0:
            break
        dest = os.path.join(outdir, f"{base}_part{i + 1:0{width}d}{ext}")
        print(f"  section {i + 1}/{count}: {fmt_ts(start)} -> {fmt_ts(start + length)}")
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y",
            "-ss", f"{start:.3f}", "-i", src, "-t", f"{length:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            dest,
        ])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a video into fixed-length sections (default 1 minute each).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h", action="help", default=argparse.SUPPRESS,
        help="show a short usage summary and exit",
    )
    parser.add_argument(
        "--help", action=ReadmeHelpAction,
        help="show the full README documentation and exit",
    )
    parser.add_argument("video", help="path to the input video file")
    parser.add_argument(
        "-i", "--interval", default="60", metavar="TIME",
        help="section length in seconds (e.g. 60) or clock form (e.g. 1:30)",
    )
    parser.add_argument(
        "-o", "--output-dir", default=None, metavar="DIR",
        help="where to write sections (default: <video>_sections next to the input)",
    )
    parser.add_argument(
        "--exact", action="store_true",
        help="re-encode for precise cuts on each interval (slower, exact lengths)",
    )
    args = parser.parse_args()

    require_tools()

    src = os.path.abspath(args.video)
    if not os.path.isfile(src):
        die(f"file not found: {args.video}")

    interval = parse_interval(args.interval)
    duration = probe_duration(src)

    directory, filename = os.path.split(src)
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".mp4"

    outdir = os.path.abspath(args.output_dir) if args.output_dir \
        else os.path.join(directory, f"{base}_sections")
    os.makedirs(outdir, exist_ok=True)

    count = max(1, math.ceil(duration / interval))
    print(f"input     : {src}")
    print(f"duration  : {fmt_ts(duration)} ({duration:.2f}s)")
    print(f"interval  : {fmt_ts(interval)} ({interval:g}s)")
    print(f"mode      : {'exact (re-encode)' if args.exact else 'fast (stream copy)'}")
    print(f"sections  : {count}")
    print(f"output    : {outdir}")
    print()

    if args.exact:
        split_exact(src, base, ext, outdir, interval, duration)
    else:
        out_pattern = os.path.join(outdir, f"{base}_part%0{max(2, len(str(count)))}d{ext}")
        split_fast(src, out_pattern, interval)

    written = sorted(
        f for f in os.listdir(outdir)
        if f.startswith(f"{base}_part") and f.endswith(ext)
    )
    print(f"\ndone - wrote {len(written)} section(s) to {outdir}")
    for f in written:
        print(f"  {f}")


if __name__ == "__main__":
    main()
