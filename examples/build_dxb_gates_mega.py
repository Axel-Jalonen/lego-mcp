"""Two gates of DXB Terminal 3 — MEGA scale, ~100k pieces.

A 320x320-stud slice of the Concourse at roughly 5x the minifig-scale build:
the parabolic ribbed vault spans 216 studs (crown ~75 bricks), the apron wall
is a banded curtain wall with two 20-stud arched boarding portals under a red
signage band, each gate has desks, seating banks, FIDS totems, queue lines and
a giant "A1"/"A2" floor label, jet-bridge tubes run out to two brick-built
widebody fuselages parked on marked stands. Floors and tarmac are laid as
individual 1x1 tiles (that is where most of the piece count lives — maximum
"resolution"). Every placement is validated by the engine; z starts at 0
(no baseplate part is big enough, the ground itself is the baseplate).
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.catalog import CATALOG  # noqa: E402
from lego_mcp.engine import Build  # noqa: E402
from lego_mcp.export import to_ldraw  # noqa: E402

WARNINGS: list[str] = []


def _depths(kind, width):
    ds = [p.depth for p in CATALOG.values()
          if p.name.startswith(kind + "_") and p.width == width]
    return sorted(set(ds), reverse=True)


def _put(b, part, x, y, z, rot, color):
    _, warns = b.place(part, x, y, z, rot, color)
    WARNINGS.extend(warns)


def row(b, kind, x0, x1, y, z, color):
    """1xN pieces laid along x, greedy from the left."""
    x = x0
    while x <= x1:
        n = next(s for s in _depths(kind, 1) if s <= x1 - x + 1)
        _put(b, f"{kind}_1x{n}", x, y, z, 90, color)
        x += n


def lintel_row(b, kind, x0, x1, y, z, color):
    """Row whose BOTH ends may overhang the course below by <=6 studs:
    anchor a 1x8 at each end, fill the middle greedily."""
    length = x1 - x0 + 1
    if length <= 8:
        row(b, kind, x0, x1, y, z, color)
        return
    _put(b, f"{kind}_1x8", x0, y, z, 90, color)
    _put(b, f"{kind}_1x8", x1 - 7, y, z, 90, color)
    if x0 + 8 <= x1 - 8:
        row(b, kind, x0 + 8, x1 - 8, y, z, color)


def _pick2(kind, rem):
    """Largest 2-wide length <= rem that doesn't strand a 1-stud remainder."""
    return next(s for s in _depths(kind, 2)
                if s <= rem and rem - s != 1)


def col2(b, kind, x, y0, y1, z, color):
    """2-wide (x) pieces laid along y."""
    y = y0
    while y <= y1:
        n = _pick2(kind, y1 - y + 1)
        _put(b, f"{kind}_2x{n}", x, y, z, 0, color)
        y += n


def strip2(b, kind, x0, x1, y, z, color):
    """2-deep (y) pieces laid along x (rot 90)."""
    x = x0
    while x <= x1:
        n = _pick2(kind, x1 - x + 1)
        _put(b, f"{kind}_2x{n}", x, y, z, 90, color)
        x += n


def tile_fill(b, x0, x1, y0, y1, colorfn, maxlen=1):
    """Tile free ground cells with 1x1s (or short runs of one color)."""
    for y in range(y0, y1 + 1):
        x = x0
        while x <= x1:
            if (x, y, 0) in b._occ:
                x += 1
                continue
            c = colorfn(x, y)
            n = 1
            while (n < maxlen and n < 6 and x + n <= x1
                   and (x + n, y, 0) not in b._occ
                   and colorfn(x + n, y) == c):
                n += 1
            n = next(s for s in (6, 4, 2, 1) if s <= n)
            _put(b, f"tile_1x{n}", x, y, 0, 90, c)
            x += n


# --- geometry (studs / bricks / plates) --------------------------------------
S = 216                # vault span in x
H = 72                 # crown parabola parameter (bricks)
DEEP = 150             # concourse depth in y
T = 4                  # vault shell thickness
XO, YO = 52, 40        # shell offset
CX = XO + S // 2       # 160
WALL_Y = YO + DEEP     # 190: apron curtain wall
DOORS = [(114, 133), (186, 205)]   # two 20-stud boarding portals
DOOR_SPRING = 26       # courses before the door arch starts closing
WALL_TOP = 42          # curtain wall height in courses
BRIDGES = [(116, 131), (188, 203)]  # outer x extents (2-thick walls)
PLANES = [(92, 155), (164, 227)]    # fuselage x extents, 64 long
PLANE_CY = 300                      # fuselage centre pair (y=300,301)

