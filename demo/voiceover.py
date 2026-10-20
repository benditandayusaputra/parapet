"""Generate the voice-over with ElevenLabs and mux it onto the demo video.

    export ELEVENLABS_API_KEY=...
    pip install requests
    python demo/voiceover.py
"""
import os, re, subprocess, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "voiceover.txt"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"   # "George", calm narrator; swap for any voice id from your library
MODEL = "eleven_multilingual_v2"
MAX_SPEED = 1.25   # atempo cap for clips that overrun their slot
KEY = os.environ["ELEVENLABS_API_KEY"]

def tts(text: str, out: Path) -> None:
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={"xi-api-key": KEY, "accept": "audio/mpeg"},
        json={"text": text, "model_id": MODEL,
              "voice_settings": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.2}},
        timeout=120,
    )
    r.raise_for_status()
    out.write_bytes(r.content)

def dur(p: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))

def main() -> None:
    blocks = re.findall(r"\[(\d+):(\d+)\]\s*\n(.+?)(?=\n\[|\Z)", SCRIPT.read_text(), flags=re.S)
    clips = HERE / "_voice"; clips.mkdir(exist_ok=True)
    starts = [int(m) * 60 + int(s) for m, s, _ in blocks] + [dur(HERE / "Parapet_Demo.mp4")]
    inputs, filters, cursor = [], [], 0.0
    for i, (_, _, text) in enumerate(blocks):
        mp3 = clips / f"{i:02d}.mp3"
        if not mp3.exists():
            tts(text.strip(), mp3); time.sleep(0.5)
        # ponytail: the speech is longer than the timestamps allow, so a clip that overruns its slot
        # is sped up to MAX_SPEED and any remainder pushes the next clip later. Re-time voiceover.txt to remove it.
        start = max(starts[i], cursor)
        length = dur(mp3)
        speed = min(MAX_SPEED, max(1.0, length / max(starts[i + 1] - start, 0.1)))
        ms = int(start * 1000)
        inputs += ["-i", str(mp3)]
        filters.append(f"[{i+1}:a]atempo={speed:.3f},adelay={ms}|{ms}[a{i}]")
        print(f"{i:02d} @{start:6.1f}s  drift +{start - starts[i]:.1f}s  speed x{speed:.2f}")
        cursor = start + length / speed + 0.2
    mix = "".join(f"[a{i}]" for i in range(len(blocks))) + f"amix=inputs={len(blocks)}:normalize=0[voice]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(HERE / "Parapet_Demo.mp4"), *inputs,
           "-filter_complex", ";".join(filters) + ";" + mix,
           "-map", "0:v", "-map", "[voice]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           str(HERE / "Parapet_Demo_voiced.mp4")]
    subprocess.run(cmd, check=True)
    print("wrote", HERE / "Parapet_Demo_voiced.mp4")

if __name__ == "__main__":
    sys.exit(main())
