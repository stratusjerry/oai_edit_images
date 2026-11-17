"""Print the resolution (width x height) of every JPG file in the current directory.

Uses only the Python standard library by reading the JPEG SOF header directly.
"""
import struct
from pathlib import Path

# SOF markers that carry image dimensions (excludes DHT 0xC4, JPG 0xC8, DAC 0xCC)
SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def jpeg_size(path):
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("not a JPEG file")
        while True:
            byte = f.read(1)
            while byte and byte != b"\xff":
                byte = f.read(1)
            while byte == b"\xff":
                byte = f.read(1)
            if not byte:
                raise ValueError("no size marker found")
            marker = byte[0]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                continue  # standalone markers, no length
            length_bytes = f.read(2)
            if len(length_bytes) < 2:
                raise ValueError("truncated file")
            length = struct.unpack(">H", length_bytes)[0]
            if marker in SOF_MARKERS:
                _, height, width = struct.unpack(">BHH", f.read(5))
                return width, height
            f.seek(length - 2, 1)


def main():
    files = sorted(p for p in Path.cwd().iterdir()
                   if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg"))
    if not files:
        print("No JPG files found in", Path.cwd())
        return
    for p in files:
        try:
            w, h = jpeg_size(p)
            print(f"{p.name}: {w}x{h}")
        except (OSError, ValueError, struct.error) as e:
            print(f"{p.name}: error - {e}")


if __name__ == "__main__":
    main()
