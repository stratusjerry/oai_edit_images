Use OpenAI Images Edit API to remove lens flare from pictures

## Python Scripts

| Script | What it does | Run with | Main settings |
|---|---|---|---|
| `jpg_resolution.py` | Prints the width x height of every JPG in the folder. Needs only Python. | `uv run python jpg_resolution.py` | None |
| `jpg_resize.py` | Shrinks every JPG and saves it next to the original as `<name>_resize.jpg`. It keeps the camera details and color profile, and skips files that are already resized. You can pass a folder as an argument. | `uv run python jpg_resize.py` | `SCALE = 0.80`, `QUALITY = 95` |
| `jpg_oai.py` | Sends photos to OpenAI with the prompt "remove sun flare" and saves each result as `<name>_oai.jpg`. It chooses an output size from each photo's own dimensions. It prints the requested and returned sizes, and skips photos that already have a result. It can process one file, or send everything as a cheaper batch job that finishes within 24 hours (cancel with `--cancel`). | `uv run python jpg_oai.py` | `MODEL`, `PROMPT`, `SIZE = "match"`, `ALLOW_EXPERIMENTAL`, `QUALITY`, `OUTPUT_FORMAT`, `INPUT_FIDELITY`, `USE_BATCH`, `SINGLE_FILE`, `OVERWRITE`, `OPENAI_API_KEY` |
| `compare_html.py` | Builds `compare.html`, which shows a before/after slider for each matching pair of photos. It lists in the terminal any photo that has no partner. | `uv run python compare_html.py` | `BEFORE_SUFFIX = "_resize.jpg"`, `AFTER_SUFFIX = "_resize_oai.jpg"` |

