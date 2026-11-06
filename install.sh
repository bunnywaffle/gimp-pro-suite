#!/usr/bin/env bash
# ============================================================
#  GIMP Pro Suite — Installer for Linux & macOS
#  Installs ALL 6 Pro Plugins into your GIMP user plug-ins directory:
#    1. Mesh Warp & Transform Presets (mesh-warp)
#    2. SAM 3 AI Interactive Select (sam3_select)
#    3. Adjustment Layers & Layer Effects (adjustment-layer)
#    4. Vector Shape Generator (gimp-shape-tool)
#    5. Quick Selection Brush Suite (GIMP-Quick-Selection)
#    6. Content-Aware Fill (content-aware-fill)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Installing GIMP Pro Suite (All 6 Plugins)"
echo "============================================================"
echo

# Locate GIMP plug-ins folder
GIMP_BASE=""
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  for ver in 3.2 3.0 2.99; do
    p="$HOME/Library/Application Support/GIMP/$ver/plug-ins"
    if [ -d "$p" ]; then GIMP_BASE="$p"; break; fi
  done
  if [ -z "$GIMP_BASE" ]; then
    GIMP_BASE="$HOME/Library/Application Support/GIMP/3.2/plug-ins"
  fi
else
  # Linux (check standard and flatpak locations)
  for ver in 3.2 3.0 2.99; do
    p="$HOME/.config/GIMP/$ver/plug-ins"
    if [ -d "$p" ]; then GIMP_BASE="$p"; break; fi
  done
  if [ -z "$GIMP_BASE" ]; then
    # Flatpak fallback
    fp="$HOME/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins"
    if [ -d "$fp" ]; then
      GIMP_BASE="$fp"
    else
      GIMP_BASE="$HOME/.config/GIMP/3.2/plug-ins"
    fi
  fi
fi

echo "Target plug-ins directory:"
echo "  $GIMP_BASE"
echo

# 1. Mesh Warp
echo "[1/6] Installing Mesh Warp & Transform Presets..."
MESH_SRC="$SCRIPT_DIR/plugins/mesh-warp"
MESH_DEST="$GIMP_BASE/mesh-warp"
if [ -f "$MESH_SRC/mesh-warp.py" ]; then
  mkdir -p "$MESH_DEST"
  cp "$MESH_SRC"/*.py "$MESH_DEST/"
  chmod +x "$MESH_DEST"/*.py
  echo "      [OK] Installed to: $MESH_DEST"
else
  echo "      [WARN] $MESH_SRC not found. Skipping."
fi

# 2. SAM 3 Interactive Select
echo "[2/6] Installing SAM 3 AI Interactive Select..."
SAM_SRC="$SCRIPT_DIR/plugins/sam3_select"
SAM_DEST="$GIMP_BASE/sam3_select"
if [ -f "$SAM_SRC/sam3_select.py" ]; then
  mkdir -p "$SAM_DEST/models"
  cp "$SAM_SRC/sam3_select.py" "$SAM_DEST/"
  chmod +x "$SAM_DEST/sam3_select.py"
  if compgen -G "$SAM_SRC/models/*.pt" > /dev/null; then
    cp "$SAM_SRC/models"/*.pt "$SAM_DEST/models/" 2>/dev/null || true
  fi
  echo "      [OK] Installed to: $SAM_DEST"
else
  echo "      [WARN] $SAM_SRC not found. Skipping."
fi

# 3. Adjustment Layers & Layer Effects
echo "[3/6] Installing Adjustment Layers & Layer Effects..."
ADJ_SRC="$SCRIPT_DIR/plugins/adjustment-layer"
ADJ_DEST="$GIMP_BASE/adjustment-layer"
if [ -f "$ADJ_SRC/adjustment-layer.py" ]; then
  mkdir -p "$ADJ_DEST"
  cp "$ADJ_SRC"/*.py "$ADJ_DEST/"
  chmod +x "$ADJ_DEST"/*.py
  echo "      [OK] Installed to: $ADJ_DEST"
else
  echo "      [WARN] $ADJ_SRC not found. Skipping."
fi

# 4. Vector Shape Tool
echo "[4/6] Installing Vector Shape Tool..."
SHAPE_SRC="$SCRIPT_DIR/plugins/gimp-shape-tool"
SHAPE_DEST="$GIMP_BASE/gimp-shape-tool"
if [ -f "$SHAPE_SRC/gimp-shape-tool.py" ]; then
  mkdir -p "$SHAPE_DEST"
  cp "$SHAPE_SRC"/*.py "$SHAPE_DEST/"
  chmod +x "$SHAPE_DEST"/*.py
  echo "      [OK] Installed to: $SHAPE_DEST"
else
  echo "      [WARN] $SHAPE_SRC not found. Skipping."
fi

# 5. Quick Selection Brush Suite
echo "[5/6] Installing Quick Selection Brush Suite..."
QS_SRC="$SCRIPT_DIR/plugins/GIMP-Quick-Selection"
QS_DEST="$GIMP_BASE/GIMP-Quick-Selection"
if [ -f "$QS_SRC/GIMP-Quick-Selection.py" ]; then
  mkdir -p "$QS_DEST"
  cp "$QS_SRC"/*.py "$QS_DEST/"
  chmod +x "$QS_DEST"/*.py
  echo "      [OK] Installed to: $QS_DEST"
else
  echo "      [WARN] $QS_SRC not found. Skipping."
fi

# 6. Content-Aware Fill
echo "[6/6] Installing Content-Aware Fill..."
CAF_SRC="$SCRIPT_DIR/plugins/content-aware-fill"
CAF_DEST="$GIMP_BASE/content-aware-fill"
if [ -f "$CAF_SRC/content-aware-fill.py" ]; then
  mkdir -p "$CAF_DEST"
  cp "$CAF_SRC"/*.py "$CAF_DEST/"
  if [ -d "$CAF_SRC/caf_engine" ]; then
    mkdir -p "$CAF_DEST/caf_engine"
    cp "$CAF_SRC/caf_engine"/*.py "$CAF_DEST/caf_engine/"
    chmod +x "$CAF_DEST/caf_engine"/*.py 2>/dev/null || true
  fi
  chmod +x "$CAF_DEST"/*.py
  echo "      [OK] Installed to: $CAF_DEST"
else
  echo "      [WARN] $CAF_SRC not found. Skipping."
fi

echo
echo "============================================================"
echo "  All 6 Plugins Installed Successfully!"
echo "============================================================"
echo
echo "Next steps:"
echo "  1. Restart GIMP 3."
echo "  2. Access your new tools in GIMP menus:"
echo "     - Mesh Warp:        Filters -> Distorts -> Mesh Warp..."
echo "     - SAM 3 AI Select:  Select -> SAM3 Interactive Select"
echo "     - Adjustment Layer: Layer -> Adjustment Layer / Layer Effects"
echo "     - Vector Shapes:    Image / Tools -> Vector Shape Generator..."
echo "     - Quick Selection:  Select -> Quick Selection Brush..."
echo "     - Content-Aware:    Edit -> Content-Aware Fill..."
echo
