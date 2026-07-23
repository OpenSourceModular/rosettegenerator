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
     https://github.com/OpenSourceModular/rosettegenerator/releases/download/v0.1.11/OctoPrint-RosetteGenerator.zip
3. Install and restart OctoPrint.

## Release Checklist

- Keep `version` synchronized in `pyproject.toml`, `setup.py`, and `__plugin_version__` in `__init__.py`.
- Run `python scripts/check_versions.py` before creating a tag.
- Create a Git tag that exactly matches the version, prefixed with `v` (example: `v0.1.9`).
- Ensure the GitHub release title and tag refer to the same version number.
- Upload `OctoPrint-RosetteGenerator.zip` from the matching tagged commit.
- Verify updater metadata by checking this endpoint after publish:
  `https://api.github.com/repos/OpenSourceModular/rosettegenerator/releases/latest`

## Notes

- Default export location is stored in OctoPrint's plugin data folder (`.../data/rosettegenerator/exports`) so it stays writable for installed plugins.
- If the shapely python library is not automatically installed during installation, normal generation and export still work; only merge functionality is unavailable.
