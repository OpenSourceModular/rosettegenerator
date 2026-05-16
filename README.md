# OctoPrint Rosette Generator

Generate decorative rosette curve patterns directly in OctoPrint, preview them in the UI, and export SVG files.

## Features

- 12 rosette styles (Bump, Dip, Arch, Concave+Convex, Puffy, W, X + 1, Flat, Lotus, A, Sine, Bead)
- Live preview with optional auto-preview
- Save defaults in plugin settings
- Hold + merge workflow
- SVG export
- Optional Shapely-powered geometry merge support

## Installation

### Option 1: OctoPrint Plugin Manager (recommended)

1. In OctoPrint, open **Settings > Plugin Manager > Get More...**
2. Use **...from URL** and paste this in:
     https://github.com/OpenSourceModular/rosettegenerator/releases/download/v0.1.0/OctoPrint-RosetteGenerator.zip
3. Install and restart OctoPrint.

Install optional merge support:

```bash
pip install "OctoPrint-RosetteGenerator[merge]"
```

## Notes

- Default export location is stored in OctoPrint's plugin data folder (`.../data/rosettegenerator/exports`) so it stays writable for installed plugins.
- If Shapely is not installed, normal generation and export still work; only merge functionality is unavailable.
