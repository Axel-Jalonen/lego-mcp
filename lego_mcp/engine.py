"""Lego build engine: a stud-grid world where every placement is validated.

Rules enforced (rejections, not warnings):
  1. Part must exist in the catalog.
  2. Rotation must be 0 or 90 degrees.
  3. Footprint must be inside the baseplate bounds.
  4. No cell may overlap an existing piece (solid bricks, no clipping).
  5. Every piece must connect stud-to-tube: at least one bottom cell resting
     on a stud of an existing piece, sitting on the baseplate (z=0), or at
     least one of its own top studs engaging the underside of an existing
     piece. Tiles have no top studs, so nothing can stack on a tile.
  6. Removing a piece is refused if it would leave any other piece
     disconnected from the baseplate.

Coordinates: x,y in studs; z in plates (brick = 3 plates). z=0 is the baseplate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

from .catalog import CATALOG, COLORS, Part


class PlacementError(Exception):
    """Raised with a model-friendly explanation of which constraint failed."""


@dataclass
class Piece:
    id: int
    part_name: str
    x: int
    y: int
    z: int          # bottom of piece, in plates
    rotation: int   # 0, 90, 180 or 270
    color: str

    @property
    def part(self) -> Part:
        return CATALOG[self.part_name]

    @property
    def w(self) -> int:
        return self.part.depth if self.rotation in (90, 270) else self.part.width

    @property
    def d(self) -> int:
        return self.part.width if self.rotation in (90, 270) else self.part.depth

    @property
    def top(self) -> int:
        return self.z + self.part.height

    def local_to_world(self, i: int, j: int) -> tuple[int, int]:
        """Map a part-local cell (i, j) to a world stud, honoring rotation."""
        p = self.part
        if self.rotation == 0:
            dx, dy = i, j
        elif self.rotation == 90:
            dx, dy = j, p.width - 1 - i
        elif self.rotation == 180:
            dx, dy = p.width - 1 - i, p.depth - 1 - j
        else:
            dx, dy = p.depth - 1 - j, i
        return self.x + dx, self.y + dy

    @property
    def stud_cells(self) -> frozenset[tuple[int, int]]:
        """World cells with a stud on this piece's top surface."""
        return frozenset(self.local_to_world(i, j)
                         for i, j in self.part.stud_cells)

    @property
    def tube_cells(self) -> frozenset[tuple[int, int]]:
        """World cells whose underside can grip a stud below."""
        return frozenset(self.local_to_world(i, j)
                         for i, j in self.part.tube_cells)

    def footprint(self) -> Iterator[tuple[int, int]]:
        for dx in range(self.w):
            for dy in range(self.d):
                yield self.x + dx, self.y + dy

    def cells(self) -> Iterator[tuple[int, int, int]]:
        for cx, cy in self.footprint():
            for cz in range(self.z, self.top):
                yield cx, cy, cz

    def to_dict(self) -> dict:
        return {"id": self.id, "part": self.part_name, "x": self.x, "y": self.y,
                "z": self.z, "rotation": self.rotation, "color": self.color}


