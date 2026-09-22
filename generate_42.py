#!/usr/bin/env python3
"""
Generate an animated dot-matrix "42" that morphs through a series of typefaces.

Requires Pillow (only to rasterise the fonts):

    python3 -m pip install Pillow
    python3 generate_42.py > assets/42.svg

The output is a plain static SVG with no dependencies of its own, so this script
is a build step, not something the banner needs at runtime.

How it works
------------
Every typeface is rasterised, then reduced to exactly DOTS points by binary
searching a grid spacing that lands on that count -- a heavy face gets a coarse
grid, a hairline face a fine one. Because every glyph is made of the same number
of dots, consecutive glyphs can be matched one-to-one (nearest-neighbour, greedy)
and each dot simply flies from its old seat to its new one.

That means one CSS keyframe rule per dot -- 160 of them -- rather than one per
frame. cx, cy and r all animate inside the same rule, so a dot changes size as
it travels: coarse grids get fat dots, fine grids get small ones.

GitHub renders SVG inside <img>, so there is no JavaScript available; all of the
motion has to be baked into CSS at build time. Hence the above.
"""

import sys
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- CONFIG ----

WIDTH, HEIGHT = 760, 210        # canvas size in px
GLYPH_HEIGHT = 170              # cap height of the "42" in px
DOTS = 210                      # dots per glyph; identical across all typefaces

HOLD = 0.60                     # share of each slot spent holding the glyph still
SLOT_SECONDS = 1.7              # seconds per typeface, morph included

DOT_SCALE = 0.30                # dot radius as a fraction of that glyph's spacing
DOT_MIN, DOT_MAX = 2.3, 4.6     # clamp, so dense glyphs stay legible

DOT_DARK = "#7C6BF5"            # dot colour on dark backgrounds
DOT_LIGHT = "#4B3FD4"           # dot colour on light backgrounds

TEXT = "42"

# Ordered so the loop closes on two similarly wide, heavy faces.
FONTS = [
    ("/System/Library/Fonts/Supplemental/Arial Black.ttf", 0),
    ("/System/Library/Fonts/Futura.ttc", 0),
    ("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Didot.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Bodoni 72.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Brush Script.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Copperplate.ttc", 0),
]

COVERAGE = 0.30                 # ink share of a cell needed to earn a dot
#
# Sampling by coverage rather than by the cell's centre pixel matters: a high
# contrast face like Didot draws the crossbar of its "4" only 2-3px thick, and
# a centre probe steps straight over it, leaving a glyph that reads as "12".

# -------------------------------------------------------------- GENERATOR ---


def rasterise(path, index):
    """Render TEXT at GLYPH_HEIGHT, cropped tight to its ink."""
    font = ImageFont.truetype(path, 420, index=index)
    canvas = Image.new("L", (2000, 900), 0)
    ImageDraw.Draw(canvas).text((120, 150), TEXT, 255, font=font)
    box = canvas.getbbox()
    if box is None:
        raise ValueError(f"{path} rendered nothing")
    cropped = canvas.crop(box)
    width = max(1, round(cropped.width * GLYPH_HEIGHT / cropped.height))
    return cropped.resize((width, GLYPH_HEIGHT), Image.LANCZOS)


def sample(mask, spacing):
    """
    Dot centres on a grid of roughly `spacing`, wherever enough of the cell is
    ink. Downscaling with BOX averages each cell, so the pixel value that comes
    back is that cell's ink coverage -- thin strokes register instead of being
    stepped over.
    """
    cols = max(1, round(mask.width / spacing))
    rows = max(1, round(mask.height / spacing))
    cells = mask.resize((cols, rows), Image.BOX)
    step_x, step_y = mask.width / cols, mask.height / rows
    return [((x + 0.5) * step_x, (y + 0.5) * step_y, cells.getpixel((x, y)))
            for y in range(rows) for x in range(cols)
            if cells.getpixel((x, y)) > COVERAGE * 255]


