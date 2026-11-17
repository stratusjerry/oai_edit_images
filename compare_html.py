"""Build compare.html: a before/after slider for every matching image pair in the current directory.

A pair is <base>BEFORE_SUFFIX and <base>AFTER_SUFFIX, e.g.
    foo_resize.jpg  ->  foo_resize_oai.jpg

Run:  uv run python compare_html.py
"""
import html
from pathlib import Path

BEFORE_SUFFIX = "_resize.jpg"
AFTER_SUFFIX = "_resize_oai.jpg"
HTML_FILE = "compare.html"


def find_pairs(folder: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Return (pairs, befores without an after, afters without a before)."""
    files = {p.name.lower(): p for p in folder.iterdir() if p.is_file()}
    befores = {n[:-len(BEFORE_SUFFIX)]: p for n, p in files.items()
               if n.endswith(BEFORE_SUFFIX.lower())}
    afters = {n[:-len(AFTER_SUFFIX)]: p for n, p in files.items()
              if n.endswith(AFTER_SUFFIX.lower())}
    pairs = [(befores[k], afters[k]) for k in sorted(befores.keys() & afters.keys())]
    lonely_before = [befores[k] for k in sorted(befores.keys() - afters.keys())]
    lonely_after = [afters[k] for k in sorted(afters.keys() - befores.keys())]
    return pairs, lonely_before, lonely_after


def render(pairs: list[tuple[Path, Path]]) -> str:
    cards = "\n".join(f"""
    <figure class="card">
      <div class="cmp" style="--pos:50%">
        <img src="{html.escape(a.name)}" alt="Before" loading="lazy">
        <img class="after" src="{html.escape(b.name)}" alt="After" loading="lazy">
        <span class="lbl l">Before</span><span class="lbl r">After</span>
        <input type="range" min="0" max="100" value="50" aria-label="Before/after slider">
      </div>
      <figcaption>{html.escape(a.name[:-len(BEFORE_SUFFIX)])}</figcaption>
    </figure>""" for a, b in pairs)
    count = f"{len(pairs)} image{'s' if len(pairs) != 1 else ''}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sun Flare Comparison</title>
<style>
  :root {{ --bg:#f6f6f4; --fg:#1d1d1b; --muted:#6b6b66; --card:#fff; --line:#ddd; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#141413; --fg:#ececea; --muted:#9a9a94; --card:#1f1f1d; --line:#333; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--fg);
         font:15px/1.5 system-ui, sans-serif; }}
  header, main {{ max-width:1400px; margin:0 auto; }}
  h1 {{ margin:0 0 4px; font-size:22px; }}
  header p {{ margin:0 0 20px; color:var(--muted); }}
  main {{ display:grid; gap:20px; grid-template-columns:repeat(auto-fill, minmax(min(100%, 560px), 1fr)); }}
  .card {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  .cmp {{ position:relative; line-height:0; user-select:none; }}
  .cmp img {{ width:100%; height:auto; display:block; }}
  .cmp .after {{ position:absolute; inset:0; height:100%; object-fit:cover;
                 clip-path:inset(0 0 0 var(--pos)); }}
  .cmp::after {{ content:""; position:absolute; top:0; bottom:0; left:var(--pos); width:2px;
                 background:#fff; box-shadow:0 0 4px #0008; pointer-events:none; }}
  .cmp input {{ position:absolute; inset:0; width:100%; height:100%; margin:0; opacity:0; cursor:ew-resize; }}
  .lbl {{ position:absolute; top:8px; padding:2px 8px; border-radius:4px; font-size:12px; line-height:1.6;
          background:#000a; color:#fff; pointer-events:none; }}
  .lbl.l {{ left:8px; }} .lbl.r {{ right:8px; }}
  figcaption {{ padding:8px 12px; font-size:13px; color:var(--muted); word-break:break-all; }}
  .empty {{ color:var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>Sun flare removal</h1>
  <p>{count} · drag across a photo to compare before (left) and after (right)</p>
</header>
<main>{cards or '<p class="empty">No matching image pairs found.</p>'}
</main>
<script>
  document.querySelectorAll(".cmp input").forEach(r =>
    r.addEventListener("input", () => r.parentElement.style.setProperty("--pos", r.value + "%")));
</script>
</body>
</html>
"""


def main():
    folder = Path.cwd()
    pairs, lonely_before, lonely_after = find_pairs(folder)
    for p in lonely_before:
        print(f"No {AFTER_SUFFIX} match for {p.name}")
    for p in lonely_after:
        print(f"No {BEFORE_SUFFIX} match for {p.name}")
    (folder / HTML_FILE).write_text(render(pairs), encoding="utf-8")
    print(f"Wrote {HTML_FILE} with {len(pairs)} pair(s)")


if __name__ == "__main__":
    main()
