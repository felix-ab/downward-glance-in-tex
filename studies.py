"""Private photographic studies and the comparison plate."""

from io import BytesIO

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

from typeset import ROOT, WORK

RESAMPLE = Image.Resampling.LANCZOS


def font(size, face="helv"):
    data = pymupdf.Font(fontname=face).buffer
    return ImageFont.truetype(BytesIO(data), size)


def prepare(photo):
    original = Image.open(photo).convert("RGB")
    rgb = np.asarray(original).copy()
    if rgb.shape[:2] != (667, 736):
        raise ValueError("Recomposition expects the original 736 by 667 reference.")
    # Only the white EDIT lettering on the top edge is repaired in the working copy.
    yy, xx = np.indices(rgb.shape[:2])
    lo = rgb.min(axis=2)
    mask = (
        (xx >= 569)
        & (xx < 629)
        & (yy < 19)
        & (lo > 162)
        & ((rgb.max(axis=2).astype(int) - lo) < 47)
    ).astype("uint8") * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    clean = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    gray = cv2.cvtColor(clean, cv2.COLOR_RGB2GRAY)
    local = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(gray)
    working = np.clip(np.rint(0.73 * gray + 0.27 * local), 0, 255).astype("uint8")
    return original, gray, working, int((mask > 0).sum())


def atkinson(g):
    a = np.pad(g.astype(float), ((0, 2), (1, 2)), mode="edge")
    h, w = g.shape
    for y in range(h):
        for x in range(1, w + 1):
            old = a[y, x]
            new = 255 if old >= 128 else 0
            a[y, x] = new
            err = (old - new) / 8
            a[y, x + 1 : x + 3] += err
            a[y + 1, x - 1 : x + 2] += err
            a[y + 2, x] += err
    return a[:h, 1 : w + 1].astype("uint8")


