"""从 PNG 源图生成 Windows ico 与 macOS icns。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icon"
SOURCE = ICON_DIR / "alpha-yoki.png"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _load_square(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != (1024, 1024):
        image = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    return image


def build(source: Path = SOURCE) -> dict[str, Path]:
    if not source.exists():
        raise SystemExit(f"缺少源图：{source}")
    image = _load_square(source)
    png_path = ICON_DIR / "alpha-yoki.png"
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    image.save(png_path, format="PNG")
    ico_path = ICON_DIR / "alpha-yoki.ico"
    image.save(ico_path, format="ICO", sizes=[(size, size) for size in ICO_SIZES])
    icns_path = ICON_DIR / "alpha-yoki.icns"
    try:
        image.save(icns_path, format="ICNS")
    except (ValueError, OSError, KeyError):
        icns_path = _write_icns_via_iconutil(image, icns_path)
    return {"png": png_path, "ico": ico_path, "icns": icns_path}


def _write_icns_via_iconutil(image: Image.Image, dest: Path) -> Path:
    import shutil
    import subprocess
    import tempfile

    iconutil = shutil.which("iconutil")
    if not iconutil:
        print("Pillow 无法写 icns 且找不到 iconutil，已跳过", file=sys.stderr)
        return dest
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "alpha-yoki.iconset"
        iconset.mkdir()
        for size in (16, 32, 64, 128, 256, 512, 1024):
            resized = image.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(iconset / f"icon_{size}x{size}.png")
            if size <= 512:
                doubled = image.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
                doubled.save(iconset / f"icon_{size}x{size}@2x.png")
        subprocess.run([iconutil, "-c", "icns", str(iconset), "-o", str(dest)], check=True)
    return dest


def main() -> None:
    written = build()
    for kind, path in written.items():
        print(f"{kind}: {path}")


if __name__ == "__main__":
    main()
