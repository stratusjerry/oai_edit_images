"""Send every *_resize.jpg in the current directory to OpenAI to remove sun flare.

Each result is saved next to its source as <name>_resize_oai.jpg.
Run compare_html.py afterwards to build the before/after comparison page.

Setup:  uv sync, and set OPENAI_API_KEY in your environment (or hard-code it below)
Run:    uv run python jpg_oai.py

Batch mode (USE_BATCH = True): cheaper, but results arrive within 24 hours.
  1st run submits the batch and saves its details to oai_batch.json.
  Run again later to check progress; once finished it saves the images,
  deletes the uploaded files from OpenAI and removes oai_batch.json.
  uv run python jpg_oai.py --cancel   cancels a submitted batch
"""
import base64
import io
import json
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
# "high" or "low": how closely the result keeps the original's details.
# None leaves it out of the request (required for models that don't support it).
INPUT_FIDELITY = None
OVERWRITE = False  # True re-processes files that already have an _oai.jpg

# From https://developers.openai.com/api/reference/resources/images/methods/edit Output image Width and height
#  must both be divisible by 16 and the requested aspect ratio must be between 1:3 and 3:1. Resolutions above
#  2560x1440 are experimental, and the maximum supported resolution is 3840x2160
#
# SIZE: "match" picks a size per image from its own dimensions (same shape, as large as allowed,
#       never bigger than the input); "WIDTHxHEIGHT" forces one size; None lets OpenAI choose.
SIZE = "match"
ALLOW_EXPERIMENTAL = False  # True lets "match" go above 2560x1440 (up to 3840x2160)
# "low", "medium", "high", "xhigh", "max" or "auto"; None leaves it out of the request.
QUALITY = None
# Format OpenAI returns: "jpeg", "png", "webp", "gif" or "svg" (API default is "png").
# "gif" and "svg" need a model and project with access to them.
# Results are always saved as .jpg: png/webp/gif are converted to JPEG on save
# (gif keeps only its first frame), and svg can't be converted so it fails to save.
OUTPUT_FORMAT = "jpeg"

# True uses the Batch API (lower cost, results within 24h) instead of one request per image.
USE_BATCH = False
BATCH_STATE = "oai_batch.json"  # tracks a submitted batch between runs

# Only process this one file when set (name of a *_resize.jpg in this folder).
SINGLE_FILE = None
# SINGLE_FILE = "foo.jpg"


STEP = 16                 # width and height must be multiples of this
MAX_RATIO = 3.0           # aspect ratio must stay between 1:3 and 3:1
NORMAL_MAX = (2560, 1440)  # larger is experimental
EXPERIMENTAL_MAX = (3840, 2160)
ASPECT_TOLERANCE = 0.0025  # accept up to 0.25% shape change to get a bigger size


