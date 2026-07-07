"""Demo: a bone cathedral, assembled entirely through the constraint engine.

Gothic-ish: a long nave with lancet windows, a corbelled pointed portal,
a rose window, twin west towers with stepped spires, and free-standing
buttress ribs. Palette: bone white + tan, weathered gray roof.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.engine import Build, PlacementError  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402

BRICK_RUNS = [8, 6, 4, 3, 2, 1]

# Nave footprint (outer wall line, inclusive)
X0, X1 = 9, 16
Y0, Y1 = 8, 35
COURSES = [0, 3, 6, 9, 12, 15]          # six brick courses; wall top z=18
DOOR = {(12, Y0), (13, Y0)}             # portal in the west front
ROSE = {(12, Y0), (13, Y0)}             # rose window (higher course, same x)
WINDOW_YS = [12, 16, 20, 24, 28]        # lancet slits in both side walls
TOWER_XS = [7, 15]                      # 4x4 towers flanking the front


def fill_run(build, cells, z, color, along_x):
    """Tile a sorted run of (x, y) wall cells with 1xN bricks."""
    i = 0
    while i < len(cells):
        stretch = 1
        while (i + stretch < len(cells)
               and cells[i + stretch - 1][0 if along_x else 1] + 1
               == cells[i + stretch][0 if along_x else 1]):
            stretch += 1
        n = next(s for s in BRICK_RUNS if s <= stretch)
        x, y = cells[i]
        build.place(f"brick_1x{n}", x, y, z, 90 if along_x else 0, color)
        i += n


def nave_course(build, z, color, gaps=frozenset()):
    front = [(x, Y0) for x in range(X0, X1 + 1) if (x, Y0) not in gaps]
    back = [(x, Y1) for x in range(X0, X1 + 1) if (x, Y1) not in gaps]
    west = [(X0, y) for y in range(Y0 + 1, Y1) if (X0, y) not in gaps]
    east = [(X1, y) for y in range(Y0 + 1, Y1) if (X1, y) not in gaps]
    for run in (front, back):
        fill_run(build, run, z, color, along_x=True)
    for run in (west, east):
        fill_run(build, run, z, color, along_x=False)


def main():
    b = Build(name="bone_cathedral", width=26, depth=44)
    windows = {(x, y) for y in WINDOW_YS for x in (X0, X1)}

    # --- nave walls ---
    nave_course(b, 0, "white", gaps=DOOR)
    nave_course(b, 3, "white", gaps=DOOR)
    # portal course: leave the arch zone open, then corbel bricks step inward
    nave_course(b, 6, "white", gaps={(x, Y0) for x in (11, 12, 13, 14)} | windows)
    b.place("brick_1x2", 11, Y0, 6, 90, "tan")   # corbel over the door, left
    b.place("brick_1x2", 13, Y0, 6, 90, "tan")   # corbel over the door, right
    nave_course(b, 9, "white", gaps=windows)
    nave_course(b, 12, "white", gaps=ROSE)       # rose window opening
    nave_course(b, 15, "tan")                    # trim course bridges everything

    # --- stepped roof (plates spanning wall to wall, stepping inward) ---
    for y in range(Y0, Y1 + 1):
        b.place("plate_1x8", X0, y, 18, 90, "light_gray")
    for y in range(Y0, Y1 + 1):
        b.place("plate_1x6", X0 + 1, y, 19, 90, "light_gray")
    for y in range(Y0, Y1 + 1):
        b.place("plate_1x4", X0 + 2, y, 20, 90, "light_gray")
    for y in range(Y0, Y1 + 1):
        b.place("plate_1x2", X0 + 3, y, 21, 90, "white")
    for y in range(Y0, Y1 + 1, 4):               # smooth bone ridge
        b.place("tile_2x4", X0 + 3, y, 22, 0, "tan")

    # --- twin west towers with spires ---
    for tx in TOWER_XS:
        for i, z in enumerate(range(0, 30, 3)):
            color = "tan" if z == 27 else "white"
            b.place("brick_1x4", tx, 4, z, 90, color)       # south face
            b.place("brick_1x4", tx, 7, z, 90, color)       # north face
            b.place("brick_1x2", tx, 5, z, 0, color)        # west face
            b.place("brick_1x2", tx + 3, 5, z, 0, color)    # east face
        b.place("plate_4x4", tx, 4, 30, 0, "tan")
        b.place("plate_2x2", tx + 1, 5, 31, 0, "white")
        b.place("plate_2x2", tx + 1, 5, 32, 0, "tan")
        b.place("brick_1x1", tx + 1, 5, 33, 0, "white")
        b.place("brick_1x1", tx + 1, 5, 36, 0, "white")
        b.place("tile_1x1", tx + 1, 5, 39, 0, "dark_gray")

    # --- buttress ribs (free-standing bone spurs beside the window piers) ---
    for y in (10, 14, 18, 22, 26, 30):
        for bx in (X0 - 1, X1 + 1):
            for z in (0, 3, 6, 9):
                b.place("brick_1x1", bx, y, z, 0, "tan")
            b.place("plate_1x1", bx, y, 12, 0, "tan")
            b.place("tile_1x1", bx, y, 13, 0, "white")

    # --- portal steps ---
    b.place("plate_2x4", 12, 4, 0, 0, "tan")

    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates ({s['height_bricks']} bricks) tall.")

    # Adversarial checks: the engine must still say no.
    for bad, kwargs in [
        ("brick floating in the nave", dict(part_name="brick_2x4", x=11, y=15, z=9)),
        ("gargoyle on the smooth ridge", dict(part_name="brick_1x1", x=12, y=20, z=23)),
        ("brick clipping the tower", dict(part_name="brick_2x2", x=7, y=4, z=10)),
        ("phantom 3x7 part", dict(part_name="brick_3x7", x=0, y=0, z=0)),
    ]:
        try:
            b.place(**kwargs)
            print(f"UNEXPECTED: {bad} was accepted!")
        except PlacementError as e:
            print(f"rejected {bad}: {str(e).split(':')[0]}")

    out = Path(__file__).resolve().parent.parent / "builds"
    out.mkdir(exist_ok=True)
    (out / f"{b.name}.json").write_text(b.to_json())
    (out / f"{b.name}.ldr").write_text(to_ldraw(b))
    (out / f"{b.name}_blender.py").write_text(to_blender_script(b))
    print(f"Exported to {out}/{b.name}.{{json,ldr}} and {b.name}_blender.py")


if __name__ == "__main__":
    main()
