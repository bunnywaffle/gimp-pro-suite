#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAM3 Interactive Select — self-contained GIMP 3 plug-in.
========================================================
Select the object you want by clicking on it (foreground / background
points), dragging a box, and/or typing what it is ("red car"). The mask
is produced by Meta's Segment Anything Model 3 (SAM 3) and applied to
the image as a GIMP selection / channel / layer.

ONE FILE, TWO MODES
-------------------
1. GIMP mode  : placed in  <GIMP user dir>/plug-ins/sam3_select/sam3_select.py
                GIMP 3 imports it and registers "SAM3 Interactive Select"
                under  Select > SAM3 Interactive Select.
2. Worker mode: the plug-in re-invokes ITSELF with a normal system Python::

                    python sam3_select.py --sam3-worker --job job.json
                    python sam3_select.py --sam3-caps
                    python sam3_select.py --demo
                    python sam3_select.py --setup [--with-ai] [--no-grabcut]

   --setup pip-installs the small worker deps (pillow, numpy, opencv) into
   the user site on any OS, so no manual installs are needed for the
   built-in engines.

GIMP's bundled interpreter (3.14, no pip, no torch) can never run SAM, so
the GIMP side only handles UI + pixels and delegates inference to a system
Python found on PATH. Backend priority in the worker:

    1. transformers  facebook/sam3  (true SAM 3, text + points + boxes)
    2. ultralytics   sam3.pt        (true SAM 3, points/boxes, text via semantic predictor)
    3. SAM 2         (explicit option: transformers facebook/sam2*,
                      ultralytics sam2*, or sam2 repo — points/boxes)
    4. OpenCV GrabCut (no model download, still point/box interactive)
    5. Pure NumPy region-grow fallback (zero extra deps, always works)

All model weights live in <plugin folder>/models (transformers cache,
ultralytics .pt files, SAM 2 checkpoints) — downloaded once on first use,
then fully offline. Drop your own .pt files there and they are used first.

Backends 1-3 are tried best-effort with several call conventions because the
SAM 3 APIs are still young; anything that raises falls through to the next
backend so the plug-in NEVER hard-fails.

Layout inside GIMP (Windows example):
    %APPDATA%\\GIMP\\3.2\\plug-ins\\sam3_select\\sam3_select.py
