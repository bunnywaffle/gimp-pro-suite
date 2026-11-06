# gimp-sam-select — SAM 3 / SAM 2 interactive selection for GIMP 3

## Install in 30 seconds (nothing to configure)

1. Download this repo: **Code → Download ZIP** (or `git clone` it).
2. Install with one double-click:
   - **Windows** → double-click **`install.bat`**
   - **macOS / Linux** → run **`./install.sh`** (or double-click it)
3. Restart GIMP → open an image → **Select → SAM3 Interactive Select**.

That's it. The installer copies one folder into your GIMP user plug-ins
directory. The first AI run downloads the SAM 2 tiny model (~156 MB) into
the plugin's own `models/` folder by itself — after that it works offline.

Manual alternative: copy the `sam3_select/` folder into your GIMP
`plug-ins/` directory
(Windows: `%APPDATA%\GIMP\3.2\plug-ins\` ·
Linux: `~/.config/GIMP/3.2/plug-ins/` ·
macOS: `~/Library/Application Support/GIMP/3.2/plug-ins/` ·
Flatpak: `~/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins/`).

---

# SAM3 Interactive Select — GIMP 3 plug-in (OS-agnostic, self-contained)

One self-contained file (`sam3_select/sam3_select.py`, LF endings, UTF-8,
stdlib-only inside GIMP). Click the object you want, SAM 3 selects it —
**live**: every click, box, or description re-runs the engine and shows the
mask as a green overlay in the preview, optionally mirrored straight into
the GIMP selection (marching ants on the canvas) as you work. The final
**Run full-res** button recomputes at full resolution and applies your
chosen output (selection / channel / masked layer).

- **Left-click** = this is the object · **Right-click / Shift+click** = background
- **Drag** = box around the object · or just **type what it is** (`"red car"`)
- Output: GIMP **selection**, selection + channel, or a new masked layer.

Works on **Windows, macOS and Linux** with the same file — interpreter
discovery, paths, and dependency setup are all per-OS aware
(`VIRTUAL_ENV`/`CONDA_PREFIX` honoured, PATH scanned fully, symlinks
collapsed, well-known install locations per OS).

## Install

Copy the folder so the file lands here (**keep the double folder name** —
GIMP 3 requires `<plug-ins>/<name>/<name>.py`):

| OS | Target |
|----|--------|
| Windows | `%APPDATA%\GIMP\3.2\plug-ins\sam3_select\sam3_select.py` |
| Linux | `~/.config/GIMP/3.2/plug-ins/sam3_select/sam3_select.py` (`chmod +x`) |
| macOS | `~/Library/Application Support/GIMP/3.2/plug-ins/sam3_select/sam3_select.py` |
| Flatpak | `~/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins/sam3_select/sam3_select.py` |

Then restart GIMP. Find it under **Select → SAM3 Interactive Select**.

## Speed notes (no more waiting)

- **No console windows**: helper processes run hidden (`CREATE_NO_WINDOW`
  on Windows) — nothing pops up, ever.
- **Interpreter is picked once**: the choice is cached in
  `sam3_select/.worker_choice.json` (re-validated after 24 h), so the
  dialog opens immediately instead of re-probing every Python.
- **Persistent worker server**: one worker process per dialog session keeps
  Python/torch imports and loaded models warm and even skips re-encoding
  the image when you just move clicks. Measured on CPU (SAM 2 tiny):
  first click ~8 s, every later click **~0.1 s**.
- **Default engine is SAM 2** (tiny 156 MB, fast on CPU, no login).
  Switch to SAM 3 in the dropdown when you want to type the object.

## Using it (live workflow)

1. Click the object (**left** = object, **right** = background), drag a box,
   and/or type what it is (`"red car"`, Enter to apply the text).
2. The green mask overlay updates **live** after every change (runs on a
   downscaled copy for speed; uncheck *Live preview* or press *Preview* for
   manual control).
3. With *Mirror live mask into the GIMP selection* checked, the canvas
   selection follows your clicks in real time.
4. Press **Run full-res → Select** for the final full-resolution mask.

First AI run downloads weights into `sam3_select/models/` (see below);
afterwards it works offline.

No manual installs needed for the built-in engines: if no ready Python is
found, the plug-in offers a one-time automatic setup
(`pip install --user pillow numpy opencv-python-headless` — user site only,
never system packages). You can also run it yourself on any OS:

```sh
python sam3_select.py --setup                 # small deps only
python sam3_select.py --setup --with-ai       # + torch/transformers/ultralytics (~GBs)
python sam3_select.py --sam3-caps             # show what this python can do
python sam3_select.py --demo                  # headless self-test, no GIMP needed
```

## How it works (why one file is enough)

GIMP's bundled Python has no `pip` and no `torch`, so it can never run SAM
directly. This plug-in is dual-mode:

1. **GIMP mode** — UI, preview, point/box/text collection, pixel export
   (flattened PNG via PDB, no raw-buffer code), applying the mask back as
   a selection. Uses only the stdlib + GIMP's own GI bindings.
2. **Worker mode** — the plug-in re-invokes *itself* with the best system
   Python (`python sam3_select.py --sam3-worker --job job.json`) which does
   the inference. On startup it probes every Python on the machine
   (`--sam3-caps`) and picks the most capable one.

Backend chain (first success wins, failures fall through silently).
Smallest to biggest: NumPy = GrabCut (0 MB) < SAM 2 tiny 156 MB <
SAM 2 large ~900 MB < SAM 3 ~3.4 GB. **Only SAM 3 understands typed words.**
The dialog shows a one-line summary per engine plus a "Which one...?"
comparison window; `python sam3_select.py --engines` prints it headless.

| Engine (dialog label) | Weights | Speed | Quality | Use when |
|---|---|---|---|---|
| **Auto** (default) | whatever is installed | fastest ready first | best available | you just want it to work |
| **SAM 3 (Transformers)** | ~3.4 GB (`facebook/sam3`, gated login) | slow on CPU (minutes), fast on GPU | best; finds EVERY match | you TYPE the object ("all red cars"), many instances, best edges |
| **SAM 3 (Ultralytics)** | 3.45 GB `sam3.pt` — MANUAL download (gated), copy to `models/` | slow on CPU, ~3 s/image on GPU | best | same power as offline `.pt` file |
| **SAM 2** | tiny 156 MB (auto) … small ~185 … base+ ~320 … large ~900 MB | fast, even on CPU with tiny | very good, no text search | small download + quick result; you point at ONE object with clicks/box |
| **GrabCut** | none (0 MB) | seconds on CPU | good on clear fg/bg contrast | zero downloads: products, logos, sky vs ground |
| **NumPy** | none (0 MB) | instant | basic | last resort; always works offline |

## Models live in the plugin folder

All weights are stored in `sam3_select/models/` — next to the plugin, not
in caches or home directories:

| File | Source | Size | When |
|------|--------|------|------|
| `hf/` | `facebook/sam3`, `facebook/sam2*` via Transformers (gated login for SAM 3) | ~1–3.5 GB | first Transformers run |
| `sam3.pt` | MANUAL download from `huggingface.co/facebook/sam3` (gated), copy here | 3.45 GB | first Ultralytics SAM 3 run |
| `sam2.1_hiera_tiny.pt` | auto-download from Meta mirror (or copy by hand) | 156 MB | first SAM 2 repo run |
| `sam2*.pt`, `sam2*hiera*.pt` | any copy-you-own checkpoint | varies | used first when present |

Recognised names: `sam3.pt`; `sam2.1_l/b/s/t.pt`, `sam2_l/b/s/t.pt`;
`sam2.1_hiera_l/b/s/t.pt`, `sam2_hiera_l.pt`. Local files always win over
downloads; after a download the file is kept in `models/`, so the next run
(and any offline machine you copy the folder to) needs no network.

To move to another machine / OS: copy the whole `sam3_select/` folder
(including `models/`) into that machine's GIMP `plug-ins/` dir — done.

CUDA builds of torch make it ~10–50× faster; CPU works for small images.

## Notes / limits

- Text-only prompts need a real SAM 3 backend (1 or 2); without weights the
  plug-in says so instead of guessing.
- First SAM 3 run downloads weights (~1–2 GB) — subsequent runs are local.
- Very large images: the preview is full-resolution; expect slower CPU
  inference. Downscale a duplicate layer for scouting if needed.
- Heavy AI packages are never auto-installed — only the small wheels in
  `--setup`. Pass `--with-ai` explicitly if you want everything fetched.
