# GIMP Pro Suite — Library & Switch Kit

> **Switch to GIMP without losing Photoshop.** A curated suite, showcase site, and complete all-in-one plugin pack for essential GIMP 3.0 & 3.2+ plugins that close the last professional feature gaps.

**Live site:** [bunnywaffle.github.io/gimp-pro-suite](https://bunnywaffle.github.io/gimp-pro-suite/)  
**Direct Download:** [**Download Complete Suite ZIP (All 6 Plugins)**](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip)

---

## All 6 Plugins Included by Default

Every plugin in this suite is included directly under [`plugins/`](plugins/) with full source code, ready for one-click installation:

| # | Plugin | What it Replaces | Menu Location | Repo |
|---|---|---|---|---|
| 1 | **Mesh Warp & Transform Presets** | Photoshop/Illustrator Warp (Arc, Bulge, Flag, etc.) + Puppet Warp | `Filters → Distorts → Mesh Warp...` | [bunnywaffle/gimp-mesh-warp](https://github.com/bunnywaffle/gimp-mesh-warp) |
| 2 | **SAM 3 AI Interactive Select** | Photoshop Object Selection / Select Subject (Meta SAM 2 & SAM 3) | `Select → SAM3 Interactive Select` | [bunnywaffle/gimp-sam-select](https://github.com/bunnywaffle/gimp-sam-select) |
| 3 | **Adjustment Layers & Layer Effects** | Photoshop Adjustment Layers (19 GEGL) + Layer Styles (6 effects) | `Layer → Adjustment Layer` | [bunnywaffle/adjustment-layer](https://github.com/bunnywaffle/adjustment-layer) |
| 4 | **Vector Shape Tool** | Photoshop Custom Shapes (15 families, 60+ variants) | `Image / Tools → Vector Shape Generator` | [bunnywaffle/gimp-shape-tool](https://github.com/bunnywaffle/gimp-shape-tool) |
| 5 | **Quick Selection Brush** | Photoshop Quick Selection Brush (edge-aware graph-cut) | `Select → Quick Selection Brush` | [bunnywaffle/GIMP-Quick-Selection](https://github.com/bunnywaffle/GIMP-Quick-Selection) |
| 6 | **Content-Aware Fill** | Photoshop Content-Aware Fill (PatchMatch, Telea, multi-scale) | `Edit → Content-Aware Fill...` | [bunnywaffle/GIMP-Content-Aware-Fill](https://github.com/bunnywaffle/GIMP-Content-Aware-Fill) |

---

## How to Install All 6 Plugins

> **No Git required!** You do not need Git, command-line skills, or Python packages. Everything installs with one click.

### Method 1: 1-Click Installer (Recommended — No Git Needed)

1. Click [**Download Complete Suite ZIP**](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip) (or click the green **Code → Download ZIP** button on GitHub).
2. Right-click the downloaded `.zip` file and select **Extract All...** (or unzip it).
3. Open the unzipped folder and run the installer:
   - **Windows**: Double-click **`install.bat`**.
   - **Linux / macOS**: Open terminal in folder and run **`./install.sh`** (or `bash install.sh`).
4. Restart GIMP 3. Done!

All 6 plugins are now copied into your GIMP user plug-ins directory.

---

### Method 2: Drag & Drop (Zero Scripts, Zero Git)

If you prefer not running any scripts, you can manually copy all 6 folders from `plugins/` directly into your GIMP user plug-ins folder:

1. Download and extract the [Suite ZIP](https://github.com/bunnywaffle/gimp-pro-suite/archive/refs/heads/main.zip).
2. Copy the 6 folders inside `plugins/` directly into your GIMP plug-ins directory:
   - `mesh-warp`
   - `sam3_select`
   - `adjustment-layer`
   - `gimp-shape-tool`
   - `GIMP-Quick-Selection`
   - `content-aware-fill`

| OS | Plug-in Destination Folder |
|---|---|
| **Windows** | `%APPDATA%\GIMP\3.2\plug-ins\` *(e.g. `C:\Users\<YourUser>\AppData\Roaming\GIMP\3.2\plug-ins\`)* |
| **Linux** | `~/.config/GIMP/3.2/plug-ins/` *(run `chmod +x */*.py`)* |
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

## Repository Structure

```
gimp-pro-suite/
  ├── index.html                  # Responsive showcase & documentation site (Tailwind CDN)
  ├── README.md                   # Project guide & reference
  ├── .nojekyll                   # For GitHub Pages hosting
  ├── install.bat                 # 1-click Windows installer (Installs all 6 plugins)
  ├── install.sh                  # 1-click Linux / macOS installer (Installs all 6 plugins)
  └── plugins/                    # Full source code for ALL 6 plugins included by default
      ├── mesh-warp/              # 1. Mesh Warp & 15 Warp Presets
      ├── sam3_select/            # 2. SAM 3 AI Interactive Selection
      ├── adjustment-layer/       # 3. Adjustment Layers & Layer Effects
      ├── gimp-shape-tool/        # 4. Vector Shape Generator (60+ variants)
      ├── GIMP-Quick-Selection/   # 5. Quick Selection Brush Suite (5-stage hybrid)
      └── content-aware-fill/     # 6. Content-Aware Fill (PatchMatch & Poisson)
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
- Included plugins: **GNU General Public License v3.0 (GPL-3.0)** — see respective license files in each plugin folder under `plugins/`.
- Not affiliated with GIMP or Adobe.