"""

import os
import sys
import glob
import json
import subprocess
import tempfile
import time
import shutil
import traceback

PLUGIN_NAME = "sam3-interactive-select"
PLUGIN_LABEL = "SAM3 Interactive Select"
HF_SAM3_ID = "facebook/sam3"

IN_GIMP = False
try:
    import gi  # noqa: F401
    gi.require_version("Gimp", "3.0")
    from gi.repository import Gimp  # noqa: F401
    IN_GIMP = True
except Exception:
    IN_GIMP = False

WORKER_MODES = ("--sam3-worker", "--sam3-caps", "--demo", "--setup",
                "--engines", "--sam3-server")

# Small, always-safe worker requirements. Installed with `pip --user` by
# --setup / auto-bootstrap. Heavy AI deps (torch, transformers, ultralytics)
# are NEVER auto-installed (hundreds of MB); the plug-in just uses them when
# present and otherwise falls back to GrabCut / NumPy.
WORKER_MIN_DEPS = ["pillow", "numpy"]
WORKER_NICE_DEPS = ["opencv-python-headless"]  # GrabCut without GUI libs


def _popen_kwargs():
    """Windows: never pop up a terminal/console window for helper processes.
    (This was the 'terminal opens every time' bug — plain subprocess.run /
    Popen spawns a visible console on Windows unless CREATE_NO_WINDOW.)"""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW",
                                         0x08000000)}
    return {}


def run_quiet(*args, **kwargs):
    """subprocess.run without ever showing a console window (Windows)."""
    kw = _popen_kwargs()
    kw.update(kwargs)
    return subprocess.run(*args, **kw)


def popen_quiet(*args, **kwargs):
    """subprocess.Popen without ever showing a console window (Windows)."""
    kw = _popen_kwargs()
    kw.update(kwargs)
    if "stderr" not in kw:
        kw["stderr"] = subprocess.DEVNULL
    return subprocess.Popen(*args, **kw)


def parse_first_json(text):
    """First JSON object in process output. Torch/sam2 print startup
    warnings (often to stdout on some platforms) — this tolerates leading
    and trailing junk on any OS."""
    i = (text or "").find("{")
    if i < 0:
        raise RuntimeError("no JSON in output: %s" % (text or "")[-300:])
    obj, _ = json.JSONDecoder().raw_decode(text, i)
    if not isinstance(obj, dict):
        raise RuntimeError("JSON is not an object")
    return obj


def read_json_reply(stream, max_lines=100):
    """Next line on a server pipe that parses as a JSON object, skipping
    blank lines and library chatter. Returns None on EOF (dead server)."""
    for _ in range(max_lines):
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def worker_choice_cache_path():
    return os.path.join(plugin_base_dir(), ".worker_choice.json")

# ---------------------------------------------------------------------------
# Model store: EVERYTHING lives in <plugin folder>/models  (self-contained).
# The worker derives this from its own __file__, so GIMP and worker always
# agree, on every OS. First AI run downloads into it; afterwards the
# plug-in is fully offline-capable. Users may also copy weights there by
# hand (any file name below is recognised).
# ---------------------------------------------------------------------------
ULTRA_SAM3_NAMES = ["sam3.pt"]
ULTRA_SAM2_NAMES = ["sam2.1_l.pt", "sam2_l.pt", "sam2.1_b.pt", "sam2_b.pt",
                    "sam2.1_s.pt", "sam2_s.pt", "sam2.1_t.pt", "sam2_t.pt"]
SAM2_REPO_CKPTS = ["sam2.1_hiera_l.pt", "sam2_hiera_l.pt",
                   "sam2.1_hiera_b.pt", "sam2.1_hiera_t.pt",
                   "sam2.1_hiera_s.pt"]
# Official Meta mirror (same links as the SAM 2 README). Only the tiny
# checkpoint is auto-fetched (~150 MB); larger ones can be dropped into
# models/ manually or pointed at via SAM2_CHECKPOINT.
SAM2_TINY_URL = ("https://dl.fbaipublicfiles.com/segment_anything_2/092824/"
                 "sam2.1_hiera_tiny.pt")
SAM2_TINY_NAME = "sam2.1_hiera_tiny.pt"


# ---------------------------------------------------------------------------
# "Which engine should I use?" guide (sizes from Ultralytics benchmarks +
# Meta's checkpoint table; speeds are qualitative — GPU changes everything).
# Smallest to biggest: NumPy = GrabCut (0 MB) < SAM 2 tiny 156 MB <
# SAM 2 large ~900 MB < SAM 3 ~3.4 GB. Only SAM 3 understands typed words.
# ---------------------------------------------------------------------------
ENGINE_GUIDE = [
    {"id": "auto",
     "name": "Auto",
     "weights": "whatever is installed",
     "speed": "fastest ready engine first",
     "quality": "best available",
     "prompts": "click / box / text",
     "use": "Default. Just works: tries SAM 3, SAM 2, GrabCut, NumPy."},
    {"id": "sam3_transformers",
     "name": "SAM 3 (Transformers)",
     "weights": "~3.4 GB (facebook/sam3, needs login OK)",
     "speed": "slow on CPU (minutes), fast on GPU",
     "quality": "best; finds EVERY match",
     "prompts": "text + clicks + box",
     "use": "TYPE the object ('all red cars'); many instances; best edges."},
    {"id": "sam3_ultralytics",
     "name": "SAM 3 (Ultralytics)",
     "weights": "3.45 GB sam3.pt — MANUAL download (gated), copy to models/",
     "speed": "slow on CPU, ~3 s/image on GPU",
     "quality": "best; finds EVERY match",
     "prompts": "text + clicks + box",
     "use": "Same power as above as an offline .pt file."},
    {"id": "sam2",
     "name": "SAM 2",
     "weights": "tiny 156 MB (auto) ... small ~185 ... base+ ~320 ... large ~900 MB",
     "speed": "fast, even on CPU with tiny",
     "quality": "very good (no text search)",
     "prompts": "clicks + box",
     "use": "Small download + quick result; you point at ONE object."},
    {"id": "grabcut",
     "name": "GrabCut",
     "weights": "none (0 MB)",
     "speed": "seconds on CPU",
     "quality": "good on clear fg/bg contrast",
     "prompts": "box (+ clicks)",
     "use": "No downloads, no torch: products, logos, sky vs ground."},
    {"id": "numpy",
     "name": "NumPy",
     "weights": "none (0 MB)",
     "speed": "instant",
     "quality": "basic",
     "prompts": "clicks / box",
     "use": "Last resort; always works offline."},
]

ENGINE_RULES = [
    "Want to TYPE the object ('red car', 'all dogs')?  ->  SAM 3 (only one that understands words).",
    "Small download + fast CPU result?                 ->  SAM 2 tiny (156 MB, auto-fetched).",
    "Best quality + you have a GPU?                    ->  SAM 3 (~3.4 GB).",
    "Point at ONE thing with clicks/box?               ->  SAM 2.",
    "Zero downloads, zero setup?                       ->  GrabCut, then NumPy.",
]


def engine_hint_text(bid):
    """One-line summary for the engine dropdown."""
    for e in ENGINE_GUIDE:
        if e["id"] == bid:
            return "%s | %s | %s | prompts: %s -- %s" % (
                e["weights"], e["speed"], e["quality"], e["prompts"], e["use"])
    return ""


def engine_table_text():
    """Monospace comparison table for the 'Which one?' dialog / --engines."""
    lines = ["%-22s %-34s %-28s %-24s" %
             ("ENGINE", "WEIGHTS (bigger = slower)", "SPEED", "QUALITY"),
             "-" * 112]
    for e in ENGINE_GUIDE:
        lines.append("%-22s %-34s %-28s %-24s" %
                     (e["name"][:22], e["weights"][:34],
                      e["speed"][:28], e["quality"][:24]))
    lines += ["", "Prompts & when to use:"]
    for e in ENGINE_GUIDE:
        lines.append("  %-22s [%s] %s" %
                     (e["name"][:22], e["prompts"], e["use"]))
    lines += ["", "Rule of thumb:"] + ["  " + r for r in ENGINE_RULES]
    return "\n".join(lines)


def plugin_base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def plugin_models_dir():
    d = os.path.join(plugin_base_dir(), "models")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def find_local_model(names):
    """First matching weight file inside the plugin models/ dir, else None."""
    try:
        mdir = plugin_models_dir()
        for n in names:
            p = os.path.join(mdir, n)
            try:
                if os.path.isfile(p) and os.path.getsize(p) > 1000000:
                    return p
            except Exception:
                continue
    except Exception:
        pass
    return None


def download_to(url, dest, timeout=900):
    """Stream a URL to dest (stdlib only). Raises on failure."""
    import urllib.request
    import shutil as _sh
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "sam3-gimp/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, \
            open(tmp, "wb") as f:
        _sh.copyfileobj(r, f, 1024 * 256)
    os.replace(tmp, dest)
    return dest


def local_models_status():
    """{'dir': ..., 'files': [{'name':..., 'mb':...}]} — for caps + dialog."""
    info = {"dir": plugin_models_dir(), "files": []}
    try:
        for n in sorted(os.listdir(info["dir"])):
            p = os.path.join(info["dir"], n)
            try:
                if os.path.isfile(p) and not n.endswith(".part"):
                    info["files"].append(
                        {"name": n,
                         "mb": round(os.path.getsize(p) / 1048576.0, 1)})
            except Exception:
                continue
    except Exception:
        pass
    return info


def cache_ultralytics_weights(names):
    """Best-effort: copy auto-downloaded ultralytics *.pt weights into the
    plugin models/ dir so next run is local-first (and offline)."""
    try:
        dest = plugin_models_dir()
        tried = set()
        cands = []
        for root in (os.getcwd(), os.path.expanduser("~/.ultralytics"),
                     os.path.expanduser("~/.cache")):
            for n in names:
                for sub in ("", "weights", "hub/checkpoints"):
                    cands.append(os.path.join(root, sub, n))
        for src in cands:
            try:
                base = os.path.basename(src)
                if base in tried:
                    continue
                tried.add(base)
                if os.path.isfile(src) and \
                        os.path.getsize(src) > 1000000 and \
                        os.path.realpath(src) != os.path.realpath(
                            os.path.join(dest, base)):
                    shutil.copyfile(src, os.path.join(dest, base))
            except Exception:
                continue
    except Exception:
        pass


def setup_worker_deps(python_exe=None, with_ai=False, with_grabcut=True):
    """OS-agnostic bootstrap: pip-install worker deps into the user site.

    Returns {"ok": bool, "log": str}. Only touches the user site
    (--user), never system packages. Safe to run on Windows / macOS / Linux.
    """
    exe = python_exe or sys.executable
    pkgs = list(WORKER_MIN_DEPS)
    if with_grabcut:
        pkgs += WORKER_NICE_DEPS
    if with_ai:
        pkgs += ["torch", "transformers", "ultralytics"]
    log = []
    for pkg in pkgs:
        try:
            r = run_quiet(
                [exe, "-m", "pip", "install", "--user", "--upgrade", pkg],
                capture_output=True, text=True, timeout=900)
            tail = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
            tail = tail[-600:] if len(tail) > 600 else tail
            log.append("== %s -> rc=%d\n%s" % (pkg, r.returncode, tail))
            if r.returncode != 0 and pkg in WORKER_MIN_DEPS:
                return {"ok": False, "python": exe, "log": "\n".join(log)}
        except Exception as e:  # noqa: BLE001
            log.append("== %s -> ERROR %s" % (pkg, str(e)[:300]))
            if pkg in WORKER_MIN_DEPS:
                return {"ok": False, "python": exe, "log": "\n".join(log)}
    return {"ok": True, "python": exe, "log": "\n".join(log)}


# ============================================================================
# PART 1 — worker side (runs under plain system python, no GIMP imports)
# ============================================================================

def worker_caps():
    """Report what this interpreter can do (used by the GIMP side to pick
    the best python on the system)."""
    caps = {
        "python": sys.executable,
        "version": sys.version.split()[0],
        "pil": False, "numpy": False, "cv2": None,
        "torch": None, "cuda": False,
        "transformers": None, "transformers_has_sam3": False,
        "ultralytics": None, "sam2_repo": False,
    }
    try:
        import PIL  # noqa: F401
        caps["pil"] = True
    except Exception:
        pass
    try:
        import numpy  # noqa: F401
        caps["numpy"] = True
    except Exception:
        pass
    try:
        import cv2
        caps["cv2"] = cv2.__version__
    except Exception:
        pass
    try:
        import torch
        caps["torch"] = torch.__version__
        try:
            caps["cuda"] = bool(torch.cuda.is_available())
        except Exception:
            pass
    except Exception:
        pass
    try:
        import transformers
        caps["transformers"] = transformers.__version__
        try:
            from transformers import Sam3Model, Sam3Processor  # noqa: F401
            caps["transformers_has_sam3"] = True
        except Exception:
            caps["transformers_has_sam3"] = False
    except Exception:
        pass
    try:
        import ultralytics
        caps["ultralytics"] = ultralytics.__version__
    except Exception:
        pass
    try:
        import sam2  # noqa: F401
        caps["sam2_repo"] = True
    except Exception:
        pass
    try:
        caps["models"] = local_models_status()
    except Exception:
        caps["models"] = {"dir": "", "files": []}
    return caps


def _load_image(job_image_path):
    from PIL import Image
    img = Image.open(job_image_path).convert("RGB")
    return img


def _points_to_lists(points, w, h, clamp=True):
    """job points: [{'x':..,'y':..,'label':1|0}, ...] in full-res pixels."""
    coords, labels = [], []
    for p in points or []:
        x = float(p["x"])
        y = float(p.get("y", 0))
        lab = int(p.get("label", 1))
        if clamp:
            x = min(max(x, 0.0), w - 1.0)
            y = min(max(y, 0.0), h - 1.0)
        coords.append([x, y])
        labels.append(lab)
    return coords, labels


def _harvest_mask_tensor(obj, w, h):
    """Best-effort: find the first tensor/array in a transformers-style
    output that looks like (instances, H, W) masks and collapse to one
    (H, W) float mask in [0, 1]. Returns None if nothing found."""
    import numpy as np
    try:
        import torch
        has_torch = True
    except Exception:
        torch = None
        has_torch = False

    candidates = []
    if has_torch and isinstance(obj, torch.Tensor):
        candidates.append(obj)
    if isinstance(obj, np.ndarray):
        candidates.append(obj)
    # HF ModelOutput: dict-like with .keys() / attributes
    try:
        keys = list(obj.keys()) if hasattr(obj, "keys") else []
    except Exception:
        keys = []
    for k in keys:
        try:
            candidates.append(obj[k])
        except Exception:
            pass
    for attr in ("pred_masks", "masks", "mask", "semantic_masks",
                 "instance_masks", "logits", "pred_logits"):
        try:
            v = getattr(obj, attr, None)
            if v is not None:
                candidates.append(v)
        except Exception:
            pass

    for c in candidates:
        try:
            if has_torch and isinstance(c, torch.Tensor):
                a = c.detach().float().cpu().numpy()
            else:
                a = np.asarray(c, dtype=np.float32)
            if a.ndim == 4:      # (B, N, H, W) or (N, 1, H, W)
                a = a.reshape(-1, a.shape[-2], a.shape[-1])
            elif a.ndim == 3:    # (N, H, W)
                pass
            elif a.ndim == 2:    # single (H, W)
                a = a[None]
            else:
                continue
            if a.shape[0] < 1 or a.shape[1] < 2 or a.shape[2] < 2:
                continue
            if a.min() < 0 or a.max() > 1:   # logits -> prob
                a = 1.0 / (1.0 + np.exp(-a))
            m = a.max(axis=0).astype(np.float32)  # union of instances
            # resize to image size
            from PIL import Image
            pm = Image.fromarray((m * 255).astype("uint8")).resize(
                (w, h), Image.BILINEAR)
            return np.asarray(pm, dtype=np.float32) / 255.0
        except Exception:
            continue
    return None


# Warm caches for --sam3-server (and repeated one-shot runs in one
# process): loaded models stay in RAM so clicks after the first pay
# inference time only. Keys: ("ultra", weights) / ("ultra_sem", weights).
_MODEL_CACHE = {}
# SAM 2 repo predictor + the image it already encoded: when the dialog
# re-sends the same (downscaled) input file, set_image() — the expensive
# image-encoder pass — is skipped and only the new prompts are decoded.
_SAM2_STATE = {}


def backend_sam3_transformers(img, text, coords, labels, box):
    """True SAM 3 via HuggingFace transformers (facebook/sam3).

    Supports text concepts, points and boxes. Output harvesting is generic
    so minor API drift does not break us; any exception -> fall through.
    NOTE: facebook/sam3 is a gated repo (accept terms + HF login once).
    Weights are cached into <plugin folder>/models (self-contained)."""
    import torch
    from transformers import Sam3Model, Sam3Processor
    from PIL import Image
    import numpy as np

    w, h = img.size
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_cache = os.path.join(plugin_models_dir(), "hf")
    try:
        model = Sam3Model.from_pretrained(HF_SAM3_ID, cache_dir=hf_cache)
        processor = Sam3Processor.from_pretrained(HF_SAM3_ID,
                                                  cache_dir=hf_cache)
    except TypeError:
        # very old transformers without cache_dir support
        model = Sam3Model.from_pretrained(HF_SAM3_ID)
        processor = Sam3Processor.from_pretrained(HF_SAM3_ID)
    model.to(device)
    model.eval()

    # --- attempt 1: native call convention (text + points + boxes) ---
    attempts = []
    kw = {"images": img, "return_tensors": "pt"}
    if text:
        kw["text"] = [[text]] if isinstance(text, str) else text
    if coords:
        kw["input_points"] = [[[coords]]]
        kw["input_labels"] = [[[labels]]]
    if box:
        x0, y0, x1, y1 = box
        kw["input_boxes"] = [[[[x0, y0, x1, y1]]]]
    attempts.append(kw)
    # --- attempt 2: bare image+text ---
    if text:
        attempts.append({"images": img, "text": [[text]],
                         "return_tensors": "pt"})
    # --- attempt 3: bare image (unconditional proposals) ---
    attempts.append({"images": img, "return_tensors": "pt"})

    last_err = None
    with torch.no_grad():
        for kw in attempts:
            try:
                inputs = processor(**kw)
                # move tensors to device
                if isinstance(inputs, dict):
                    inputs = {k: (v.to(device) if hasattr(v, "to") else v)
                              for k, v in inputs.items()}
                else:
                    try:
                        inputs = inputs.to(device)
                    except Exception:
                        pass
                out = model(**inputs) if isinstance(inputs, dict) else model(inputs)
                m = _harvest_mask_tensor(out, w, h)
                if m is not None and float(m.max()) > 0:
                    # text-less unconditional run returns everything; only
                    # accept it if user gave no text at all.
                    return m
            except Exception as e:  # noqa: BLE001 - fall through by design
                last_err = e
                continue
    raise RuntimeError("SAM3 transformers backend failed: %r" % (last_err,))


def backend_ultralytics(img, text, coords, labels, box, family="sam3"):
    """SAM via ultralytics, weights local-first from <plugin>/models.

    family="sam3": sam3.pt — points/boxes segment that object, text goes
      through SAM3SemanticPredictor (concept segmentation).
    family="sam2": sam2*.pt — points/boxes only.
    Local .pt files in <plugin>/models win; missing SAM 2 weights
    auto-download once, then are cached into models/ (offline next run).
    NOTE: sam3.pt is gated — download it manually from
    https://huggingface.co/facebook/sam3 and copy it into models/."""
    import numpy as np
    from PIL import Image
    import tempfile as _tf
    import os as _os

    names = ULTRA_SAM3_NAMES if family == "sam3" else ULTRA_SAM2_NAMES
    local = find_local_model(names)

    arr = np.asarray(img)
    tmp = _tf.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        Image.fromarray(arr).save(tmp.name, quality=92)
        src = tmp.name

        # --- text path (SAM 3 concept segmentation over the whole image) ---
        if text and family == "sam3":
            try:
                from ultralytics.models.sam import SAM3SemanticPredictor
                overrides = {"model": local or "sam3.pt", "conf": 0.25,
                             "task": "segment", "mode": "predict"}
                cache_key = ("ultra_sem", str(overrides["model"]))
                pred = _MODEL_CACHE.get(cache_key)
                if pred is None:
                    pred = SAM3SemanticPredictor(overrides=overrides)
                    _MODEL_CACHE[cache_key] = pred
                results = pred(text=[text])
                # results reference the predictor's loaded image; force ours
                if not getattr(results, "__sam3_src__", None):
                    results = pred(source=src, text=[text])
                m = _harvest_ultralytics_results(results, arr.shape[1],
                                                 arr.shape[0])
                if m is not None:
                    cache_ultralytics_weights(names)
                    return m
            except Exception:
                pass  # try visual-prompt path below

        # --- visual path: points / boxes segment that object ---
        try:
            from ultralytics import SAM
        except Exception:
            from ultralytics.models.sam import SAM  # older layout
        last_err = None
        tried = ([local] if local else []) + \
            [n for n in names if n != (os.path.basename(local) if local
                                       else None)]
        for weights in tried:
            try:
                cache_key = ("ultra", str(weights))
                model = _MODEL_CACHE.get(cache_key)
                if model is None:
                    model = SAM(weights)
                    _MODEL_CACHE[cache_key] = model
                call = {"source": src, "verbose": False}
                if box:
                    x0, y0, x1, y1 = box
                    call["bboxes"] = [[x0, y0, x1, y1]]
                if coords:
                    call["points"] = [coords]
                    call["labels"] = [labels]
                if len(call) == 2 and not text:
                    continue  # nothing to prompt with
                results = model.predict(**call)
                m = _harvest_ultralytics_results(results, arr.shape[1],
                                                arr.shape[0])
                if m is not None and float(m.max()) > 0:
                    try:
                        ckpt = getattr(model, "ckpt_path", None)
                        if ckpt and os.path.isfile(str(ckpt)):
                            dest = os.path.join(
                                plugin_models_dir(),
                                os.path.basename(str(ckpt)))
                            if os.path.realpath(str(ckpt)) != \
                                    os.path.realpath(dest):
                                shutil.copyfile(str(ckpt), dest)
                    except Exception:
                        pass
                    cache_ultralytics_weights(names)
                    return m
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
        raise RuntimeError("ultralytics-%s backend failed: %r"
                           % (family, last_err,))
    finally:
        try:
            _os.unlink(tmp.name)
        except Exception:
            pass


