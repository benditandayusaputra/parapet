"""Record the demo page with Playwright.

    python demo/record.py            -> demo/Parapet_Demo.mp4

Requires: pip install playwright && python -m playwright install chromium; ffmpeg on PATH.
The page drives itself (timed steps) and sets document.title to DONE when finished.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = HERE / "demo.html"
OUT_DIR = HERE / "_rec"
MP4 = HERE / "Parapet_Demo.mp4"


def main() -> None:
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = ctx.new_page()
        page.goto(PAGE.as_uri())
        page.wait_for_function("document.fonts.ready.then(() => true)")
        page.wait_for_function("document.title === 'DONE'", timeout=400_000)
        page.wait_for_timeout(500)
        ctx.close()
        browser.close()
    webm = next(OUT_DIR.glob("*.webm"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", "30", "-movflags", "+faststart", str(MP4)]
    subprocess.run(cmd, check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(MP4)], capture_output=True, text=True)
    print(f"wrote {MP4} ({float(probe.stdout):.1f}s)")


if __name__ == "__main__":
    sys.exit(main())
