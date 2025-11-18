from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image


QUALITY_SIZES = {
    "LOW": (160, 120),
    "MID": (320, 240),
}


def _resize_preserving_aspect(image: Image.Image, target: Tuple[int, int]) -> Image.Image:
    width, height = target
    o_width, o_height = image.size
    ratio = o_width / float(o_height or 1)
    if o_width > o_height:
        new_height = max(1, int(width / ratio))
        new_width = width
    else:
        new_width = max(1, int(height * ratio))
        new_height = height
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def prepare_picture(source: Path, quality: str) -> Image.Image:
    """Resize ``source`` to the configured quality and return a PIL image."""

    quality = quality.upper()
    target = QUALITY_SIZES.get(quality, QUALITY_SIZES["LOW"])
    with Image.open(source) as original:
        if original.size == target:
            return original.copy()
        return _resize_preserving_aspect(original, target)
