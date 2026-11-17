#!/usr/bin/env python3
"""Independently parse the emitted TeX, certify polynomial segments and integrate exactly."""

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from fractions import Fraction as Q
from functools import cache
from math import comb, factorial, isqrt, prod
from pathlib import Path

BASE = Path(__file__).resolve().parent
TOKEN = re.compile(r"\\\\|\\[A-Za-z]+|\d+|[{}()!+^_=.,&\-]|[a-z]")
DISCARD = re.compile(
    r"\\m?kern\s*[-+]?\d+(?:\.\d+)?(?:mu|pt)\s*|\\(?:textstyle|displaystyle|qquad|quad|left(?![a-zA-Z])|right(?![a-zA-Z]))\s*|\\[!,]"
)


def require(test, message):
    if not test:
        raise ValueError(message)


class Reader:
    def __init__(self, s):
        clean = DISCARD.sub(" ", s)
        self.t = TOKEN.findall(clean)
        require(
            "".join(self.t) == re.sub(r"\s+", "", clean),
            "Unrecognized input in " + clean,
        )
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self, expected=None):
        token = self.peek()
        require(
            token is not None and (expected is None or token == expected),
            f"Expected {expected}, found {token} in {self.t}",
        )
        self.i += 1
        return token

    def integer(self):
        neg = -1 if self.peek() == "-" and self.take() == "-" else 1
        t = self.take()
        require(t.isdigit(), "Integer expected")
        return neg * int(t)

    def group(self):
        self.take("{")
        a = self.expression()
        self.take("}")
        return a

    def atom(self):
        t = self.take()
        if t.isdigit():
            if self.peek() == ".":
                require(t == "0", "Only pure repeating decimals expected")
                self.take(".")
                self.take(r"\overline")
                self.take("{")
                digits = self.take()
                self.take("}")
                require(digits.isdigit(), "Expected decimal digits")
                return ("repeat", digits)
            return ("num", int(t))
        if len(t) == 1 and t.isalpha():
            return ("var", t)
        delimiters = {
            "(": (")", None),
            r"\lvert": (r"\rvert", "abs"),
            r"\lfloor": (r"\rfloor", "floor"),
            r"\lceil": (r"\rceil", "ceil"),
            "{": ("}", None),
        }
        if t == r"\lvert" and self.peek() == r"\begin":
            self.take(r"\begin")
            self.take("{")
            for k in "smallmatrix":
                self.take(k)
            self.take("}")
            a = self.expression()
            self.take("&")
            b = self.expression()
            self.take(r"\\")
            c = self.expression()
            self.take("&")
            d = self.expression()
            self.take(r"\end")
            self.take("{")
            for k in "smallmatrix":
                self.take(k)
            self.take("}")
            self.take(r"\rvert")
            return ("det", a, b, c, d)
        if t in delimiters:
            end, op = delimiters[t]
            a = self.expression()
            self.take(end)
            return (op, a) if op else a
        if t in (r"\frac", r"\binom"):
            return ("div" if t == r"\frac" else "bin", self.group(), self.group())
        if t == r"\sqrt":
            return ("sqrt", self.group())
        if t in (r"\sum", r"\prod"):
            self.take("_")
            self.take("{")
            v = self.take()
            self.take("=")
            lo = self.integer()
            self.take("}")
            self.take("^")
            self.take("{")
            hi = self.integer()
            self.take("}")
            return (t[1:], v, lo, hi, self.power())
        if t == r"\int":
            self.take("_")
            self.take("{")
            lo = self.integer()
            self.take("}")
            self.take("^")
            upper = self.group()
            hi = upper[1] if upper[0] == "num" else upper
            body = self.expression()
            self.take(r"\mathrm")
            self.take("{")
            self.take("d")
            self.take("}")
            var = self.take()
            return ("int", var, lo, hi, body)
        raise ValueError("Unexpected atom " + t)

    def power(self):
        a = self.atom()
        while self.peek() in ("^", "!"):
            op = self.take()
            a = ("fact", a) if op == "!" else ("pow", a, self.group())
        return a

    def term(self):
        a = self.power()
        while self.peek() not in (
            None,
            r"\rvert",
            r"\rceil",
            r"\rfloor",
            "}",
            ")",
            "+",
            "-",
            r"\mathrm",
            "&",
            r"\\",
            r"\end",
        ):
            if self.peek() == r"\cdot":
                self.take()
            a = ("mul", a, self.power())
        return a

    def expression(self):
        a = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            a = ("add" if op == "+" else "sub", a, self.term())
        return a

    def finish(self):
        tree = self.expression()
        require(self.peek() is None, "Unconsumed source tokens")
        return tree


