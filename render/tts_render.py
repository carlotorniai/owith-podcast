#!/usr/bin/env python3
"""OWITH.ai cloud renderer: script text -> WAV + MP3, fully offline TTS (Kokoro ONNX).

No API keys, no network calls except the one time model download from GitHub,
which is verified against pinned SHA256 hashes.

Usage:
  python3 -I tts_render.py <script.txt> <out_dir> [--voice am_michael] [--speed 1.0]
Outputs in out_dir: episode.wav (24 kHz mono), episode.mp3 (128 kbps mono), render.json
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

MODEL_DIR = Path(os.environ.get("OWITH_MODEL_DIR", Path.home() / ".owith_models"))
FILES = {
    "kokoro.onnx": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
                    "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    "voices.bin": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                   "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ensure_models() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in FILES.items():
        p = MODEL_DIR / name
        if not p.exists() or sha256(p) != digest:
            print(f"downloading {name}", flush=True)
            urllib.request.urlretrieve(url, p)
            if sha256(p) != digest:
                p.unlink()
                sys.exit(f"checksum mismatch for {name}; refusing to run")


def tts_clean(text: str) -> str:
    """Make text speakable: same intent as sanitize_text_for_tts in the old pipeline."""
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"[#*_`>\[\]]", "", t)
    t = t.replace("&", " and ").replace("%", " percent").replace("@", " at ")
    t = re.sub(r"\bOWITH\.ai\b", "OWITH dot A I", t)
    t = re.sub(r"\bAI\b", "A I", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def chunks(text: str, max_chars: int = 400):
    """Split on sentence boundaries; Kokoro handles ~500 phoneme tokens per call."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 > max_chars and buf:
            yield buf
            buf = s
        else:
            buf = f"{buf} {s}".strip()
    if buf:
        yield buf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("out_dir")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()

    ensure_models()
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = tts_clean(Path(a.script).read_text(encoding="utf-8"))
    k = Kokoro(str(MODEL_DIR / "kokoro.onnx"), str(MODEL_DIR / "voices.bin"))

    t0 = time.time()
    parts, sr = [], 24000
    pause = None
    for i, c in enumerate(chunks(text)):
        samples, sr = k.create(c, voice=a.voice, speed=a.speed, lang="en-us")
        if pause is None:
            pause = np.zeros(int(sr * 0.25), dtype=samples.dtype)
        parts += [samples, pause]
        print(f"chunk {i + 1} done", flush=True)
    audio = np.concatenate(parts)
    wav = out / "episode.wav"
    sf.write(wav, audio, sr, subtype="PCM_16")

    mp3 = out / "episode.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ac", "1", "-b:a", "128k", str(mp3)], check=True)

    meta = {"voice": a.voice, "speed": a.speed, "duration_sec": round(len(audio) / sr),
            "render_sec": round(time.time() - t0), "wav_sha256": sha256(wav), "mp3_sha256": sha256(mp3)}
    (out / "render.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
