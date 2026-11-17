"""Compile ordinary LaTeX and measure the actual glyphs in the calibration PDF."""

import os
import re
import subprocess
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"
FONT = "STIXTwoMath-Regular.otf"
BUNDLE = "https://relay.fullyjustified.net/default_bundle_v33.tar"
BP = 72 / 72.27
BASE = 24.0
SCALE = 7


def compile_tex(path, cached=False):
    WORK.mkdir(exist_ok=True)
    cmd = [
        "tectonic",
        "--bundle",
        BUNDLE,
        "--reruns",
        "0",
        "--keep-logs",
        "--outdir",
        str(WORK),
    ]
    if cached or os.environ.get("TECTONIC_ONLY_CACHED") == "1":
        cmd.append("--only-cached")
    env = dict(os.environ, SOURCE_DATE_EPOCH="1794916800", FORCE_SOURCE_DATE="1")
    result = subprocess.run(
        [*cmd, str(path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    if result.returncode:
        raise RuntimeError(result.stdout[-6000:])
    log = (WORK / path.with_suffix(".log").name).read_text()
    for diagnostic in (
        "Overfull",
        "Missing character:",
        "TeX capacity exceeded",
        "Undefined control sequence",
    ):
        if diagnostic in log:
            raise RuntimeError(next(s for s in log.splitlines() if diagnostic in s))
    return log


def atlas(strings, font=FONT):
    entries = [
        r"\documentclass{article}",
        r"\usepackage[paperwidth=180pt,paperheight=54pt,margin=0pt,noheadfoot]{geometry}",
        r"\usepackage{amsmath}",
        r"\usepackage[mathrm=sym]{unicode-math}",
        r"\setmathfont{" + font + "}",
        r"\pagestyle{empty}\begin{document}\fontsize{10pt}{10pt}\selectfont",
        r"\hoffset=-1in \voffset=-1in \newdimen\samplebaseline",
    ]
    for i, s in enumerate(strings):
        entries.extend(
            (
                r"\setbox0=\hbox{\(\textstyle " + s + r"\)}",
                rf"\typeout{{TILE {i} \the\wd0,\the\ht0,\the\dp0}}",
                rf"\samplebaseline={BASE:.1f}pt \advance\samplebaseline by -\ht0",
                r"\shipout\vbox{\kern\samplebaseline\hbox{\kern3pt\box0}}",
            )
        )
    path = WORK / ("calibration-" + font.removesuffix(".otf") + ".tex")
    path.write_text("\n".join(entries + [r"\end{document}", ""]))
    log = compile_tex(path)
    measures = re.findall(r"TILE \d+ ([\d.]+)pt,([\d.]+)pt,([\d.]+)pt", log)
    assert len(measures) == len(strings)
    results = []
    with pymupdf.open(path.with_suffix(".pdf")) as doc:
        assert len(doc) == len(strings)
        for p, m in zip(doc, measures):
            w, h, d = map(float, m)
            clip = pymupdf.Rect(0, 0, (6 + w) * BP, (BASE + d + 3) * BP)
            pix = p.get_pixmap(
                matrix=pymupdf.Matrix(SCALE, SCALE),
                clip=clip,
                colorspace=pymupdf.csGRAY,
                alpha=False,
            )
            im = np.asarray(Image.frombytes("L", (pix.width, pix.height), pix.samples))
            ink = (255 - im) / 255
            # The PDF coordinate origin and the TeX baseline are fixed across all samples.
            ys, xs = np.nonzero(ink > 0.12)
            inkarea = ink.sum() / (SCALE * BP) ** 2
            results.append(
                dict(
                    width=w,
                    height=h,
                    depth=d,
                    area=float(inkarea),
                    top=BASE - ys.min() / (SCALE * BP),
                    bottom=(ys.max() + 1) / (SCALE * BP) - BASE,
                    left=xs.min() / (SCALE * BP) - 3,
                    right=(xs.max() + 1) / (SCALE * BP) - 3,
                    profile=ink.sum(axis=0) / (SCALE * BP),
                    bitmap=im,
                )
            )
    return results


def render(pdf, width, dest, oversample=2):
    """The full PDF is the only input to the final raster."""
    with pymupdf.open(pdf) as d:
        if len(d) != 1:
            raise ValueError("Expected exactly one page")
        p = d[0]
        factor = width * oversample / p.rect.width
        pix = p.get_pixmap(
            matrix=pymupdf.Matrix(factor, factor),
            colorspace=pymupdf.csGRAY,
            alpha=False,
        )
        im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        out = im.resize(
            (width, round(width * p.rect.height / p.rect.width)),
            Image.Resampling.LANCZOS,
        )
        out.save(dest, dpi=(300, 300), optimize=False)
    return out
