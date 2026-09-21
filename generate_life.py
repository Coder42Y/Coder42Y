#!/usr/bin/env python3
"""
Generate an animated dot-matrix banner: Conway's Game of Life, opening on "42".

No dependencies beyond the Python standard library.

    python3 generate_life.py > assets/life.svg

The loop, in three acts:

    1. "42" sits still for a moment so you can read it.
    2. Random cells rain in and the whole grid boils.
    3. Cells settle back into "42", and it starts over.

The grid wraps around at the edges (a torus), so gliders that fly off one side
come back in the other and the field never goes quiet.

Why it is not one animation per dot
-----------------------------------
GitHub renders SVG inside <img>, so there is no JavaScript. Instead each
generation is rendered once as a <g>, and every <g> shares a single keyframe
rule; a negative animation-delay slides each one's visibility window into its
own slot. One @keyframes drives the entire thing, which keeps both the file and
the browser's workload small.

That also gives reduced-motion support for free: pausing every animation leaves
each <g> stopped outside its window except the first, so the banner falls back
to a still "42" rather than a frozen mess.
"""

import random
import sys

# ---------------------------------------------------------------- CONFIG ----

COLS, ROWS = 80, 20             # grid in cells
CELL = 11                       # px per cell -> 880 x 220 canvas

HOLD_FRAMES = 6                 # generations spent holding the opening "42"
EVOLVE_FRAMES = 40              # generations of free-running Life
SETTLE_FRAMES = 10              # generations spent reassembling into "42"
FRAME_SECONDS = 0.35            # how long one generation stays on screen

NOISE_DENSITY = 0.30            # fraction of cells seeded when the grid ignites
SEED = 42                       # fixed, so the same file regenerates byte-identical

R_LIVE = 0.30                   # live-cell radius, in cell units
R_DEAD = 0.16                   # background-grid dot radius
OPACITY_DEAD = 0.13             # background grid: the LEDs that are switched off

DOT_DARK = "#7C6BF5"            # dot colour on dark backgrounds
DOT_LIGHT = "#4B3FD4"           # dot colour on light backgrounds

GLYPHS = [
    ["....###.",
     "...####.",
     "..##.##.",
     ".##..##.",
     "##...##.",
     "########",
     "########",
     ".....##.",
     ".....##.",
     ".....##.",
     ".....##."],
    [".######.",
     "##....##",
     "......##",
     ".....##.",
     "....##..",
     "...##...",
     "..##....",
     ".##.....",
     "##......",
     "########",
     "########"],
]
GLYPH_GAP = 3                   # cells between the 4 and the 2

# -------------------------------------------------------------- GENERATOR ---

WIDTH, HEIGHT = COLS * CELL, ROWS * CELL


def blank():
    return [[0] * COLS for _ in range(ROWS)]


def seed_grid():
    """The opening frame: '42' centred on the grid."""
    grid = blank()
    glyph_w = [len(g[0]) for g in GLYPHS]
    total_w = sum(glyph_w) + GLYPH_GAP * (len(GLYPHS) - 1)
    ox = (COLS - total_w) // 2
    oy = (ROWS - len(GLYPHS[0])) // 2
    for glyph in GLYPHS:
        for r, row in enumerate(glyph):
            for c, ch in enumerate(row):
                if ch == "#":
                    grid[oy + r][ox + c] = 1
        ox += len(glyph[0]) + GLYPH_GAP
    return grid


def step(grid):
    """One Life generation, with the grid wrapped into a torus."""
    out = blank()
    for y in range(ROWS):
        up, down = grid[(y - 1) % ROWS], grid[(y + 1) % ROWS]
        mid = grid[y]
        for x in range(COLS):
            left, right = (x - 1) % COLS, (x + 1) % COLS
            n = (up[left] + up[x] + up[right]
                 + mid[left] + mid[right]
                 + down[left] + down[x] + down[right])
            out[y][x] = 1 if (n == 3 or (n == 2 and mid[x])) else 0
    return out


