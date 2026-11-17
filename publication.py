"""The separate proof sheet and measured specimen. Neither is an input to the art."""

import shutil

from PIL import Image, ImageDraw, ImageOps

from mathscore import optical
from typeset import ROOT, WORK, atlas, compile_tex


def grouped_digits(s):
    sign = "-" if s.startswith("-") else ""
    s = s.lstrip("-")
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return sign + r"\,".join(reversed(parts))


def proof(s):
    body = r"""\documentclass[10pt]{article}
\usepackage[paperwidth=170mm,paperheight=225mm,left=17mm,right=17mm,top=14mm,bottom=14mm]{geometry}
\usepackage{amsmath}
\usepackage[mathrm=sym]{unicode-math}
\setmainfont{NewCM10-Book.otf}
\setmathfont{STIXTwoMath-Regular.otf}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4.5pt}
\begin{document}
\fontsize{10.6}{14.0}\selectfont
{\fontsize{29}{32}\selectfont Downward Glance}\par
{\fontsize{15}{18}\selectfont Proof of the integer value}\par
\vspace{3pt}
The opening floor contains one integral from $-3$ to $3$ in the real variable $l$.
The large parenthesis ends just before $\mathrm{d}l$. Each continuation begins
with $+$. Reading the printed integrand by ordinary precedence gives @TERMS@
products in @ROWS@ lines.

\smallskip{\fontsize{14}{17}\selectfont Six intervals suffice}\par
Cut the integral at $-2,-1,0,1,2$. On every resulting open unit interval
$\lfloor l\rfloor$ and $\lceil l\rceil$ are constants, and $|l|$ is affine.
The other moduli have affine arguments of constant sign there.
Their zeroes and discrete jumps occur only at interval endpoints.
Endpoint values exist and have no effect on these integrals.

Factorials, binomials and finite sums or products are evaluated directly.
A repeated decimal block of $m$ digits with integer value $b$ contributes
$b/(10^m-1)$. Each printed radical has a nonnegative rational square as its
radicand. A two-by-two determinant contributes $ad-bc$ in row order.
An inner moment with upper limit $B(l)\geq0$ contributes
\[
   \int_0^{B(l)} t^p\,\mathrm{d}t=\frac{B(l)^{p+1}}{p+1},\qquad \int_0^{|l|}t^4\,\mathrm{d}t=\frac{|l|^5}{5}.
\]
The remaining inner integrals have constant bounds and polynomial integrands.
All divisors are nonzero. Consequently each product on each interval is a
polynomial over the rationals. Its degree is at most @DEG@.

\smallskip{\fontsize{14}{17}\selectfont Exact computation}\par
The score evaluator expands these polynomials and integrates each monomial.
A second evaluator parses the complete printed TeX. For degree bound $d$, it
samples the polynomial at the $d+1$ interior points
$j+k/(d+2)$, $1\leq k\leq d+1$, on $(j,j+1)$.
Integrating the Lagrange basis gives rational weights exact through degree $d$.
Both calculations agree separately on every line. For the unrounded integral
$I$ and the integer $N$, the resulting equality is
\[
 I=N+\frac{@REM@}{@DEN@},\qquad 0<\frac{@REM@}{@DEN@}<1 .
\]
\smallskip{\fontsize{14}{17}\selectfont The printed floor}\par
\[
   \lfloor I\rfloor=N=@INTEGER@ .
\]
\end{document}
"""
    # Avoid printing a long remainder fraction twice.
    body = body.replace(r"0<\frac{@REM@}{@DEN@}<1", r"0<I-N<1")
    for k, val in (
        ("TERMS", f"{s['terms']:,}"),
        ("ROWS", str(s["rows"])),
        ("DEG", str(s["max_degree"])),
        ("REM", s["remainder_num"]),
        ("DEN", s["remainder_den"]),
        ("INTEGER", grouped_digits(s["integer"])),
    ):
        body = body.replace("@" + k + "@", val)
    path = ROOT / "proof.tex"
    path.write_text(body)
    compile_tex(path)
    shutil.copyfile(WORK / "proof.pdf", ROOT / "proof.pdf")


def specimen(score):
    from mathscore import freeze
    from studies import font

    forms = [freeze(t) for t in score["factors"]]
    families = score["families"]
    choices = [
        ("Open integral", "open integral", lambda t: t[-1] == 1 and t[-2] == "em"),
        ("Variable-limit moment", "variable-limit integral", lambda t: t[2] == 2),
        ("Finite product", "telescoping prod", lambda t: True),
        (
            "Binomial quotient",
            "binomial quotient",
            lambda t: t[1][0] == "choose" and t[2][0] == "choose",
        ),
        ("Rational radical", "rational radical", lambda t: t[1][1] != t[1][2]),
        ("Two-by-two determinant", "two-by-two determinant", lambda t: True),
        ("Rational distance", "rational distance", lambda t: True),
        ("Rounded magnitude", "nested fence", lambda t: t[0] == "floor"),
        ("Step factorial", "step factorial", lambda t: True),
    ]
    selected = []
    for label, family, test in choices:
        group = [t for t, f in zip(forms, families) if f == family and test(t)]
        if not group:
            group = [t for t, f in zip(forms, families) if f == family]
        if group:
            selected.append((label, group[len(group) // 2]))
    measured = atlas([optical(t) for label, t in selected])
    out = Image.new("RGB", (1320, 796), "white")
    draw = ImageDraw.Draw(out)
    draw.text((38, 20), "The mathematical marks", font=font(43, "tiro"), fill="black")
    draw.text(
        (39, 79),
        "STIX Two Math Regular, 10 pt. All samples are enlarged by the same factor.",
        font=font(20),
        fill="#343434",
    )
    for i, ((name, t), m) in enumerate(zip(selected, measured)):
        col = i % 3
        row = i // 3
        x = 38 + col * 418
        y = 140 + row * 215
        im = Image.fromarray(m["bitmap"])
        box = ImageOps.invert(im).getbbox()
        im = im.crop(box)
        factor = 0.62
        im = im.resize(
            (max(1, round(im.width * factor)), max(1, round(im.height * factor))),
            Image.Resampling.LANCZOS,
        )
        out.paste(im, (x, y + (107 - im.height) // 2))
        draw.text((x, y + 119), name, font=font(23, "tiro"), fill="black")
        draw.text(
            (x, y + 153),
            f"Advance {m['width']:.1f} pt   ·   Ink {m['area']:.1f} pt²",
            font=font(16),
            fill="#434343",
        )
    out.save(ROOT / "specimen.png")


def public_detail(art):
    w, h = art.size
    # The crease and lower lip in the complete expression, at native raster resolution.
    art.crop(
        (round(0.426 * w), round(0.501 * h), round(0.574 * w), round(0.594 * h))
    ).save(ROOT / "detail.png")