def sample_exactly(mask, target):
    """
    The widest grid spacing that still yields at least `target` dots, trimmed
    down to exactly that many.

    Finer spacing always means more dots, so the search is well behaved. The
    dots dropped are the faintest cells -- the half-covered ones along a
    stroke's edge -- which costs the least shape. Dots are never duplicated to
    pad a glyph out: two dots at one position would look like a missing dot,
    and every glyph has to show the same count as all the others.
    """
    lo, hi = 0.8, 40.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if len(sample(mask, mid)) >= target:
            lo = mid
        else:
            hi = mid
    pts = sample(mask, lo)
    pts.sort(key=lambda p: -p[2])
    return lo, [(x, y) for (x, y, _ink) in pts[:target]]


def centre(pts, mask):
    """Move a glyph's dots into the middle of the canvas."""
    ox = (WIDTH - mask.width) / 2
    oy = (HEIGHT - mask.height) / 2
    return [(round(x + ox, 1), round(y + oy, 1)) for (x, y) in pts]


def match(previous, nxt):
    """
    Reorder `nxt` so nxt[i] is a near neighbour of previous[i], keeping each dot's
    journey short. Greedy nearest-neighbour: good enough, and O(n^2) on n=160.
    """
    free = list(range(len(nxt)))
    out = [None] * len(previous)
    # Longest-travelling dots pick first, so no straggler is left with a far seat.
    order = sorted(range(len(previous)), key=lambda i: -previous[i][0])
    for i in order:
        px, py = previous[i]
        best = min(free, key=lambda j: (nxt[j][0] - px) ** 2 + (nxt[j][1] - py) ** 2)
        out[i] = nxt[best]
        free.remove(best)
    return out


def build():
    glyphs = []
    for path, index in FONTS:
        mask = rasterise(path, index)
        spacing, pts = sample_exactly(mask, DOTS)
        radius = round(min(DOT_MAX, max(DOT_MIN, spacing * DOT_SCALE)), 2)
        glyphs.append((centre(pts, mask), radius))
        print(f"  {path.split('/')[-1]:26s} spacing={spacing:5.2f} r={radius} "
              f"dots={len(pts)}", file=sys.stderr)

    # Chain the matching so a dot keeps its identity all the way around the loop.
    chained = [glyphs[0]]
    for pts, radius in glyphs[1:]:
        chained.append((match(chained[-1][0], pts), radius))

    slots = len(chained)
    duration = round(slots * SLOT_SECONDS, 3)
    slot_pct = 100 / slots

    rules = []
    for dot in range(DOTS):
        stops = []
        for i, (pts, radius) in enumerate(chained):
            x, y = pts[dot]
            frame = f"cx:{x}px;cy:{y}px;r:{radius}px"
            stops.append(f"{round(i * slot_pct, 3):g}%{{{frame}}}")
            stops.append(f"{round((i + HOLD) * slot_pct, 3):g}%{{{frame}}}")
        x, y = chained[0][0][dot]
        stops.append(f"100%{{cx:{x}px;cy:{y}px;r:{chained[0][1]}px}}")
        rules.append(f"@keyframes d{dot}{{{''.join(stops)}}}")

    circles = []
    for dot in range(DOTS):
        x, y = chained[0][0][dot]
        circles.append(
            f'<circle cx="{x}" cy="{y}" r="{chained[0][1]}" '
            f'style="animation-name:d{dot}"/>'
        )

    css = (
        f":root{{--dot:{DOT_DARK}}}"
        f"@media(prefers-color-scheme:light){{:root{{--dot:{DOT_LIGHT}}}}}"
        f"circle{{fill:var(--dot);"
        f"animation-duration:{duration}s;animation-iteration-count:infinite;"
        f"animation-timing-function:cubic-bezier(.65,0,.35,1)}}"
        # Without animation the circles fall back to their cx/cy/r attributes,
        # which spell the first typeface -- a perfectly readable still "42".
        "@media(prefers-reduced-motion:reduce){circle{animation:none}}"
        + "".join(rules)
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        f'aria-label="The number 42 drawn in dots, morphing through a series of '
        f'typefaces">'
        f"<style>{css}</style>{''.join(circles)}</svg>"
    )
    print(f"{slots} typefaces, {DOTS} dots, {duration}s loop, "
          f"{len(svg) / 1024:.1f} KB", file=sys.stderr)
    return svg


if __name__ == "__main__":
    sys.stdout.write(build() + "\n")
