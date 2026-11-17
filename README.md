# Downward Glance

A face in headphones, typeset as one mathematical expression. The lowered eyelids, the smile, the headband, and the folds of the hoodie are made of black notation on white paper. The expression evaluates to **−373571877419178597233231125653**.

[![Downward Glance, the complete expression](portrait.png)](portrait.pdf)

[Vector print](portrait.pdf) · [Full-resolution PNG](portrait.png) · [Detail of the smile](detail.png) · [Measured type specimen](specimen.png) · [One-page proof](proof.pdf)

## Reading the expression

The first line opens a floor, a definite integral from −3 to 3, and a parenthesis. Every subsequent line begins with a plus sign. The last line closes the parenthesis, prints the differential, and closes the floor. Ordinary addition and multiplication join 2,507 products across 216 lines. A pair of bars around a two-by-two array denotes its determinant.

The integral variable is the lowercase italic letter *l*. It passes through zero and crosses integer boundaries. Taking its magnitude, rounding it, or taking the factorial of a rounded magnitude changes the integrand. These operations supply the close vertical hatching in the headband and earcups. In the sky, a single bounded integral can span the width occupied by several short factors in the face. The highlight on the lower lip is paper between terms.

The complete formula is written out in one LaTeX file. Its braces, spaces, and line layout use standard TeX. The page-size special sets the print dimensions. The direct page output allows Tectonic to ship the large mathematical box without duplicating it in memory. [Standalone expression](expression.tex)

## How the portrait was composed

The source photograph measures 736 × 667 pixels. I tested an Otsu threshold, four and sixteen gray levels, continuous grayscale, Floyd–Steinberg, Bayer, and Atkinson dithering. A blend of 73% original grayscale and 27% locally contrast-enhanced grayscale kept the light under the mouth and the gradation around the eyes. The working copy repairs the small “EDIT” overlay at the upper edge. The original is preserved byte for byte. The photograph and both plates containing it are local deliverables.

I typeset candidate expressions in New Computer Modern and STIX Two Math. STIX Two Math Regular gave the compact floor, ceiling, and modulus signs clearer separation and a stronger shadow range. The final art uses that one font at a 10-point base size. Limits, scripts, and delimiters follow mathematical sizing conventions. The specimen shows actual advances and ink areas measured from rendered TeX.

The compositor measures each phrase's width, baseline, ink area, and occupied outline. It assigns variable-width phrases and whitespace to successive parts of the image, carries some local ink surplus or deficit into the following line, and reserves the space occupied by tall fractions and integrals. The score stores the outer floor, its integral and bounds, the sum of products, the factor trees, and their typeset placements. [Compositor](compose.py) · [Semantic score](score.json.gz)

The source and finished artwork have different tonal ranges. On a 0–255 grayscale, the same sky patch averages **196** in the photograph and **249** in the print. The dark left earcup averages **18** and **171**, respectively. Open paper between legible strokes lifts the shadows. After registration and a five-pixel Gaussian blur, luminance correlation with the original is **0.980** and mean absolute luminance error is **101.4 levels**. The former describes the placement of tones. The latter includes the difference in their absolute brightness.

## Exact value

The integrand is polynomial on each of the six open unit intervals between −3 and 3. Its coefficients are rational. For example, an actual inner integral is the integral of the fourth power of *t* from zero to the magnitude of *l*. Its value is the fifth power of that magnitude divided by five. The values assigned to the seven integer endpoints do not affect the integral.

One evaluator expands the score into rational polynomial coefficients and integrates monomials. The other parses the emitted TeX, checks the scope of its operators, and integrates each polynomial by exact rational interpolation. The two methods agree on every line. The unrounded integral is the reported integer plus **17602437396215302323978349 / 25410946577841365997456000**. That fraction lies strictly between zero and one. [Proof](proof.pdf) · [Exact integer](value.txt) · [Verification report](verification.txt)

## Rebuild

The recorded build used CPython 3.12.3, Tectonic 0.17.0 with its XeTeX engine, and Tectonic resource bundle v33. The font file is STIXTwoMath-Regular.otf from that bundle. The Python package versions are pinned. The PDF timestamp is fixed to 17 November 2026 for reproducible exports. With Tectonic and uv on the executable path, run this command from the repository.

```sh
uv run --python 3.12 --with-requirements requirements.txt python generate.py
```

The default build reads the published score, regenerates the source, compiles the PDF, renders the 7680 × 7013 PNG at twice its delivery width before Lanczos reduction, and produces the detail, specimen, proof, value, and verification report. It runs entirely from the public files once the software dependencies and TeX resources are cached. The PDF is about 34.47 × 31.47 inches at its native size.

To run the independent checker against the published files, use the following command.

```sh
uv run --python 3.12 --with-requirements requirements.txt python check.py
```

To typeset just the expression, put its TeX file in an empty directory and run the compiler directly.

```sh
tectonic expression.tex
```

With the original photograph, the full composition, reference contact sheet, side-by-side comparison, and local tonal measurements can also be regenerated.

```sh
uv run --python 3.12 --with-requirements requirements.txt python generate.py --compose /path/to/original.png
```

Use `--private-plates /path/to/original.png` in place of `--compose` to retain the published score and regenerate the photographic plates. Local working files go into `.work/`. A populated Tectonic cache supports offline builds with `TECTONIC_ONLY_CACHED=1`.

The output audit checks the embedded font, opaque black text and horizontal mathematical rules, page count, glyph coverage, and white margins. It independently recompiles the final TeX and compares the freshly rasterized output with every delivered PNG pixel. [Build script](generate.py) · [Independent checker](check.py) · [Caption options](captions.txt)
