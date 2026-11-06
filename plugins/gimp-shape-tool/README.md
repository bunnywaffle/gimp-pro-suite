# GIMP Vector Shape Tool

A shape generator plug-in for **GIMP 3.0 / 3.2+** that creates native Vector Layers, Paths, Raster Layers, and Selection Marquees.

## Features

- **15 shape families**: rectangles (rounded / chamfered / inverted corners), ellipses (arc / pie / donut), triangles, n-gons (3–64 sides), stars & starbursts, parallelograms / trapezoids / rhombi, arrows (linear / double / chevron / curved), speech bubbles (comic / callout / thought cloud), clouds, organic blobs, badges & ribbons, spirals, gears, and symbols (heart / cross / map pin).
- **Selection → Shape**: traces any active selection into an exact vector path (`🖼️ Exact Selection`), or generates a shape from the selection's bounding box.
- **Output modes**: native `Gimp.VectorLayer`, standalone Path (Paths dock), Raster Layer, or Selection Marquee (replace / add / subtract / intersect).
- **Live canvas preview** with in-place color updates.
- **Interactive sizing** — scale slider, quick multipliers, precise W/H, position, and rotation controls.
- **Colors** from GIMP's foreground/background with exact RGBA handling.

## Installation

GIMP 3 requires plug-ins to live in a subdirectory named after the main script.

1. Copy the folder `gimp-shape-tool/` into your plug-ins directory:
   - Windows: `%APPDATA%\GIMP\3.2\plug-ins\`
   - Linux: `~/.config/GIMP/3.2/plug-ins/`
   - macOS: `~/Library/Application Support/GIMP/3.2/plug-ins/`
2. (Linux/macOS) Make `gimp-shape-tool.py` executable.
3. Restart GIMP.

## Usage

Menu: **Image → Layer → Vector Shape Generator...**, **Tools → Vector Shape Generator...**, or **Filters → Render → Vector Shape Generator...**

1. Pick a **Shape** from the dropdown.
2. Adjust the shape-specific parameters.
3. Set size, position, rotation, fill/stroke, and **Output To**.
4. Click **Create Shape**.

For **From Active Selection**: select something on canvas, open the tool, choose *From Active Selection*, and pick *Exact Selection (Trace)* to convert the selection's actual outline into a vector shape.

## Files

| File                | Purpose                                        |
| ------------------- | ---------------------------------------------- |
| `gimp-shape-tool.py`| Plug-in entry point & shape creation pipeline  |
| `shape_dialog.py`   | GTK3 dialog, live preview, selection handling  |
| `shape_engine.py`   | Pure-Python SVG path geometry generators        |

## License

This project is licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).