def unwrap(s):
    """TeX atom spacing braces are checked separately from visible mathematical fences."""
    require(s.startswith("{") and s.endswith("}"), "Expected a complete typeset atom")
    d = 0
    for i, ch in enumerate(s):
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
        require(d >= 0 and (d or i == len(s) - 1), "Extra material outside atom")
    require(d == 0, "Unclosed TeX group")
    return s[1:-1]


def read_source(path):
    text = path.read_text()
    num = r"[-+]?\d+(?:\.\d+)?"
    container = re.compile(
        r"\\documentclass\{article\}\n\\usepackage\[paperwidth="
        + num
        + r"pt,paperheight="
        + num
        + r"pt,margin=0pt,noheadfoot\]\{geometry\}\n\\usepackage\{amsmath,atbegshi\}\n"
        r"\\usepackage\[mathrm=sym\]\{unicode-math\}\n\\setmathfont\{STIXTwoMath-Regular\.otf\}\n"
        r"\\pagestyle\{empty\}\n\\begin\{document\}\n\\hoffset=-1in \\voffset=-1in\n"
        r"\\AtBeginShipoutOriginalShipout\\vbox\{\n\\special\{papersize=\\the\\paperwidth,\\the\\paperheight\}\n"
        r"\\kern8pt\\hbox\{\\kern8pt\n\\\(\n\\begin\{array\}\{@\{\}l@\{\}\}\n(.*?)\n"
        r"\\end\{array\}\n\\\)\n\}\}\n\\end\{document\}\n",
        re.S,
    )
    m = container.fullmatch(text)
    require(m, "Unexpected TeX wrapper, font, or unparsed page material")
    chunks = re.split(r"\n\\\\\n\\noalign\{\\kern" + num + r"pt\}\n", m[1])
    groups = []
    explicit = []
    allf = []
    atomline = re.compile(
        r"\\kern(" + num + r")pt (?:(\{\+\}|\{\\cdot\})\\kern(" + num + r")pt )?(.+)"
    )
    for j, ch in enumerate(chunks):
        lines = ch.splitlines()
        header = re.fullmatch(r"\\textstyle \\kern(" + num + r")pt (.+)", lines.pop(0))
        require(header, "Invalid line start")
        if j == 0:
            start = re.fullmatch(
                r"\{\\Bigl\\lfloor\\int_\{(-?\d+)\}\^\{(-?\d+)\}\\!\\Bigl\(\}",
                header[2],
            )
            require(
                start,
                "Missing opening floor, integral bounds, or integrand parenthesis",
            )
            lo, hi = map(int, start.groups())
        else:
            require(header[2] == "{+}", "Missing explicit row addition")
        if j == len(chunks) - 1:
            close = re.search(
                r"\\,\{\\Bigr\)\\,\\mathrm\{d\}([a-z])\\Bigr\\rfloor\}$", lines[-1]
            )
            require(close, "Missing differential or global closing delimiters")
            variable = close[1]
            lines[-1] = lines[-1][: close.start()]
        items = []
        signs = []
        raw = []
        blocks = []
        current = []
        for line in lines:
            m = atomline.fullmatch(line)
            require(m, "Unexpected source line: " + line[:100])
            sign = {None: "", "{+}": "+", r"{\cdot}": "."}[m[2]]
            atom = unwrap(m[4])
            t = Reader(atom).finish()
            if sign == "+":
                require(current, "Empty product")
                blocks.append(tuple(current))
                current = []
            current.append(t)
            items.append(t)
            signs.append(sign)
            raw.append(
                (("+" if sign == "+" else r"\cdot " if sign == "." else " ") + atom)
            )
        require(signs and signs[0] == "", "Leading operator inside a line")
        blocks.append(tuple(current))
        groups.append(blocks)
        explicit.append(signs)
        allf.append(items)
        # Parse each complete typeset product again with the invisible atom braces removed.
        # This catches ambiguous numeral concatenation or an unscoped sum/integral swallowing a neighbor.
        flat_raw = "".join(raw)
        entire = Reader(flat_raw).finish()
        expected = None
        for block in blocks:
            t = block[0]
            for b in block[1:]:
                t = ("mul", t, b)
            expected = ("add", expected, t) if expected is not None else t
        require(
            entire == expected, f"Visible product/grouping ambiguity on line {j + 1}"
        )
    return (variable, lo, hi), groups, explicit, allf


