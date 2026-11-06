#!/bin/sh
# ============================================================
#  gimp-sam-select — one-click installer for macOS / Linux.
#  Usage: download this repo (ZIP or git clone), then run:
#      ./install.sh
#  (or double-click it in your file manager). It copies the
#  plugin into your GIMP user folder. Then restart GIMP.
# ============================================================
set -eu
cd "$(dirname "$0")"

SRC="sam3_select"
if [ ! -f "$SRC/sam3_select.py" ]; then
  echo "[ERROR] $SRC/sam3_select.py not found next to this script."
  echo "        Run install.sh from the repo folder you downloaded."
  exit 1
fi

pick_first_existing_dir() {
  for d in "$@"; do
    if [ -d "$d" ]; then
      printf '%s' "$d"
      return 0
    fi
  done
  return 1
}

case "$(uname -s)" in
  Darwin)
    DEST="$(pick_first_existing_dir \
      "$HOME/Library/Application Support/GIMP/3.2/plug-ins" \
      "$HOME/Library/Application Support/GIMP/3.0/plug-ins" \
      || true)"
    [ -z "$DEST" ] && \
      DEST="$HOME/Library/Application Support/GIMP/3.2/plug-ins"
    ;;
  *)
    DEST="$(pick_first_existing_dir \
      "$HOME/.config/GIMP/3.2/plug-ins" \
      "$HOME/.config/GIMP/3.0/plug-ins" \
      "$HOME/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins" \
      || true)"
    [ -z "$DEST" ] && DEST="$HOME/.config/GIMP/3.2/plug-ins"
    ;;
esac
DEST="$DEST/sam3_select"

mkdir -p "$DEST/models"
cp -f "$SRC/sam3_select.py" "$DEST/"
chmod +x "$DEST/sam3_select.py"
# Carry any weights you already have (e.g. copied from another PC).
for w in "$SRC"/models/*.pt; do
  [ -f "$w" ] && cp -f "$w" "$DEST/models/"
done

echo ""
echo "[OK] Installed to: $DEST"
echo ""
echo "Next steps:"
echo "  1. Restart GIMP (quit it fully first)."
echo "  2. Open an image: Select -> SAM3 Interactive Select."
echo "  3. First AI run downloads the SAM 2 tiny model (~156 MB) into"
echo "     the models folder by itself. No setup needed for that."
echo ""
echo "Optional, for the big guns (needs python3 with pip):"
echo "  python3 \"$DEST/sam3_select.py\" --setup"
echo "  (adds GrabCut support; --setup --with-ai adds SAM 3, ~3.4 GB)"
