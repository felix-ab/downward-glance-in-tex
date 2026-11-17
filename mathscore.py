"""Expression trees, their ordinary LaTeX spelling, and exact arithmetic."""

import random
from fractions import Fraction
from functools import cache
from math import comb, factorial, isqrt, prod


def node(op, *args):
    return (op, *args)


def portrait_tree(rows):
    return node("floor", node("int", "l", -3, 3, node("sum_of_products", rows)))


def outer_integral(root):
    operation, (integral, variable, low, high, (addition, rows)) = root
    if (operation, integral, addition) != ("floor", "int", "sum_of_products"):
        raise ValueError("Expected a floor of an integral of a sum of products")
    return variable, low, high, rows


def outer_notation(root):
    variable, low, high, _ = outer_integral(root)
    opening = r"\Bigl\lfloor\int_{" + str(low) + "}^{" + str(high) + r"}\!\Bigl("
    closing = r"\Bigr)\,\mathrm{d}" + variable + r"\Bigr\rfloor"
    return opening, closing


def num(n):
    return node("n", n)


def var(name):
    return node("v", name)


def fold(op, a, b):
    return node(op, a, b)


def frac(a, b):
    return node("frac", a, b)


def enclosed(op, a):
    return node(op, a)


def scope(a):
    return node("par", a)


def exponent(a, n):
    return node("pow", a, n)


def grouped(a):
    return scope(a) if a[0] in {"add", "sub", "mul", "sum", "prod", "int"} else a


def choose(a, b):
    return node("choose", a, b)


@cache
def tex(t):
    op, *a = t
    if op in ("n", "v"):
        return str(a[0])
    if op == "pow":
        base, power = a
        return tex(grouped(base)) + "^{" + str(power) + "}"
    if op == "fact":
        return tex(grouped(a[0])) + "!"
    if op in ("add", "sub", "mul"):
        sign = {"add": "+", "sub": "-", "mul": r"\cdot "}[op]
        return tex(a[0]) + sign + tex(a[1])
    if op in ("frac", "choose"):
        return (
            ("\\frac" if op == "frac" else "\\binom")
            + "{"
            + tex(a[0])
            + "}{"
            + tex(a[1])
            + "}"
        )
    if op == "root":
        return r"\sqrt{" + tex(a[0]) + "}"
    if op in ("par", "abs", "floor", "ceil"):
        left, right = {
            "par": ("(", ")"),
            "abs": (r"\lvert", r"\rvert"),
            "floor": (r"\lfloor", r"\rfloor"),
            "ceil": (r"\lceil", r"\rceil"),
        }[op]
        return r"\left" + left + " " + tex(a[0]) + r"\right" + right
    if op in ("sum", "prod"):
        v, lo, hi, body = a
        return (
            "\\"
            + op
            + "_{"
            + v
            + "="
            + str(lo)
            + "}^{"
            + str(hi)
            + "}"
            + tex(grouped(body))
        )
    if op == "int":
        v, lo, hi, body = a
        return (
            r"\int_{"
            + str(lo)
            + "}^{"
            + str(hi)
            + "}"
            + tex(grouped(body))
            + r"\,\mathrm{d}"
            + v
        )
    if op == "rep":
        return r"0.\overline{" + str(a[0]) + "}"
    raise ValueError(t)


