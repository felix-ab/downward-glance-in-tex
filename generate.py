#!/usr/bin/env python3
"""Build from the published score, or recompose from the original photograph."""

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from mathscore import freeze, optical, outer_integral, outer_notation
from typeset import FONT, ROOT, WORK, compile_tex, render

SCORE = ROOT / "score.json.gz"


def source(score):
    terms = [optical(freeze(t)) for t in score["factors"]]
    _, _, _, rows = outer_integral(score["expression"])
    opening, closing = outer_notation(score["expression"])
    first, last = rows[0], rows[-1]
    ph = 16 + first["height"] + last["y"] - first["y"] + last["depth"]
    lines = [
        r"\documentclass{article}",
        r"\usepackage[paperwidth="
        + f"{score['width'] + 16:.3f}pt,paperheight={ph:.3f}pt,margin=0pt,noheadfoot"
        + r"]{geometry}",
        r"\usepackage{amsmath,atbegshi}",
        r"\usepackage[mathrm=sym]{unicode-math}",
        r"\setmathfont{" + FONT + "}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\hoffset=-1in \voffset=-1in",
        r"\AtBeginShipoutOriginalShipout\vbox{",
        r"\special{papersize=\the\paperwidth,\the\paperheight}",
        r"\kern8pt\hbox{\kern8pt",
        r"\(",
        r"\begin{array}{@{}l@{}}",
    ]
    for j, row in enumerate(rows):
        if j:
            prev = rows[j - 1]
            skip = row["y"] - prev["y"] - prev["depth"] - row["height"]
            lines.extend((r"\\", r"\noalign{\kern" + f"{skip:.5f}pt" + "}"))
        lines.append(
            r"\textstyle \kern"
            + f"{row['indent']:.3f}pt "
            + ("{+}" if j else "{" + opening + "}")
        )
        for op, i, gap in row["items"]:
            s = "{" + terms[i] + "}"
            if op in (".", "+"):
                sign = r"\cdot" if op == "." else "+"
                lines.append(
                    r"\kern"
                    + f"{gap - 1.3:.4f}pt "
                    + "{"
                    + sign
                    + "}"
                    + r"\kern1.3000pt "
                    + s
                )
            else:
                lines.append(r"\kern" + f"{gap:.3f}pt " + s)
    lines[-1] += r"\," + "{" + closing + "}"
    return "\n".join(lines + [r"\end{array}", r"\)", r"}}", r"\end{document}", ""])


def save_score(s):
    data = json.dumps(s, separators=(",", ":"), ensure_ascii=True).encode()
    SCORE.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


def build_art(score, width):
    path = ROOT / "expression.tex"
    path.write_text(source(score))
    compile_tex(path)
    shutil.copyfile(WORK / "expression.pdf", ROOT / "portrait.pdf")
    return render(ROOT / "portrait.pdf", width, ROOT / "portrait.png", oversample=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, metavar="ORIGINAL_PNG")
    parser.add_argument("--private-plates", type=Path, metavar="ORIGINAL_PNG")
    args = parser.parse_args()
    WORK.mkdir(exist_ok=True)
    if args.compose:
        from compose import compose

        print("Measuring and fitting the notation…", flush=True)
        s = compose(args.compose)
        save_score(s)
    else:
        s = json.loads(gzip.decompress(SCORE.read_bytes()))
    _, _, _, rows = outer_integral(s["expression"])
    print(f"Typesetting {len(rows)} lines…", flush=True)
    art = build_art(s, 7680)
    p = args.compose or args.private_plates
    if p:
        from studies import comparison, contact, tonal_report

        contact(p)
        comparison(p, ROOT / "portrait.png")
        tonal_report(p, art, s)
    from publication import public_detail, specimen

    specimen(s)
    public_detail(art)
    subprocess.run(
        [sys.executable, str(ROOT / "check.py"), "--write"], cwd=ROOT, check=True
    )
    print(art.size, flush=True)


if __name__ == "__main__":
    main()
