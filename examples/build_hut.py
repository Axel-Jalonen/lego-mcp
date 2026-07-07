"""Demo: baseplate + slope showcase — a hut with a real pitched roof and an
arch built from inverted slopes. Every placement goes through the engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lego_mcp.engine import Build, PlacementError  # noqa: E402
from lego_mcp.export import to_blender_script, to_ldraw  # noqa: E402


def main():
    b = Build(name="slope_hut", width=16, depth=16)

    # Green baseplate floor: everything else sits on its studs (z=1).
    b.place("baseplate_16x16", 0, 0, 0, 0, "green")

    # --- hut: 4x4 walls (x 3..6, y 6..9), two brick courses ---
    for z in (1, 4):
        b.place("brick_1x4", 3, 6, z, 90, "white")      # south wall
        b.place("brick_1x4", 3, 9, z, 90, "white")      # north wall
        b.place("brick_1x2", 3, 7, z, 0, "white")       # west wall
        b.place("brick_1x2", 6, 7, z, 0, "white")       # east wall

    # Pitched roof: opposing 45-degree slopes meeting at a flat ridge.
    b.place("slope_2x2", 3, 6, 7, 180, "red")   # south pitch, descends -y
    b.place("slope_2x2", 5, 6, 7, 180, "red")
    b.place("slope_2x2", 3, 8, 7, 0, "red")     # north pitch, descends +y
    b.place("slope_2x2", 5, 8, 7, 0, "red")
    b.place("tile_2x4", 3, 7, 10, 90, "dark_red")   # smooth ridge cap

    # --- arch: two columns bridged via inverted slopes ---
    for cy in (4, 10):
        b.place("brick_2x2", 10, cy, 1, 0, "light_gray")
        b.place("brick_2x2", 10, cy, 4, 0, "light_gray")
    b.place("slope_inv_2x2", 10, 5, 7, 0, "tan")     # grips south column
    b.place("slope_inv_2x2", 10, 9, 7, 180, "tan")   # grips north column
    b.place("plate_2x4", 10, 6, 10, 0, "tan")        # span resting on both
    b.place("tile_2x4", 10, 6, 11, 0, "white")       # smooth walkway

    # A little 33-degree stair of slopes out front.
    b.place("slope_1x3", 4, 10, 1, 0, "blue")
    b.place("slope_1x2", 5, 11, 1, 0, "yellow")

    s = b.summary()
    print(f"Built '{b.name}': {s['piece_count']} pieces, "
          f"{s['height_plates']} plates tall.")

    for bad, kwargs in [
        ("brick on a sloped face", dict(part_name="brick_1x1", x=3, y=9, z=10)),
        ("baseplate in the sky", dict(part_name="baseplate_16x16", x=0, y=0, z=12)),
        ("inv slope gripping nothing", dict(part_name="slope_inv_2x2",
                                            x=13, y=5, z=7)),
    ]:
        try:
            b.place(**kwargs)
            print(f"UNEXPECTED: {bad} was accepted!")
        except PlacementError as e:
            print(f"rejected {bad}: {str(e).split(':')[0]}")

    out = Path(__file__).resolve().parent.parent / "builds"
    (out / f"{b.name}.json").write_text(b.to_json())
    (out / f"{b.name}.ldr").write_text(to_ldraw(b))
    (out / f"{b.name}_blender.py").write_text(to_blender_script(b))
    print(f"Exported to {out}/{b.name}.*")


if __name__ == "__main__":
    main()