def _harvest_ultralytics_results(results, w, h):
    import numpy as np
    from PIL import Image
    try:
        rs = results if isinstance(results, list) else [results]
        acc = None
        for r in rs:
            mk = getattr(r, "masks", None)
            data = getattr(mk, "data", None) if mk is not None else None
            if data is None:
                continue
            try:
                import torch
                if isinstance(data, torch.Tensor):
                    a = data.detach().float().cpu().numpy()
                else:
                    a = np.asarray(data, dtype=np.float32)
            except Exception:
                a = np.asarray(data, dtype=np.float32)
            if a.ndim == 4:
                a = a.reshape(-1, a.shape[-2], a.shape[-1])
            if a.ndim != 3:
                continue
            m = a.max(axis=0).astype(np.float32)
            if m.max() > 1:
                m = m / m.max()
            pm = Image.fromarray((m * 255).astype("uint8")).resize(
                (w, h), Image.BILINEAR)
            cur = np.asarray(pm, dtype=np.float32) / 255.0
            acc = cur if acc is None else np.maximum(acc, cur)
        return acc
    except Exception:
        return None


def backend_sam2(img, coords, labels, box, allow_download=True):
    """SAM 2, explicit option: transformers -> ultralytics -> sam2 repo.

    Points/boxes only (SAM 2 has no text concepts). Checkpoints resolve
    local-first: $SAM2_CHECKPOINT, then <plugin>/models/*.pt, then a
    one-time auto-download of the tiny checkpoint into models/
    (skipped when allow_download=False, e.g. offline self-test)."""
    import numpy as np
    w, h = img.size
    last_err = None
    # 1) transformers sam2 (weights cached into plugin models/)
    try:
        import torch
        from transformers import Sam2Model, Sam2Processor
        hf_cache = os.path.join(plugin_models_dir(), "hf")
        for ckpt in ("facebook/sam2-hiera-large",
                     "facebook/sam2.1-hiera-large"):
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                try:
                    model = Sam2Model.from_pretrained(
                        ckpt, cache_dir=hf_cache).to(device).eval()
                    processor = Sam2Processor.from_pretrained(
                        ckpt, cache_dir=hf_cache)
                except TypeError:
                    model = Sam2Model.from_pretrained(ckpt).to(device).eval()
                    processor = Sam2Processor.from_pretrained(ckpt)
                kw = {"images": img, "return_tensors": "pt"}
                if coords:
                    kw["input_points"] = [[[coords]]]
                    kw["input_labels"] = [[[labels]]]
                if box:
                    x0, y0, x1, y1 = box
                    kw["input_boxes"] = [[[[x0, y0, x1, y1]]]]
                with torch.no_grad():
                    inputs = processor(**kw)
                    if isinstance(inputs, dict):
                        inputs = {k: (v.to(device) if hasattr(v, "to") else v)
                                  for k, v in inputs.items()}
                    out = model(**inputs)
                m = _harvest_mask_tensor(out, w, h)
                if m is not None and float(m.max()) > 0:
                    return m
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
    except Exception as e:  # noqa: BLE001
        last_err = e
    # 2) ultralytics sam2 (local-first weights, cached after download)
    try:
        m = backend_ultralytics(img, "", coords, labels, box, family="sam2")
        if m is not None and float(np.asarray(m).max()) > 0:
            return m
    except Exception as e:  # noqa: BLE001
        last_err = e
    # 3) facebook sam2 repo: env -> plugin models/ -> auto-fetch tiny
    try:
        ckpt = os.environ.get("SAM2_CHECKPOINT", "")
        if not (ckpt and os.path.isfile(ckpt)):
            ckpt = find_local_model(list(SAM2_REPO_CKPTS) +
                                    [SAM2_TINY_NAME]) or ""
        if not ckpt:
            if not allow_download:
                raise RuntimeError(
                    "no local SAM 2 checkpoint in %s and downloads disabled"
                    % plugin_models_dir())
            dest = os.path.join(plugin_models_dir(), SAM2_TINY_NAME)
            download_to(SAM2_TINY_URL, dest)   # one-time ~150 MB
            ckpt = dest
        if ckpt and os.path.isfile(ckpt):
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            import torch
            try:
                import sam2 as _sam2pkg
                pkgdir = os.path.dirname(os.path.abspath(_sam2pkg.__file__))
            except Exception:
                pkgdir = ""
            base = os.path.basename(ckpt).lower()
            size = "t" if ("tiny" in base or "_t." in base) else \
                   "s" if "_s." in base else \
                   "b" if ("_b." in base or "base" in base) else "l"
            ver = "sam2.1" if "2.1" in base or "2_1" in base else "sam2"
            cfg_cands = ([os.environ.get("SAM2_CONFIG", "")] if
                         os.environ.get("SAM2_CONFIG") else []) + [
                os.path.join("configs", ver,
                             "%s_hiera_%s.yaml" % (ver, size)),
                os.path.join(pkgdir, "..", "configs", ver,
                             "%s_hiera_%s.yaml" % (ver, size)),
                os.path.join(pkgdir, "configs", ver,
                             "%s_hiera_%s.yaml" % (ver, size)),
            ]
            cfg = next((c for c in cfg_cands
                        if c and os.path.isfile(c)), None)
            if cfg is None:
                raise RuntimeError("sam2 config yaml not found next to "
                                   "checkpoint %s" % ckpt)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            state_key = (ckpt, cfg, device)
            st = _SAM2_STATE.get(state_key)
            if st is None:
                st = {"predictor": SAM2ImagePredictor(
                    build_sam2(cfg, ckpt, device=device)), "img_key": None}
                _SAM2_STATE[state_key] = st
            predictor = st["predictor"]
            # Same image as last call (the dialog re-sends one downscaled
            # file while you click) -> skip set_image(), the slow encoder.
            img_key = (img.size, img.mode, hash(img.tobytes()))
            if st.get("img_key") != img_key:
                predictor.set_image(np.asarray(img))
                st["img_key"] = img_key
            kw = {}
            if coords:
                kw["point_coords"] = np.array(coords)
                kw["point_labels"] = np.array(labels, dtype=np.int32)
            if box:
                x0, y0, x1, y1 = box
                kw["box"] = np.array([x0, y0, x1, y1])
            masks, _, _ = predictor.predict(multimask_output=False, **kw)
            m = np.asarray(masks[0], dtype=np.float32)
            if float(m.max()) > 0:
                return m
    except Exception as e:  # noqa: BLE001
        last_err = e
    raise RuntimeError("SAM2 backends failed: %r" % (last_err,))