SKIN, RIB = "white", "light_gray"
GLASS, BAND, SIGN = "dark_blue", "light_gray", "red"
FLOOR, WALK, TARMAC = "tan", "dark_gray", "dark_gray"
DESK, SEAT = "dark_red", "dark_blue"

# 5x7 pixel font for the floor labels
FONT = {
    "A": [" XXX ", "X   X", "X   X", "XXXXX", "X   X", "X   X", "X   X"],
    "1": ["  X  ", " XX  ", "  X  ", "  X  ", "  X  ", "  X  ", " XXX "],
    "2": [" XXX ", "X   X", "   X ", "  X  ", " X   ", "X    ", "XXXXX"],
}


def vault(b):
    prev_l = prev_r = None
    for k in range(H + 24):
        z = 3 * k
        f = min(1.0, (k + 0.5) / H)
        half = (S / 2) * math.sqrt(max(0.0, 1 - f))
        xl = max(XO, round(CX - half))
        xr = min(XO + S - 1, round(CX + half))
        if prev_l is not None:
            xl = max(prev_l, min(xl, prev_l + 2))
            xr = min(prev_r, max(xr, prev_r - 2))
        lo_l, hi_l, lo_r, hi_r = xl, xl + T - 1, xr - T + 1, xr
        gap = lo_r - hi_l - 1

        def ribbed(x0, x1, zz):
            for y in range(YO, YO + DEEP):
                c = RIB if (y - YO) % 10 in (0, 1) else SKIN
                row(b, "brick", x0, x1, y, zz, c)

        if gap <= 0:
            ribbed(lo_l, hi_r, z)
            return z
        if gap <= 4:
            ribbed(lo_l, hi_l, z)
            ribbed(lo_r, hi_r, z)
            ribbed(lo_l, hi_r, z + 3)      # cap row across both flanks
            ribbed(hi_l + 1, lo_r - 1, z)  # slit hung under the cap
            return z + 3
        ribbed(lo_l, hi_l, z)
        ribbed(lo_r, hi_r, z)
        prev_l, prev_r = xl, xr
    return 3 * (H - 1)


def curtain_wall(b):
    """Banded glass wall with two arched boarding portals + red sign band."""
    gaps = {i: list(d) for i, d in enumerate(DOORS)}
    for k in range(WALL_TOP):
        z = 3 * k
        if k >= DOOR_SPRING:               # arch: close each gap 2/side/course
            for g in gaps.values():
                if g[1] - g[0] >= 0:
                    g[0] += 2
                    g[1] -= 2
        if 32 <= k <= 34:
            color = SIGN
        elif k % 6 == 5:
            color = BAND
        else:
            color = GLASS
        spans, x = [], XO
        openings = sorted(g for g in gaps.values() if g[1] - g[0] >= 0)
        for g in openings:
            spans.append((x, g[0] - 1))
            x = g[1] + 1
        spans.append((x, XO + S - 1))
        for x0, x1 in spans:
            if x1 >= x0:
                lintel_row(b, "brick", x0, x1, WALL_Y, z, color)


def jet_bridges(b):
    for wl, wr in BRIDGES:
        for k in range(16):
            z = 3 * k
            c = GLASS if k in (6, 7, 8, 9) else RIB
            col2(b, "brick", wl, WALL_Y + 1, WALL_Y + 96, z, c)
            col2(b, "brick", wr - 1, WALL_Y + 1, WALL_Y + 96, z, c)
        for yy in range(WALL_Y + 1, WALL_Y + 96, 8):
            _put(b, "plate_8x8", wl, yy, 48, 0, RIB)
            _put(b, "plate_8x8", wl + 8, yy, 48, 0, RIB)


