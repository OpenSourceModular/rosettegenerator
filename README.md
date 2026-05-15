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
2. Use **...from URL** and paste one of the following:
   - Latest release zip URL (recommended):
     - `https://github.com/OpenSourceModular/OctoPrint-RosetteGenerator/releases/latest/download/OctoPrint-RosetteGenerator.zip`
   - Or main branch zip URL:
     - `https://github.com/OpenSourceModular/OctoPrint-RosetteGenerator/archive/refs/heads/main.zip`
3. Install and restart OctoPrint.

For best results, publish a GitHub Release first and use the release zip URL so users always install a known version.

### Option 2: pip install from GitHub

Run this in the same Python environment as OctoPrint:

```bash
pip install git+https://github.com/your-user/OctoPrint-RosetteGenerator.git
```

Install optional merge support:

```bash
pip install "OctoPrint-RosetteGenerator[merge]"
```

## Development install

From this repository root:

```bash
pip install -e .
```

Optional merge dependencies:

```bash
pip install -e ".[merge]"
```

## Repository setup before publishing

Update these placeholders before publishing your repo:

- `setup.py` URL: `https://github.com/your-user/OctoPrint-RosetteGenerator`
- Install URLs in this README (`your-user`)
- `LICENSE` copyright owner name

## Publish a release zip automatically

This repository includes GitHub Actions workflows:

- `.github/workflows/ci.yml`: builds the package on pushes and pull requests
- `.github/workflows/release.yml`: creates `OctoPrint-RosetteGenerator.zip` and attaches it to GitHub Releases

To publish a release users can install from:

1. Push your repository to GitHub.
2. Create a tag and release (example `v0.1.0`).
3. GitHub Actions attaches `OctoPrint-RosetteGenerator.zip` to the release.
4. Share this URL in OctoPrint Plugin Manager:
  - `https://github.com/your-user/OctoPrint-RosetteGenerator/releases/latest/download/OctoPrint-RosetteGenerator.zip`

## Notes

- Default export location is stored in OctoPrint's plugin data folder (`.../data/rosettegenerator/exports`) so it stays writable for installed plugins.
- If Shapely is not installed, normal generation and export still work; only merge functionality is unavailable.