def match_size(w: int, h: int) -> tuple[int, int]:
    """Largest allowed WIDTHxHEIGHT with the same shape as w x h, no bigger than the input."""
    long_max, short_max = EXPERIMENTAL_MAX if ALLOW_EXPERIMENTAL else NORMAL_MAX
    max_pixels = long_max * short_max
    ratio = min(max(w / h, 1 / MAX_RATIO), MAX_RATIO)  # clamp extreme shapes into range
    best, best_key = (STEP, STEP), None
    for cw in range(STEP, long_max + 1, STEP):
        ideal_h = cw / ratio
        for ch in {int(ideal_h // STEP) * STEP, int(-(-ideal_h // STEP)) * STEP}:
            if ch < STEP or not (1 / MAX_RATIO <= cw / ch <= MAX_RATIO):
                continue
            if max(cw, ch) > long_max or min(cw, ch) > short_max:
                continue  # each edge within the limit, in either orientation
            if cw * ch > max_pixels or cw > w or ch > h:
                continue  # within the pixel budget, and never upscale
            err = abs(cw / ch - ratio) / ratio
            # Prefer sizes within tolerance, then the largest, then the closest shape.
            key = (err <= ASPECT_TOLERANCE, cw * ch, -err)
            if best_key is None or key > best_key:
                best, best_key = (cw, ch), key
    return best


def size_for(src: Path) -> str | None:
    if SIZE != "match":
        return SIZE
    with Image.open(src) as img:
        return "{}x{}".format(*match_size(*img.size))


def extra_params(src: Path) -> dict:
    """Optional request settings; anything left as None isn't sent."""
    params = {"input_fidelity": INPUT_FIDELITY, "quality": QUALITY, "size": size_for(src)}
    return {k: v for k, v in params.items() if v}


def out_path(src: Path) -> Path:
    return src.with_name(src.stem + OUT_SUFFIX)  # foo_resize.jpg -> foo_resize_oai.jpg


def find_inputs(folder: Path) -> list[Path]:
    if SINGLE_FILE:
        p = folder / SINGLE_FILE
        if not p.is_file():
            sys.exit(f"SINGLE_FILE not found: {p}")
        files = [p]
    else:
        files = sorted(p for p in folder.iterdir()
                       if p.is_file() and p.name.lower().endswith(IN_SUFFIX))
    todo = []
    for p in files:
        if out_path(p).exists() and not OVERWRITE:
            print(f"{p.name}: skipped, {out_path(p).name} exists")
        else:
            todo.append(p)
    return todo


def image_bytes(b64_json: str | None, url: str | None) -> bytes:
    if b64_json:
        return base64.b64decode(b64_json)
    if url:
        with urllib.request.urlopen(url) as r:
            return r.read()
    raise ValueError("response contained no image")


def save_jpeg(data: bytes, dst: Path) -> str:
    """Save as JPEG and return the image's actual size as 'WIDTHxHEIGHT'."""
    with Image.open(io.BytesIO(data)) as img:
        if img.format == "JPEG":
            dst.write_bytes(data)
        else:
            img.convert("RGB").save(dst, "JPEG", quality=95)
        return "{}x{}".format(*img.size)


def saved_msg(dst: Path, actual: str, requested: str | None) -> str:
    msg = f"saved {dst.name} ({actual})"
    if requested and requested != actual:
        msg += f" - WARNING: requested {requested}"
    return msg


# ---------- one request per image ----------

def process(client: OpenAI, files: list[Path]):
    for i, src in enumerate(files, 1):
        dst = out_path(src)
        tag = f"[{i}/{len(files)}] {src.name}"
        try:
            params = extra_params(src)
            print(f"{tag}: sending ({params.get('size', 'size auto')})")
            with open(src, "rb") as f:
                resp = client.images.edit(
                    model=MODEL,
                    image=f,
                    prompt=PROMPT,
                    output_format=OUTPUT_FORMAT,
                    **params,
                )
            item = resp.data[0]
            actual = save_jpeg(image_bytes(item.b64_json, item.url), dst)
            print(f"{tag}: {saved_msg(dst, actual, params.get('size'))}")
        except Exception as e:
            print(f"{tag}: error - {e}")


# ---------- Batch API ----------

def delete_uploads(client: OpenAI, file_ids: list[str]):
    for fid in file_ids:
        try:
            client.files.delete(fid)
        except Exception as e:
            print(f"Could not delete uploaded file {fid}: {e}")


def submit_batch(client: OpenAI, folder: Path, files: list[Path]):
    uploaded, jobs, sizes, lines = [], {}, {}, []
    try:
        for i, src in enumerate(files, 1):
            params = extra_params(src)
            print(f"[{i}/{len(files)}] uploading {src.name} ({params.get('size', 'size auto')})")
            with open(src, "rb") as f:
                fid = client.files.create(file=f, purpose="vision").id
            uploaded.append(fid)
            cid = f"img-{i:04d}"
            jobs[cid] = src.name
            sizes[cid] = params.get("size")
            lines.append(json.dumps({
                "custom_id": cid,
                "method": "POST",
                "url": "/v1/images/edits",
                "body": {
                    "model": MODEL,
                    "prompt": PROMPT,
                    "images": [{"file_id": fid}],
                    "output_format": OUTPUT_FORMAT,
                    **params,
                },
            }))
        jsonl = ("\n".join(lines) + "\n").encode()
        input_id = client.files.create(file=("batch.jsonl", jsonl), purpose="batch").id
        uploaded.append(input_id)
        batch = client.batches.create(
            input_file_id=input_id,
            endpoint="/v1/images/edits",
            completion_window="24h",
        )
    except Exception:
        delete_uploads(client, uploaded)  # don't leave orphaned uploads behind
        raise
    state = {"batch_id": batch.id, "jobs": jobs, "sizes": sizes, "uploaded_file_ids": uploaded}
    (folder / BATCH_STATE).write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Submitted batch {batch.id} with {len(files)} image(s). Run again later to collect results.")


def collect_batch(client: OpenAI, folder: Path, state_file: Path):
    state = json.loads(state_file.read_text(encoding="utf-8"))
    batch = client.batches.retrieve(state["batch_id"])
    counts = batch.request_counts
    progress = f"{counts.completed} done, {counts.failed} failed of {counts.total}" if counts else ""
    print(f"Batch {batch.id}: {batch.status} {progress}")

    if batch.status in ("validating", "in_progress", "finalizing", "cancelling"):
        print("Not finished yet; run again later.")
        return

    jobs = state["jobs"]
    for file_id in (batch.output_file_id, batch.error_file_id):
        if not file_id:
            continue
        for line in client.files.content(file_id).text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            name = jobs.get(row.get("custom_id"), row.get("custom_id"))
            resp = row.get("response") or {}
            body = resp.get("body") or {}
            if row.get("error") or resp.get("status_code") != 200:
                err = row.get("error") or body.get("error") or body
                print(f"{name}: error - {err}")
                continue
            try:
                item = body["data"][0]
                dst = out_path(folder / name)
                actual = save_jpeg(image_bytes(item.get("b64_json"), item.get("url")), dst)
                requested = state.get("sizes", {}).get(row.get("custom_id"))
                print(f"{name}: {saved_msg(dst, actual, requested)}")
            except Exception as e:
                print(f"{name}: error - {e}")
        client.files.delete(file_id)

    if batch.errors and batch.errors.data:
        for err in batch.errors.data:
            print(f"Batch error: {err.message}")

    delete_uploads(client, state["uploaded_file_ids"])
    state_file.unlink()
    print("Batch finished; uploads cleaned up.")


def cancel_batch(client: OpenAI, state_file: Path):
    state = json.loads(state_file.read_text(encoding="utf-8"))
    batch = client.batches.cancel(state["batch_id"])
    print(f"Batch {batch.id}: {batch.status}. Run again once it shows 'cancelled' to clean up.")


def main():
    folder = Path.cwd()
    client = OpenAI(api_key=OPENAI_API_KEY)  # None falls back to the env var
    state_file = folder / BATCH_STATE

    # A submitted batch is always followed up, even if USE_BATCH was switched off since.
    if state_file.exists():
        if "--cancel" in sys.argv:
            cancel_batch(client, state_file)
        else:
            collect_batch(client, folder, state_file)
        return
    if "--cancel" in sys.argv:
        print(f"No {BATCH_STATE} found; nothing to cancel.")
        return

    files = find_inputs(folder)
    if not files:
        print(f"No *{IN_SUFFIX} files to process in {folder}")
        return
    if USE_BATCH:
        submit_batch(client, folder, files)
    else:
        process(client, files)


if __name__ == "__main__":
    main()