def backend_grabcut(img, coords, labels, box):
    """OpenCV GrabCut driven by the same prompts. No model download."""
    import numpy as np
    try:
        import cv2
    except Exception as e:
        raise RuntimeError("opencv not available: %r" % (e,))
    arr = np.asarray(img)
    h, w = arr.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    def stamp(x, y, val, r=6):
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        disc = (xx - x) ** 2 + (yy - y) ** 2 <= r * r
        sub = mask[y0:y1, x0:x1]
        sub[disc] = val

    has_fg = False
    for (x, y), lab in zip(coords, labels):
        if int(lab) == 1:
            stamp(int(x), int(y), cv2.GC_FGD, 6)
            has_fg = True
        else:
            stamp(int(x), int(y), cv2.GC_BGD, 8)
    iters = 5
    if box:
        x0, y0, x1, y1 = [int(v) for v in box]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w - 1, x1), min(h - 1, y1)
        if x1 > x0 + 2 and y1 > y0 + 2:
            cv2.grabCut(arr, mask, (x0, y0, x1 - x0, y1 - y0),
                        bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
        elif has_fg:
            cv2.grabCut(arr, mask, None, bgd, fgd, iters,
                        cv2.GC_INIT_WITH_MASK)
        else:
            raise RuntimeError("grabcut needs a box or FG points")
    elif has_fg:
        cv2.grabCut(arr, mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    else:
        raise RuntimeError("grabcut needs a box or FG points")
    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                   1.0, 0.0).astype(np.float32)
    if out.max() <= 0:
        raise RuntimeError("grabcut returned empty mask")
    return out


def backend_numpy(img, coords, labels, box):
    """Zero-dependency fallback: colour-distance region grow from the FG/BG
    points, hard-constrained by the box when given, lightly smoothed."""
    import numpy as np
    from PIL import Image
    arr = np.asarray(img).astype(np.float32) / 255.0
    h, w = arr.shape[:2]

    def sample(cx, cy, r=4):
        x0, x1 = max(0, cx - r), min(w, cx + r + 1)
        y0, y1 = max(0, cy - r), min(h, cy + r + 1)
        patch = arr[y0:y1, x0:x1].reshape(-1, 3)
        if patch.size == 0:
            return None
        return np.median(patch, axis=0)

    fg_cols = [sample(int(x), int(y)) for (x, y), l
               in zip(coords, labels) if int(l) == 1]
    bg_cols = [sample(int(x), int(y)) for (x, y), l
               in zip(coords, labels) if int(l) == 0]
    fg_cols = [c for c in fg_cols if c is not None]
    bg_cols = [c for c in bg_cols if c is not None]
    if not fg_cols and not box:
        raise RuntimeError("numpy fallback needs FG points or a box")
    if not fg_cols and box:
        x0, y0, x1, y1 = [int(v) for v in box]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        c = sample(cx, cy, 8)
        if c is not None:
            fg_cols = [c]
    if not bg_cols:  # image border as background model
        edge = np.concatenate([arr[0].reshape(-1, 3), arr[-1].reshape(-1, 3),
                               arr[:, 0].reshape(-1, 3),
                               arr[:, -1].reshape(-1, 3)], axis=0)
        bg_cols = [np.median(edge, axis=0)]

    fg = np.median(np.stack(fg_cols), axis=0)
    bg = np.median(np.stack(bg_cols), axis=0)

    d_fg = np.sqrt(((arr - fg) ** 2).sum(axis=2))
    d_bg = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    # soft decision with margin; sigma from colour spread
    margin = 0.06
    m = np.clip((d_bg - d_fg + margin) / (2 * margin + 1e-6), 0, 1)

    if box:
        x0, y0, x1, y1 = [int(v) for v in box]
        pad = 4
        yy, xx = np.mgrid[0:h, 0:w]
        outside = (xx < x0 - pad) | (xx > x1 + pad) | \
                  (yy < y0 - pad) | (yy > y1 + pad)
        m[outside] = 0.0

    # cheap smoothing: 2 passes of 3x3 box blur (pure numpy)
    for _ in range(2):
        p = np.pad(m, 1, mode="edge")
        m = (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] +
             p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:] +
             p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0
    m = (m > 0.5).astype(np.float32)

    # keep FG seeds covered: stamp discs at FG points
    yy, xx = np.mgrid[0:h, 0:w]
    for (x, y), lab in zip(coords, labels):
        if int(lab) == 1:
            m[((xx - x) ** 2 + (yy - y) ** 2) <= 36] = 1.0
    if m.max() <= 0:
        raise RuntimeError("numpy fallback returned empty mask")
    # tidy small version for saving
    _ = Image  # keep import used
    return m


def _smooth_mask(m):
    try:
        import cv2
        import numpy as np
        u8 = (m * 255).astype("uint8")
        u8 = cv2.medianBlur(u8, 5)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        u8 = cv2.morphologyEx(u8, cv2.MORPH_CLOSE, k)
        return (u8.astype(np.float32) / 255.0 > 0.5).astype(np.float32)
    except Exception:
        return m


def run_job(job):
    """job keys: input, output, points, box, text, backend, threshold."""
    import numpy as np
    from PIL import Image
    img = _load_image(job["input"])
    w, h = img.size
    coords, labels = _points_to_lists(job.get("points"), w, h)
    box = job.get("box")
    if box:
        x0, y0, x1, y1 = [float(v) for v in box]
        box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    text = (job.get("text") or "").strip()
    want = (job.get("backend") or "auto").lower()
    thr = float(job.get("threshold", 0.5))

    order = []
    if want in ("auto", "sam3"):
        order += ["sam3_transformers", "sam3_ultralytics"]
    elif want == "sam3_transformers":
        order += ["sam3_transformers"]
    elif want in ("sam3_ultralytics", "ultralytics"):
        order += ["sam3_ultralytics"]
    if want in ("auto", "sam2", "sam3"):
        # explicit SAM 2 option; also tried after SAM 3 in "sam3" mode
        order += ["sam2"]
    elif want == "sam2" and "sam2" not in order:
        order += ["sam2"]
    if want in ("auto", "grabcut"):
        order += ["grabcut"]
    elif want == "grabcut" and "grabcut" not in order:
        order += ["grabcut"]
    order += ["numpy"]

    errors, used = {}, None
    m = None
    for name in order:
        try:
            if name == "sam3_transformers":
                if not (text or coords or box):
                    raise RuntimeError("no prompt given")
                m = backend_sam3_transformers(img, text, coords, labels, box)
            elif name == "sam3_ultralytics":
                if not (text or coords or box):
                    raise RuntimeError("no prompt given")
                m = backend_ultralytics(img, text, coords, labels, box,
                                        family="sam3")
            elif name == "sam2":
                if not (coords or box):
                    raise RuntimeError("sam2 needs points or a box")
                m = backend_sam2(img, coords, labels, box,
                                 allow_download=bool(
                                     job.get("allow_download", True)))
            elif name == "grabcut":
                m = backend_grabcut(img, coords, labels, box)
            elif name == "numpy":
                m = backend_numpy(img, coords, labels, box)
            used = name
            break
        except Exception as e:  # noqa: BLE001 - fallthrough chain
            errors[name] = str(e)[:300]
            continue
    if m is None:
        raise RuntimeError("all backends failed: %s" % json.dumps(errors))

    m = np.asarray(m, dtype=np.float32)
    if m.shape[:2] != (h, w):
        m = np.asarray(Image.fromarray(
            (np.clip(m, 0, 1) * 255).astype("uint8")).resize((w, h),
                                                             Image.BILINEAR),
            dtype=np.float32) / 255.0
    m = _smooth_mask(np.clip(m, 0, 1))
    m = (m >= thr).astype("uint8") * 255
    # Live-preview jobs run on a downscaled input for speed; upscale the
    # mask back to full resolution when out_w/out_h are given.
    try:
        ow, oh = int(job.get("out_w") or 0), int(job.get("out_h") or 0)
    except Exception:
        ow, oh = 0, 0
    if ow > 0 and oh > 0 and (ow, oh) != (w, h):
        m = np.asarray(Image.fromarray(m, mode="L").resize(
            (ow, oh), Image.BILINEAR), dtype=np.uint8)
        w, h = ow, oh

    mask_l = Image.fromarray(m, mode="L")
    mask_l.save(job["output"])
    # RGBA twin (white + alpha) so GIMP can select-by-alpha trivially
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 255
    rgba[..., 2] = 255
    rgba[..., 3] = m
    twin = os.path.splitext(job["output"])[0] + "_rgba.png"
    Image.fromarray(rgba, mode="RGBA").save(twin)
    return {"ok": True, "backend": used, "mask": job["output"],
            "mask_rgba": twin, "width": w, "height": h,
            "fallbacks": errors}


