#!/usr/bin/env python3
"""
Generate an animated dot-matrix interference-wave banner as a single SVG file.

No dependencies beyond the Python standard library.

    python3 generate_wave.py > assets/wave.svg

Everything you would want to tweak lives in the CONFIG block below.

How it works
------------
GitHub renders SVG inside <img>, which means no JavaScript. So every dot's
motion is baked into CSS keyframes at generation time. Three wave sources with
co-prime periods (7s / 11s / 13s) drive three separate animations; their
opacities multiply, so the visible pattern only truly repeats after
lcm(7, 11, 13) = 1001 seconds. Nobody watches a profile README for 17 minutes.

Phases are quantised into PHASE_BUCKETS steps so that a few dozen CSS rules
cover ~1900 dots instead of inlining a delay on every one.
"""

import math
import sys

# ---------------------------------------------------------------- CONFIG ----

WIDTH, HEIGHT = 880, 220        # canvas size in px
SPACING = 10                    # distance between dots
MARGIN = 5                      # inset from the edges

R_MIN, R_MAX = 0.70, 3.20       # dot radius at wave trough / crest
OPACITY_MIN = 0.50              # per-layer opacity floor (three layers multiply)

DOT_DARK = "#7C6BF5"            # dot colour on dark backgrounds
DOT_LIGHT = "#4B3FD4"           # dot colour on light backgrounds

# Three wave sources: (x, y, period_seconds, wavelength_px).
# Sources may sit outside the canvas — that just flattens their curvature.
SOURCES = [
    (110.0, 100.0, 7.0, 74.0),
    (770.0, 55.0, 11.0, 98.0),
    (450.0, 320.0, 13.0, 132.0),
]

PHASE_BUCKETS = 24              # phase quantisation; higher = smoother, bigger file
KEYFRAME_STEPS = 12             # samples per sine cycle in the CSS keyframes

# -------------------------------------------------------------- GENERATOR ---

B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def b36(n: int) -> str:
    """Short class-name suffix, keeps the markup compact."""
    return B36[n] if n < 36 else B36[n // 36] + B36[n % 36]


def phase_bucket(px: float, py: float, src) -> int:
    """Which quantised phase of `src` the dot at (px, py) sits on."""
    sx, sy, _period, wavelength = src
    dist = math.hypot(px - sx, py - sy)
    return int(round(dist / wavelength * PHASE_BUCKETS)) % PHASE_BUCKETS


def sine01(step: int) -> float:
    """Sine mapped to 0..1, sampled at `step`/KEYFRAME_STEPS of a cycle."""
    return (math.sin(2 * math.pi * step / KEYFRAME_STEPS) + 1) / 2


def keyframes(name: str, prop: str, lo: float, hi: float, digits: int) -> str:
    out = [f"@keyframes {name}{{"]
    for step in range(KEYFRAME_STEPS + 1):
        pct = round(step / KEYFRAME_STEPS * 100, 2)
        val = round(lo + (hi - lo) * sine01(step % KEYFRAME_STEPS), digits)
        out.append(f"{pct:g}%{{{prop}:{val}}}")
    out.append("}")
    return "".join(out)


def delay_rules(prefix: str, anim_index: int, anim_count: int, period: float) -> str:
    """
    One rule per phase bucket. Negative delays start the animation mid-cycle,
    which is also what makes the reduced-motion freeze-frame look like a real
    interference pattern rather than a flat grid.
    """
    rules = []
    for bucket in range(PHASE_BUCKETS):
        delay = -round(bucket / PHASE_BUCKETS * period, 3)
        slots = ["0s"] * anim_count
        slots[anim_index] = f"{delay}s"
        rules.append(f".{prefix}{b36(bucket)}{{animation-delay:{','.join(slots)}}}")
    return "".join(rules)


def build() -> str:
    src_r, src_a, src_b = SOURCES
    period_r, period_a, period_b = src_r[2], src_a[2], src_b[2]

    # Dots are grouped by their outer-layer (wave B) phase, so 24 <g> elements
    # carry the whole grid instead of one wrapper per dot.
    groups = {bucket: [] for bucket in range(PHASE_BUCKETS)}

    y = MARGIN
    while y <= HEIGHT - MARGIN:
        x = MARGIN
        while x <= WIDTH - MARGIN:
            outer = phase_bucket(x, y, src_b)
            br = phase_bucket(x, y, src_r)
            ba = phase_bucket(x, y, src_a)
            groups[outer].append(
                f'<circle class="r{b36(br)} a{b36(ba)}" cx="{x:g}" cy="{y:g}"/>'
            )
            x += SPACING
        y += SPACING

    total = sum(len(v) for v in groups.values())

    css = [
        f":root{{--dot:{DOT_DARK}}}",
        f"@media(prefers-color-scheme:light){{:root{{--dot:{DOT_LIGHT}}}}}",
        # Two animations per circle: radius (wave R) and opacity (wave A).
        # The enclosing <g> supplies the third, multiplying opacity (wave B).
        "circle{fill:var(--dot);"
        f"r:{round((R_MIN + R_MAX) / 2, 2)};"
        f"animation:swell {period_r}s linear infinite,pulse {period_a}s linear infinite}}",
        f"g{{animation:drift {period_b}s linear infinite}}",
        keyframes("swell", "r", R_MIN, R_MAX, 2),
        keyframes("pulse", "opacity", OPACITY_MIN, 1.0, 3),
        keyframes("drift", "opacity", OPACITY_MIN, 1.0, 3),
        delay_rules("r", 0, 2, period_r),
        delay_rules("a", 1, 2, period_a),
        delay_rules("g", 0, 1, period_b),
        # Vestibular safety: freeze every layer on its own phase. Because the
        # delays are negative, the frozen frame *is* the interference pattern.
        "@media(prefers-reduced-motion:reduce){*{animation-play-state:paused!important}}",
    ]

    body = "".join(
        f'<g class="g{b36(bucket)}">{"".join(dots)}</g>'
        for bucket, dots in groups.items()
        if dots
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        f'aria-label="An animated field of dots rippling with interference waves">'
        f"<style>{''.join(css)}</style>{body}</svg>"
    )
    print(f"{total} dots, {len(svg) / 1024:.1f} KB", file=sys.stderr)
    return svg


if __name__ == "__main__":
    sys.stdout.write(build() + "\n")
