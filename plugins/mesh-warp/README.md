# GIMP 3.0 / 3.2 Mesh Warp & Transform Presets Plugin

An interactive, GPU/C-accelerated **Mesh Warp & Puppet/Grid Transformation suite** for **GIMP 3.0 & GIMP 3.2+**.

Includes all 15 classic **Photoshop/Illustrator Warp Presets**, continuous backward pixel remapping (100% seam-free and wireframe-free), smooth bilinear patch subdivision, soft proportional falloff, horizontal/vertical symmetry, and layer auto-expansion.

Zero external dependencies — pure Python 3 using GIMP 3, GTK 3, and Cairo GObject Introspection bindings.

---

## Features

### 1. Photoshop / Illustrator Warp Presets Suite
- **15 Built-in Presets**:
  - **Arc**, **Arc Lower**, **Arc Upper**, **Arch**
  - **Bulge**, **Shell Lower**, **Shell Upper**
  - **Flag**, **Wave**, **Fish**, **Rise**
  - **FishEye**, **Inflate**, **Squeeze**, **Twist**
  - **Custom** (Free-form interactive mesh dragging)
- **Interactive Modifiers**:
  - **Bend Slider**: Continuous distortion control from $-100\%$ to $+100\%$.
  - **Horizontal & Vertical Distortion**: Tapers/perspectives the mesh in X and Y directions.
  - **Orientation Toggle**: Instantly switch between Horizontal and Vertical warps.
- **Hybrid Editing**: Pick any preset as a base shape, then grab and drag any control point on the grid to customize!

### 2. Seam-Free Direct Inverse Pixel Remapping
- Uses **Direct Continuous Backward Mapping** with sub-pixel bilinear interpolation for final layer commits.
- Eliminates polygon edge antialiasing artifacts completely — **100% solid, crisp, and free of any grid, wireframe, or zigzag seams**.

### 3. Interactive Viewport & Controls
- **Dynamic Resolution**: Change Columns & Rows ($2 \times 2$ to $24 \times 24$) with continuous bilinear deformation resampling to preserve edits.
- **Soft Proportional Falloff**: Smooth cosine-weighted brush influence radius for organic deformations.
- **Symmetry Mode**: Horizontal (Left/Right) and Vertical (Top/Bottom) mirroring.
- **Laplacian Mesh Smoothing**: One-click relaxation to smooth out folds and kinks.
- **Multi-Selection**: Marquee box drag selection or `Shift + Click`.
- **Single Vertex Reset**: `Right-Click` or `Delete/Backspace` to reset selected pins.
- **Navigation**: Mouse wheel zoom (cursor-anchored), `Space + Drag` or `Middle-Click` pan, "Fit View", and "100%" buttons.
- **Auto-Expand Layer**: Automatically resizes layer canvas if the warp expands beyond original boundaries so artwork is never clipped.

---

## Installation

### 1. Locate your GIMP 3.x Plug-ins folder:
- **Windows**: `C:\Users\<Username>\AppData\Roaming\GIMP\3.2\plug-ins\` (or `...\3.0\plug-ins\`)
- **Linux**: `~/.config/GIMP/3.2/plug-ins/` (or `~/.config/GIMP/3.0/plug-ins/`)
- **macOS**: `~/Library/Application Support/GIMP/3.2/plug-ins/`

### 2. Copy or Clone:
Create a folder named `mesh-warp` inside your `plug-ins` directory:
```bash
git clone https://github.com/bunnywaffle/gimp-mesh-warp.git mesh-warp
```
*(or copy `mesh-warp.py` directly into a `mesh-warp/` subfolder).*

> **Note for Linux / macOS**: Ensure the script is executable:
> ```bash
> chmod +x mesh-warp/mesh-warp.py
> ```

### 3. Restart GIMP 3.x:
The plugin will appear in:
- **Filters → Distorts → Mesh Warp...**
- *(and **Tools → Transform Tools → Mesh Warp...**)*

---

## Keyboard & Mouse Shortcuts

| Action | Shortcut |
| :--- | :--- |
| **Warp Control Point** | `Click & Drag` pin |
| **Multi-Select Pins** | `Shift + Click` or `Click & Drag Box` |
| **Reset Pin(s)** | `Right-Click` on pin or `Delete` / `Backspace` |
| **Pan Canvas** | `Middle-Click + Drag` or `Spacebar + Drag` |
| **Zoom Canvas** | `Mouse Wheel` (anchored to cursor) or `+` / `-` |
| **Fit to View** | `0` key or `Fit View` button |
| **Toggle Wireframe Grid** | `H` key |
| **Deselect Pins** | `Escape` key |

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
