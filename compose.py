"""Fit variable-width mathematical phrases to a continuous luminance field."""

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

from mathscore import (
    air_factors,
    moving_factors,
    optical,
    outer_notation,
    portrait_tree,
    vocabulary,
)
from studies import prepare
from typeset import BASE, BP, SCALE, atlas

WIDTH = 2475.0
HEIGHT = WIDTH * 667 / 736
SIGNS = [r"+", r"\cdot", *outer_notation(portrait_tree([]))]


def catalog():
    families = vocabulary() | moving_factors() | air_factors()
    forms = list(families)
    strings = [optical(t) for t in forms] + SIGNS
    metrics = []
    for offset in range(0, len(strings), 180):
        chunk = atlas(strings[offset : offset + 180])
        for m in chunk:
            # Keep the real upper and lower outline, including blank interstices.
            a = m.pop("bitmap") < 239
            a = np.asarray(a, dtype=bool)
            width = max(1, int(np.ceil(m["width"])))
            upper = np.full(width, -np.inf)
            lower = np.full(width, -np.inf)
            for k in range(width):
                l = round((3 + k) * SCALE * BP)
                r = round((4 + k) * SCALE * BP)
                yy = np.nonzero(np.any(a[:, l:r], axis=1))[0]
                if len(yy):
                    upper[k] = BASE - yy.min() / (SCALE * BP)
                    lower[k] = (yy.max() + 1) / (SCALE * BP) - BASE
            m["upper"] = upper
            m["lower"] = lower
            m.pop("profile")
            metrics.append(m)
    # Tall phrases reserve their complete printed bounding rectangle. The next line
    # cannot put a detached numeral into an integral or between a numerator and its bar.
    for m in metrics:
        if m["top"] + m["bottom"] > 10.35:
            a = max(0, int(np.floor(m["left"])))
            b = min(len(m["upper"]), int(np.ceil(m["right"])))
            m["upper"][a:b] = m["top"]
            m["lower"][a:b] = m["bottom"]
    return forms, [families[t] for t in forms], metrics


def ink_target(photo):
    _, _, work, _ = prepare(photo)
    gray = work.astype(float)
    # Restore small feature edges after antialiasing; leave the broad cheek modeling continuous.
    sharp = np.clip(
        gray
        + 0.67 * (gray - gaussian_filter(gray, 2.2))
        + 0.17 * (gray - gaussian_filter(gray, 7)),
        0,
        255,
    )
    levels = [0, 10, 25, 48, 73, 97, 120, 149, 174, 195, 215, 250, 255]
    coverage = [
        0.470,
        0.455,
        0.420,
        0.353,
        0.284,
        0.220,
        0.161,
        0.100,
        0.051,
        0.018,
        0.005,
        0.0015,
        0.0015,
    ]
    return np.interp(sharp, levels, coverage)


