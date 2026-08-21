# GIMP Pro Suite — Library & Switch Kit

> **Switch to GIMP without losing Photoshop.** A curated docs & showcase site for 5 essential GIMP 3.2 plugins that close the last pro feature gaps.

**Live site:** `https://<your-username>.github.io/gimp-suite/` (enable GitHub Pages on `main` → `/gimp-suite` or root)

This repo **does not host plugin code**. It documents, compares, and links to the upstream plugins.

---

## Included plugins

| Plugin | What it replaces | Repo |
|---|---|---|
| **Mesh Warp & Transform Presets** | Photoshop/Illustrator Warp (Arc, Bulge, Flag, etc.) | [bunnywaffle/gimp-mesh-warp](https://github.com/bunnywaffle/gimp-mesh-warp) |
| **Adjustment Layers & Layer Effects** | Photoshop Adjustment Layers + Layer Styles | [bunnywaffle/adjustment-layer](https://github.com/bunnywaffle/adjustment-layer) |
| **Vector Shape Tool** | Photoshop Custom Shapes | [bunnywaffle/gimp-shape-tool](https://github.com/bunnywaffle/gimp-shape-tool) |
| **Quick Selection Brush** | Photoshop Quick Selection / Object Selection | [bunnywaffle/GIMP-Quick-Selection](https://github.com/bunnywaffle/GIMP-Quick-Selection) |
| **Content-Aware Fill** | Photoshop Content-Aware Fill (PatchMatch) | [bunnywaffle/GIMP-Content-Aware-Fill](https://github.com/bunnywaffle/GIMP-Content-Aware-Fill) |

---

## Features of this site

- Hero + value proposition for switchers (save $659/yr vs Creative Cloud)
- Plugin cards with presets, menu paths, and direct GitHub links
- **Why Switch** comparison table (Photoshop vs GIMP + Suite)
- **Advanced Tool Library** — Color & Tone Lab (19 adjustments), Warp Lab (15 presets), Select & Heal Lab, Shapes & Effects
- **Installation** — OS paths + one-liner clone commands + menu locations
- FAQ, responsive, no build step

## Structure

```
gimp-suite/
  index.html   # single-file site (Tailwind CDN, no build)
  README.md
  .nojekyll    # for GitHub Pages
```

## Deploy to GitHub Pages

1. Create a new GitHub repo, e.g. `gimp-pro-suite` or `gimp-suite`
2. Push this folder as the repo root:
   ```bash
   git init
   git add .
   git commit -m "feat: GIMP Pro Suite docs site"
   git branch -M main
   git remote add origin https://github.com/<you>/gimp-suite.git
   git push -u origin main
   ```
3. In repo **Settings → Pages**: Source = `Deploy from a branch`, Branch = `main` / `root`, Save.
4. Your site will be at `https://<you>.github.io/gimp-suite/`

Alternatively use `docs/` folder or GitHub Actions — this site is static, either works.

## Customize

- Change `bunnywaffle` links to your own org if you fork the plugins
- Edit `index.html` — all styles are Tailwind CDN, sections are commented
- Add screenshots: put in `assets/` and reference with `assets/…`
- To add a 6th plugin: duplicate a card in the `#plugins` grid

## License

Site content: **MIT** (or keep GPL-3.0 to match plugins). Plugin code remains under their own **GPL-3.0** licenses — see each upstream repo.

---

Built for GIMP 3.2. Not affiliated with GIMP or Adobe.
