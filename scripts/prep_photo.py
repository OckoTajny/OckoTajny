#!/usr/bin/env python3
"""Prep a photo for ASCII conversion.

A flatly-lit photo converts to a dark, unreadable blob. Three steps fix that:

1. Remove the background so only the subject survives – rembg (u2net) by
   default, with an OpenCV GrabCut fallback for offline environments where
   the u2net model can't be downloaded.
2. Boost local contrast with CLAHE so the face gets real highlights/shadows.
3. Composite onto pure white – white maps to the blank end of the ASCII ramp,
   so the background prints as nothing.

Run once per photo (the daily workflow never touches this):

    python scripts/prep_photo.py source-photo.jpg [--crop X Y W H] [--engine rembg|grabcut]

Writes source-prepped.png (grayscale) next to the scripts.
"""

import argparse
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "source-prepped.png"


def alpha_rembg(img: Image.Image) -> np.ndarray:
    from rembg import remove

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cut = Image.open(io.BytesIO(remove(buf.getvalue()))).convert("RGBA")
    return np.array(cut)[:, :, 3].astype(np.float32) / 255.0


def alpha_grabcut(img: Image.Image, iters: int = 8) -> np.ndarray:
    """Model-free fallback: GrabCut seeded with a centered subject rect."""
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * 0.06), int(h * 0.02), int(w * 0.88), int(h * 0.96))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0)
    # Soften the matte edge a touch so the ASCII edge isn't jagged.
    return cv2.GaussianBlur(alpha.astype(np.float32), (5, 5), 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", help="input photo (jpg/png)")
    ap.add_argument(
        "--crop",
        nargs=4,
        type=int,
        metavar=("X", "Y", "W", "H"),
        help="crop the subject region before processing",
    )
    ap.add_argument("--engine", choices=["rembg", "grabcut"], default="rembg")
    args = ap.parse_args()

    img = Image.open(args.photo).convert("RGB")
    if args.crop:
        x, y, w, h = args.crop
        img = img.crop((x, y, x + w, y + h))

    # 1. Background removal.
    if args.engine == "rembg":
        try:
            alpha = alpha_rembg(img)
        except Exception as e:  # model download blocked / rembg not installed
            print(f"rembg unavailable ({e.__class__.__name__}), falling back to grabcut")
            alpha = alpha_grabcut(img)
    else:
        alpha = alpha_grabcut(img)

    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

    # 2. CLAHE – local contrast so a flat face gets usable tonal range.
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 3. Composite onto pure white using the matte.
    out = (gray.astype(np.float32) * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)

    Image.fromarray(out, mode="L").save(OUT)
    print(f"wrote {OUT} ({out.shape[1]}x{out.shape[0]})")


if __name__ == "__main__":
    main()