def normalized(s):
    op, *a = s
    if op == "par":
        return normalized(a[0])
    if op == "moment":
        v, p, upper = a
        body = ("var", v) if p == 1 else ("pow", ("var", v), ("num", p))
        return ("int", v, 0, normalized(upper), body)
    if op == "air":
        v, h, p, _, _ = a
        body = ("var", v) if p == 1 else ("pow", ("var", v), ("num", p))
        return ("int", v, 0, h, body)
    if op in ("int", "sum", "prod"):
        return (op, *a[:3], normalized(a[3]))
    if op in ("n", "v"):
        return ("num" if op == "n" else "var", a[0])
    if op == "rep":
        return ("repeat", str(a[0]))
    if op == "pow":
        return ("pow", normalized(a[0]), ("num", a[1]))
    op = {"choose": "bin", "frac": "div", "root": "sqrt"}.get(op, op)
    return (op, *(normalized(i) for i in a))


@cache
def open_rule(degree):
    """Integrate all polynomials of degree <= degree on [0,1], using only interior rational nodes."""
    n = degree + 1
    nodes = tuple(Q(i + 1, n + 1) for i in range(n))
    weights = []
    for i, x in enumerate(nodes):
        coeff = [Q(1)]
        denominator = Q(1)
        for j, y in enumerate(nodes):
            if i == j:
                continue
            p = [Q(0)] * (len(coeff) + 1)
            for k, v in enumerate(coeff):
                p[k] -= y * v
                p[k + 1] += v
            coeff = p
            denominator *= x - y
        weights.append(sum(v / Q(k + 1) for k, v in enumerate(coeff)) / denominator)
    require(
        all(
            sum(w * x**j for x, w in zip(nodes, weights)) == Q(1, j + 1)
            for j in range(n)
        ),
        "Quadrature failed moment check",
    )
    return tuple(zip(nodes, weights))


@cache
def free(t):
    op, *a = t
    if op == "var":
        return frozenset([a[0]])
    if op in ("num", "repeat"):
        return frozenset()
    if op in ("sum", "prod", "int"):
        bound = free(a[2]) if isinstance(a[2], tuple) else frozenset()
        return (free(a[3]) - {a[0]}) | bound
    return frozenset().union(*(free(z) for z in a))


@cache
def value(t, name="", x=Q(0)):
    op, *a = t
    if op == "num":
        return Q(a[0])
    if op == "repeat":
        return Q(int(a[0]), 10 ** len(a[0]) - 1)
    if op == "var":
        require(a[0] == name, "Free variable " + a[0])
        return x
    if op in ("sum", "prod", "int"):
        var, lo, hi, body = a
        require(free(body) <= {var}, "Unbound variable in operator body")
        if op == "int" and isinstance(hi, tuple):
            limit = value(hi, name, x)
            require(
                lo == 0 and limit >= 0,
                "Moving integration limit outside its certified range",
            )
            d = monomial_degree(body, var)
            return limit * sum(w * value(body, var, limit * u) for u, w in open_rule(d))
        require(hi >= lo, "Reversed finite bounds")
        if op == "int":
            vals = []
            for j in range(lo, hi):
                d = degree(body, var, j)
                vals.append(sum(w * value(body, var, j + u) for u, w in open_rule(d)))
            return sum(vals, Q(0))
        vals = (value(body, var, Q(k)) for k in range(lo, hi + 1))
        return sum(vals, Q(0)) if op == "sum" else prod(vals, start=Q(1))
    if op == "det":
        a1, b1, c1, d1 = (value(z, name, x) for z in a)
        return a1 * d1 - b1 * c1
    a0 = value(a[0], name, x)
    if op == "abs":
        return abs(a0)
    if op == "floor":
        return Q(a0.__floor__())
    if op == "ceil":
        return Q(a0.__ceil__())
    if op == "fact":
        require(a0.denominator == 1 and a0 >= 0, "Invalid factorial")
        return Q(factorial(int(a0)))
    if op == "sqrt":
        require(a0 >= 0, "Negative radicand")
        u, v = isqrt(a0.numerator), isqrt(a0.denominator)
        require(Q(u, v) ** 2 == a0, "Irrational radicand")
        return Q(u, v)
    b = value(a[1], name, x)
    if op == "add":
        return a0 + b
    if op == "sub":
        return a0 - b
    if op == "mul":
        return a0 * b
    if op == "div":
        return a0 / b
    if op == "pow":
        require(b.denominator == 1 and b >= 0, "Invalid exponent")
        return a0 ** int(b)
    if op == "bin":
        require(
            a0.denominator == b.denominator == 1 and 0 <= b <= a0, "Invalid binomial"
        )
        return Q(comb(int(a0), int(b)))
    raise ValueError(t)


