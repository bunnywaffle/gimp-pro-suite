# GIMP Pro Suite — Library & Switch Kit

> **Switch to GIMP without losing Photoshop.** A curated suite, showcase site, and plugin pack for essential GIMP 3.0 & 3.2+ plugins that close the last professional feature gaps.

**Live site:** [bunnywaffle.github.io/gimp-pro-suite](https://bunnywaffle.github.io/gimp-pro-suite/)  
**Direct Download:** [**Download ZIP (No Git Required)**](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip)

---

## Included Plugins

| Plugin | What it Replaces | Menu Location | Repo |
|---|---|---|---|
| **Mesh Warp & Transform Presets** | Photoshop/Illustrator Warp (Arc, Bulge, Flag, etc.) + Puppet Warp | `Filters → Distorts → Mesh Warp...` | [bunnywaffle/gimp-mesh-warp](https://github.com/bunnywaffle/gimp-mesh-warp) |
| **SAM 3 AI Interactive Select** | Photoshop Object Selection / Select Subject (Meta SAM 2 & SAM 3) | `Select → SAM3 Interactive Select` | [bunnywaffle/gimp-sam-select](https://github.com/bunnywaffle/gimp-sam-select) |
| **Adjustment Layers & Layer Effects** | Photoshop Adjustment Layers (19 GEGL) + Layer Styles (6 effects) | `Layer → Adjustment Layer` | [bunnywaffle/adjustment-layer](https://github.com/bunnywaffle/adjustment-layer) |
| **Vector Shape Tool** | Photoshop Custom Shapes (15 families, 60+ variants) | `Image / Tools → Vector Shape Generator` | [bunnywaffle/gimp-shape-tool](https://github.com/bunnywaffle/gimp-shape-tool) |
| **Quick Selection Brush** | Photoshop Quick Selection Brush (edge-aware graph-cut) | `Select → Quick Selection Brush` | [bunnywaffle/GIMP-Quick-Selection](https://github.com/bunnywaffle/GIMP-Quick-Selection) |
| **Content-Aware Fill** | Photoshop Content-Aware Fill (PatchMatch, Telea, multi-scale) | `Edit → Content-Aware Fill...` | [bunnywaffle/GIMP-Content-Aware-Fill](https://github.com/bunnywaffle/GIMP-Content-Aware-Fill) |

---

## How to Install

> **No Git required!** You do not need Git, command-line skills, or Python packages to install and use these plugins.

### Method 1: 1-Click Installer (Recommended — No Git Needed)

1. Click [**Download ZIP**](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip) (or click the green **Code → Download ZIP** button above).
2. Right-click the downloaded `.zip` file and select **Extract All...** (or unzip it).
3. Open the unzipped folder and run the installer:
   - **Windows**: Double-click **`install.bat`**.
   - **Linux / macOS**: Open terminal in folder and run **`./install.sh`** (or `bash install.sh`).
4. Restart GIMP 3. Done!

Both **Mesh Warp** and **SAM 3 Interactive Select** are now installed in your GIMP user plug-ins directory.

---

### Method 2: Drag & Drop (Zero Scripts, Zero Git)

If you prefer not running any scripts, you can manually copy the folders from `plugins/` directly into your GIMP user plug-ins folder:

1. Download and extract the [Suite ZIP](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip).
2. Copy the two folders inside `plugins/` (`mesh-warp` and `sam3_select`) into your GIMP plug-ins directory:

| OS | Plug-in Destination Folder |
|---|---|
| **Windows** | `%APPDATA%\GIMP\3.2\plug-ins\` *(e.g. `C:\Users\<YourUser>\AppData\Roaming\GIMP\3.2\plug-ins\`)* |
| **Linux** | `~/.config/GIMP/3.2/plug-ins/` *(run `chmod +x *.py`)* |
| **macOS** | `~/Library/Application Support/GIMP/3.2/plug-ins/` |
| **Flatpak (Linux)** | `~/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins/` |

3. Restart GIMP 3.

---

### Method 3: Using Git (For Developers)

```bash
git clone https://github.com/bunnywaffle/gimp-pro-suite.git
cd gimp-pro-suite

# Windows:
.\install.bat

# Linux / macOS:
chmod +x install.sh && ./install.sh
```

---

## Featured Plugins Detail

### 1. Mesh Warp & Transform Presets
- **15 Photoshop/Illustrator Warp Presets**: Arc, Arc Lower/Upper, Arch, Bulge, Shell Lower/Upper, Flag, Wave, Fish, Rise, FishEye, Inflate, Squeeze, Twist, and Custom.
- **Continuous Seam-Free Remapping**: Subpixel bilinear backward mapping. No antialiasing seams, wireframes, or polygon tears.
- **Dynamic Control Grid**: $2 \times 2$ to $24 \times 24$ mesh, soft cosine falloff radius, symmetry mirroring, and auto-expanding canvas.
- Upstream: [bunnywaffle/gimp-mesh-warp](https://github.com/bunnywaffle/gimp-mesh-warp)

### 2. SAM 3 AI Interactive Selection Tool
- **Meta SAM 2 & SAM 3 Integration**: Interactive object segmentation with live preview overlay.
- **Multimodal Prompts**: Left-click for foreground, right-click for background, drag bounding boxes, or type plain-text descriptions (`"red car"`).
- **Persistent High-Speed Worker**: Zero console windows, interpreter auto-discovery, persistent server caching (~0.1s clicks).
- Upstream: [bunnywaffle/gimp-sam-select](https://github.com/bunnywaffle/gimp-sam-select)

---

## Repository Structure

```
gimp-pro-suite/
  ├── index.html         # Responsive showcase & documentation site (Tailwind CDN)
  ├── README.md          # Project guide & reference
  ├── .nojekyll          # For GitHub Pages hosting
  ├── install.bat        # 1-click Windows installer (No Git required)
  ├── install.sh         # 1-click Linux / macOS installer (No Git required)
  └── plugins/
      ├── mesh-warp/     # Mesh Warp plugin code
      │   ├── mesh-warp.py
      │   ├── mesh_warp.py
      │   └── README.md
      └── sam3_select/   # SAM 3 Interactive Select plugin code
          ├── sam3_select.py
          ├── install.bat
          ├── install.sh
          └── README.md
```

---

## GitHub Pages Deployment

The static showcase site is live from the root of the repository:
1. Go to **Settings → Pages** in your GitHub repository.
2. Select **Source:** `Deploy from a branch`.
3. Set **Branch:** `main` and folder `/ (root)`, then click **Save**.
4. The site will deploy at `https://bunnywaffle.github.io/gimp-pro-suite/`.

---

## License

- Site & installation scripts: **MIT**
- Included plugins: **GNU General Public License v3.0 (GPL-3.0)** — see respective license files in `plugins/`.
- Not affiliated with GIMP or Adobe.
