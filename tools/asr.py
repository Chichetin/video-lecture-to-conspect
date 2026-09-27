"""Yandex SpeechKit v3 async recognition helper (audio sent inline, no Object Storage).

Usage:
  python tools/asr.py extract <video> <out.mp3>          -> mono MP3 (~22 MB/hour)
  python tools/asr.py split   <audio.mp3> <W> [part_s=1500] -> W/part_NN.mp3 + W/parts.json
  python tools/asr.py submit  <W> [--deferred] [--only N]   -> sends parts without operation_id
  python tools/asr.py poll    <W> [wait_s=90]              -> checks operations, downloads ready parts
  python tools/asr.py parse   <W> <segments.json>          -> merges parts with time offsets

All state lives in W/parts.json; submit/poll are idempotent (already submitted or
downloaded parts are skipped). Secrets are read from environment or from .env.
"""
import base64
import json
import os
import re
import subprocess
import sys
import time

import requests

STT = "https://stt.api.cloud.yandex.net/stt/v3"
OPS = "https://operation.api.cloud.yandex.net/operations"


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"missing env var {name} (set it in .env)")
    return v


def headers():
    return {"Authorization": f"Api-key {env('YC_API_KEY')}",
            "x-folder-id": env("YC_FOLDER_ID")}


def err(r):
    try:
        return json.dumps(r.json(), ensure_ascii=False)[:2000]
    except Exception:
        return r.text[:2000]


# ---------- state ----------

def state_path(w):
    return os.path.join(w, "parts.json")


def load_state(w):
    p = state_path(w)
    if not os.path.exists(p):
        sys.exit(f"{p} not found, run split first")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_state(w, st):
    p = state_path(w)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ---------- audio ----------

def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def extract(video, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-map", "0:a:0", "-vn",
                    "-ac", "1", "-ar", "16000", "-b:a", "48k", out], check=True)
    print(f"{out}: {probe_duration(out):.0f}s, {os.path.getsize(out) / 1e6:.1f} MB")


