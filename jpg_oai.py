"""Send every *_resize.jpg in the current directory to OpenAI to remove sun flare.

Each result is saved next to its source as <name>_resize_oai.jpg.
Run compare_html.py afterwards to build the before/after comparison page.

Setup:  uv sync, and set OPENAI_API_KEY in your environment (or hard-code it below)
Run:    uv run python jpg_oai.py
"""
import base64
import io
import sys
import urllib.request
from pathlib import Path

from openai import OpenAI
from PIL import Image

# Hard-coded key; leave as None to use the OPENAI_API_KEY environment variable.
# Don't commit or share this file with a real key in it.
OPENAI_API_KEY = None
# OPENAI_API_KEY = "sk-..."

MODEL = "gpt-image-2.5-sunburst-2026-09-08"
PROMPT = "remove sun flare"
IN_SUFFIX = "_resize.jpg"
OUT_SUFFIX = "_oai.jpg"
INPUT_FIDELITY = "high"  # "high" or "low": how closely the result keeps the original's details
OVERWRITE = False  # True re-processes files that already have an _oai.jpg

# Only process this one file when set (name of a *_resize.jpg in this folder).
SINGLE_FILE = None
# SINGLE_FILE = "foo.jpg"


def out_path(src: Path) -> Path:
    return src.with_name(src.stem + OUT_SUFFIX)  # foo_resize.jpg -> foo_resize_oai.jpg


def find_inputs(folder: Path) -> list[Path]:
    if SINGLE_FILE:
        p = folder / SINGLE_FILE
        if not p.is_file():
            sys.exit(f"SINGLE_FILE not found: {p}")
        return [p]
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.name.lower().endswith(IN_SUFFIX))


def image_bytes(item) -> bytes:
    if item.b64_json:
        return base64.b64decode(item.b64_json)
    if item.url:
        with urllib.request.urlopen(item.url) as r:
            return r.read()
    raise ValueError("response contained no image")


def save_jpeg(data: bytes, dst: Path):
    with Image.open(io.BytesIO(data)) as img:
        if img.format == "JPEG":
            dst.write_bytes(data)
        else:
            img.convert("RGB").save(dst, "JPEG", quality=95)


def process(client: OpenAI, files: list[Path]):
    for i, src in enumerate(files, 1):
        dst = out_path(src)
        tag = f"[{i}/{len(files)}] {src.name}"
        if dst.exists() and not OVERWRITE:
            print(f"{tag}: skipped, {dst.name} exists")
            continue
        try:
            with open(src, "rb") as f:
                resp = client.images.edit(
                    model=MODEL,
                    image=f,
                    prompt=PROMPT,
                    input_fidelity=INPUT_FIDELITY,
                    output_format="jpeg",
                )
            save_jpeg(image_bytes(resp.data[0]), dst)
            print(f"{tag}: saved {dst.name}")
        except Exception as e:
            print(f"{tag}: error - {e}")


def main():
    folder = Path.cwd()
    files = find_inputs(folder)
    if not files:
        print(f"No *{IN_SUFFIX} files found in {folder}")
        return
    process(OpenAI(api_key=OPENAI_API_KEY), files)  # None falls back to the env var


if __name__ == "__main__":
    main()