def monomial_degree(t, var):
    if t == ("var", var):
        return 1
    require(
        t[0] == "pow" and t[1] == ("var", var) and t[2][0] == "num" and t[2][1] >= 0,
        "Moving-limit integrand is not a nonnegative power of its dummy",
    )
    return t[2][1]


@cache
def degree(t, var, j):
    if var not in free(t):
        return 0
    op, *a = t
    if op == "var":
        return 1
    if op == "det":
        a1, b1, c1, d1 = (degree(z, var, j) for z in a)
        return max(a1 + d1, b1 + c1)
    if op == "int" and isinstance(a[2], tuple):
        return degree(a[2], var, j) * (1 + monomial_degree(a[3], a[0]))
    d = degree(a[0], var, j)
    if op in ("floor", "ceil", "abs"):
        require(d <= 1, "Non-affine fence argument")
        u = value(a[0], var, Q(3 * j + 1, 3))
        v = value(a[0], var, Q(3 * j + 2, 3))
        low, hi = sorted([2 * u - v, 2 * v - u])
        if op == "abs":
            require(not low < 0 < hi, "Interior sign change")
            return d
        require(not low < low.__floor__() + 1 < hi, "Interior integer crossing")
        return 0
    if op == "fact":
        require(d == 0, "Nonconstant factorial")
        return 0
    e = degree(a[1], var, j)
    if op in ("add", "sub"):
        return max(d, e)
    if op == "mul":
        return d + e
    if op == "div":
        require(e == 0, "Variable denominator")
        return d
    if op == "pow":
        require(e == 0, "Variable exponent")
        return d * int(value(a[1]))
    raise ValueError("Cannot certify local degree: " + str(t))


def independently_integrate(blocks, variable, lo, hi):
    total = Q(0)
    largest = 0
    for j in range(lo, hi):
        for group in blocks:
            d = sum(degree(t, variable, j) for t in group)
            largest = max(largest, d)
            fixed = prod((value(t) for t in group if not free(t)), start=Q(1))
            moving = [t for t in group if free(t)]
            total += fixed * sum(
                w * prod((value(t, variable, j + u) for t in moving), start=Q(1))
                for u, w in open_rule(d)
            )
    return total, largest


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inspect_exports():
    import pymupdf
    from PIL import Image, ImageOps

    with pymupdf.open(BASE / "portrait.pdf") as d:
        require(len(d) == 1, "Expected a single PDF page")
        p = d[0]
        pw, ph = p.rect.width, p.rect.height
        require(not p.get_images(full=True), "Unexpected image in vector PDF")
        require(not p.get_xobjects(), "Unexpected embedded form")
        fonts = p.get_fonts(full=True)
        require(
            len(fonts) == 1 and "STIXTwoMath-Regular" in fonts[0][3],
            "Unexpected PDF font",
        )
        require(len(d.extract_font(fonts[0][0])[3]) > 0, "Font is not embedded")
        marks = 0
        for run in p.get_texttrace():
            require(
                run["type"] == 0 and run["opacity"] == 1,
                "Invisible or overprinted PDF text",
            )
            require(
                all(c == 0 for c in run["color"])
                if isinstance(run["color"], tuple)
                else run["color"] == 0,
                "Nonblack PDF glyph",
            )
            for unicode_id, gid, origin, _ in run["chars"]:
                require(gid > 0 and unicode_id != 0xFFFD, "Missing font glyph")
                require(
                    0 <= origin[0] < pw and 0 <= origin[1] < ph,
                    "Glyph origin off the page",
                )
                marks += 1
        rules = p.get_drawings()
        for rule in rules:
            require(
                rule["type"] == "s"
                and rule["color"] == (0, 0, 0)
                and rule["stroke_opacity"] == 1,
                "Unexpected painted path",
            )
            for item in rule["items"]:
                require(
                    item[0] == "l" and abs(item[1].y - item[2].y) < 0.012,
                    "Unexpected nonhorizontal drawn path",
                )
                require(
                    p.rect.contains(item[1]) and p.rect.contains(item[2]),
                    "Rule endpoint off page",
                )
    with Image.open(BASE / "portrait.png") as im:
        require(
            im.mode == "L" and im.width >= 4096,
            "Final grayscale export is missing or undersized",
        )
        require(
            abs(im.height / im.width - ph / pw) < 2 / im.width,
            "Page and image bounds disagree",
        )
        bounds = ImageOps.invert(im).point(lambda x: 255 if x > 18 else 0).getbbox()
        require(bounds is not None, "Empty raster")
        l, t, r, b = bounds
        margins = (l, t, im.width - r, im.height - b)
        require(min(margins) >= 4, "Visible ink reaches the image edge")
        size = im.size
    return marks, len(rules), size, margins, (pw, ph)


