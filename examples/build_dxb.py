"""Minifigure-scale DXB (Dubai International) departures entrance -- one bay of
the Terminal 3 concourse, sized so a minifig can actually walk through it.

A full terminal at true minifig scale would be metres of baseplate, so this is a
"set-sized" section (like a LEGO City / modular building): a double-height glazed
hall ~10 bricks tall, 5-brick-tall entrance doors (a minifig is ~4 bricks), and a
big cantilevered departures canopy. Every placement is validated by the engine.

Front faces -y (the plaza / drop-off side). Building spans x=4..27, y=12..19.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.catalog import CATALOG  # noqa: E402
from lego_mcp.engine import Build  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402


def _depths(kind, width):
    ds = [p.depth for p in CATALOG.values()
          if p.name.startswith(kind + "_") and p.width == width]
    return sorted(set(ds), reverse=True)


def fill_rect(b, kind, x0, x1, y0, y1, z, color):
    """Tile solid rect x0..x1 by y0..y1 (2-wide cols, 1-wide leftovers)."""
    x = x0
    while x <= x1:
        width = 2 if x + 1 <= x1 else 1
        y = y0
        while y <= y1:
            remaining = y1 - y + 1
            n = next((s for s in _depths(kind, width) if s <= remaining), None)
            if n is not None:
                b.place(f"{kind}_{width}x{n}", x, y, z, 0, color)
            else:
                n = next(s for s in _depths(kind, 1) if s <= remaining)
                for xx in range(x, x + width):
                    b.place(f"{kind}_1x{n}", xx, y, z, 0, color)
            y += n
        x += width


def row(b, kind, x0, x1, y, z, color):
    """Tile a 1-deep row along +x at fixed y (parts rotated 90)."""
    x = x0
    while x <= x1:
        n = next(s for s in _depths(kind, 1) if s <= x1 - x + 1)
        b.place(f"{kind}_1x{n}", x, y, z, 90, color)
        x += n


# Wall courses (brick = 3 plates). 10 courses -> eave at z=31 (~10 bricks tall).
Z = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28]
DOOR_TOP = 16   # first course above the door opening (the lintel course)


def build():
    b = Build(name="dxb", width=32, depth=32)

    SAND = "tan"
    GLASS = "dark_blue"     # tinted curtain-wall glazing
    STRUCT = "light_gray"   # mullions / piers / structure
    ROOF = "white"
    ROAD = "dark_gray"
    TRUNK = "brown"
    FROND = "green"

    X0, X1 = 4, 27          # building width (24 studs)
    YF, YB = 12, 19         # front / back walls (8 deep hall)
    MULL = [4, 8, 12, 17, 21, 25, 27]                     # mullion columns
    SEG = [(4, 8), (8, 12), (12, 17), (17, 21),
           (21, 25), (25, 27)]                            # glass bays
    DOOR = (12, 17)         # central bay x13..16 is the doorway

    # ---- z0: sand baseplate + drop-off road ------------------------------
    b.place("baseplate_32x32", 0, 0, 0, 0, SAND)
    fill_rect(b, "tile", 1, 30, 2, 4, 1, ROAD)            # kerbside road strip

    # ---- front curtain wall, per course ----------------------------------
    def front_course(z):
        phase = "door" if z < DOOR_TOP else ("lintel" if z == DOOR_TOP else "glass")
        for m in MULL:
            if phase == "lintel" and m in DOOR:
                continue                                  # jambs become lintel
            b.place("brick_1x1", m, YF, z, 0, STRUCT)
        for a, c in SEG:
            if c - a < 2:
                continue
            if (a, c) == DOOR:
                if phase == "door":
                    continue                              # leave the opening
                if phase == "lintel":
                    b.place("brick_1x6", a, YF, z, 90, STRUCT)   # spans x12..17
                    continue
            row(b, "brick", a + 1, c - 1, YF, z, GLASS)

    for z in Z:
        front_course(z)

    # ---- side + back walls (structural gray) -----------------------------
    for z in Z:
        row(b, "brick", X0, X1, YB, z, STRUCT)            # back wall
        for x in (X0, X1):
            fill_rect(b, "brick", x, x, YF + 1, YB - 1, z, STRUCT)  # sides

    # ---- roof: white deck spanning the 8-deep hall + smooth cap ----------
    fill_rect(b, "plate", X0, X1, YF, YB, 31, ROOF)
    fill_rect(b, "tile", X0, X1, YF, YB, 32, ROOF)

    # ---- departures canopy on four columns over the entrance -------------
    for cx in (13, 16):
        for cy in (5, 10):
            for z in [1, 4, 7, 10, 13, 16, 19]:
                b.place("brick_1x1", cx, cy, z, 0, STRUCT)
    b.place("plate_8x8", 11, 4, 22, 0, ROOF)             # 8x8 canopy slab

    # ---- two palms flanking the entrance ---------------------------------
    for px in (7, 24):
        for z in [1, 4, 7]:
            b.place("brick_1x1", px, 7, z, 0, TRUNK)      # trunk (~3 bricks)
        b.place("plate_2x2", px - 1, 6, 10, 0, FROND)     # fronds
        b.place("plate_1x2", px - 1, 7, 11, 90, FROND)

    return b


def main():
    b = build()
    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall, "
          f"footprint {s['baseplate']}.")

    out = Path(__file__).resolve().parent.parent / "builds"
    out.mkdir(exist_ok=True)
    (out / "dxb.json").write_text(b.to_json())
    (out / "dxb.ldr").write_text(to_ldraw(b))
    (out / "dxb_blender.py").write_text(to_blender_script(b))
    print(f"Exported dxb.{{json,ldr}} and dxb_blender.py to {out}")


if __name__ == "__main__":
    main()
