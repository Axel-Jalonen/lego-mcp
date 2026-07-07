"""Part catalog: the only pieces that exist. Anything else is a hallucination.

Units: footprint in studs (width x depth), height in plates.
1 brick = 3 plates tall. A tile has no studs on top, so nothing can stack on it.

Slopes: `slope_rows` sloped rows sit at the high-j (depth) end of the footprint
at rotation 0, descending toward +y. A regular slope has studs only on its
non-sloped rows; an inverted slope has studs everywhere on top but attaches
below only at its non-sloped rows. Baseplates have studs on top, nothing
underneath, and may only sit on the ground.
"""

from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class Part:
    name: str
    width: int           # studs along x at rotation 0
    depth: int           # studs along y at rotation 0
    height: int          # in plates (brick=3, plate/tile=1)
    studs_top: bool      # False for tiles: nothing can attach above
    ldraw_id: str        # LDraw part number for export
    slope_rows: int = 0  # sloped rows at the high-j end (0 = not a slope)
    inverted: bool = False   # inverted slope (sloped underside)
    ground_only: bool = False  # baseplates: only placeable at z=0

    @cached_property
    def stud_cells(self) -> frozenset[tuple[int, int]]:
        """Local (i, j) cells that have a stud on top (rotation 0)."""
        if not self.studs_top:
            return frozenset()
        if self.slope_rows and not self.inverted:
            rows = range(self.depth - self.slope_rows)
        else:
            rows = range(self.depth)
        return frozenset((i, j) for i in range(self.width) for j in rows)

    @cached_property
    def tube_cells(self) -> frozenset[tuple[int, int]]:
        """Local (i, j) cells whose underside can grip studs (rotation 0)."""
        if self.ground_only:
            return frozenset()
        if self.slope_rows and self.inverted:
            rows = range(self.depth - self.slope_rows)
        else:
            rows = range(self.depth)
        return frozenset((i, j) for i in range(self.width) for j in rows)


_BRICK_FOOTPRINTS = [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8),
                     (2, 2), (2, 3), (2, 4), (2, 6), (2, 8)]
_PLATE_FOOTPRINTS = _BRICK_FOOTPRINTS + [(4, 4), (4, 6), (4, 8), (6, 6), (6, 8), (8, 8)]
_TILE_FOOTPRINTS = [(1, 1), (1, 2), (1, 4), (1, 6), (2, 2), (2, 4)]

_LDRAW = {
    ("brick", 1, 1): "3005", ("brick", 1, 2): "3004", ("brick", 1, 3): "3622",
    ("brick", 1, 4): "3010", ("brick", 1, 6): "3009", ("brick", 1, 8): "3008",
    ("brick", 2, 2): "3003", ("brick", 2, 3): "3002", ("brick", 2, 4): "3001",
    ("brick", 2, 6): "2456", ("brick", 2, 8): "3007",
    ("plate", 1, 1): "3024", ("plate", 1, 2): "3023", ("plate", 1, 3): "3623",
    ("plate", 1, 4): "3710", ("plate", 1, 6): "3666", ("plate", 1, 8): "3460",
    ("plate", 2, 2): "3022", ("plate", 2, 3): "3021", ("plate", 2, 4): "3020",
    ("plate", 2, 6): "3795", ("plate", 2, 8): "3034",
    ("plate", 4, 4): "3031", ("plate", 4, 6): "3032", ("plate", 4, 8): "3035",
    ("plate", 6, 6): "3958", ("plate", 6, 8): "3036", ("plate", 8, 8): "41539",
    ("tile", 1, 1): "3070b", ("tile", 1, 2): "3069b", ("tile", 1, 4): "2431",
    ("tile", 1, 6): "6636", ("tile", 2, 2): "3068b", ("tile", 2, 4): "87079",
}


# name -> (w, d, slope_rows, inverted, ldraw_id); slopes are 1 brick tall
_SLOPES = {
    "slope_1x2": (1, 2, 1, False, "3040b"),      # 45 deg
    "slope_2x2": (2, 2, 1, False, "3039"),       # 45 deg
    "slope_1x3": (1, 3, 2, False, "4286"),       # 33 deg
    "slope_2x3": (2, 3, 2, False, "3298"),       # 33 deg
    "slope_inv_1x2": (1, 2, 1, True, "3665"),    # 45 deg inverted
    "slope_inv_2x2": (2, 2, 1, True, "3660"),    # 45 deg inverted
}

_BASEPLATES = {  # size -> ldraw id; studs on top, nothing underneath, z=0 only
    16: "3867",
    32: "3811",
    48: "4186",
}


def _build_catalog() -> dict[str, Part]:
    parts: dict[str, Part] = {}
    for kind, footprints, height, studs in (
        ("brick", _BRICK_FOOTPRINTS, 3, True),
        ("plate", _PLATE_FOOTPRINTS, 1, True),
        ("tile", _TILE_FOOTPRINTS, 1, False),
    ):
        for w, d in footprints:
            name = f"{kind}_{w}x{d}"
            parts[name] = Part(name, w, d, height, studs,
                               _LDRAW.get((kind, w, d), "3001"))
    for name, (w, d, rows, inv, ldraw) in _SLOPES.items():
        parts[name] = Part(name, w, d, 3, True, ldraw,
                           slope_rows=rows, inverted=inv)
    for size, ldraw in _BASEPLATES.items():
        name = f"baseplate_{size}x{size}"
        parts[name] = Part(name, size, size, 1, True, ldraw, ground_only=True)
    return parts


CATALOG: dict[str, Part] = _build_catalog()

# name -> (hex for rendering, LDraw colour code)
COLORS: dict[str, tuple[str, int]] = {
    "red": ("#C91A09", 4),
    "blue": ("#0055BF", 1),
    "yellow": ("#F2CD37", 14),
    "green": ("#237841", 2),
    "white": ("#FFFFFF", 15),
    "black": ("#05131D", 0),
    "light_gray": ("#A0A5A9", 71),
    "dark_gray": ("#6C6E68", 72),
    "orange": ("#FE8A18", 25),
    "brown": ("#583927", 6),
    "tan": ("#E4CD9E", 19),
    "dark_red": ("#720E0F", 320),
    "dark_blue": ("#0A3463", 272),
    "lime": ("#BBE90B", 27),
}