def exact(t, env=None):
    e = {} if env is None else env
    op, *a = t
    if op == "n":
        return Fraction(a[0])
    if op == "v":
        return Fraction(e[a[0]])
    if op in ("sum", "prod"):
        name, lo, hi, body = a
        terms = (exact(body, {**e, name: j}) for j in range(lo, hi + 1))
        return (
            sum(terms, Fraction(0)) if op == "sum" else prod(terms, start=Fraction(1))
        )
    if op == "int":
        v, lo, hi, body = a
        coeffs = polynomial(body, v)
        return sum(
            Fraction(c, n + 1) * (hi ** (n + 1) - lo ** (n + 1))
            for n, c in enumerate(coeffs)
        )
    if op == "rep":
        return Fraction(a[0], 10 ** len(str(a[0])) - 1)
    x = exact(a[0], e)
    if op == "pow":
        return x ** a[1]
    if op == "fact":
        assert x.denominator == 1 and x >= 0
        return Fraction(factorial(int(x)))
    if op == "par":
        return x
    if op == "abs":
        return abs(x)
    if op == "floor":
        return Fraction(x.numerator // x.denominator)
    if op == "ceil":
        return Fraction(-(-x.numerator // x.denominator))
    if op == "root":
        n, d = isqrt(x.numerator), isqrt(x.denominator)
        assert n * n == x.numerator and d * d == x.denominator
        return Fraction(n, d)
    y = exact(a[1], e)
    if op == "add":
        return x + y
    if op == "sub":
        return x - y
    if op == "mul":
        return x * y
    if op == "frac":
        return x / y
    if op == "choose":
        assert x.denominator == y.denominator == 1 and 0 <= y <= x
        return Fraction(comb(int(x), int(y)))
    raise ValueError(t)


def polynomial(t, variable):
    op, *a = t
    if op == "n":
        return [a[0]]
    if op == "v" and a[0] == variable:
        return [0, 1]
    if op == "pow" and a[0] == var(variable) and a[1] >= 0:
        return [0] * a[1] + [1]
    if op in ("add", "sub"):
        lhs, rhs = polynomial(a[0], variable), polynomial(a[1], variable)
        size = max(len(lhs), len(rhs))
        lhs += [0] * (size - len(lhs))
        for j, v in enumerate(rhs):
            lhs[j] += v if op == "add" else -v
        return lhs
    raise ValueError(t)


def freeze(t):
    return tuple(freeze(i) for i in t) if isinstance(t, list) else t


def vocabulary():
    """Closed positive factors. Exposed big operators get a scope before juxtaposition."""
    factors = {}

    def add(t, family):
        if exact(t) <= 0:
            raise ValueError(t)
        factors.setdefault(t, family)

    I = num
    R = lambda a, b: frac(I(a), I(b))
    rng = random.Random(7417)
    for k in range(2, 10):
        add(enclosed("fact", I(k)), "factorial")
        add(enclosed("root", I(k * k)), "radical")
        add(exponent(I(k), 2), "power")
        for j in range(1, k):
            add(choose(I(k), I(j)), "binomial")
    for a in range(2, 12):
        for b in range(2, 10):
            if a != b:
                add(R(a, b), "quotient")
    for i in range(80):
        a, b, c, d = rng.choices(range(2, 10), k=4)
        add(frac(enclosed("fact", I(a)), I(b)), "factorial quotient")
        add(frac(I(a), choose(I(max(b, c) + 1), I(min(b, c)))), "binomial quotient")
        add(frac(choose(I(max(b, c) + 1), I(min(b, c))), I(a)), "binomial quotient")
        add(enclosed("root", R(a * a, b * b)), "rational radical")
        add(
            frac(enclosed("root", I(a * a)), enclosed("root", I(b * b))),
            "radical quotient",
        )
        add(frac(exponent(I(a), 2), exponent(I(b), 3)), "power quotient")
        top, bottom = R(a, b), R(c, d)
        add(frac(top, bottom), "compound quotient")
        add(
            frac(fold("add", I(a), top), fold("add", I(c), bottom)),
            "continued quotient",
        )
        if exact(top) != exact(bottom):
            add(enclosed("abs", fold("sub", top, bottom)), "rational distance")
        if a < b:
            add(enclosed("abs", fold("sub", I(a), I(b))), "integer distance")
        if a > b and a % b:
            add(enclosed("floor", R(a, b)), "integer part")
        if a % b:
            add(enclosed("ceil", R(a, b)), "integer part")
        decimal = node("rep", 10 * a + b)
        add(frac(decimal, R(c, d)), "periodic quotient")
        add(frac(node("rep", a), node("rep", b)), "periodic quotient")
        add(
            frac(fold("add", I(a), node("rep", b)), fold("add", I(d), node("rep", c))),
            "periodic quotient",
        )
        add(frac(exponent(I(a), 2), enclosed("fact", I(b))), "factorial quotient")
        add(exponent(choose(I(max(b, c) + 1), I(min(b, c))), 2), "binomial power")
        add(
            frac(
                choose(I(max(a, b) + 1), I(min(a, b))),
                choose(I(max(c, d) + 1), I(min(c, d))),
            ),
            "binomial quotient",
        )
    for v in ("x", "t", "u"):
        for a in range(2, 7):
            for p in range(1, 5):
                body = var(v) if p == 1 else exponent(var(v), p)
                add(scope(node("int", v, 0, a, body)), "definite integral")
                if p == 2:
                    add(
                        scope(node("int", v, 1, a, fold("add", body, I(a)))),
                        "definite integral",
                    )
    for v in ("j", "k"):
        for n in range(3, 9):
            for op in ("sum", "prod"):
                add(scope(node(op, v, 1, n, var(v))), "finite " + op)
                add(scope(node(op, v, 1, n, exponent(var(v), 2))), "finite " + op)
                add(
                    scope(node(op, v, 1, n, frac(fold("add", var(v), I(1)), var(v)))),
                    "telescoping " + op,
                )
    return factors


def moving_factors():
    """Factors in the outer integral's bound variable; every fence acts on a real argument."""
    l = var("l")
    result = {}
    for op in ("abs", "floor", "ceil"):
        a = enclosed(op, l)
        result[a] = "variable fence"
        for p in (2, 3):
            result[exponent(a, p)] = "fence power"
        for inner in ("abs", "floor", "ceil"):
            if (op == "abs") != (inner == "abs"):
                b = enclosed(op, enclosed(inner, l))
                result[b] = "nested fence"
                result[exponent(b, 2)] = "fence power"
                result[enclosed("fact", b)] = "step factorial"
    for offset in (1, 2, 3):
        for sign in ("add", "sub"):
            b = fold(sign, l, num(offset))
            result[enclosed("abs", b)] = "shifted modulus"
            result[enclosed("abs", fold("sub", enclosed("abs", l), num(offset)))] = (
                "folded modulus"
            )
        result[frac(enclosed("abs", l), num(offset + 1))] = "scaled modulus"
    for a in range(2, 7):
        for b in range(1, 4):
            result[
                node("det", enclosed("floor", l), num(a), num(b), enclosed("ceil", l))
            ] = "two-by-two determinant"
            result[node("det", enclosed("abs", l), num(a), frac(num(b), num(a)), l)] = (
                "two-by-two determinant"
            )
    for dummy in ("x", "t", "u"):
        for power in (1, 2, 3, 4):
            for upper in (
                enclosed("abs", l),
                enclosed("ceil", enclosed("abs", l)),
                enclosed("abs", enclosed("floor", l)),
            ):
                result[node("moment", dummy, power, upper)] = "variable-limit integral"
    result[l] = "variable"
    for p in (2, 3, 4, 5):
        result[exponent(l, p)] = "monomial"
    return result


def depends(t):
    if t[0] == "v":
        return t[1] == "l"
    if t[0] == "moment":
        return True
    if t[0] in ("n", "rep", "int", "sum", "prod", "air"):
        return False
    return any(depends(k) for k in t[1:] if isinstance(k, tuple))


def optical(t):
    """Fixed, collision-tested spacing for fences at the base text size."""
    op, *a = t
    if op == "det":
        return (
            r"\left\lvert\begin{smallmatrix}"
            + tex(a[0])
            + "&"
            + tex(a[1])
            + r"\\"
            + tex(a[2])
            + "&"
            + tex(a[3])
            + r"\end{smallmatrix}\right\rvert"
        )
    if op == "moment":
        v, p, upper = a
        body = v if p == 1 else v + "^{" + str(p) + "}"
        return (
            r"\left(\int_{0}^{"
            + tex(upper)
            + "}"
            + body
            + r"\,\mathrm{d}"
            + v
            + r"\right)"
        )
    if op == "air":
        v, hi, p, glue, display = a
        spacing = {"thin": r"\,", "em": r"\quad ", "double": r"\qquad "}[glue]
        power = v if p == 1 else v + "^{" + str(p) + "}"
        style = r"\displaystyle " if display else ""
        return (
            r"\left("
            + style
            + r"\int_{0}^{"
            + str(hi)
            + "}"
            + spacing
            + power
            + spacing
            + r"\mathrm{d}"
            + v
            + r"\right)"
        )
    if op in ("abs", "floor", "ceil") and depends(t):
        left, right = {
            "abs": (r"\lvert", r"\rvert"),
            "floor": (r"\lfloor", r"\rfloor"),
            "ceil": (r"\lceil", r"\rceil"),
        }[op]
        # Each pair was measured at the actual font size. The selected advances
        # leave at least half a TeX point between the separate ink components.
        key = a[0][0]
        inner = {
            "abs": {"v": (1.5, 1.5), "floor": (2.1, 2.4), "ceil": (2.1, 2.4)},
            "floor": {"v": (3.0, 2.7), "abs": (1.2, 1.2)},
            "ceil": {"v": (1.2, 0.3), "abs": (1.2, 1.2)},
        }[op]
        lspace, rspace = inner.get(key, (0.3, 0.3))
        return (
            left
            + r"\mkern-"
            + f"{lspace:.1f}mu "
            + optical(a[0])
            + r"\mkern-"
            + f"{rspace:.1f}mu "
            + right
        )
    if op == "pow" and depends(t):
        return optical(grouped(a[0])) + "^{" + str(a[1]) + "}"
    if op == "fact" and depends(t):
        return optical(a[0]) + "!"
    if op == "frac" and depends(t):
        return r"\frac{" + optical(a[0]) + "}{" + optical(a[1]) + "}"
    if op in ("add", "sub") and depends(t):
        return optical(a[0]) + ("+" if op == "add" else "-") + optical(a[1])
    return tex(t)


def air_factors():
    return {
        node("air", v, h, p, s, d): "open integral"
        for v in ("x", "t", "u")
        for h in (1, 2, 3)
        for p in (1, 2, 3)
        for s in ("thin", "em", "double")
        for d in (0, 1)
    }


def const(t):
    if t[0] == "air":
        _, v, h, p, _, _ = t
        return exact(node("int", v, 0, h, exponent(var(v), p)))
    return exact(t)


def trim(coeff):
    while len(coeff) > 1 and coeff[-1] == 0:
        coeff.pop()
    return coeff


def pluspoly(a, b, sign=1):
    c = [Fraction(0)] * max(len(a), len(b))
    for i, v in enumerate(a):
        c[i] += v
    for i, v in enumerate(b):
        c[i] += sign * v
    return trim(c)


def timespoly(a, b):
    c = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            c[i + j] += x * y
    return trim(c)


@cache
def segment(t, j):
    """Coefficients on the open unit interval (j,j+1)."""
    if not depends(t):
        return (const(t),)
    op, *a = t
    if op == "v":
        return (Fraction(0), Fraction(1))
    if op == "det":
        u, v, w, z = (segment(k, j) for k in a)
        return tuple(pluspoly(timespoly(u, z), timespoly(v, w), -1))
    if op == "moment":
        v, p, upper = a
        limit = segment(upper, j)
        coeff = [Fraction(1)]
        for _ in range(p + 1):
            coeff = timespoly(coeff, limit)
        return tuple(c / (p + 1) for c in coeff)
    x = segment(a[0], j)
    point = Fraction(2 * j + 1, 2)
    mid = sum(v * point**i for i, v in enumerate(x))
    if op == "abs":
        # All arguments that reach an absolute value are affine with integral breakpoints.
        assert len(x) <= 2
        if len(x) == 2:
            assert not (j < -x[0] / x[1] < j + 1)
        return x if mid >= 0 else tuple(-v for v in x)
    if op in ("floor", "ceil"):
        assert len(x) <= 2
        if len(x) == 2:
            assert (
                all((x[0] + x[1] * p).denominator == 1 for p in (j, j + 1))
                and abs(x[1]) <= 1
            )
        value = (
            mid.numerator // mid.denominator
            if op == "floor"
            else -(-mid.numerator // mid.denominator)
        )
        return (Fraction(value),)
    if op == "fact":
        assert len(x) == 1 and mid.denominator == 1 and mid >= 0
        return (Fraction(factorial(int(mid))),)
    if op == "pow":
        y = [Fraction(1)]
        for _ in range(a[1]):
            y = timespoly(y, x)
        return tuple(y)
    y = segment(a[1], j)
    if op in ("add", "sub"):
        return tuple(pluspoly(x, y, 1 if op == "add" else -1))
    if op == "frac":
        assert len(y) == 1 and y[0]
        return tuple(z / y[0] for z in x)
    raise ValueError(t)


def components(score):
    forms = [freeze(t) for t in score["factors"]]
    values = []
    _, low, high, rows = outer_integral(score["expression"])
    for row in rows:
        total = Fraction(0)
        for j in range(low, high):
            addition = [Fraction(0)]
            group = [Fraction(1)]
            for op, i, _ in row["items"]:
                if op == "+":
                    addition = pluspoly(addition, group)
                    group = [Fraction(1)]
                group = timespoly(group, segment(forms[i], j))
            addition = pluspoly(addition, group)
            total += sum(
                c * Fraction((j + 1) ** (k + 1) - j ** (k + 1), k + 1)
                for k, c in enumerate(addition)
            )
        values.append(total)
    return values
