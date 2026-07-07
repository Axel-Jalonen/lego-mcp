"""Minifigure-scale Aston Martin DBX (coupe-SUV) through the constraint engine.

8 studs wide (a minifig sits inside), ~16 long. Front is +y. Every placement is
validated by the engine, so this is a physically buildable model. Body in Aston
racing green, black greenhouse + wheels, gray grille/bumper.

Layers (z in plates, 1 brick = 3):
  z0        chassis floor plates
  z1..3     lower body course (sills, wheels, hood, tail) -- one brick tall
  z4..6     cabin course (doors + black window band); hood capped low with tiles
  z4        windshield & tailgate slopes (climb hood level -> cabin roof)
  z7        cabin roof (green plates + smooth tiles)
Front nose and tail get slopes; grille, lights and bumpers are surface detail.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.catalog import CATALOG  # noqa: E402
from lego_mcp.engine import Build, PlacementError  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402


def _depths(kind, width):
    """Catalog depths available for a given kind at a given footprint width,
    longest first (a 1xN part covers width 1; a WxN part covers width W)."""
    ds = [p.depth for p in CATALOG.values()
          if p.name.startswith(kind + "_") and p.width == width]
    return sorted(set(ds), reverse=True)


def fill_rect(b, kind, x0, x1, y0, y1, z, color):
    """Tile the solid rectangle x0..x1 (incl) by y0..y1 with kind bricks/plates.

    Lays columns running along +y, preferring 2-wide parts and dropping to
    1-wide for odd leftovers or lengths the catalog only offers 1-wide.
    """
    x = x0
    while x <= x1:
        width = 2 if x + 1 <= x1 else 1
        y = y0
        while y <= y1:
            remaining = y1 - y + 1
            n = next((s for s in _depths(kind, width) if s <= remaining), None)
            if n is not None:
                b.place(f"{kind}_{width}x{n}", x, y, z, 0, color)
            else:  # width>1 can't cover leftover; lay 1-wide parts side by side
                n = next(s for s in _depths(kind, 1) if s <= remaining)
                for xx in range(x, x + width):
                    b.place(f"{kind}_1x{n}", xx, y, z, 0, color)
            y += n
        x += width


def build():
    # Footprint x=1..8 (8 wide), y=1..16 (front is +y). Sporty coupe-SUV stance:
    # a 3-course-tall cabin/tail body, a lower 2-course hood, greenhouse on top.
    #   tail y=1..3   cabin y=4..10   hood y=11..16 (nose slopes y=14..16)
    b = Build(name="dbx", width=10, depth=18)

    GREEN = "green"        # Aston Martin racing green
    GLASS = "black"        # greenhouse / windows
    TIRE = "black"
    GRILLE = "dark_gray"
    LIGHT = "white"
    TAIL = "dark_red"

    # Wheels: 1-wide black columns at the outer edges, rear axle y2..3, front
    # y12..13, two bricks tall so the tires read on the flanks.
    wheels = [(1, 2), (8, 2), (1, 12), (8, 12)]

    def body_course(z, y_hi):
        """One green brick course over the body, y=1..y_hi, skipping wheels."""
        fill_rect(b, "brick", 2, 7, 1, y_hi, z, GREEN)          # inner columns
        for x in (1, 8):                                        # outer, gap wheels
            fill_rect(b, "brick", x, x, 1, 1, z, GREEN)
            fill_rect(b, "brick", x, x, 4, 11, z, GREEN)
            if y_hi >= 14:
                fill_rect(b, "brick", x, x, 14, y_hi, z, GREEN)

    # ---- z0: chassis floor ------------------------------------------------
    fill_rect(b, "plate", 1, 8, 1, 16, 0, "dark_gray")

    # ---- courses A & B, z1..6: lower body + tall tires --------------------
    # Course A runs the full length (solid base under the nose); course B stops
    # at y=13 so the nose slopes can take y=14..16.
    for z, y_hi in ((1, 16), (4, 13)):
        for wx, wy in wheels:
            b.place("brick_1x2", wx, wy, z, 0, TIRE)
        body_course(z, y_hi)

    # ---- course C, z7..9: raise cabin + tail only (hood stays low) ---------
    fill_rect(b, "brick", 1, 8, 1, 10, 7, GREEN)

    # ---- hood: nose slopes + smooth bonnet cap ----------------------------
    # Nose 33-deg slopes over course B (z4..6), descending toward the front.
    for x in (1, 3, 5, 7):
        b.place("slope_2x3", x, 14, 4, 0, GREEN)      # tall row y14 -> low at y16
    fill_rect(b, "tile", 1, 8, 11, 13, 7, GREEN)      # flat bonnet, top of hood
    # Cowl step: the y=11 face of course C is the vertical wall up to the screen.

    # ---- greenhouse, z10..12: black glass on the cabin body ---------------
    for x in (1, 3, 5, 7):
        b.place("slope_2x3", x, 8, 10, 0, GLASS)      # windshield: tall y8, low y10
        b.place("slope_2x3", x, 4, 10, 180, GLASS)    # backlight: tall y6, low y4
    for x in (1, 8):
        b.place("brick_1x1", x, 7, 10, 0, GLASS)      # side glass pillar
    fill_rect(b, "brick", 2, 7, 7, 7, 10, GLASS)      # side-glass row interior

    # ---- roof, z13..14: green plates + smooth tiles -----------------------
    fill_rect(b, "plate", 1, 8, 6, 8, 13, GREEN)
    fill_rect(b, "tile", 2, 7, 6, 8, 14, GREEN)

    # ---- surface detail (stud-up only in this brick world) ----------------
    # Nose: dark grille lip across the tall slope row, headlights flanking it.
    b.place("plate_1x6", 2, 14, 7, 90, GRILLE)        # grille lip, x2..7
    b.place("plate_1x1", 1, 14, 7, 0, LIGHT)          # headlights
    b.place("plate_1x1", 8, 14, 7, 0, LIGHT)
    # Tail (y1..3, top at z10): red tail-light bar + smooth trunk tiles.
    b.place("plate_1x6", 2, 2, 10, 90, TAIL)          # tail-light bar, x2..7
    b.place("plate_1x1", 1, 2, 10, 0, TAIL)
    b.place("plate_1x1", 8, 2, 10, 0, TAIL)
    fill_rect(b, "tile", 1, 8, 1, 1, 10, GREEN)       # rear deck tiles
    fill_rect(b, "tile", 1, 8, 3, 3, 10, GREEN)

    return b


def main():
    b = build()
    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall, "
          f"footprint {s['baseplate']}.")

    out = Path(__file__).resolve().parent.parent / "builds"
    out.mkdir(exist_ok=True)
    (out / "dbx.json").write_text(b.to_json())
    (out / "dbx.ldr").write_text(to_ldraw(b))
    (out / "dbx_blender.py").write_text(to_blender_script(b))
    print(f"Exported dbx.{{json,ldr}} and dbx_blender.py to {out}")


if __name__ == "__main__":
    main()