def worker_main(argv):
    if "--sam3-caps" in argv:
        print(json.dumps(worker_caps(), indent=2))
        return 0
    if "--demo" in argv:
        return demo_main()
    if "--engines" in argv:
        print(engine_table_text())
        return 0
    if "--setup" in argv:
        # One-time, OS-agnostic bootstrap of the small worker deps.
        # Optional flags: --with-ai (also torch/transformers/ultralytics,
        # hundreds of MB) and --no-grabcut (skip opencv wheel).
        res = setup_worker_deps(
            sys.executable,
            with_ai="--with-ai" in argv,
            with_grabcut="--no-grabcut" not in argv)
        print(json.dumps(res, indent=2))
        print("--- capability after setup ---")
        print(json.dumps(worker_caps(), indent=2))
        return 0 if res["ok"] else 1
    if "--sam3-server" in argv:
        # Persistent worker: the dialog spawns this ONCE per session and
        # sends one job-JSON per stdin line, getting one result-JSON per
        # stdout line. Python/torch imports and loaded models stay warm, so
        # every click after the first costs inference time only.
        # Commands: {"cmd": "ping"} -> {"ok": true, "pong": true}
        #           {"cmd": "quit"} -> {"ok": true, "bye": true} + exit
        #           {job...}        -> run_job result
        return server_main()
    # --sam3-worker --job job.json
    job_path = None
    for i, a in enumerate(argv):
        if a == "--job" and i + 1 < len(argv):
            job_path = argv[i + 1]
    if not job_path:
        print(json.dumps({"ok": False,
                          "error": "usage: --sam3-worker --job job.json"}))
        return 2
    try:
        with open(job_path, "r", encoding="utf-8") as f:
            job = json.load(f)
        res = run_job(job)
        print(json.dumps(res))
        return 0
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)[:2000],
                          "trace": traceback.format_exc()[-3000:]}))
        return 1


def server_main():
    """ stdin: one JSON job per line. stdout: one JSON result per line. """
    data_in = sys.stdin
    count = 0
    for line in data_in:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except Exception:
            print(json.dumps({"ok": False,
                              "error": "server expects one JSON per line"}),
                  flush=True)
            continue
        if not isinstance(job, dict):
            print(json.dumps({"ok": False,
                              "error": "job must be a JSON object"}),
                  flush=True)
            continue
        if job.get("cmd") == "ping":
            print(json.dumps({"ok": True, "pong": True,
                              "served": count}), flush=True)
            continue
        if job.get("cmd") == "quit":
            print(json.dumps({"ok": True, "bye": True,
                              "served": count}), flush=True)
            return 0
        try:
            res = run_job(job)
            count += 1
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": str(e)[:2000]}
        print(json.dumps(res), flush=True)
    return 0


def demo_main():
    """Headless self-test: synthetic image, GrabCut/numpy fallback, no GIMP."""
    import numpy as np
    from PIL import Image, ImageDraw
    tmp = tempfile.mkdtemp(prefix="sam3demo_")
    src = os.path.join(tmp, "input.png")
    out = os.path.join(tmp, "mask.png")
    img = Image.new("RGB", (320, 240), (30, 120, 60))
    d = ImageDraw.Draw(img)
    d.ellipse([90, 50, 230, 190], fill=(210, 60, 50))   # fake "object"
    img.save(src)
    job = {"input": src, "output": out,
           "points": [{"x": 160, "y": 120, "label": 1},
                      {"x": 20, "y": 20, "label": 0}],
           "box": [80, 40, 240, 200], "text": "",
           "backend": "auto", "threshold": 0.5,
           "allow_download": False}  # demo stays offline: no weight fetch
    res = run_job(job)
    m = np.asarray(Image.open(out).convert("L")) > 127
    # object centre must be selected, far corner must not be
    assert bool(m[120, 160]), "demo: centre pixel not selected!"
    assert not bool(m[10, 10]), "demo: corner pixel wrongly selected!"
    coverage = float(m.mean())
    print(json.dumps({"demo": "PASS", "tmp": tmp, "result": res,
                      "coverage": round(coverage, 4)}, indent=2))
    return 0


# ============================================================================
# PART 2 — GIMP side (imported by GIMP 3; never imported by the worker)
# ============================================================================

