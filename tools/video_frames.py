"""Slides from a screen-share video when the lecture has no separate presentation.

Usage:
  python tools/video_frames.py extract <video> <W> [--cam X,Y|none]
      -> W/slides_png/NN.png, W/slides.json, W/frames_sheet_NN.png
  python tools/video_frames.py drop <W> <N,N,...>
      -> removes service frames (participant grid, camera only), renumbers the rest

extract samples one frame per second at low resolution, masks the lecturer's camera
window (bottom-right corner from X,Y as fractions of width/height; default 0.84,0.74),
splits the video into stable stretches and keeps the last frame of each stretch
(animation already built up) at full resolution. Consecutive stretches that differ
only slightly are merged (steps of one animation). Text: OCR tesseract rus+eng.
slides.json: [{"page", "from", "time", "text", "low_text"}] — from/time are when the
frame appeared and when it was taken (HH:MM:SS of the video).
Contact sheets (5x4, frame numbers drawn) are for picking frames to drop.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

SW, SH = 160, 90
DIFF = 4.0        # mean pixel difference above which the screen has changed
MIN_STABLE = 4    # seconds without changes to count a stretch as a slide
DUP = 3.0         # difference below which the next stretch replaces the current one


def hms(t):
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def extract(video, w, cam):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps=1,scale={SW}:{SH}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW).astype(np.int16)
    mask = np.ones((SH, SW), bool)
    if cam:
        mask[int(SH * cam[1]):, int(SW * cam[0]):] = False

    def diff(a, b):
        return float(np.abs(a - b)[mask].mean())

    segs, start = [], 0
    for i in range(1, len(frames)):
        if diff(frames[i], frames[i - 1]) > DIFF:
            if i - start >= MIN_STABLE:
                segs.append((start, i - 1))
            start = i
    if len(frames) - start >= MIN_STABLE:
        segs.append((start, len(frames) - 1))

    picked = []
    for s, e in segs:
        if picked and diff(frames[picked[-1][1]], frames[e]) < DUP:
            picked[-1] = (picked[-1][0], e)
            continue
        picked.append((s, e))

    out = os.path.join(w, "slides_png")
    if os.path.exists(out):
        sys.exit(f"{out} already exists; remove it to extract again")
    os.makedirs(out)
    slides = []
    for n, (s, e) in enumerate(picked, 1):
        png = os.path.join(out, f"{n:02d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(e), "-i", video,
                        "-frames:v", "1", png], check=True)
        txt = subprocess.run(["tesseract", png, "-", "-l", "rus+eng"],
                             capture_output=True, text=True).stdout.strip()
        slides.append({"page": n, "from": hms(s), "time": hms(e),
                       "text": txt, "low_text": len(txt.split()) < 8})
    with open(os.path.join(w, "slides.json"), "w", encoding="utf-8") as f:
        json.dump(slides, f, ensure_ascii=False, indent=1)
    sheets(w)
    print(f"{len(frames)} s, {len(segs)} stable stretches, {len(slides)} frames")


def sheets(w):
    """Contact sheets 5x4 with frame numbers: W/frames_sheet_NN.png."""
    for f in os.listdir(w):
        if f.startswith("frames_sheet_"):
            os.remove(os.path.join(w, f))
    n = len(os.listdir(os.path.join(w, "slides_png")))
    for k, first in enumerate(range(1, n + 1, 20)):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-start_number", str(first),
             "-i", os.path.join(w, "slides_png", "%02d.png"), "-frames:v", "1", "-vf",
             f"scale=320:-1,drawtext=text='%{{eif\\:n+{first}\\:d}}':x=6:y=6:fontsize=28:"
             "fontcolor=yellow:box=1:boxcolor=black@0.7,tile=5x4",
             os.path.join(w, f"frames_sheet_{k:02d}.png")], check=True)


def drop(w, nums):
    drop_set = {int(x) for x in nums.split(",") if x}
    path = os.path.join(w, "slides.json")
    slides = json.load(open(path, encoding="utf-8"))
    src, tmp, gone = (os.path.join(w, d) for d in ("slides_png", "slides_png_new", "frames_dropped"))
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(gone, exist_ok=True)
    keep = []
    for s in slides:
        f = os.path.join(src, f"{s['page']:02d}.png")
        if s["page"] in drop_set:
            shutil.move(f, os.path.join(gone, f"{s['time'].replace(':', '')}.png"))
            continue
        keep.append(s)
        s["page"] = len(keep)
        shutil.move(f, os.path.join(tmp, f"{s['page']:02d}.png"))
    os.rmdir(src)
    os.rename(tmp, src)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(keep, f, ensure_ascii=False, indent=1)
    sheets(w)
    print(f"dropped {len(slides) - len(keep)}, {len(keep)} frames left")


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "extract":
        cam = (0.84, 0.74)
        if "--cam" in a:
            v = a[a.index("--cam") + 1]
            cam = None if v == "none" else tuple(float(x) for x in v.split(","))
        extract(a[1], a[2], cam)
    elif len(a) == 3 and a[0] == "drop":
        drop(a[1], a[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