def main():
    import mathscore
    from typeset import WORK, compile_tex

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--write",
        action="store_true",
        help="write value, proof, and verification report",
    )
    args = ap.parse_args()
    path = BASE / "expression.tex"
    score = json.loads(gzip.decompress((BASE / "score.json.gz").read_bytes()))
    printed_outer, groups, signs, printed = read_source(path)
    rounding, (operator, variable, lo, hi, (body, rows)) = score["expression"]
    require(
        (rounding, operator, body) == ("floor", "int", "sum_of_products"),
        "Outer score operators differ",
    )
    require(
        printed_outer == (variable, lo, hi),
        "Printed variable or integral limits differ from the score",
    )
    require(len(rows) == len(groups), "Row count differs")
    reference = [normalized(t) for t in score["factors"]]
    distinct = set()
    for j, (rf, symbols, row_trees) in enumerate(zip(rows, signs, printed)):
        require(
            [s for s, i, g in rf["items"]] == symbols,
            f"Product/addition signs differ on row {j + 1}",
        )
        require(
            [reference[i] for s, i, g in rf["items"]] == row_trees,
            f"AST mismatch on row {j + 1}",
        )
        distinct.update(row_trees)
    for t in distinct:
        require(free(t) <= {variable}, "Unbound variable in a printed factor")
        for k in range(lo, hi + 1):
            value(t, variable, Q(k))
    for raw, printed_tree in zip(score["factors"], reference):
        tree = mathscore.freeze(raw)
        cells = range(lo, hi) if free(printed_tree) else (lo,)
        for j in cells:
            coeff = mathscore.segment(tree, j)
            bound = max(len(coeff) - 1, degree(printed_tree, variable, j))
            for u, _ in open_rule(bound):
                x = j + u
                expanded = sum(c * x**k for k, c in enumerate(coeff))
                require(
                    expanded == value(printed_tree, variable, x),
                    "Independent factor value differs",
                )
    print(
        f"Parsed and cross-checked all {sum(map(len, printed)):,} printed factors.",
        flush=True,
    )
    model = mathscore.components(score)
    results = []
    maxdegree = 0
    for j, g in enumerate(groups):
        y, n = independently_integrate(g, *printed_outer)
        require(y == model[j], f"Row {j + 1}: exact integrals disagree")
        results.append(y)
        maxdegree = max(n, maxdegree)
    exact = sum(results, Q(0))
    integer = exact.__floor__()
    require(
        integer <= exact < integer + 1 and exact == sum(model, Q(0)),
        "Outer floor failed",
    )
    row_hash = hashlib.sha256(
        "\n".join(f"{z.numerator}/{z.denominator}" for z in results).encode()
    ).hexdigest()
    compile_tex(path)
    require(
        digest(WORK / "expression.pdf") == digest(BASE / "portrait.pdf"),
        "PDF differs from fresh deterministic compilation",
    )
    marks, lines, size, margin, page = inspect_exports()
    stats = Counter()

    def visit(t):
        stats[t[0]] += 1
        for a in t[1:]:
            if isinstance(a, tuple):
                visit(a)

    for row in printed:
        for t in row:
            visit(t)
    from typeset import render

    # Re-rasterize the freshly compiled vector source at the delivered native dimensions.
    rebuilt = render(
        WORK / "expression.pdf", size[0], WORK / "comparison-render.png", oversample=2
    )
    from PIL import Image, ImageChops

    with Image.open(BASE / "portrait.png") as delivered:
        require(
            ImageChops.difference(rebuilt, delivered).getbbox() is None,
            "PNG differs from freshly rasterized PDF",
        )
    terms = sum(map(len, groups))
    factors = sum(map(len, printed))
    R = exact - integer
    totals = dict(
        integer=str(integer),
        numerator=str(exact.numerator),
        denominator=str(exact.denominator),
        remainder_num=str(R.numerator),
        remainder_den=str(R.denominator),
        rows=len(rows),
        terms=terms,
        factors=factors,
        distinct=len(distinct),
        max_degree=maxdegree,
        inner_integrals=stats["int"],
        sums=stats["sum"],
        prods=stats["prod"],
        glyphs=marks,
        rules=lines,
        row_hash=row_hash,
        png_size=size,
        margins=margin,
        page=page,
    )
    report = (
        "DOWNWARD GLANCE\nExact mathematical and rendering verification\n\n"
        f"Integer  {integer}\n"
        f"Integral before taking its floor  {exact.numerator} / {exact.denominator}\n"
        f"Fraction discarded by the floor  {R.numerator} / {R.denominator}\n\n"
        f"The standalone TeX was parsed from its first floor to its final differential and closing floor. "
        f"All {len(rows)} lines, {len(rows) - 1} explicit continuation plus signs, {terms:,} additive products, and {factors:,} printed factor occurrences "
        f"match the semantic score. Each whole line was also reparsed after removing invisible atom braces.\n"
        f"The integrand contains {stats['int']:,} inner definite integrals, {stats['sum']:,} finite sums, "
        f"{stats['prod']:,} finite products, and {stats['det']:,} two-by-two determinants, counted with multiplicity.\n"
        f"Every one of the {len(distinct):,} distinct parsed factors also agrees with its score value separately, "
        f"at sufficiently many exact points to identify its polynomial on each interval.\n\n"
        f"On each of the six open unit intervals from −3 to 3, the score evaluator expands each product in "
        f"rational polynomial coefficients and integrates its monomials. The separate TeX evaluator proves "
        f"there are no interior sign or integer crossings under the relevant fences, bounds every local degree "
        f"(maximum {maxdegree}), and uses exact interior Lagrange quadrature. All row integrals agree as rational "
        f"numbers. Every printed factor is defined at all seven integer endpoints.\n"
        f"SHA-256 of ordered row integrals, numerator/denominator joined with LF  {row_hash}\n\n"
        f"Freshly compiled one vector page with {marks:,} glyph occurrences, one embedded STIX Two Math Regular "
        f"subset, and {lines:,} native horizontal mathematical rules. Zero image objects. All glyphs and rules "
        f"use opaque black. The compile log passed checks for overfull boxes and missing characters.\n"
        f"PDF page  {page[0]:.2f} × {page[1]:.2f} PostScript points\n"
        f"PNG  {size[0]} × {size[1]} pixels, 8-bit grayscale antialiasing, rasterized at twice the export width "
        f"and reduced with Lanczos. A second rendering matched every pixel.\n"
        f"White edge clearances at ink contrast > 18/255, left/top/right/bottom  {margin}\n"
        f"TeX source SHA-256  {digest(path)}\nPDF SHA-256  {digest(BASE / 'portrait.pdf')}\n"
        f"PNG SHA-256  {digest(BASE / 'portrait.png')}\n\n"
        "The arithmetic checks are exact. Tonal resemblance and the legibility of the densest hatching are "
        "visual judgments. The darkest pencil-like passages still contain white paper between the glyphs.\n"
    )
    if args.write:
        (BASE / "value.txt").write_text(str(integer) + "\n")
        (BASE / "verification.txt").write_text(report)
        (WORK / "summary.json").write_text(json.dumps(totals, indent=2))
        from publication import proof

        proof(totals)
    else:
        require(
            (BASE / "value.txt").read_text() == str(integer) + "\n",
            "Published integer differs",
        )
        require(
            (BASE / "verification.txt").read_text() == report,
            "Published report differs",
        )
    print(f"All {len(rows)} row integrals agree. Floor = {integer}", flush=True)


if __name__ == "__main__":
    main()
