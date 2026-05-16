# OctoPrint Rosette Generator

Generate decorative rosette curve patterns directly in OctoPrint, preview them in the UI, and export SVG files.

## Features

- 12 rosette styles (Bump, Dip, Arch, Concave+Convex, Puffy, W, X + 1, Flat, Lotus, A, Sine, Bead)
- Live preview with optional auto-preview
- Save defaults in plugin settings
- Hold + merge workflow
- SVG export
- Shapely-powered geometry merge support

## Installation

### Option 1: OctoPrint Plugin Manager (recommended)

1. In OctoPrint, open **Settings > Plugin Manager > Get More...**
2. Use **...from URL** and paste this in:
     https://github.com/OpenSourceModular/rosettegenerator/releases/download/v0.1.0/OctoPrint-RosetteGenerator.zip
3. Install and restart OctoPrint. `shapely` is installed automatically with the plugin.

## Notes

- Default export location is OctoPrint's uploads folder under `rosette` (`.../uploads/rosette`).
- Merge features depend on `shapely`, which is now included as a required plugin dependency.
