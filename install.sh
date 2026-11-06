#!/usr/bin/env bash
# ============================================================
#  GIMP Pro Suite — Installer for Linux & macOS
#  Installs both plugins into your GIMP user plug-ins directory:
#    - Mesh Warp & Transform Presets (mesh-warp)
#    - SAM 3 AI Interactive Select (sam3_select)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Installing GIMP Pro Suite Plugins"
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
echo "[1/2] Installing Mesh Warp & Transform Presets..."
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
echo "[2/2] Installing SAM 3 AI Interactive Select..."
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

echo
echo "============================================================"
echo "  Installation Complete!"
echo "============================================================"
echo
echo "Next steps:"
echo "  1. Restart GIMP 3."
echo "  2. Find Mesh Warp in:"
echo "     Filters -> Distorts -> Mesh Warp..."
echo "  3. Find SAM 3 AI Selection in:"
echo "     Select -> SAM3 Interactive Select"
echo
