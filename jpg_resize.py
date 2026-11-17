"""Resize every JPG in the current directory to 50% and save as <name>_resize.jpg.

Requires Pillow:  pip install Pillow
"""
import sys
from pathlib import Path

from PIL import Image

SCALE = 0.5
SUFFIX = "_resize"
QUALITY = 95


def resize(src: Path, dst: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    with Image.open(src) as img:
        exif = img.info.get("exif")
        icc = img.info.get("icc_profile")
        new_size = (max(1, round(img.width * SCALE)), max(1, round(img.height * SCALE)))
        out = img.resize(new_size, Image.Resampling.LANCZOS)
        kwargs = {"quality": QUALITY, "subsampling": "keep" if img.format == "JPEG" else 0}
        if exif:
            kwargs["exif"] = exif
        if icc:
            kwargs["icc_profile"] = icc
        try:
            out.save(dst, "JPEG", **kwargs)
        except ValueError:
            # "keep" subsampling can fail on some images; fall back to default
            kwargs.pop("subsampling")
            out.save(dst, "JPEG", **kwargs)
        return img.size, new_size


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    files = sorted(p for p in folder.iterdir()
                   if p.is_file()
                   and p.suffix.lower() in (".jpg", ".jpeg")
                   and not p.stem.endswith(SUFFIX))
    if not files:
        print("No JPG files found in", folder)
        return
    for p in files:
        dst = p.with_name(f"{p.stem}{SUFFIX}.jpg")
        try:
            (w, h), (nw, nh) = resize(p, dst)
            print(f"{p.name}: {w}x{h} -> {dst.name}: {nw}x{nh}")
        except Exception as e:
            print(f"{p.name}: error - {e}")


if __name__ == "__main__":
    main()