if IN_GIMP and "--sam3-worker" not in sys.argv and \
        "--sam3-caps" not in sys.argv and "--demo" not in sys.argv:
    import gi
    gi.require_version("GimpUi", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gegl", "0.4")
    from gi.repository import (Gimp, GimpUi, Gtk, Gdk, Gegl, GObject,
                               GLib, Gio, GdkPixbuf)

    # ------------------------------------------------------------------
    def pdb_run(proc_name, props):
        """Call a PDB procedure via create_config; raise with GIMP's own
        error text on failure. Tries dashed + underscored prop names."""
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure(proc_name)
        if proc is None:
            raise RuntimeError("PDB procedure not found: %s" % proc_name)
        config = proc.create_config()
        for key, value in props.items():
            ok = False
            for variant in (key, key.replace("_", "-"),
                            key.replace("-", "_")):
                try:
                    config.set_property(variant, value)
                    ok = True
                    break
                except Exception:
                    continue
            if not ok:
                raise RuntimeError(
                    "cannot set property '%s' on %s" % (key, proc_name))
        result = proc.run(config)
        try:
            status = result.index(0)
        except Exception:
            status = Gimp.PDBStatusType.SUCCESS
        if int(status) != int(Gimp.PDBStatusType.SUCCESS):
            try:
                err = pdb.get_last_error()
            except Exception:
                err = "unknown PDB error"
            raise RuntimeError("%s failed: %s" % (proc_name, err))
        return result

    # ------------------------------------------------------------------
    def find_system_python():
        """Pick the best interpreter to run the worker, on any OS.

        Strategy (all OS-agnostic unless noted):
          1. honour VIRTUAL_ENV / CONDA_PREFIX (user's active env first),
          2. every python* found on PATH (all matches, not just the first),
          3. well-known install locations per OS,
          4. GIMP's own interpreter last (probed anyway; rarely usable).
        Each candidate is probed with --sam3-caps and scored; duplicates
        (symlinks, e.g. /usr/bin/python -> python3) are collapsed.
        """
        seen, cands = set(), []

        def add(p):
            if not p:
                return
            try:
                key = os.path.realpath(os.path.abspath(p))
            except Exception:
                key = p
            if key not in seen and os.path.isfile(key):
                seen.add(key)
                cands.append(key)

        def add_all_on_path(*names):
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            exts = (".exe", ".bat", ".cmd") if os.name == "nt" else ("",)
            for d in path_dirs:
                if not d or not os.path.isdir(d):
                    continue
                try:
                    entries = set(os.listdir(d))
                except Exception:
                    continue
                for n in names:
                    for e in (n + x for x in exts):
                        if e in entries:
                            add(os.path.join(d, e))

        # 1) active virtualenv / conda env
        for env_key, sub in (("VIRTUAL_ENV",
                              "Scripts/python.exe" if os.name == "nt"
                              else "bin/python3"),
                             ("CONDA_PREFIX",
                              "python.exe" if os.name == "nt"
                              else "bin/python3")):
            base = os.environ.get(env_key)
            if base:
                add(os.path.join(base, sub))

        # 2) everything on PATH (Windows: also the py launcher shims)
        add_all_on_path("python3", "python")
        if os.name == "nt":
            add_all_on_path("py")

        # 3) well-known locations
        if os.name == "nt":
            roots = [os.path.join(os.path.expanduser("~"), "AppData",
                                  "Local", "Programs", "Python"),
                     r"C:\Program Files\Python310",
                     r"C:\Program Files\Python311",
                     r"C:\Program Files\Python312",
                     r"C:\Python310", r"C:\Python311", r"C:\Python312",
                     r"C:\Python313", os.path.expanduser("~")]
            for root in roots:
                for pat in ("python.exe", "*/python.exe"):
                    try:
                        for m in glob.glob(os.path.join(root, pat)):
                            add(m)
                    except Exception:
                        continue
            # py launcher -> resolve real interpreters
            for arg in (["-3"], []):
                try:
                    r = run_quiet(
                        ["py"] + arg + ["-c",
                                        "import sys; print(sys.executable)"],
                        capture_output=True, text=True, timeout=20)
                    if r.returncode == 0 and r.stdout.strip():
                        add(r.stdout.strip().splitlines()[0].strip())
                except Exception:
                    continue
        else:  # posix: macOS / Linux / BSD
            for pat in ("/usr/bin/python3*", "/usr/local/bin/python3*",
                        "/opt/homebrew/bin/python3*",
                        "/opt/local/bin/python3*",
                        os.path.expanduser("~/.pyenv/shims/python*"),
                        os.path.expanduser("~/anaconda3/bin/python*"),
                        os.path.expanduser("~/miniconda3/bin/python*"),
                        os.path.expanduser("~/mambaforge/bin/python*"),
                        os.path.expanduser("~/.local/bin/python*"),
                        "/opt/python*/bin/python3*",
                        "/snap/bin/python*"):
                try:
                    for m in glob.glob(pat):
                        add(m)
                except Exception:
                    continue

        # 4) GIMP's own interpreter (last resort)
        add(sys.executable)

        def score(caps):
            s = 0
            if caps.get("pil") and caps.get("numpy"):
                s += 10
            else:
                return -1
            if caps.get("transformers_has_sam3"):
                s += 60
            elif caps.get("transformers"):
                s += 20
            if caps.get("ultralytics"):
                s += 40
            if caps.get("sam2_repo"):
                s += 15
            if caps.get("torch"):
                s += 10
            if caps.get("cuda"):
                s += 25
            if caps.get("cv2"):
                s += 5
            return s

        best, best_caps, notes = None, None, []
        for exe in cands[:10]:
            try:
                r = run_quiet([exe, os.path.abspath(__file__),
                                    "--sam3-caps"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    notes.append("%s: no caps" % exe)
                    continue
                caps = parse_first_json(r.stdout)
                sc = score(caps)
                notes.append("%s: score %d %s" % (
                    exe, sc, json.dumps(caps)))
                if sc >= 0 and (best is None or
                                sc > score(best_caps)):
                    best, best_caps = exe, caps
            except Exception as e:  # noqa: BLE001
                notes.append("%s: %s" % (exe, str(e)[:120]))
                continue
        # remember the full candidate list: run() may bootstrap deps on the
        # most promising interpreter and re-probe it.
        return best, best_caps, notes, cands[:10]

    # ------------------------------------------------------------------
    def bootstrap_worker(cands, notes):
        """Self-containment: if no interpreter has pillow+numpy yet, try
        `pip install --user pillow numpy opencv-python-headless` on the
        most promising candidates and re-probe. Returns (exe, caps) or
        (None, None). Only small wheels; never torch/transformers."""
        for exe in (cands or [])[:4]:
            try:
                probe = run_quiet(
                    [exe, "-c", "import sys; print(sys.executable)"],
                    capture_output=True, text=True, timeout=30)
                if probe.returncode != 0:
                    continue
                res = setup_worker_deps(exe)
                notes.append("bootstrap %s: %s" %
                             (exe, "ok" if res["ok"] else "FAILED"))
                if not res["ok"]:
                    continue
                r = run_quiet([exe, os.path.abspath(__file__),
                                    "--sam3-caps"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    continue
                caps = parse_first_json(r.stdout)
                if caps.get("pil") and caps.get("numpy"):
                    return exe, caps
            except Exception as e:  # noqa: BLE001
                notes.append("bootstrap %s: %s" % (exe, str(e)[:120]))
                continue
        return None, None

    # ------------------------------------------------------------------
    def cached_worker_choice():
        """Interpreter choice, cached in the plugin folder.

        A full rescan probes ~10 interpreters (each importing torch) and is
        what made the dialog slow to open every time. The choice is stored
        in .worker_choice.json and trusted for 24 h (exe must still exist),
        then re-validated with a single quick probe."""
        notes = []
        cache_path = worker_choice_cache_path()
        try:
            with open(cache_path, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            exe = saved.get("exe", "")
            age = time.time() - float(saved.get("saved_at", 0))
            if exe and os.path.isfile(exe):
                if age < 24 * 3600:
                    caps = saved.get("caps") or {}
                    if caps.get("pil") and caps.get("numpy"):
                        notes.append("worker from cache: %s" % exe)
                        return exe, caps, notes, [exe]
                r = run_quiet([exe, os.path.abspath(__file__),
                               "--sam3-caps"],
                              capture_output=True, text=True, timeout=25)
                caps = parse_first_json(r.stdout)
                if caps.get("pil") and caps.get("numpy"):
                    notes.append("cached worker re-validated: %s" % exe)
                    return exe, caps, notes, [exe]
                notes.append("cached worker stale: %s" % exe)
        except Exception as e:  # noqa: BLE001
            notes.append("worker cache miss: %s" % str(e)[:120])
        exe, caps, more, cands = find_system_python()
        notes = notes + more
        if exe:
            try:
                with open(cache_path, "w", encoding="utf-8") as fh:
                    json.dump({"exe": exe, "saved_at": time.time(),
                               "caps": caps}, fh)
            except Exception as e:  # noqa: BLE001
                notes.append("worker cache save failed: %s" % str(e)[:100])
        return exe, caps, notes, cands

    # ------------------------------------------------------------------
    class Sam3Dialog(Gtk.Dialog):
        """Interactive prompt collector: click FG/BG points, drag a box,
        type a concept. The mask is shown LIVE as a green overlay in the
        preview (auto re-runs on every change) and optionally mirrored
        straight into the GIMP selection as you click."""

        def __init__(self, image, preview_path, img_w, img_h,
                     python_exe, caps, tmpdir, worker_script, mirror_fn):
            super().__init__(title=PLUGIN_LABEL, modal=True)
            self.set_default_size(760, 660)
            self.image = image
            self.img_w, self.img_h = img_w, img_h
            self.points = []   # [(x, y, label)] full-res coords
            self.box = None    # (x0, y0, x1, y1) full-res
            self._drag = None  # preview-coords drag start
            self.python_exe = python_exe
            self.caps = caps or {}
            self.tmpdir = tmpdir
            self.worker_script = worker_script
            self.mirror_fn = mirror_fn
            self.result = None
            self.overlay_pix = None  # full-res GdkPixbuf (white + alpha)
            self._working = False
            self.server_proc = None  # persistent --sam3-server, one per dialog

            self.add_button("Cancel", Gtk.ResponseType.CANCEL)
            self.add_button("Clear points", 10)
            self.add_button("Undo point", 11)
            self.add_button("Preview", 12)
            self.run_btn = self.add_button("Run full-res  →  Select",
                                           Gtk.ResponseType.APPLY)
            self.run_btn.get_style_context().add_class("suggested-action")

            root = self.get_content_area()
            root.set_spacing(8)
            root.set_border_width(10)

            hint = Gtk.Label()
            hint.set_markup(
                "<b>Left-click</b> = object  •  "
                "<b>Right-click / Shift+click</b> = background  •  "
                "<b>drag</b> = box around object  •  "
                "or just type what it is below. "
                "The green mask updates <b>live</b> after every change.")
            hint.set_line_wrap(True)
            root.pack_start(hint, False, False, 0)

            # preview pixbuf
            self.pix = GdkPixbuf.Pixbuf.new_from_file(preview_path)
            self.area = Gtk.DrawingArea()
            self.area.set_hexpand(True)
            self.area.set_vexpand(True)
            self.area.set_size_request(640, 400)
            self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                                 Gdk.EventMask.BUTTON_RELEASE_MASK |
                                 Gdk.EventMask.POINTER_MOTION_MASK |
                                 Gdk.EventMask.BUTTON1_MOTION_MASK)
            self.area.connect("draw", self.on_draw)
            self.area.connect("button-press-event", self.on_press)
            self.area.connect("button-release-event", self.on_release)
            self.area.connect("motion-notify-event", self.on_motion)
            frame = Gtk.Frame()
            frame.add(self.area)
            root.pack_start(frame, True, True, 0)

            # text concept row
            trow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            trow.pack_start(Gtk.Label(label="Describe object:"), False,
                            False, 0)
            self.text_entry = Gtk.Entry()
            self.text_entry.set_placeholder_text(
                'e.g. "red car" — SAM 3 finds every match (optional)')
            self.text_entry.set_hexpand(True)
            trow.pack_start(self.text_entry, True, True, 0)
            root.pack_start(trow, False, False, 0)
            self.text_entry.connect("activate", self.on_text_go)

            # live row
            lrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.live_check = Gtk.CheckButton.new_with_label(
                "Live preview (re-run on every change)")
            self.live_check.set_active(True)
            lrow.pack_start(self.live_check, False, False, 0)
            self.mirror_check = Gtk.CheckButton.new_with_label(
                "Mirror live mask into the GIMP selection")
            self.mirror_check.set_active(True)
            self.mirror_check.set_tooltip_text(
                "Each live preview is also applied to the image selection, "
                "so you see marching ants on the canvas as you click.")
            lrow.pack_start(self.mirror_check, False, False, 0)
            root.pack_start(lrow, False, False, 0)

            # options row
            orow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            orow.pack_start(Gtk.Label(label="Engine:"), False, False, 0)
            self.backend_combo = Gtk.ComboBoxText()
            choices = (
                    ("auto", "Auto (SAM 3 → SAM 2 → GrabCut)"),
                    ("sam3", "SAM 3 (transformers → ultralytics)"),
                    ("sam3_transformers", "SAM 3 via Transformers"),
                    ("sam3_ultralytics", "SAM 3 via Ultralytics"),
                    ("sam2", "SAM 2 (transformers → ultralytics → repo)"),
                    ("grabcut", "GrabCut (no download)"),
                    ("numpy", "NumPy (no download)"))
            for bid, blabel in choices:
                self.backend_combo.append(bid, blabel)
            # Default = SAM 2: small download, fast even on CPU, no login.
            self.backend_combo.set_active(next(
                (i for i, (bid, _) in enumerate(choices) if bid == "sam2"),
                0))
            orow.pack_start(self.backend_combo, False, False, 0)
            orow.pack_start(Gtk.Label(label="Output:"), False, False, 0)
            self.out_combo = Gtk.ComboBoxText()
            for oid, olabel in (("selection", "Selection"),
                                ("channel", "Selection + channel"),
                                ("layer", "New masked layer")):
                self.out_combo.append(oid, olabel)
            self.out_combo.set_active(0)
            orow.pack_start(self.out_combo, False, False, 0)
            self.feather = Gtk.CheckButton.new_with_label("Feather 2px")
            orow.pack_start(self.feather, False, False, 0)
            which_btn = Gtk.Button.new_with_label("Which one...?")
            which_btn.set_tooltip_text("Compare engines: size, speed, "
                                       "quality — which fits your need")
            which_btn.connect("clicked", self.on_compare_engines)
            orow.pack_start(which_btn, False, False, 0)
            root.pack_start(orow, False, False, 0)

            self.engine_hint = Gtk.Label()
            self.engine_hint.set_line_wrap(True)
            self.engine_hint.set_halign(Gtk.Align.START)
            root.pack_start(self.engine_hint, False, False, 0)
            self.backend_combo.connect("changed", self.on_engine_changed)
            self.on_engine_changed(self.backend_combo)

            eng = []
            c = self.caps
            if c.get("transformers_has_sam3"):
                eng.append("SAM 3 ready (transformers)")
            if c.get("ultralytics"):
                eng.append("ultralytics present")
            if c.get("torch"):
                eng.append("torch %s%s" % (
                    c.get("torch"), " +CUDA" if c.get("cuda") else " (CPU)"))
            if c.get("cv2"):
                eng.append("GrabCut ready")
            eng.append("NumPy fallback")
            try:
                minfo = c.get("models") or {}
                mfiles = minfo.get("files") or []
                mdir = minfo.get("dir") or ""
                if mfiles:
                    models_txt = "Models in plugin folder: " + ", ".join(
                        "%s (%s MB)" % (f["name"], f["mb"]) for f in mfiles)
                else:
                    models_txt = ("Models folder is empty — weights "
                                  "auto-download here on first AI run: " + mdir)
            except Exception:
                models_txt = ""
            self.status = Gtk.Label()
            self.status.set_markup(
                "<small>Worker: <tt>%s</tt>  •  %s\n%s</small>" %
                (GLib.markup_escape_text(str(self.python_exe or "?")),
                 GLib.markup_escape_text(" | ".join(eng)),
                 GLib.markup_escape_text(models_txt)))
            self.status.set_line_wrap(True)
            root.pack_start(self.status, False, False, 0)

            self.connect("response", self.on_response)
            self.show_all()

        # ----- coordinate mapping -----
        def view(self):
            aw = max(1, self.area.get_allocated_width())
            ah = max(1, self.area.get_allocated_height())
            s = min(aw / self.img_w, ah / self.img_h)
            dw, dh = self.img_w * s, self.img_h * s
            ox, oy = (aw - dw) / 2.0, (ah - dh) / 2.0
            return s, ox, oy

        def to_preview(self, x, y):
            s, ox, oy = self.view()
            return ox + x * s, oy + y * s

        def to_image(self, px, py):
            s, ox, oy = self.view()
            return ((px - ox) / s, (py - oy) / s)

        # ----- drawing -----
        def on_draw(self, area, cr):
            aw = area.get_allocated_width()
            ah = area.get_allocated_height()
            cr.set_source_rgb(0.13, 0.13, 0.14)
            cr.paint()
            s, ox, oy = self.view()
            dw, dh = self.img_w * s, self.img_h * s
            Gdk.cairo_set_source_pixbuf(
                cr, self.pix.scale_simple(int(dw), int(dh),
                                          GdkPixbuf.InterpType.BILINEAR),
                ox, oy)
            cr.rectangle(ox, oy, dw, dh)
            cr.fill()
            # live mask overlay (green, alpha comes from the mask)
            if self.overlay_pix is not None:
                try:
                    ov = self.overlay_pix.scale_simple(
                        max(1, int(dw)), max(1, int(dh)),
                        GdkPixbuf.InterpType.BILINEAR)
                    surf = Gdk.cairo_surface_create_from_pixbuf(ov, 0, None)
                    cr.save()
                    cr.set_source_rgba(0.25, 1.0, 0.45, 0.45)
                    cr.mask_surface(surf, ox, oy)
                    cr.restore()
                except Exception:
                    pass
            # box
            if self.box:
                x0, y0 = self.to_preview(self.box[0], self.box[1])
                x1, y1 = self.to_preview(self.box[2], self.box[3])
                cr.set_source_rgba(0.2, 0.8, 1.0, 0.95)
                cr.set_line_width(2.0)
                cr.set_dash([6, 4], 0)
                cr.rectangle(x0, y0, x1 - x0, y1 - y0)
                cr.stroke()
                cr.set_dash([], 0)
            if self._drag:
                (sx, sy), (cx, cy) = self._drag
                cr.set_source_rgba(0.2, 0.8, 1.0, 0.7)
                cr.set_line_width(1.5)
                cr.rectangle(sx, sy, cx - sx, cy - sy)
                cr.stroke()
            # points
            for (x, y, lab) in self.points:
                px, py = self.to_preview(x, y)
                if lab == 1:
                    cr.set_source_rgba(0.25, 1.0, 0.4, 0.95)
                else:
                    cr.set_source_rgba(1.0, 0.3, 0.3, 0.95)
                cr.arc(px, py, 7, 0, 6.2832)
                cr.fill()
                cr.set_source_rgb(1, 1, 1)
                cr.set_line_width(1.5)
                cr.arc(px, py, 7, 0, 6.2832)
                cr.stroke()
                cr.set_source_rgb(1, 1, 1)
                cr.move_to(px - 4, py + 0.5)
                cr.set_font_size(11)
                cr.show_text("+" if lab == 1 else "–")
            return False

        # ----- mouse -----
        def on_press(self, area, event):
            if event.button == 3:
                x, y = self.to_image(event.x, event.y)
                self.points.append((x, y, 0))
                self.area.queue_draw()
                self.maybe_live()
                return True
            if event.button == 1:
                self._press_xy = (event.x, event.y)
                self._drag = [(event.x, event.y), (event.x, event.y)]
            return True

        def on_motion(self, area, event):
            if self._drag:
                self._drag[1] = (event.x, event.y)
                self.area.queue_draw()
            return True

        def on_release(self, area, event):
            if event.button != 1 or not self._drag:
                return True
            (sx, sy), _ = self._drag
            dx, dy = event.x - sx, event.y - sy
            self._drag = None
            if abs(dx) > 12 or abs(dy) > 12:
                # drag -> box
                x0, y0 = self.to_image(min(sx, event.x), min(sy, event.y))
                x1, y1 = self.to_image(max(sx, event.x), max(sy, event.y))
                x0 = min(max(x0, 0), self.img_w - 1)
                y0 = min(max(y0, 0), self.img_h - 1)
                x1 = min(max(x1, 0), self.img_w - 1)
                y1 = min(max(y1, 0), self.img_h - 1)
                self.box = (x0, y0, x1, y1)
            else:
                x, y = self.to_image(event.x, event.y)
                is_bg = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
                self.points.append((x, y, 0 if is_bg else 1))
            self.area.queue_draw()
            self.maybe_live()
            return True

        def on_text_go(self, _entry):
            self.maybe_live(force=True)

        def maybe_live(self, force=False):
            try:
                if self.live_check.get_active() or force:
                    if not self._working:
                        self.refresh_live()
            except Exception:
                pass

        def _set_working(self, on, backend=""):
            self._working = on
            try:
                self.run_btn.set_sensitive(not on)
            except Exception:
                pass
            if on:
                self.engine_hint.set_markup(
                    "<small>Running <b>%s</b> live... "
                    "(dialog pauses briefly)</small>" %
                    GLib.markup_escape_text(str(backend or "engine")))
                while Gtk.events_pending():
                    Gtk.main_iteration()
            else:
                try:
                    self.on_engine_changed(self.backend_combo)
                except Exception:
                    pass

        def server_request(self, job):
            """Send one job to the persistent worker (spawn it on first use).
            Restarts the server once if it died; raises on repeated failure
            so the caller can fall back to a one-shot run."""
            for attempt in (0, 1):
                proc = self.server_proc
                if proc is None or proc.poll() is not None:
                    self.server_proc = popen_quiet(
                        [self.python_exe, self.worker_script,
                         "--sam3-server"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        text=True, bufsize=1)
                    proc = self.server_proc
                    try:
                        proc.stdin.write(json.dumps({"cmd": "ping"}) + "\n")
                        proc.stdin.flush()
                        hello = read_json_reply(proc.stdout)
                        if not hello or not hello.get("pong"):
                            raise RuntimeError("no pong")
                    except Exception:
                        self.server_proc = None
                        raise RuntimeError("worker server did not start")
                try:
                    proc.stdin.write(json.dumps(job) + "\n")
                    proc.stdin.flush()
                    info = read_json_reply(proc.stdout)
                except Exception as e:  # noqa: BLE001
                    self.server_proc = None
                    if attempt == 0:
                        continue
                    raise RuntimeError(
                        "worker server comms failed: %s" % str(e)[:150])
                if not info:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    self.server_proc = None
                    if attempt == 0:
                        continue
                    raise RuntimeError("worker server exited")
                return info
            raise RuntimeError("worker server failed")

        def close_server(self):
            proc, self.server_proc = self.server_proc, None
            if proc is None:
                return
            try:
                if proc.poll() is None:
                    try:
                        proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                        proc.stdin.flush()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            except Exception:
                pass

        def refresh_live(self):
            """Re-run the worker on a downscaled copy for speed and show the
            mask as a live overlay (+ optional mirror into GIMP)."""
            if self._working:
                return
            has_prompt = bool(self.points) or self.box is not None or \
                bool(self.text_entry.get_text().strip())
            if not has_prompt:
                self.overlay_pix = None
                self.area.queue_draw()
                return
            backend = self.backend_combo.get_active_id()
            self._set_working(True, backend)
            try:
                maxside = 512
                s = min(1.0, maxside / float(max(self.img_w, self.img_h)))
                sw, sh = max(1, int(self.img_w * s)), \
                    max(1, int(self.img_h * s))
                small_in = os.path.join(self.tmpdir, "live_in.png")
                small = self.pix.scale_simple(
                    sw, sh, GdkPixbuf.InterpType.BILINEAR)
                small.savev(small_in, "png", [], [])
                pts = [{"x": x * s, "y": y * s, "label": lab}
                       for (x, y, lab) in self.points]
                box = [self.box[0] * s, self.box[1] * s,
                       self.box[2] * s, self.box[3] * s] \
                    if self.box else None
                mask_out = os.path.join(self.tmpdir, "live_mask.png")
                job = {"input": small_in, "output": mask_out,
                       "points": pts, "box": box,
                       "text": self.text_entry.get_text().strip(),
                       "backend": backend, "threshold": 0.5,
                       "allow_download": True,
                       "out_w": self.img_w, "out_h": self.img_h}
                jp = os.path.join(self.tmpdir, "live_job.json")
                with open(jp, "w", encoding="utf-8") as fh:
                    json.dump(job, fh)
                try:
                    info = self.server_request(job)
                except Exception:
                    # Persistent server unavailable -> one-shot fallback.
                    r = run_quiet(
                        [self.python_exe, self.worker_script,
                         "--sam3-worker", "--job", jp],
                        capture_output=True, text=True, timeout=600)
                    if r.returncode != 0:
                        out = ((r.stdout or "") + "\n" +
                               (r.stderr or ""))[-800:]
                        raise RuntimeError("worker failed: %s" % out)
                    info = parse_first_json(r.stdout)
                if not info.get("ok"):
                    raise RuntimeError(info.get("error", "worker failed"))
                rgba = info.get("mask_rgba", "")
                if not (rgba and os.path.isfile(rgba)):
                    raise RuntimeError("worker produced no mask")
                self.overlay_pix = GdkPixbuf.Pixbuf.new_from_file(rgba)
                self.area.queue_draw()
                mirrored = ""
                if self.mirror_check.get_active() and self.mirror_fn:
                    try:
                        self.mirror_fn(rgba)
                        mirrored = " + mirrored to GIMP selection"
                    except Exception as e:  # noqa: BLE001
                        mirrored = " (mirror failed: %s)" % str(e)[:150]
                self._set_working(False)
                self.engine_hint.set_markup(
                    "<small>Live: <b>%s</b> via %s%s. "
                    "Click to refine, then <b>Run full-res</b>.</small>" %
                    (GLib.markup_escape_text(str(info.get("backend", "?"))),
                     GLib.markup_escape_text(str(backend)),
                     GLib.markup_escape_text(mirrored)))
            except Exception as e:  # noqa: BLE001
                self._set_working(False)
                self.engine_hint.set_markup(
                    "<small>Live preview failed: %s</small>" %
                    GLib.markup_escape_text(str(e)[:300]))

        def on_engine_changed(self, combo):
            try:
                bid = combo.get_active_id()
            except Exception:
                bid = "auto"
            self.engine_hint.set_markup(
                "<small><b>%s:</b> %s</small>" %
                (GLib.markup_escape_text(
                    (combo.get_active_text() or bid or "")),
                 GLib.markup_escape_text(engine_hint_text(bid))))

        def on_compare_engines(self, _btn):
            dlg = Gtk.Dialog(title="Which engine should I use?",
                             transient_for=self, modal=True)
            dlg.set_default_size(780, 420)
            dlg.add_button("Close", Gtk.ResponseType.CLOSE)
            box = dlg.get_content_area()
            box.set_border_width(10)
            scroll = Gtk.ScrolledWindow()
            scroll.set_hexpand(True)
            scroll.set_vexpand(True)
            label = Gtk.Label()
            label.set_markup("<tt>%s</tt>" %
                             GLib.markup_escape_text(engine_table_text()))
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_selectable(True)
            scroll.add(label)
            box.pack_start(scroll, True, True, 0)
            dlg.show_all()
            dlg.run()
            dlg.destroy()

        def on_response(self, dlg, resp):
            if resp == 10:      # Clear points
                self.points = []
                self.box = None
                self.overlay_pix = None
                self.area.queue_draw()
                self.stop_emission_by_name("response")
                self.maybe_live()
            elif resp == 11:    # Undo point
                if self.box is not None and not self.points:
                    self.box = None
                elif self.points:
                    self.points.pop()
                self.overlay_pix = None
                self.area.queue_draw()
                self.stop_emission_by_name("response")
                self.maybe_live()
            elif resp == 12:    # Preview button: manual live refresh
                self.stop_emission_by_name("response")
                self.refresh_live()
            elif resp == int(Gtk.ResponseType.APPLY):
                if not self.points and self.box is None and \
                        not self.text_entry.get_text().strip():
                    Gimp.message("Click the object first (or drag a box, "
                                 "or type what it is).")
                    self.stop_emission_by_name("response")
                    return
                self.result = {
                    "points": [{"x": x, "y": y, "label": lab}
                               for (x, y, lab) in self.points],
                    "box": list(self.box) if self.box else None,
                    "text": self.text_entry.get_text().strip(),
                    "backend": self.backend_combo.get_active_id(),
                    "output": self.out_combo.get_active_id(),
                    "feather": self.feather.get_active(),
                }

    # ------------------------------------------------------------------
    def export_image_png(image, path):
        """Save a flattened PNG copy of the image via PDB (no Gegl bytes)."""
        dup = image.duplicate()
        try:
            try:
                dup.flatten()
            except Exception:
                pass
            f = Gio.File.new_for_path(path)
            # GIMP 3 file-save: (run-mode, image, file)
            try:
                pdb_run("gimp-file-save",
                        {"run-mode": Gimp.RunMode.NONINTERACTIVE,
                         "image": dup, "file": f})
            except Exception:
                # older/alternate signature with explicit options
                pdb_run("gimp-file-save",
                        {"run_mode": Gimp.RunMode.NONINTERACTIVE,
                         "image": dup, "file": f})
        finally:
            try:
                dup.delete()
            except Exception:
                pass

    def apply_mask(image, mask_rgba_path, mode, feather):
        """mask_rgba: white RGB + mask alpha. Select by its alpha."""
        f = Gio.File.new_for_path(mask_rgba_path)
        res = pdb_run("gimp-file-load-layer",
                      {"run-mode": Gimp.RunMode.NONINTERACTIVE,
                       "image": image, "file": f})
        try:
            layer = res.index(1)
        except Exception:
            layer = res.index(0)
        image.insert_layer(layer, None, 0)
        try:
            # NOTE: signature is select_item(operation, item) — verified
            # against Gimp 3.x GI: select_item(self, operation, item).
            image.select_item(Gimp.ChannelOps.REPLACE, layer)
            if feather:
                try:
                    pdb_run("gimp-selection-feather",
                            {"image": image, "radius": 2.0})
                except Exception:
                    pass
            if mode in ("channel", "layer"):
                # keep a copy of the selection as a channel
                try:
                    pdb_run("gimp-selection-save", {"image": image})
                except Exception:
                    pass
            if mode == "layer":
                # mask stays as a new layer: keep layer, drop selection
                try:
                    layer.set_name("SAM3 mask")
                except Exception:
                    pass
                try:
                    pdb_run("gimp-selection-none", {"image": image})
                except Exception:
                    pass
                return
        finally:
            if mode != "layer":
                try:
                    image.remove_layer(layer)
                except Exception:
                    pass
        Gimp.displays_flush()

    # ------------------------------------------------------------------
    def run(procedure, run_mode, image, drawables, config, data):
        GimpUi.init("sam3-select")
        tmpdir = tempfile.mkdtemp(prefix="sam3gimp_")
        try:
            preview_path = os.path.join(tmpdir, "preview.png")
            export_image_png(image, preview_path)

            try:
                from PIL import Image as _PI
                with _PI.open(preview_path) as im:
                    img_w, img_h = im.size
            except Exception:
                img_w, img_h = image.get_width(), image.get_height()

            python_exe, caps, notes, cands = cached_worker_choice()
            if python_exe is None:
                # Self-containment: try to bootstrap pillow/numpy/opencv
                # into the user site of the best interpreter candidate.
                Gimp.message("SAM3: no ready Python found — trying a one-time "
                             "setup (pip install --user pillow numpy "
                             "opencv-python-headless)...")
                try:
                    python_exe, caps = bootstrap_worker(cands, notes)
                except Exception as e:  # noqa: BLE001
                    notes.append("bootstrap: %s" % str(e)[:200])
                    python_exe, caps = None, None
            if python_exe is None:
                setup_cmd = ("python " if os.name == "nt"
                             else "python3 ") + os.path.abspath(__file__) \
                    + " --setup"
                Gimp.message(
                    "SAM3: no system Python with Pillow+NumPy found, and "
                    "automatic setup failed.\n\nFix ONE of these (any OS):\n"
                    "  1. Run once in a terminal:\n"
                    "       " + setup_cmd + "\n"
                    "  2. Or manually:\n"
                    "       python -m pip install --user pillow numpy "
                    "opencv-python-headless\n\nProbed:\n"
                    + "\n".join(notes[:10]))
                return procedure.new_return_values(
                    Gimp.PDBStatusType.CALLING_ERROR, GLib.Error())

            def _mirror_live(mask_rgba_path):
                # Live mirror: selection only, no channel/layer, no feather.
                apply_mask(image, mask_rgba_path, "selection", False)

            dlg = Sam3Dialog(image, preview_path, img_w, img_h,
                             python_exe, caps, tmpdir,
                             os.path.abspath(__file__), _mirror_live)
            resp = dlg.run()
            req = dlg.result
            try:
                dlg.close_server()
            except Exception:
                pass
            dlg.destroy()
            if resp != int(Gtk.ResponseType.APPLY) or not req:
                return procedure.new_return_values(
                    Gimp.PDBStatusType.SUCCESS, GLib.Error())

            mask_path = os.path.join(tmpdir, "mask.png")
            job = {"input": preview_path, "output": mask_path,
                   "points": req["points"], "box": req["box"],
                   "text": req["text"], "backend": req["backend"],
                   "threshold": 0.5, "allow_download": True}
            job_path = os.path.join(tmpdir, "job.json")
            with open(job_path, "w", encoding="utf-8") as fh:
                json.dump(job, fh)

            # busy cursor while the worker thinks
            try:
                image.set_busy(True)
            except Exception:
                pass
            try:
                r = run_quiet(
                    [python_exe, os.path.abspath(__file__),
                     "--sam3-worker", "--job", job_path],
                    capture_output=True, text=True, timeout=1200)
            finally:
                try:
                    image.set_busy(False)
                except Exception:
                    pass
            if r.returncode != 0 or not os.path.exists(mask_path):
                out = (r.stdout or "")[-1500:] + "\n" + (r.stderr or "")[-1500:]
                Gimp.message("SAM3 worker failed:\n" + out)
                return procedure.new_return_values(
                    Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())
            try:
                info = parse_first_json(r.stdout)
            except Exception:
                info = {}
            mask_rgba = info.get("mask_rgba",
                                 os.path.splitext(mask_path)[0] + "_rgba.png")
            apply_mask(image, mask_rgba, req["output"], req["feather"])
            Gimp.message("SAM3: mask applied (engine: %s)." %
                         info.get("backend", "?"))
            return procedure.new_return_values(
                Gimp.PDBStatusType.SUCCESS, GLib.Error())
        except Exception as e:  # noqa: BLE001
            Gimp.message("SAM3 error: %s\n%s" % (e, traceback.format_exc()[-2000:]))
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    class Sam3Plugin(Gimp.PlugIn):
        def do_set_i18n(self, name):
            return True, "gimp30-python", None

        def do_query_procedures(self):
            return [PLUGIN_NAME]

        def do_create_procedure(self, name):
            if name != PLUGIN_NAME:
                return None
            proc = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run, None)
            proc.set_image_types("*")
            proc.set_menu_label(PLUGIN_LABEL)
            proc.set_documentation(
                "Interactively select an object with SAM 3",
                "Click foreground/background points, drag a box, or type "
                "what the object is; SAM 3 (Segment Anything Model 3) "
                "returns a precise selection. Falls back to SAM 2 / "
                "GrabCut when no SAM 3 weights are available.",
                PLUGIN_NAME)
            proc.set_attribution("SAM3 GIMP plug-in", "SAM3 GIMP plug-in",
                                 "2026")
            proc.add_menu_path("<Image>/Select/" + PLUGIN_LABEL)
            return proc

    Gimp.main(Sam3Plugin.__gtype__, sys.argv)


# ============================================================================
# PART 3 — entry point
# ============================================================================
if __name__ == "__main__":
    if any(a in sys.argv for a in WORKER_MODES):
        sys.exit(worker_main(sys.argv[1:]))
    elif not IN_GIMP:
        print(__doc__)
        print("Headless tools: --sam3-caps | --sam3-worker --job job.json | "
              "--demo | --setup [--with-ai] [--no-grabcut]")
        sys.exit(0)
