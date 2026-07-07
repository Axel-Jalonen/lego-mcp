"""One bay of the DXB Terminal 3 departures forecourt canopy, at minifig scale.

Scale ~1:48 (minifig ~= human): 1 stud ~= 0.38 m, 1 brick ~= 0.46 m. So the
arch below (span 40 studs, crown 26 bricks) is ~15 m wide x ~12 m tall in real
terms -- one grand parabolic rib bay you look into, the departures glass hall
behind, a drop-off lane in front. Every placement validated by the engine.

The vault is a parabolic corbel: each brick course steps inward (<=2 studs, so
it rests on the course below) until the two flanks meet at a keystone. Tunnel
axis is +y (you look into the arch from the plaza at low y).
"""

import math
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
    x = x0
    while x <= x1:
        n = next(s for s in _depths(kind, 1) if s <= x1 - x + 1)
        b.place(f"{kind}_1x{n}", x, y, z, 90, color)
        x += n


# --- geometry (studs / bricks) ----------------------------------------------
S = 40      # arch span in x (studs)   ~15 m
H = 26      # crown height in bricks   ~12 m
D = 20      # tunnel depth in y        ~7.5 m
T = 3       # vault shell thickness (studs)
XO, YO = 3, 5                 # arch offset on the baseplate
CX = XO + S / 2               # arch centre x


def build():
    b = Build(name="dxb_arch", width=48, depth=48)
    SKIN = "white"            # vault shell
    RIB = "light_gray"        # rib rings
    UNDER = "dark_blue"       # underside light strip
    GLASS = "dark_blue"
    ROAD = "dark_gray"
    FLOOR = "light_gray"
    SIGN = "red"

    b.place("baseplate_48x48", 0, 0, 0, 0, "tan")

    # ---- floor: drop-off lane + forecourt deck ----------------------------
    fill_rect(b, "tile", XO, XO + S - 1, 0, YO - 1, 1, ROAD)          # road
    fill_rect(b, "tile", XO + T, XO + S - 1 - T, YO, YO + D - 1, 1, FLOOR)  # deck

    # ---- the parabolic vault (corbelled, meets at a keystone) -------------
    prev_l = prev_r = None
    for k in range(H):
        z = 1 + 3 * k
        f = (k + 0.5) / H
        half = (S / 2) * math.sqrt(max(0.0, 1 - f))
        xl = max(XO, round(CX - half))
        xr = min(XO + S - 1, round(CX + half))
        if prev_l is not None:                     # step inward <=2 per course
            xl = max(prev_l, min(xl, prev_l + 2))
            xr = min(prev_r, max(xr, prev_r - 2))
        lo_l, hi_l, lo_r, hi_r = xl, xl + T - 1, xr - T + 1, xr
        # rib rings every 3rd depth-slice read as the illuminated ribs
        def flank(x0, x1):
            for y in range(YO, YO + D):
                c = RIB if (y - YO) % 3 == 0 else SKIN
                row(b, "brick", x0, x1, y, z, c)
        if hi_l >= lo_r - 1:                        # flanks meet -> keystone
            for y in range(YO, YO + D):
                c = RIB if (y - YO) % 3 == 0 else SKIN
                row(b, "brick", lo_l, hi_r, y, z, c)
            crown_z = z
            break
        flank(lo_l, hi_l)
        flank(lo_r, hi_r)
        prev_l, prev_r = xl, xr
    else:
        crown_z = 1 + 3 * (H - 1)

    # ---- departures glass hall behind the arch ---------------------------
    doorl, doorr = int(CX) - 3, int(CX) + 2
    for k in range(11):
        z = 1 + 3 * k
        if k < 5:                                   # doorway opening
            row(b, "brick", XO, doorl - 1, YO + D, z, GLASS)
            row(b, "brick", doorr + 1, XO + S - 1, YO + D, z, GLASS)
        else:
            row(b, "brick", XO, XO + S - 1, YO + D, z, GLASS)

    return b, crown_z


def main():
    b, crown_z = build()
    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall, "
          f"crown at z={crown_z}.")
    out = Path(__file__).resolve().parent.parent / "builds"
    (out / "dxb_arch.json").write_text(b.to_json())
    (out / "dxb_arch.ldr").write_text(to_ldraw(b))
    (out / "dxb_arch_blender.py").write_text(to_blender_script(b))
    print(f"Exported dxb_arch.{{json,ldr}} and dxb_arch_blender.py to {out}")


if __name__ == "__main__":
    main()