def compose(photo):
    forms, families, met = catalog()
    N = len(forms)
    rng = np.random.default_rng(726113)
    target = ink_target(photo)
    xs = np.arange(int(WIDTH) + 1)
    w = np.array([m["width"] for m in met])
    area = np.array([m["area"] for m in met])
    top = np.array([m["top"] for m in met])
    bottom = np.array([m["bottom"] for m in met])
    left = np.array([m["left"] for m in met])
    right = np.array([m["right"] for m in met])
    fam = np.array(families)
    moving_set = set(moving_factors())
    moving = np.array([t in moving_set for t in forms])
    # Sample families before variants so a large combinatorial family cannot dominate by count.
    groups = [np.flatnonzero(fam == f) for f in sorted(set(families))]
    quiet = np.flatnonzero(
        np.isin(
            fam,
            [
                "open integral",
                "variable-limit integral",
                "definite integral",
                "finite sum",
                "finite prod",
                "telescoping sum",
                "telescoping prod",
            ],
        )
    )
    mid = np.flatnonzero(~moving & ~np.isin(fam, ["open integral"]))
    dark = np.flatnonzero(moving)
    determinants = np.flatnonzero(fam == "two-by-two determinant")
    height = HEIGHT
    pitch = 10.38
    nrows = round(height / pitch)
    ys = (np.arange(nrows) + 0.5) * height / nrows
    ys += 0.025 * np.sin(np.arange(nrows) * 1.715) + 0.012 * np.sin(
        np.arange(nrows) * 0.63
    )
    skyline = np.full(len(xs) + 160, -200.0)
    # Carry part of the preceding line's low-frequency area error into its neighbor.
    error = np.zeros(len(xs))
    rows = []
    gray_cache = target.astype("float32")
    for r, baseline in enumerate(ys):
        yi = baseline / height * 667 - 0.5
        ysamp = np.linspace(yi - 1.2, yi + 1.2, 5)
        line = np.mean(
            [
                cv2.getRectSubPix(gray_cache, (736, 1), (367.5, float(y)))[0]
                for y in ysamp
            ],
            axis=0,
        )
        ideal = np.interp(xs / WIDTH * 736 - 0.5, np.arange(736), line)
        level = np.clip(ideal + 0.48 * error, 0.002, 0.46)
        csum = np.r_[0, np.cumsum(level * pitch)]
        ink = np.zeros(len(xs))
        indent = round(
            float(rng.uniform(0.1, 3.0 + 18 * max(0, 1 - level[0] / 0.13))), 3
        )
        prefix = N + 2 if r == 0 else N
        # The line-continuation column is kept clear of neighboring tall factors.
        x = max(13.0 if level[0] > 0.16 else 24.0, indent + w[prefix])
        ymax = max(8.4, met[prefix]["height"])
        ymin = max(3.6, met[prefix]["depth"])
        limit = WIDTH - (w[N + 3] + 3 if r == len(ys) - 1 else 0)
        row = []
        count = 0
        nextplus = int(rng.integers(7, 15))
        last = -1
        last_right = 0
        used = {}
        while x < limit - 5:
            ix = min(int(x), len(xs) - 1)
            d = float(np.mean(level[ix : min(ix + 14, len(level))]))
            pooled = [int(g[rng.integers(len(g))]) for g in groups]
            choices = np.unique(
                np.concatenate(
                    (
                        pooled,
                        rng.choice(quiet, 9),
                        rng.choice(mid, 12),
                        rng.choice(determinants, 5),
                        rng.choice(dark, 18),
                        dark if d > 0.24 else [],
                    )
                )
            ).astype(int)
            # Compact details across the face; wider, open operators have room in the sky.
            portrait_detail = (
                0.30 < ix / WIDTH < 0.69 and 0.24 < baseline / height < 0.63
            )
            if portrait_detail:
                choices = choices[w[choices] < (43 if d < 0.075 else 49)]
            if not len(choices):
                choices = dark.copy()
            c = choices
            op = (
                "+"
                if count >= nextplus
                else ("." if count > 0 and rng.random() < 0.022 else "")
            )
            symw = w[N] if op == "+" else w[N + 1] if op == "." else 0.0
            syma = area[N] if op == "+" else area[N + 1] if op == "." else 0.0
            # Ordinary juxtaposition; use a centered dot at ambiguous adjoining absolute bars.
            ambiguous = np.array(
                [
                    op == ""
                    and last >= 0
                    and (
                        (forms[last][0] == "abs" and forms[i][0] == "abs")
                        or (
                            families[last] in ("factorial", "power")
                            and families[i] in ("factorial", "power")
                        )
                    )
                    for i in c
                ]
            )
            ow = np.where(ambiguous, w[N + 1], symw)
            oa = np.where(ambiguous, area[N + 1], syma)
            # Clip only empty side bearings. Keep genuine clearance on either side of the ink.
            clearance = 0.58 if d > 0.26 else 0.90
            minwhite = clearance - (w[last] - last_right if last >= 0 else 0) - left[c]
            mingap = np.maximum(-1.65, minwhite)
            mingap = np.where(ow > 0, 1.8, mingap)
            if count == 0:
                mingap = np.maximum(mingap, 1.0)
            masses = area[c] + oa
            end = np.searchsorted(csum, csum[ix] + masses)
            available = end - ix
            room = available - w[c] - ow
            # An operator can be laterally displaced into a sparse interval, but never scaled.
            gap = np.maximum(mingap, room)
            gapcap = 450.0 if not portrait_detail else 96.0
            gap = np.minimum(gap, gapcap)
            backing = 0.50 + 0.17 * np.sin(count * 2.37 + r * 1.09)
            gap = np.maximum(mingap, gap * backing)
            prefixgap = gap + ow
            start = x + prefixgap
            i_start = np.maximum(0, np.rint(start).astype(int))
            newend = start + w[c]
            minspan = w[c] + ow + mingap
            req = area[c] + oa
            normal = req / np.maximum(pitch * minspan, 1)
            # Preference for full-bodied marks in shadow and actual engraving in open passages.
            deficit = np.maximum(d - normal, 0)
            if d > 0.24:
                desired_tone = min(0.47, d + 0.024)
                tonal = np.abs(normal - desired_tone) * 1.4 + deficit * 3.6
            elif d > 0.095:
                tonal = (
                    np.maximum(d - normal, 0) * 3.0
                    + np.maximum(normal - (d + 0.10), 0) * 1.1
                )
            else:
                tonal = (
                    np.maximum(d - normal, 0) * 3.2
                    + np.maximum(normal - (d + 0.15), 0) * 1.6
                )
            bonus = np.where(moving[c], 0.0, 0.045)
            if d < 0.065:
                bonus += np.where(np.isin(c, quiet), 0.055, 0.0)
                if (r + count) % 4 in (0, 1) or portrait_detail:
                    bonus += np.where(w[c] < 12, 0.115, 0.0)
            if d > 0.20:
                bonus += np.where(moving[c], 0.035, 0.0)
            pref = tonal - bonus + rng.uniform(0, 0.118 if d > 0.28 else 0.095, len(c))
            pref += np.array(
                [(0.014 if d > 0.34 else 0.028) * used.get(int(i), 0) for i in c]
            )
            pref += np.where(c == last, 0.22, 0.0)
            pref += np.maximum(0, w[c] - 35) * (0.0025 if portrait_detail else 0.0008)
            if d > 0.280:
                pref += np.where((top[c] + bottom[c] > 10.3) | ~moving[c], 1.2, 0.0)
                pref += np.maximum(0.40 - normal, 0) * 2.2
            if 0.085 < d < 0.42 and rng.random() < (0.06 if d < 0.3 else 0.022):
                pref -= np.where(fam[c] == "two-by-two determinant", 2.1, 0.0)
            pref = np.where(newend <= limit, pref, np.inf)
            kbest = None
            for idx in np.argsort(pref):
                if not np.isfinite(pref[idx]):
                    break
                i = int(c[idx])
                m = met[i]
                s = i_start[idx]
                stop = s + len(m["upper"])
                if np.any(baseline - m["upper"] < skyline[s:stop] + 0.48):
                    continue
                if ow[idx] > 0:
                    sym = N + 1 if ambiguous[idx] or op == "." else N
                    prev_end = row[-1][3] if row else indent + w[prefix]
                    # Put the binary sign beside its following factor, including in long white passages.
                    sx = round(start[idx] - w[sym] - 1.3)
                    sm = met[sym]
                    if sx < prev_end - 0.05 or np.any(
                        baseline - sm["upper"]
                        < skyline[sx : sx + len(sm["upper"])] + 0.65
                    ):
                        continue
                kbest = idx
                break
            if kbest is None:
                # Advance through a neighbor's tall integral, preserving open counterspace.
                if limit - x < 9:
                    break
                x += 2.0
                continue
            k = kbest
            i = int(c[k])
            m = met[i]
            s = i_start[k]
            actualop = "." if ambiguous[k] else op
            symbolwidth = float(ow[k])
            # Store the advance relative to the last printed factor, including any skipped space.
            lastend = row[-1][3] if row else indent + w[prefix]
            glue = round(float(start[k] - lastend - symbolwidth), 3)
            if actualop in (".", "+"):
                si = N if actualop == "+" else N + 1
                signalx = float(start[k]) - symbolwidth - 1.3
                sx = round(signalx)
                sm = met[si]
                skyline[sx : sx + len(sm["lower"])] = np.maximum(
                    skyline[sx : sx + len(sm["lower"])], baseline + sm["lower"]
                )
                j0 = max(0, round(signalx))
                j1 = min(len(ink), round(signalx + w[si]))
                if j1 > j0:
                    ink[j0:j1] += area[si] / (j1 - j0) / pitch
            stop = s + len(m["upper"])
            skyline[s:stop] = np.maximum(skyline[s:stop], baseline + m["lower"])
            tw = max(1, int(round(w[i])))
            ink[s : min(len(ink), s + tw)] += area[i] / tw / pitch
            endx = float(start[k] + w[i])
            row.append([actualop, i, glue, endx])
            # The remainder of the mass-balanced interval becomes following whitespace.
            remainder = max(0.0, min(gapcap, room[k]) - gap[k])
            x = endx + remainder
            last = i
            last_right = right[i]
            ymax = max(ymax, m["height"])
            ymin = max(ymin, m["depth"])
            count += 1
            if op == "+":
                nextplus = count + int(
                    rng.integers(12, 24) if d > 0.29 else rng.integers(7, 16)
                )
            used[i] = min(3, used.get(i, 0) + 1)
            if count % 15 == 0:
                used = {}
        if not row:
            raise ValueError("Empty line")
        row[0][0] = ""
        if r == len(ys) - 1:
            ymax = max(ymax, met[N + 3]["height"])
            ymin = max(ymin, met[N + 3]["depth"])
        rows.append(
            dict(
                indent=indent,
                y=round(float(baseline), 3),
                height=round(float(ymax), 5),
                depth=round(float(ymin), 5),
                items=[v[:3] for v in row],
            )
        )
        error = np.clip(gaussian_filter1d(ideal - ink, 4), -0.18, 0.20)
    chosen = sorted({i for r in rows for _, i, _ in r["items"]})
    remap = {old: new for new, old in enumerate(chosen)}
    for row in rows:
        for item in row["items"]:
            item[1] = remap[item[1]]
    return dict(
        format=1,
        width=WIDTH,
        height=HEIGHT,
        factors=[forms[i] for i in chosen],
        families=[families[i] for i in chosen],
        expression=portrait_tree(rows),
    )
