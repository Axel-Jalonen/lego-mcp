"""Two gates of DXB Terminal 3, one concourse section at minifig scale.

Scale ~1:48 (1 stud ~= 0.38 m, 1 brick ~= 0.46 m). One slice of the Concourse
shell: the parabolic ribbed vault (span 36 studs, crown ~16 bricks ~= 7.4 m),
the apron-side glass wall with TWO boarding gates (4-stud doors, 6 bricks
tall, red signage band), gate desks, seating banks, queue stanchions, FIDS
totems, and two jet-bridge corridors running out over the tarmac. The front
end of the vault is open so you can look straight down the concourse.
Every placement validated by the engine.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.catalog import CATALOG  # noqa: E402
from lego_mcp.engine import Build  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402

WARNINGS: list[str] = []


def _depths(kind, width):
    ds = [p.depth for p in CATALOG.values()
          if p.name.startswith(kind + "_") and p.width == width]
    return sorted(set(ds), reverse=True)


def _put(b, part, x, y, z, rot, color):
    _, warns = b.place(part, x, y, z, rot, color)
    WARNINGS.extend(warns)


def row(b, kind, x0, x1, y, z, color):
    """1xN pieces laid along x."""
    x = x0
    while x <= x1:
        n = next(s for s in _depths(kind, 1) if s <= x1 - x + 1)
        _put(b, f"{kind}_1x{n}", x, y, z, 90, color)
        x += n


def col(b, kind, x, y0, y1, z, color):
    """1xN pieces laid along y."""
    y = y0
    while y <= y1:
        n = next(s for s in _depths(kind, 1) if s <= y1 - y + 1)
        _put(b, f"{kind}_1x{n}", x, y, z, 0, color)
        y += n


def tile_runs(b, x0, x1, y0, y1, color):
    """Tile the free cells of a rect at z=1, skipping anything already placed."""
    sizes = [s for s in _depths("tile", 1)]
    for y in range(y0, y1 + 1):
        x = x0
        while x <= x1:
            if (x, y, 1) in b._occ:
                x += 1
                continue
            run = 0
            while x + run <= x1 and (x + run, y, 1) not in b._occ:
                run += 1
            cx = x
            while run > 0:
                n = next(s for s in sizes if s <= run)
                _put(b, f"tile_1x{n}", cx, y, 1, 90, color)
                cx += n
                run -= n
            x = cx


# --- geometry (studs / bricks / plates) --------------------------------------
S = 36        # vault span in x (studs)      ~13.7 m
H = 16        # crown target height (bricks) ~7.4 m
D = 24        # concourse depth in y (studs) ~9 m
T = 3         # vault shell thickness (studs)
XO, YO = 4, 6                 # shell offset on the baseplate
CX = XO + S / 2               # vault centre x
WALL_Y = YO + D               # apron-side glass wall
DOORS = [(12, 15), (28, 31)]  # two boarding doors, 4 studs wide

SKIN = "white"
RIB = "light_gray"
GLASS = "dark_blue"
SIGN = "red"
FLOOR = "tan"
WALK = "dark_gray"
TARMAC = "dark_gray"
DESK = "dark_red"
SEAT = "dark_blue"
BRIDGE = "light_gray"


def build():
    b = Build(name="dxb_gates", width=48, depth=48)
    b.place("baseplate_48x48", 0, 0, 0, 0, "tan")

    # ---- the parabolic ribbed vault (corbelled, open at both x ends) ------
    prev_l = prev_r = None
    crown_z = 1 + 3 * (H - 1)
    for k in range(H + 8):
        z = 1 + 3 * k
        f = min(1.0, (k + 0.5) / H)
        half = (S / 2) * math.sqrt(max(0.0, 1 - f))
        xl = max(XO, round(CX - half))
        xr = min(XO + S - 1, round(CX + half))
        if prev_l is not None:                 # corbel: step inward <= 2
            xl = max(prev_l, min(xl, prev_l + 2))
            xr = min(prev_r, max(xr, prev_r - 2))
        lo_l, hi_l, lo_r, hi_r = xl, xl + T - 1, xr - T + 1, xr
        gap = lo_r - hi_l - 1

        def ribbed(x0, x1, zz):
            for y in range(YO, YO + D):
                c = RIB if (y - YO) % 3 == 0 else SKIN
                row(b, "brick", x0, x1, y, zz, c)

        if gap <= 0:                           # flanks meet -> solid keystone
            ribbed(lo_l, hi_r, z)
            crown_z = z
            break
        if gap <= 4:                           # cap the last small gap:
            ribbed(lo_l, hi_l, z)              # flanks,
            ribbed(lo_r, hi_r, z)
            ribbed(lo_l, hi_r, z + 3)          # cap row across both flanks,
            ribbed(hi_l + 1, lo_r - 1, z)      # slit hung under the cap.
            crown_z = z + 3
            break
        ribbed(lo_l, hi_l, z)
        ribbed(lo_r, hi_r, z)
        prev_l, prev_r = xl, xr

    # ---- apron-side glass wall with the two boarding doors ----------------
    (d1l, d1r), (d2l, d2r) = DOORS
    for k in range(8):
        z = 1 + 3 * k
        if k < 6:                              # door openings, 6 bricks tall
            row(b, "brick", XO, d1l - 1, WALL_Y, z, GLASS)
            row(b, "brick", d1r + 1, d2l - 1, WALL_Y, z, GLASS)
            row(b, "brick", d2r + 1, XO + S - 1, WALL_Y, z, GLASS)
        elif k == 6:                           # red signage band over the doors
            row(b, "brick", XO, XO + S - 1, WALL_Y, z, SIGN)
        else:
            row(b, "brick", XO, XO + S - 1, WALL_Y, z, SKIN)

    # ---- two jet-bridge corridors out to the tarmac -----------------------
    for wl in (DOORS[0][0] - 1, DOORS[1][0] - 1):   # left wall x of each bridge
        wr = wl + 5                                 # right wall x
        for k in range(5):                          # 5 bricks tall
            z = 1 + 3 * k
            c = GLASS if k in (2, 3) else BRIDGE    # glazing band
            col(b, "brick", wl, YO + D + 1, YO + D + 14, z, c)
            col(b, "brick", wr, YO + D + 1, YO + D + 14, z, c)
        _put(b, "plate_6x8", wl, YO + D + 1, 16, 0, BRIDGE)   # roof
        _put(b, "plate_6x6", wl, YO + D + 9, 16, 0, BRIDGE)

    # ---- gate furniture (placed before floor tiles) ------------------------
    for x0 in (8, 24):                         # gate desks, counter height
        _put(b, "brick_2x4", x0, 26, 1, 90, DESK)
        _put(b, "brick_2x4", x0, 26, 4, 90, DESK)
        _put(b, "tile_2x4", x0, 26, 7, 90, FLOOR)

    for x0 in (8, 26):                         # seating banks, two rows each
        for yb, ys in ((14, 15), (18, 19)):
            _put(b, "brick_1x8", x0, yb, 1, 90, SEAT)   # backrest
            _put(b, "plate_1x8", x0, yb, 4, 90, SEAT)
            _put(b, "brick_1x8", x0, ys, 1, 90, SEAT)   # seat

    for x0 in (17, 32):                        # FIDS screen totems
        for z in (1, 4, 7):
            _put(b, "brick_1x2", x0, 26, z, 90, "black")
        _put(b, "brick_1x4", x0 - 1, 26, 10, 90, "black")
        _put(b, "tile_1x4", x0 - 1, 26, 13, 90, "black")

    for x in (11, 16, 27, 32):                 # queue stanchions
        _put(b, "brick_1x1", x, 22, 1, 0, SIGN)
        _put(b, "tile_1x1", x, 22, 4, 0, "black")

    # ---- floors ------------------------------------------------------------
    tile_runs(b, XO, XO + S - 1, 0, YO - 1, FLOOR)          # concourse, front
    tile_runs(b, XO + T, XO + S - 1 - T, YO, 11, FLOOR)     # hall floor
    tile_runs(b, XO + T, XO + S - 1 - T, 12, 13, WALK)      # walkway strip
    tile_runs(b, XO + T, XO + S - 1 - T, 14, YO + D - 1, FLOOR)
    for (dl, dr) in DOORS:                                  # jet-bridge floors
        tile_runs(b, dl, dr, YO + D + 1, YO + D + 14, FLOOR)
    tile_runs(b, 0, 47, WALL_Y + 1, 47, TARMAC)             # tarmac

    return b, crown_z


def main():
    b, crown_z = build()
    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall, "
          f"crown at z={crown_z}.")
    print(f"{len(WARNINGS)} advisory warnings" +
          (f", e.g. {WARNINGS[0]}" if WARNINGS else "."))
    out = Path(__file__).resolve().parent.parent / "builds"
    (out / "dxb_gates.json").write_text(b.to_json())
    (out / "dxb_gates.ldr").write_text(to_ldraw(b))
    (out / "dxb_gates_blender.py").write_text(to_blender_script(b))
    print(f"Exported dxb_gates.{{json,ldr}} and dxb_gates_blender.py to {out}")


if __name__ == "__main__":
    main()
