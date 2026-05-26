from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent
README = ROOT / "README.md"


setup(
    name="OctoPrint-RosetteGenerator",
    version="0.1.4",
    description="Generate decorative rosette curves and export SVG files from OctoPrint.",
    long_description=README.read_text(encoding="utf-8") if README.exists() else "",
    long_description_content_type="text/markdown",
    author="RosetteGenerator Contributors",
    license="MIT",
    url="https://github.com/OpenSourceModular/OctoPrint-RosetteGenerator",
    packages=["rosettegenerator"],
    package_dir={"rosettegenerator": "."},
    include_package_data=True,
    package_data={
        "rosettegenerator": [
            "templates/*.jinja2",
            "static/css/*.css",
            "static/js/*.js",
        ]
    },
    install_requires=[],
    extras_require={
        "merge": ["shapely>=2.0"],
    },
    #python_requires=">=3.8,<4",
    entry_points={
        "octoprint.plugin": [
            "rosettegenerator = rosettegenerator",
        ]
    },
    classifiers=[
        "Framework :: OctoPrint",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
