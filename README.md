# OctoPrint Rosette Generator

Generate Rose Enging Rosette patterns directly in OctoPrint, preview them in the UI, and export SVG files.

## Features

- 12 rosette styles (Bump, Dip, Arch, Concave+Convex, Puffy, W, X + 1, Flat, Lotus, A, Sine, Bead)
- Holtzapffel A-S rosettes (Thanks to Bill Oooms) 
- Live preview with optional auto-preview
- Save defaults in plugin settings
- Hold + merge workflow
- SVG export

## Installation

### OctoPrint Plugin Manager

1. In OctoPrint, open **Settings > Plugin Manager > Get More...**
2. Use **...from URL** and paste this in:
     https://github.com/OpenSourceModular/rosettegenerator/releases/download/v0.1.6/OctoPrint-RosetteGenerator.zip
3. Install and restart OctoPrint.

## Notes

- Default export location is stored in OctoPrint's plugin data folder (`.../data/rosettegenerator/exports`) so it stays writable for installed plugins.
- If the shapely python library is not automatically installed during installation, normal generation and export still work; only merge functionality is unavailable.
