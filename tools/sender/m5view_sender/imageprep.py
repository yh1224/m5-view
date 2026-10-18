"""Convert images to PNG of the screen size for sending."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageColor, ImageOps

# Default screen size (CoreS3)
WIDTH = 320
HEIGHT = 240
FIT_MODES = ("contain", "cover", "stretch")


def fit_image(
    image: Image.Image, fit: str = "contain", bg: str = "#000000", size: tuple[int, int] = (WIDTH, HEIGHT)
) -> Image.Image:
    """Fit the image to size (width, height)."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    if fit == "contain":
        return ImageOps.pad(image, size, method=Image.Resampling.LANCZOS, color=ImageColor.getrgb(bg))
    if fit == "cover":
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    if fit == "stretch":
        return image.resize(size, Image.Resampling.LANCZOS)
    raise ValueError(f"unknown fit mode: {fit}")


def encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def prepare(
    path: Path, fit: str = "contain", bg: str = "#000000", size: tuple[int, int] = (WIDTH, HEIGHT)
) -> bytes:
    """Load an image file and return PNG bytes ready to send."""
    with Image.open(path) as image:
        return encode_png(fit_image(image, fit, bg, size))
