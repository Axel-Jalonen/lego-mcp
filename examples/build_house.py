"""Demo: build a little house through the constraint engine.

Every placement below is validated - if the design were physically impossible,
this script would crash with a PlacementError. Exports LDraw + Blender script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.engine import Build, PlacementError  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402

BRICK_RUNS = [8, 6, 4, 3, 2, 1]  # greedy 1xN brick sizes


def fill_run(build, cells, z, color, along_x):
    """Tile a sorted run of (x, y) wall cells with 1xN bricks."""
    i = 0
    while i < len(cells):
        # longest catalog brick that fits the remaining contiguous stretch
        stretch = 1
        while (i + stretch < len(cells)
               and cells[i + stretch - 1][0 if along_x else 1] + 1
               == cells[i + stretch][0 if along_x else 1]):
            stretch += 1
        n = next(s for s in BRICK_RUNS if s <= stretch)
        x, y = cells[i]
        build.place(f"brick_1x{n}", x, y, z, 90 if along_x else 0, color)
        i += n


def wall_course(build, z, color, gaps=frozenset()):
    """One brick course around the 10x8 perimeter (x 3..12, y 4..11)."""
    front = [(x, 4) for x in range(3, 13) if (x, 4) not in gaps]
    back = [(x, 11) for x in range(3, 13) if (x, 11) not in gaps]
    left = [(3, y) for y in range(5, 11) if (3, y) not in gaps]
    right = [(12, y) for y in range(5, 11) if (12, y) not in gaps]
    for run in (front, back):
        fill_run(build, run, z, color, along_x=True)
    for run in (left, right):
        fill_run(build, run, z, color, along_x=False)


def main():
    b = Build(name="house", width=16, depth=16)

    door = {(7, 4), (8, 4)}                     # 2-stud door in the front wall
    windows = {(3, 7), (3, 8), (12, 7), (12, 8)}  # one window per side wall

    wall_course(b, 0, "red", gaps=door)
    wall_course(b, 3, "red", gaps=door | windows)
    wall_course(b, 6, "white")                  # lintel course closes the gaps

    # Roof: plates spanning front-to-back wall tops, then stepped inward.
    for x in range(3, 13):
        b.place("plate_1x8", x, 4, 9, 0, "dark_gray")
    for x in range(4, 12):
        b.place("plate_1x6", x, 5, 10, 0, "dark_gray")
    for x in range(5, 11):
        b.place("plate_1x4", x, 6, 11, 0, "dark_gray")
    b.place("plate_2x4", 6, 7, 12, 90, "dark_gray")
    b.place("tile_2x4", 6, 7, 13, 90, "black")  # smooth ridge cap

    # Chimney on the second roof step (the engine rejected z=10: occupied).
    b.place("brick_1x1", 4, 10, 11, 0, "dark_red")
    b.place("brick_1x1", 4, 10, 14, 0, "dark_red")

    # Doorstep + path
    b.place("plate_2x2", 7, 2, 0, 0, "light_gray")
    b.place("plate_2x2", 7, 0, 0, 0, "light_gray")

    print(f"Built '{b.name}': {len(b.pieces)} pieces, "
          f"{b.summary()['height_plates']} plates tall.")

    # Prove the constraints hold on this build too:
    for bad, kwargs in [
        ("floating brick", dict(part_name="brick_2x2", x=0, y=0, z=6)),
        ("stack on ridge tile", dict(part_name="brick_1x1", x=6, y=7, z=14)),
        ("clip into wall", dict(part_name="brick_2x4", x=3, y=4, z=1)),
    ]:
        try:
            b.place(**kwargs)
            print(f"UNEXPECTED: {bad} was accepted!")
        except PlacementError as e:
            print(f"rejected {bad}: {str(e).split(':')[0]}")

    out = Path(__file__).resolve().parent.parent / "builds"
    out.mkdir(exist_ok=True)
    (out / "house.json").write_text(b.to_json())
    (out / "house.ldr").write_text(to_ldraw(b))
    (out / "house_blender.py").write_text(to_blender_script(b))
    print(f"Exported to {out}/house.{{json,ldr}} and house_blender.py")


if __name__ == "__main__":
    main()
