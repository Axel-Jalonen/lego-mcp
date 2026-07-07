"""lego-mcp: an MCP server where the model can only build physically valid Lego.

Every mutation is validated by the engine; invalid placements come back as
errors that explain the violated constraint and suggest a fix. State is
persisted to builds/<name>.json after every change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .catalog import CATALOG, COLORS
from .engine import Build, PlacementError
from .export import to_blender_script, to_ldraw


def _builds_dir() -> Path:
    """Where builds are read/written. Must not depend on the install location
    so the server works whether it's run from a source checkout or installed
    into site-packages (via pip/pipx/uvx).

    Resolution order:
      1. $LEGO_MCP_HOME/builds  (explicit override, set in the MCP config)
      2. <repo>/builds          (running from a writable source checkout)
      3. ~/.lego-mcp/builds     (installed anywhere else)
    """
    override = os.environ.get("LEGO_MCP_HOME")
    if override:
        return Path(override).expanduser() / "builds"
    local = Path(__file__).resolve().parent.parent / "builds"
    if local.is_dir() and os.access(local, os.W_OK):
        return local
    return Path.home() / ".lego-mcp" / "builds"


BUILDS_DIR = _builds_dir()
BUILDS_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP(
    "lego",
    instructions=(
        "A Lego building system with hard physical constraints. Coordinates: "
        "x,y in studs; z in PLATES (a brick is 3 plates tall, a plate/tile is 1). "
        "z=0 is the baseplate. Pieces must connect stud-to-tube: place a brick "
        "at z=0, then a brick on top of it goes at z=3. Placements that "
        "collide, float, or stack on tiles are REJECTED - read the error, it "
        "tells you a valid z. Build bottom-up. Use ascii view to see the state."
    ),
)

_build = Build()


def _save() -> None:
    (BUILDS_DIR / f"{_build.name}.json").write_text(_build.to_json())


@mcp.tool()
def new_build(name: str = "build", width: int = 32, depth: int = 32) -> str:
    """Start a fresh build on an empty baseplate of width x depth studs.
    Replaces the current build (previous one stays saved on disk)."""
    global _build
    if not (4 <= width <= 128 and 4 <= depth <= 128):
        return "ERROR: baseplate must be between 4x4 and 128x128 studs."
    _build = Build(name=name, width=width, depth=depth)
    _save()
    return f"New build '{name}' on a {width}x{depth} baseplate. z=0 is ground."


@mcp.tool()
def list_parts() -> str:
    """List every part in the catalog (the ONLY placeable pieces) and all
    colors. Sizes are studs; height is in plates (brick=3, plate/tile=1).
    Tiles have smooth tops. Slopes have studs only on their non-sloped rows
    (at rotation 0 the slope descends toward +y; rotate 90/180/270 to face
    it). Baseplates have studs on top, nothing underneath, and only go at
    z=0."""
    rows = []
    for p in CATALOG.values():
        note = ""
        if not p.studs_top:
            note = "  [smooth top - nothing stacks on it]"
        elif p.slope_rows and p.inverted:
            note = ("  [inverted slope: full studs on top, grips below only "
                    f"on its {p.depth - p.slope_rows} back row(s)]")
        elif p.slope_rows:
            note = (f"  [slope: studs only on {p.depth - p.slope_rows} back "
                    f"row(s); descends toward +y at rotation 0]")
        elif p.ground_only:
            note = "  [baseplate: z=0 only, studs on top]"
        rows.append(f"{p.name:16s} {p.width}x{p.depth} studs, "
                    f"{p.height} plate(s) tall{note}")
    return ("PARTS:\n" + "\n".join(rows)
            + "\n\nCOLORS: " + ", ".join(sorted(COLORS)))


@mcp.tool()
def place_brick(part: str, x: int, y: int, z: int,
                rotation: int = 0, color: str = "red") -> str:
    """Place a part with its minimum-x,y corner at stud (x,y), bottom at plate
    height z (z=0 on the ground; on top of a brick placed at z=0 means z=3).
    rotation is 0, 90, 180 or 270 (90/270 swap the footprint; slopes descend
    toward +y at 0 and rotate with the piece). Fails with an explanation if
    the placement collides, floats, or leaves the build area."""
    try:
        piece, warnings = _build.place(part, x, y, z, rotation, color)
    except PlacementError as e:
        return f"REJECTED: {e}"
    _save()
    msg = (f"OK: placed #{piece.id} {color} {part} at ({x},{y},z={z}), "
           f"rotation {rotation}. Its top surface is at z={piece.top}.")
    if warnings:
        msg += " WARNING: " + " ".join(warnings)
    return msg


@mcp.tool()
def remove_brick(piece_id: int) -> str:
    """Remove a piece by id. Refused if other pieces would be left floating."""
    try:
        piece = _build.remove(piece_id)
    except PlacementError as e:
        return f"REJECTED: {e}"
    _save()
    return f"OK: removed #{piece_id} ({piece.color} {piece.part_name})."


@mcp.tool()
def get_build() -> str:
    """Current build state: piece list with positions, inventory, dimensions."""
    return json.dumps(_build.summary(), indent=1)


@mcp.tool()
def view_layers(z_from: int | None = None, z_to: int | None = None) -> str:
    """Top-down ASCII map of each plate layer (pieces shown by id, '.' empty).
    Optionally limit to plate range [z_from, z_to)."""
    return _build.ascii_layers(z_from, z_to)


@mcp.tool()
def load_build(name: str) -> str:
    """Load a previously saved build by name (see saved .json files in builds/).
    The save is re-validated piece by piece on load."""
    global _build
    path = BUILDS_DIR / f"{name}.json"
    if not path.exists():
        existing = sorted(p.stem for p in BUILDS_DIR.glob("*.json"))
        return f"ERROR: no build named '{name}'. Saved builds: {existing}"
    try:
        _build = Build.from_json(path.read_text())
    except PlacementError as e:
        return f"ERROR: {e}"
    return (f"Loaded '{name}': {len(_build.pieces)} pieces on a "
            f"{_build.width}x{_build.depth} baseplate.")


@mcp.tool()
def export_build(fmt: str = "ldraw") -> str:
    """Export the build. fmt='ldraw' writes builds/<name>.ldr (openable in
    BrickLink Studio / LeoCAD); fmt='blender' writes builds/<name>_blender.py,
    a bpy script that constructs the model in Blender."""
    if not _build.pieces:
        return "ERROR: build is empty."
    if fmt == "ldraw":
        path = BUILDS_DIR / f"{_build.name}.ldr"
        path.write_text(to_ldraw(_build))
    elif fmt == "blender":
        path = BUILDS_DIR / f"{_build.name}_blender.py"
        path.write_text(to_blender_script(_build))
    else:
        return "ERROR: fmt must be 'ldraw' or 'blender'."
    return f"Exported {len(_build.pieces)} pieces to {path}"


def main() -> None:
    # Resume the most recently saved build so state survives restarts.
    global _build
    saves = sorted(BUILDS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if saves:
        try:
            _build = Build.from_json(saves[-1].read_text())
        except (PlacementError, KeyError, json.JSONDecodeError):
            pass
    mcp.run()


if __name__ == "__main__":
    main()