def planes(b):
    widths = list(range(2, 23, 2)) + [22, 22, 22] + list(range(20, 1, -2))
    for x0, x1 in PLANES:
        for px in range(x0, x1 - 6, 8):            # landing-gear pillars
            for k in range(16):
                _put(b, "brick_2x8", px, PLANE_CY, 3 * k, 90, "dark_gray")
        prev_w = 0
        for i, w in enumerate(widths):             # solid corbelled fuselage
            z = 48 + 3 * i
            ylo, yhi = PLANE_CY + 1 - w // 2, PLANE_CY + w // 2
            def color(yy):
                if i in (12, 13) and yy in (ylo, yhi):
                    return "black"                  # window band
                return "light_gray" if i < 3 else "white"
            if w > prev_w and w > 2:               # widening: straddle strips
                strip2(b, "brick", x0, x1, ylo, z, color(ylo))
                strip2(b, "brick", x0, x1, yhi - 1, z, color(yhi))
                inner = range(ylo + 2, yhi - 1)
            elif w == 2:
                strip2(b, "brick", x0, x1, ylo, z, color(ylo))
                inner = range(0)
            else:
                inner = range(ylo, yhi + 1)
            for yy in inner:
                row(b, "brick", x0, x1, yy, z, color(yy))
            prev_w = w
        top = 48 + 3 * len(widths)
        for j in range(14):                        # red tail fin
            xs = min(x1 - 1, x1 - 7 + (j * 7) // 13)
            strip2(b, "brick", xs, x1, PLANE_CY, top + 3 * j, SIGN)


def furniture(b):
    for x0 in (94, 166):                           # gate desks 16x4, 5 bricks
        for k in range(5):
            for xx in (x0, x0 + 8):
                for yy in (174, 176):
                    _put(b, "brick_2x8", xx, yy, 3 * k, 90, DESK)
        for xx in range(x0, x0 + 16, 4):
            for yy in (174, 176):
                _put(b, "tile_2x4", xx, yy, 15, 90, FLOOR)
        for yy in (164, 168):                      # red queue lines
            for xx in range(x0, x0 + 16):
                _put(b, "tile_1x1", xx, yy, 0, 0, SIGN)

    for x0 in (138, 210):                          # FIDS totems + screens
        for k in range(10):
            _put(b, "brick_2x4", x0, 174, 3 * k, 90, "black")
        for z in (30, 33):
            _put(b, "brick_2x8", x0 - 2, 174, z, 90, "black")
        for xx in (x0 - 2, x0 + 2):
            _put(b, "tile_2x4", xx, 174, 36, 90, "black")

    for x0 in (90, 182):                           # seating: 3 double benches
        for y0 in (128, 140, 152):
            for yy in (y0, y0 + 4):                # seat slabs, 2 bricks
                for k in range(2):
                    strip2(b, "brick", x0, x0 + 47, yy, 3 * k, SEAT)
            for k in range(5):                     # centre backrest, 5 bricks
                strip2(b, "brick", x0, x0 + 47, y0 + 2, 3 * k, "dark_gray")

    for label, lx in (("A1", 106), ("A2", 178)):   # giant floor labels
        for gi, ch in enumerate(label):
            for r, rowtxt in enumerate(FONT[ch]):
                for c, px in enumerate(rowtxt):
                    if px != "X":
                        continue
                    for dx in range(3):
                        for dy in range(3):
                            _put(b, "tile_1x1", lx + gi * 21 + c * 3 + dx,
                                 100 + (6 - r) * 3 + dy, 0, 0, "black")


def interior_color(x, y):
    if 84 <= y <= 96:
        return WALK
    if x < 58 or x > 261:
        return "white"
    if (x - 56) % 24 in (0, 1):
        return "light_gray"
    return FLOOR


def tarmac_color(x, y):
    if x in (123, 124, 195, 196) and y >= 287:
        return "yellow"                             # stand lead-in lines
    for bx0, bx1 in ((88, 157), (162, 231)):        # stand boundary boxes
        if bx0 <= x <= bx1 and y in (284, 316):
            return "white"
        if x in (bx0, bx1) and 284 <= y <= 316:
            return "white"
    if y == 192:
        return "white"                              # apron edge line
    return TARMAC


def build():
    t0 = time.time()
    b = Build(name="dxb_gates_mega", width=320, depth=320)
    crown = vault(b)
    print(f"vault done: {len(b.pieces)} pcs, crown z={crown} "
          f"({crown / 3:.0f} bricks) [{time.time() - t0:.0f}s]")
    curtain_wall(b)
    jet_bridges(b)
    planes(b)
    furniture(b)
    print(f"structures done: {len(b.pieces)} pcs [{time.time() - t0:.0f}s]")

    tile_fill(b, XO, XO + S - 1, 0, YO - 1, interior_color)      # front hall
    tile_fill(b, XO + T, XO + S - 1 - T, YO, YO + DEEP - 1, interior_color)
    for wl, wr in BRIDGES:                                       # bridge floors
        tile_fill(b, wl + 2, wr - 2, WALL_Y + 1, WALL_Y + 96, lambda x, y: FLOOR,
                  maxlen=2)
    tile_fill(b, 0, 319, WALL_Y + 1, 319, tarmac_color)          # tarmac
    print(f"floors done: {len(b.pieces)} pcs [{time.time() - t0:.0f}s]")
    return b, crown


def main():
    b, crown = build()
    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall.")
    print(f"{len(WARNINGS)} advisory warnings.")
    out = Path(__file__).resolve().parent.parent / "builds"
    (out / "dxb_gates_mega.json").write_text(b.to_json())
    (out / "dxb_gates_mega.ldr").write_text(to_ldraw(b))
    print(f"Exported dxb_gates_mega.json/.ldr to {out}")


if __name__ == "__main__":
    main()
