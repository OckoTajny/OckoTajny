#!/usr/bin/env python3
"""Prep a colour photo for ASCII conversion.

A flatly-lit photo converts to a muddy, unreadable blob. Three steps fix that:

1. Remove the background so only the subject survives – rembg's
   isnet-general-use model by default (it keeps thin things like the
   headphone band and the laptop that u2net drops), with an OpenCV GrabCut
   fallback for offline environments where no model can be downloaded.
2. Boost local contrast with CLAHE on the lightness channel only, so the face
   gets real highlights/shadows while the colours stay true.
3. Save RGBA: colour in RGB, the matte in alpha. Transparent pixels print as
   nothing; the rest pick a glyph by brightness and keep their own colour.

Run once per photo (the daily workflow never touches this):

    python scripts/prep_photo.py photo.jpg --crop 560 330 900 670 \\
        --erase 0 600 320 70

Writes source-prepped.png (RGBA) next to the scripts.
"""

import argparse
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "source-prepped.png"


def alpha_rembg(img: Image.Image, model: str) -> np.ndarray:
    from rembg import new_session, remove

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cut = Image.open(io.BytesIO(remove(buf.getvalue(), session=new_session(model))))
    return np.array(cut.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0


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
    ap.add_argument(
        "--erase",
        nargs=4,
        type=int,
        action="append",
        default=[],
        metavar=("X", "Y", "W", "H"),
        help="clear the matte in this rect (crop coords); repeatable – for "
        "props the model kept but you don't want",
    )
    ap.add_argument("--engine", choices=["rembg", "grabcut"], default="rembg")
    ap.add_argument("--model", default="isnet-general-use", help="rembg model")
    args = ap.parse_args()

    img = Image.open(args.photo).convert("RGB")
    if args.crop:
        x, y, w, h = args.crop
        img = img.crop((x, y, x + w, y + h))

    # 1. Background removal.
    if args.engine == "rembg":
        try:
            alpha = alpha_rembg(img, args.model)
        except Exception as e:  # model download blocked / rembg not installed
            print(f"rembg unavailable ({e.__class__.__name__}), falling back to grabcut")
            alpha = alpha_grabcut(img)
    else:
        alpha = alpha_grabcut(img)
    for x, y, w, h in args.erase:
        alpha[y:y + h, x:x + w] = 0

    # 2. CLAHE on L of Lab – local contrast without shifting hues.
    lab = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # 3. Colour + matte.
    out = np.dstack([rgb, (alpha * 255).round().astype(np.uint8)])
    Image.fromarray(out, mode="RGBA").save(OUT)
    print(f"wrote {OUT} ({out.shape[1]}x{out.shape[0]})")


if __name__ == "__main__":
    main()