@dataclass
class Build:
    name: str = "build"
    width: int = 32   # baseplate studs in x
    depth: int = 32   # baseplate studs in y
    pieces: dict[int, Piece] = field(default_factory=dict)
    _next_id: int = 1
    # (x, y, z) -> piece id, one entry per occupied plate-cell
    _occ: dict[tuple[int, int, int], int] = field(default_factory=dict)

    # ---------- placement ----------

    def place(self, part_name: str, x: int, y: int, z: int,
              rotation: int = 0, color: str = "red") -> tuple[Piece, list[str]]:
        """Validate and place a piece. Returns (piece, warnings) or raises
        PlacementError with an actionable message."""
        if part_name not in CATALOG:
            close = [n for n in CATALOG if part_name.split("_")[0] in n][:8]
            raise PlacementError(
                f"UNKNOWN_PART: '{part_name}' is not a real part. "
                f"Catalog names look like 'brick_2x4', 'plate_1x6', 'tile_2x2'. "
                f"Similar: {close or sorted(CATALOG)[:8]}")
        if rotation not in (0, 90, 180, 270):
            raise PlacementError(
                "BAD_ROTATION: rotation must be 0, 90, 180 or 270. Slopes "
                "descend toward +y at rotation 0; rotate to face them.")
        if color not in COLORS:
            raise PlacementError(
                f"UNKNOWN_COLOR: '{color}'. Available: {sorted(COLORS)}")
        if z < 0:
            raise PlacementError("BELOW_BASEPLATE: z must be >= 0 (z is in plates).")
        if CATALOG[part_name].ground_only and z != 0:
            raise PlacementError(
                f"GROUND_ONLY: {part_name} is a baseplate with a smooth "
                f"underside - it can only be placed at z=0.")

        piece = Piece(self._next_id, part_name, x, y, z, rotation, color)

        if not (0 <= x and x + piece.w <= self.width
                and 0 <= y and y + piece.d <= self.depth):
            raise PlacementError(
                f"OUT_OF_BOUNDS: footprint x={x}..{x + piece.w - 1}, "
                f"y={y}..{y + piece.d - 1} must fit in baseplate "
                f"0..{self.width - 1} x 0..{self.depth - 1}.")

        collisions = {}
        for cell in piece.cells():
            if cell in self._occ:
                collisions.setdefault(self._occ[cell], []).append(cell)
        if collisions:
            desc = "; ".join(
                f"piece #{pid} ({self.pieces[pid].part_name}) at cells {cells[:4]}"
                for pid, cells in collisions.items())
            free_z = self._lowest_free_z(piece)
            raise PlacementError(
                f"COLLISION: overlaps {desc}. "
                f"Lowest free z for this footprint is z={free_z}.")

        supports, hangers = self._connections(piece)
        if z > 0 and not supports and not hangers:
            free_z = self._lowest_free_z(piece)
            raise PlacementError(
                f"FLOATING: no stud connection. No stud sits at z={z} under "
                f"this piece's gripping cells and nothing rests on top of it. "
                f"Remember: sloped surfaces have no studs, and inverted "
                f"slopes/baseplates only grip on part of their underside. "
                f"Supported z for this footprint: z={free_z} "
                f"(or z=0 on the ground).")

        # Committed. Compute advisory stability warning.
        warnings = []
        n_cells = piece.w * piece.d
        supported = len(self._supported_cells(piece))
        if z > 0 and 0 < supported <= max(1, n_cells // 4) and n_cells >= 4:
            warnings.append(
                f"cantilever: only {supported}/{n_cells} studs engaged; "
                f"a real build here would be fragile.")

        self.pieces[piece.id] = piece
        for cell in piece.cells():
            self._occ[cell] = piece.id
        self._next_id += 1
        return piece, warnings

    def remove(self, piece_id: int) -> Piece:
        if piece_id not in self.pieces:
            raise PlacementError(f"NO_SUCH_PIECE: no piece with id {piece_id}. "
                                 f"Existing ids: {sorted(self.pieces)[:20]}")
        piece = self.pieces[piece_id]
        orphans = self._orphans_without(piece_id)
        if orphans:
            raise PlacementError(
                f"WOULD_ORPHAN: removing #{piece_id} would leave pieces "
                f"{sorted(orphans)} disconnected from the baseplate. "
                f"Remove those first (top down).")
        for cell in piece.cells():
            del self._occ[cell]
        del self.pieces[piece_id]
        return piece

    # ---------- connectivity ----------

    def _supported_cells(self, piece: Piece) -> list[tuple[int, int]]:
        """Cells where the piece's gripping underside engages a stud below."""
        out = []
        for cx, cy in piece.tube_cells:
            below = self._occ.get((cx, cy, piece.z - 1))
            if below is not None and (cx, cy) in self.pieces[below].stud_cells:
                out.append((cx, cy))
        return out

    def _connections(self, piece: Piece) -> tuple[set[int], set[int]]:
        """(ids supporting this piece from below, ids resting on its top studs)."""
        supports = set()
        for cx, cy in self._supported_cells(piece):
            supports.add(self._occ[(cx, cy, piece.z - 1)])
        hangers = set()
        for cx, cy in piece.stud_cells:
            above = self._occ.get((cx, cy, piece.top))
            if (above is not None and self.pieces[above].z == piece.top
                    and (cx, cy) in self.pieces[above].tube_cells):
                hangers.add(above)
        return supports, hangers

    def _lowest_free_z(self, piece: Piece) -> int:
        """Lowest z where this footprint neither collides nor floats."""
        if piece.part.ground_only:
            return 0
        tops = [0]
        for cx, cy in piece.footprint():
            column = [c[2] + 1 for c, pid in self._occ.items()
                      if c[0] == cx and c[1] == cy
                      and (cx, cy) in self.pieces[pid].stud_cells]
            tops.extend(column)
        return max(tops)

    def _orphans_without(self, removed_id: int) -> set[int]:
        """Pieces unreachable from the baseplate if removed_id disappears."""
        remaining = {pid: p for pid, p in self.pieces.items() if pid != removed_id}
        reached = {pid for pid, p in remaining.items() if p.z == 0}
        changed = True
        while changed:
            changed = False
            for pid, p in remaining.items():
                if pid in reached:
                    continue
                sup, hang = self._connections_among(p, remaining)
                if (sup | hang) & reached:
                    reached.add(pid)
                    changed = True
        return set(remaining) - reached

    def _connections_among(self, piece: Piece,
                           pool: dict[int, Piece]) -> tuple[set[int], set[int]]:
        sup, hang = self._connections(piece)
        sup = {i for i in sup if i in pool}
        hang = {i for i in hang if i in pool}
        return sup, hang

    # ---------- views / io ----------

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for p in self.pieces.values():
            key = f"{p.color} {p.part_name}"
            counts[key] = counts.get(key, 0) + 1
        max_z = max((p.top for p in self.pieces.values()), default=0)
        return {
            "name": self.name,
            "baseplate": f"{self.width}x{self.depth} studs",
            "piece_count": len(self.pieces),
            "height_plates": max_z,
            "height_bricks": round(max_z / 3, 1),
            "inventory": counts,
            "pieces": [p.to_dict() for p in sorted(self.pieces.values(),
                                                   key=lambda p: (p.z, p.id))],
        }

    def ascii_layers(self, z_from: int | None = None,
                     z_to: int | None = None) -> str:
        """Top-view ASCII map per plate level. Pieces labelled by id mod 36."""
        if not self.pieces:
            return "(empty build)"
        max_z = max(p.top for p in self.pieces.values())
        z_from = 0 if z_from is None else max(0, z_from)
        z_to = max_z if z_to is None else min(max_z, z_to)
        glyphs = "0123456789abcdefghijklmnopqrstuvwxyz"
        out = []
        for z in range(z_from, z_to):
            rows = []
            occupied = False
            for y in range(self.depth - 1, -1, -1):
                row = []
                for x in range(self.width):
                    pid = self._occ.get((x, y, z))
                    if pid is None:
                        row.append(".")
                    else:
                        occupied = True
                        row.append(glyphs[pid % 36])
                rows.append("".join(row))
            if occupied:
                out.append(f"-- z={z} (plates {z}..{z}) --\n" + "\n".join(rows))
        return "\n\n".join(out) if out else "(no pieces in that z range)"

    def to_json(self) -> str:
        return json.dumps({
            "name": self.name, "width": self.width, "depth": self.depth,
            "pieces": [p.to_dict() for p in self.pieces.values()],
        }, indent=1)

    @classmethod
    def from_json(cls, text: str) -> "Build":
        data = json.loads(text)
        build = cls(name=data["name"], width=data["width"], depth=data["depth"])
        pending = sorted(data["pieces"], key=lambda p: (p["z"], p["id"]))
        # A piece connected only by hanging under a higher piece can't be
        # placed before its anchor; retry until the queue stops shrinking.
        while pending:
            deferred = []
            for pd in pending:
                try:
                    build._next_id = pd["id"]
                    build.place(pd["part"], pd["x"], pd["y"], pd["z"],
                                pd["rotation"], pd["color"])
                except PlacementError:
                    deferred.append(pd)
            if len(deferred) == len(pending):
                raise PlacementError(
                    f"CORRUPT_SAVE: {len(deferred)} saved pieces violate "
                    f"constraints and were skipped: "
                    f"{[p['id'] for p in deferred][:10]}")
            pending = deferred
        build._next_id = max(build.pieces, default=0) + 1
        return build