def build_frames():
    rnd = random.Random(SEED)
    opening = seed_grid()

    frames = [opening] * HOLD_FRAMES

    # Act 2: ignite. The "42" stays lit and random cells rain in around it.
    grid = [row[:] for row in opening]
    for y in range(ROWS):
        for x in range(COLS):
            if rnd.random() < NOISE_DENSITY:
                grid[y][x] = 1
    frames.append(grid)
    for _ in range(EVOLVE_FRAMES):
        grid = step(grid)
        frames.append(grid)

    # Act 3: pull the survivors back into "42", a batch of cells at a time, so
    # the last frame is identical to the first and the loop closes seamlessly.
    current = [row[:] for row in grid]
    stray = [(y, x) for y in range(ROWS) for x in range(COLS)
             if current[y][x] != opening[y][x]]
    rnd.shuffle(stray)
    for k in range(SETTLE_FRAMES):
        lo = k * len(stray) // SETTLE_FRAMES
        hi = (k + 1) * len(stray) // SETTLE_FRAMES
        for (y, x) in stray[lo:hi]:
            current[y][x] = opening[y][x]
        frames.append([row[:] for row in current])

    assert frames[-1] == frames[0], "loop does not close"
    return frames[:-1]          # last frame == first, so drop it


def build():
    frames = build_frames()
    count = len(frames)
    duration = round(count * FRAME_SECONDS, 3)
    window = round(100 / count, 4)

    # The background grid: every LED, switched off. Drawn once.
    dead = "".join(
        f'<circle cx="{x}" cy="{y}"/>'
        for y in range(ROWS) for x in range(COLS)
    )

    # One <g> per generation, holding only the cells that are alive in it.
    live = []
    for i, grid in enumerate(frames):
        dots = "".join(
            f'<circle cx="{x}" cy="{y}"/>'
            for y in range(ROWS) for x in range(COLS) if grid[y][x]
        )
        live.append(f'<g class="f{i}">{dots}</g>')

    # A negative delay advances the animation, so the slot order runs backwards
    # unless the index is mirrored -- hence (count - i).
    #
    # The selector must also out-specify "#life g" below: the `animation`
    # shorthand there resets animation-delay, and a bare ".fN" would lose to it.
    delays = "".join(
        f"#life .f{i}{{animation-delay:"
        f"{round(-((count - i) % count) * FRAME_SECONDS, 3)}s}}"
        for i in range(count)
    )

    css = (
        f":root{{--dot:{DOT_DARK}}}"
        f"@media(prefers-color-scheme:light){{:root{{--dot:{DOT_LIGHT}}}}}"
        f"circle{{fill:var(--dot)}}"
        f"#grid{{opacity:{OPACITY_DEAD}}}"
        f"#grid circle{{r:{R_DEAD}}}"
        f"#life circle{{r:{R_LIVE}}}"
        # Every generation shares this one rule; the delay picks its slot.
        f"#life g{{visibility:hidden;animation:flip {duration}s step-end infinite}}"
        f"@keyframes flip{{0%{{visibility:visible}}{window:g}%{{visibility:hidden}}}}"
        f"{delays}"
        # Paused, every <g> sits outside its window except the first: a still "42".
        "@media(prefers-reduced-motion:reduce){#life g{animation-play-state:paused}}"
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        f'aria-label="A dot-matrix grid spelling 42, dissolving into Conway\'s '
        f'Game of Life and reassembling">'
        f"<style>{css}</style>"
        f'<g transform="translate({CELL / 2:g},{CELL / 2:g}) scale({CELL})">'
        f'<g id="grid">{dead}</g>'
        f'<g id="life">{"".join(live)}</g>'
        f"</g></svg>"
    )
    total_live = sum(sum(map(sum, f)) for f in frames)
    print(f"{count} frames, {duration}s loop, {total_live} live dots drawn, "
          f"{len(svg) / 1024:.1f} KB", file=sys.stderr)
    return svg


if __name__ == "__main__":
    sys.stdout.write(build() + "\n")