def silences(audio):
    """Midpoints of silences (seconds) via ffmpeg silencedetect."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", audio, "-af",
                        "silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(s + e) / 2 for s, e in zip(starts, ends)]


def split(audio, w, part_s=1500):
    if os.path.exists(state_path(w)):
        st = load_state(w)
        if any(p.get("operation_id") for p in st["parts"]):
            sys.exit("parts.json already has submitted parts; refusing to re-split")
    os.makedirs(w, exist_ok=True)
    total = probe_duration(audio)
    mids = silences(audio)
    cuts, pos = [], 0.0
    while total - pos > part_s * 1.2:
        target = pos + part_s
        cand = [m for m in mids if abs(m - target) <= 120]
        cut = min(cand, key=lambda m: abs(m - target)) if cand else target
        cuts.append(cut)
        pos = cut
    bounds = [0.0] + cuts + [total]
    parts = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        name = f"part_{i:02d}.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}",
                        "-i", audio, "-ac", "1", "-ar", "16000", "-b:a", "48k",
                        os.path.join(w, name)], check=True)
        parts.append({"idx": i, "file": name, "offset_ms": round(s * 1000),
                      "duration_ms": round((e - s) * 1000), "cut_in_silence": i == 0 or bool(
                          [m for m in mids if abs(m - s) < 0.01]),
                      "operation_id": None, "status": "new", "ndjson": None})
    save_state(w, {"audio": os.path.basename(audio), "total_ms": round(total * 1000),
                   "mode": None, "parts": parts})
    for p in parts:
        size = os.path.getsize(os.path.join(w, p["file"])) / 1e6
        print(f"{p['file']}: offset {p['offset_ms'] / 1000:.0f}s, "
              f"dur {p['duration_ms'] / 1000:.0f}s, {size:.1f} MB, "
              f"silence cut: {p['cut_in_silence']}")


# ---------- API ----------

def submit(w, deferred=False, only=None):
    st = load_state(w)
    mode = "deferred" if deferred else "normal"
    for p in st["parts"]:
        if only is not None and p["idx"] != only:
            continue
        if p.get("operation_id"):
            print(f"{p['file']}: already submitted ({p['status']}), skip")
            continue
        with open(os.path.join(w, p["file"]), "rb") as f:
            content = base64.b64encode(f.read()).decode()
        body = {
            "content": content,
            "recognitionModel": {
                "model": "deferred-general" if deferred else "general",
                "audioFormat": {"containerAudio": {"containerAudioType": "MP3"}},
                "languageRestriction": {"restrictionType": "WHITELIST", "languageCode": ["ru-RU"]},
                "textNormalization": {
                    "textNormalization": "TEXT_NORMALIZATION_ENABLED",
                    "phoneFormattingMode": "PHONE_FORMATTING_MODE_DISABLED",
                    "profanityFilter": False,
                    "literatureText": True,
                },
            },
        }
        r = requests.post(f"{STT}/recognizeFileAsync", headers=headers(), json=body, timeout=300)
        if r.status_code != 200:
            save_state(w, st)
            sys.exit(f"{p['file']}: submit failed {r.status_code}: {err(r)}")
        p["operation_id"] = r.json()["id"]
        p["status"] = "submitted"
        p["mode"] = mode
        st["mode"] = mode
        save_state(w, st)  # persist right away: never pay twice
        print(f"{p['file']}: submitted ({mode}), operation {p['operation_id']}")


def fetch(op, out):
    r = requests.get(f"{STT}/getRecognition", params={"operation_id": op},
                     headers=headers(), timeout=600)
    if r.status_code != 200:
        return f"fetch failed {r.status_code}: {err(r)}"
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(r.text)
    os.replace(tmp, out)
    return None


def poll(w, wait_s=90):
    st = load_state(w)
    deadline = time.time() + wait_s
    while True:
        for p in st["parts"]:
            if not p.get("operation_id") or p["status"] in ("done", "failed"):
                continue
            r = requests.get(f"{OPS}/{p['operation_id']}", headers=headers(), timeout=60)
            if r.status_code != 200:
                print(f"{p['file']}: status check {r.status_code}: {err(r)}", file=sys.stderr)
                continue
            d = r.json()
            if not d.get("done"):
                continue
            if "error" in d:
                p["status"] = "failed"
                p["error"] = d["error"]
                save_state(w, st)
                print(f"{p['file']}: FAILED {json.dumps(d['error'], ensure_ascii=False)}")
                continue
            out = os.path.join(w, p["file"].replace(".mp3", ".ndjson"))
            e = fetch(p["operation_id"], out)
            if e:
                print(f"{p['file']}: {e}", file=sys.stderr)
                continue
            p["status"] = "done"
            p["ndjson"] = os.path.basename(out)
            save_state(w, st)
            print(f"{p['file']}: DONE -> {p['ndjson']} ({os.path.getsize(out)} bytes)")
        pending = [p for p in st["parts"] if p.get("operation_id") and p["status"] == "submitted"]
        if not pending or time.time() >= deadline:
            break
        time.sleep(15)
    for p in st["parts"]:
        print(f"  {p['file']}: {p['status']}")
    if pending:
        print("PENDING")
    elif all(p["status"] == "done" for p in st["parts"]):
        print("ALL DONE")


# ---------- parsing ----------

def iter_objects(text):
    dec, i, n = json.JSONDecoder(), 0, len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        obj, i = dec.raw_decode(text, i)
        yield obj


def parse_raw(text):
    """Segments (relative to part start) from a getRecognition response stream."""
    finals, refs = [], []
    for obj in iter_objects(text):
        r = obj.get("result", obj)
        if "finalRefinement" in r:
            alts = r["finalRefinement"].get("normalizedText", {}).get("alternatives", [])
            if alts:
                refs.append(alts[0])
        elif "final" in r:
            alts = r["final"].get("alternatives", [])
            if alts:
                finals.append(alts[0])
    src = refs or finals
    segs, seen = [], set()
    for a in src:
        t = (a.get("text") or "").strip()
        if not t:
            continue
        s, e = int(a.get("startTimeMs", 0)), int(a.get("endTimeMs", 0))
        words = a.get("words") or []
        if words:  # utterance bounds include surrounding silence; words give real speech span
            s, e = int(words[0].get("startTimeMs", s)), int(words[-1].get("endTimeMs", e))
        if (s, t) in seen:
            continue
        seen.add((s, t))
        segs.append({"start_ms": s, "end_ms": e, "text": t})
    segs.sort(key=lambda x: x["start_ms"])
    return segs, ("finalRefinement" if refs else "final")


def parse(w, out):
    st = load_state(w)
    all_segs = []
    for p in st["parts"]:
        if p["status"] != "done":
            sys.exit(f"{p['file']} is not downloaded yet ({p['status']})")
        with open(os.path.join(w, p["ndjson"]), encoding="utf-8") as f:
            segs, src = parse_raw(f.read())
        for s in segs:
            all_segs.append({"start_ms": s["start_ms"] + p["offset_ms"],
                             "end_ms": s["end_ms"] + p["offset_ms"],
                             "part": p["idx"], "text": s["text"]})
        print(f"{p['file']}: {len(segs)} segments from {src}")
    all_segs.sort(key=lambda x: x["start_ms"])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_segs, f, ensure_ascii=False, indent=1)
    last = all_segs[-1]["end_ms"] / 1000 if all_segs else 0
    print(f"{len(all_segs)} segments; last end {last:.0f}s of {st['total_ms'] / 1000:.0f}s")
    prev = 0
    for s in all_segs:
        if s["start_ms"] - prev > 150_000:
            print(f"gap {prev / 1000:.0f}s -> {s['start_ms'] / 1000:.0f}s")
        prev = max(prev, s["end_ms"])


if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    flags = [a for a in args if a.startswith("--")]
    pos = [a for a in args if not a.startswith("--")]
    if cmd == "extract":
        extract(pos[0], pos[1])
    elif cmd == "split":
        split(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1500)
    elif cmd == "submit":
        only = None
        if "--only" in args:
            only = int(args[args.index("--only") + 1])
        submit(pos[0], deferred="--deferred" in flags, only=only)
    elif cmd == "poll":
        poll(pos[0], int(pos[1]) if len(pos) > 1 else 90)
    elif cmd == "parse":
        parse(pos[0], pos[1])
    else:
        sys.exit(__doc__)
