"""Runtime compatibility shims for third-party libraries."""

from __future__ import annotations

from PIL import Image


def patch_pil_antialias() -> None:
    """Restore ``PIL.Image.ANTIALIAS`` (removed in Pillow 10) for MoviePy 1.0.3."""
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.LANCZOS  # type: ignore[attr-defined]
