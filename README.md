# claudeStorySplitter

Split a video into fixed-length sections from the terminal. Built for iPhone
`.mov`/HEVC clips, but works with any format FFmpeg can read (`.mp4`, `.mkv`,
`.avi`, `.m4v`, ...).

Given a 4:10 video split at the default 1-minute interval you get five files -
1:00, 1:00, 1:00, 1:00, and a 0:10 remainder - exactly like the design sketch
in `Drawing.jpeg`.

## Requirements

- **Python 3** (tested on 3.13)
- **FFmpeg** on your PATH (provides `ffmpeg` and `ffprobe`) -
  <https://ffmpeg.org/download.html>

## Usage

```
python split_video.py <video> [--interval TIME] [--exact] [--output-dir DIR]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `video` | - | Path to the input video file. |
| `-i`, `--interval` | `60` | Section length. Plain seconds (`90`) or clock form (`1:30`). |
| `-o`, `--output-dir` | `<video>_sections` next to the input | Where the sections are written. |
| `--exact` | off | Re-encode so every cut is precise (see below). |

Run `python split_video.py --help` to print this document, or
`python split_video.py -h` for a short usage summary.

### Examples

```bash
# 1-minute sections, fast and lossless
python split_video.py IMG_1234.mov

# 90-second sections
python split_video.py clip.mp4 --interval 90
python split_video.py clip.mp4 --interval 1:30

# precise 1-minute cuts, written to ./out
python split_video.py clip.mp4 --exact --output-dir out
```

Output files are named `<name>_part01`, `<name>_part02`, ... in the same
container as the input.

## Cutting modes

- **Fast (default) - stream copy.** Instant and lossless, no re-encoding. Cuts
  snap to the nearest keyframe, so a boundary can drift by a fraction of a
  second up to a couple of seconds. Best for large iPhone HEVC/4K clips.
- **Exact (`--exact`) - re-encode.** Every cut lands precisely on the interval,
  so section lengths are exact. Slower and slightly recompresses (re-encodes to
  H.264 / AAC).