def contact(photo):
    original, g, work, count = prepare(photo)
    # The dither studies are performed at the sheet's actual viewing scale.
    w = 272
    size = (w, round(w * original.height / original.width))
    gr = Image.fromarray(g).resize(size, RESAMPLE)
    a = np.asarray(gr)
    threshold, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    b = np.array([[0, 2], [3, 1]])
    for _ in range(2):
        b = np.block([[4 * b, 4 * b + 2], [4 * b + 3, 4 * b + 1]])
    ordered = (
        a / 255
        > (np.tile(b, (size[1] // 8 + 1, size[0] // 8 + 1))[: size[1], : size[0]] + 0.5)
        / 64
    ) * 255
    levels = lambda n: Image.fromarray(
        np.rint(255 * np.rint(g / 255 * (n - 1)) / (n - 1)).astype("uint8")
    )
    tiles = [
        ("Original", original),
        ("Two tones · Otsu", Image.fromarray((255 * (g > threshold)).astype("uint8"))),
        ("Four tones · 2-bit", levels(4)),
        ("Sixteen tones · 4-bit", levels(16)),
        ("Continuous · 8-bit", Image.fromarray(g)),
        ("Mild local contrast", Image.fromarray(work)),
        ("Floyd–Steinberg", gr.convert("1")),
        ("Bayer · 8 × 8", Image.fromarray(ordered.astype("uint8"))),
        ("Atkinson", Image.fromarray(atkinson(a))),
    ]
    pad, gap = 28, 16
    out = Image.new(
        "RGB",
        (pad * 2 + 3 * w + 2 * gap, 82 + 3 * (size[1] + 35) + 2 * gap + 18),
        "white",
    )
    draw = ImageDraw.Draw(out)
    draw.text((pad, 15), "Downward Glance", font=font(33, "tiro"), fill="black")
    draw.text((pad, 55), "Photographic tonal studies", font=font(14), fill="#454545")
    for i, (label, im) in enumerate(tiles):
        x = pad + (i % 3) * (w + gap)
        y = 82 + (i // 3) * (size[1] + 35 + gap)
        out.paste(im.convert("RGB").resize(size, RESAMPLE), (x, y))
        draw.text((x, y + size[1] + 7), label, font=font(15), fill="#191919")
    out.save(ROOT / "contact_sheet.png")
    Image.fromarray(work).save(WORK / "working.png")
    return count


def comparison(photo, art, crop_fraction=(0.448, 0.524, 0.510, 0.586)):
    original = Image.open(photo).convert("RGB")
    with Image.open(art) as f:
        f.load()
        w, h = f.size
        x0, y0, x1, y1 = crop_fraction
        crop = f.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))
        panel_w = 612
        panel_h = round(panel_w * original.height / original.width)
        orig = original.resize((panel_w, panel_h), RESAMPLE)
        full = f.convert("RGB").resize((panel_w, panel_h), RESAMPLE)
        # Preserve the aspect of the glyphs in the detail.
        detail = Image.new("L", (panel_w, panel_h), "white")
        region = crop.resize(
            (panel_w, round(panel_w * crop.height / crop.width)), RESAMPLE
        )
        detail.paste(region, (0, (panel_h - region.height) // 2))
    pad, gap = 34, 20
    out = Image.new(
        "RGB", (2 * pad + 3 * panel_w + 2 * gap, 132 + panel_h + 83), "white"
    )
    draw = ImageDraw.Draw(out)
    draw.text((pad, 20), "Downward Glance", font=font(52, "tiro"), fill="black")
    draw.text(
        (pad, 91),
        "A single definite integral, rounded down to an integer.",
        font=font(21),
        fill="#363636",
    )
    for i, (image, label) in enumerate(
        (
            (orig, "Photographic reference"),
            (full, "Complete expression"),
            (detail, "Detail · the smile"),
        )
    ):
        x = pad + i * (panel_w + gap)
        out.paste(image, (x, 132))
        draw.text((x, 132 + panel_h + 15), label, font=font(20), fill="black")
    out.save(ROOT / "comparison.png")


def tonal_report(photo, art, score):
    """Registered, unnormalized comparisons on the original photograph's pixel scale."""
    import json

    original, _, work, mask_pixels = prepare(photo)
    raw = cv2.cvtColor(np.asarray(original), cv2.COLOR_RGB2GRAY).astype(np.float32)
    from mathscore import outer_integral

    _, _, _, rows = outer_integral(score["expression"])
    first, last = rows[0], rows[-1]
    pw = 16 + score["width"]
    ph = 16 + first["height"] + last["y"] - first["y"] + last["depth"]
    sy = 8 + first["height"] - first["y"]
    x0 = 8 / pw * art.width
    y0 = sy / ph * art.height
    x1 = (8 + score["width"]) / pw * art.width
    y1 = (sy + score["height"]) / ph * art.height
    page = np.asarray(
        art.resize(original.size, Image.Resampling.BOX, box=(x0, y0, x1, y1))
    ).astype(np.float32)
    result = {
        "original_pixels": list(original.size),
        "overlay_mask_pixels": mask_pixels,
        "scales": {},
    }
    for sigma in (2, 5, 10):
        a, b, c = (
            gaussian_filter(t, sigma) for t in (raw, work.astype(np.float32), page)
        )

        def metrics(a, b):
            return {
                "pearson": round(float(np.corrcoef(a.ravel(), b.ravel())[0, 1]), 5),
                "raw_mean_absolute_error": round(float(np.abs(a - b).mean()), 3),
            }

        result["scales"][sigma] = {
            "original": metrics(a, c),
            "working": metrics(b, c),
            "original_face": metrics(a[70:451, 220:497], c[70:451, 220:497]),
        }
    result["mean_gray_original_artwork"] = {}
    for name, (x0, y0, x1, y1) in {
        "sky": (16, 36, 144, 105),
        "earcup": (180, 275, 217, 300),
        "forehead": (272, 131, 410, 179),
        "eyelid": (264, 239, 306, 250),
        "hoodie": (43, 475, 160, 555),
    }.items():
        result["mean_gray_original_artwork"][name] = [
            round(float(t[y0:y1, x0:x1].mean()), 1) for t in (raw, page)
        ]
    (WORK / "tonal-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
