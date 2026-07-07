"""Constraint tests: every rule the engine must enforce."""

import pytest

from lego_mcp.engine import Build, PlacementError


@pytest.fixture
def b():
    return Build(name="test", width=16, depth=16)


def test_place_on_baseplate(b):
    piece, warnings = b.place("brick_2x4", 0, 0, 0)
    assert piece.top == 3
    assert warnings == []


def test_unknown_part_rejected(b):
    with pytest.raises(PlacementError, match="UNKNOWN_PART"):
        b.place("brick_3x5", 0, 0, 0)  # no such Lego part


def test_floating_rejected(b):
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("brick_2x4", 0, 0, 5)


def test_collision_rejected(b):
    b.place("brick_2x4", 0, 0, 0)
    with pytest.raises(PlacementError, match="COLLISION"):
        b.place("brick_2x2", 1, 0, 0)
    with pytest.raises(PlacementError, match="COLLISION"):
        b.place("plate_1x1", 0, 0, 2)  # inside the brick's 3-plate body


def test_stacking_needs_exact_z(b):
    b.place("brick_2x4", 0, 0, 0)
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("brick_2x4", 0, 0, 4)  # 1 plate of air above the brick
    piece, _ = b.place("brick_2x4", 0, 0, 3)  # exactly on top: fine
    assert piece.z == 3


def test_partial_overlap_stud_connection(b):
    b.place("brick_2x4", 0, 0, 0)
    piece, _ = b.place("brick_2x4", 0, 3, 3)  # offset, 2 studs engaged
    assert piece.id in b.pieces


def test_rotation_swaps_footprint(b):
    p, _ = b.place("brick_1x4", 0, 0, 0, rotation=90)
    assert (p.w, p.d) == (4, 1)
    with pytest.raises(PlacementError, match="COLLISION"):
        b.place("brick_1x1", 3, 0, 0)


def test_out_of_bounds_rejected(b):
    with pytest.raises(PlacementError, match="OUT_OF_BOUNDS"):
        b.place("brick_2x8", 15, 0, 0)
    with pytest.raises(PlacementError, match="OUT_OF_BOUNDS"):
        b.place("brick_2x2", -1, 0, 0)


def test_nothing_stacks_on_tiles(b):
    b.place("brick_2x2", 0, 0, 0)
    b.place("tile_2x2", 0, 0, 3)
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("brick_2x2", 0, 0, 4)


def test_removal_that_orphans_is_refused(b):
    base, _ = b.place("brick_2x4", 0, 0, 0)
    top, _ = b.place("brick_2x4", 0, 0, 3)
    with pytest.raises(PlacementError, match="WOULD_ORPHAN"):
        b.remove(base.id)
    b.remove(top.id)     # top-down is fine
    b.remove(base.id)


def test_bridge_survives_removing_one_support(b):
    a, _ = b.place("brick_2x2", 0, 0, 0)
    c, _ = b.place("brick_2x2", 0, 4, 0)
    b.place("brick_2x6", 0, 0, 3)  # spans both supports
    b.remove(a.id)  # bridge still held by the other pillar


def test_hanging_connection_counts(b):
    b.place("brick_2x2", 0, 0, 0)
    b.place("plate_2x6", 0, 0, 3)  # cantilever off the pillar
    # a plate pressed up under the overhang connects via ITS top studs
    piece, _ = b.place("plate_2x2", 0, 2, 2)
    assert piece.id in b.pieces
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("tile_2x2", 0, 4, 2)  # tile has no top studs: can't hang


def test_cantilever_warning(b):
    b.place("brick_2x2", 0, 0, 0)
    piece, warnings = b.place("brick_2x8", 0, 1, 3)  # 2 of 16 studs engaged
    assert any("cantilever" in w for w in warnings)


def test_save_load_roundtrip(b):
    b.place("brick_2x4", 0, 0, 0, color="blue")
    b.place("brick_2x4", 0, 2, 3, rotation=90, color="yellow")
    b.place("tile_2x2", 2, 2, 6, color="white")
    restored = Build.from_json(b.to_json())
    assert restored.summary()["inventory"] == b.summary()["inventory"]
    assert sorted(restored.pieces) == sorted(b.pieces)


def test_lowest_free_z_hint(b):
    b.place("brick_2x4", 0, 0, 0)
    b.place("brick_2x4", 0, 0, 3)
    try:
        b.place("brick_2x4", 0, 0, 0)
    except PlacementError as e:
        assert "z=6" in str(e)


def test_baseplate_ground_only(b):
    b.place("baseplate_16x16", 0, 0, 0, color="green")
    piece, _ = b.place("brick_2x4", 2, 2, 1)  # on baseplate studs
    assert piece.z == 1
    with pytest.raises(PlacementError, match="GROUND_ONLY"):
        b.place("baseplate_16x16", 0, 0, piece.top, color="green")


def test_slope_studs_only_on_back_rows(b):
    b.place("slope_2x2", 0, 0, 0)  # descends toward +y: studs at y=0 only
    piece, _ = b.place("plate_1x2", 0, 0, 3, rotation=90)  # on the stud row
    assert piece.id in b.pieces
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("plate_1x1", 0, 1, 3)  # sloped face has no studs


def test_slope_rotation_180_flips_stud_row(b):
    b.place("slope_2x2", 0, 0, 0, rotation=180)  # studs now at y=1
    piece, _ = b.place("plate_1x1", 0, 1, 3)
    assert piece.id in b.pieces
    with pytest.raises(PlacementError, match="FLOATING"):
        b.place("plate_1x1", 0, 0, 3)


def test_slope_rotation_90_footprint_and_studs(b):
    p, _ = b.place("slope_1x3", 0, 0, 0, rotation=90)  # 1x3 -> 3x1 run
    assert (p.w, p.d) == (3, 1)
    assert len(p.stud_cells) == 1  # single stud row on a 1x3 33-degree slope


def test_inverted_slope_grips_only_back_row(b):
    b.place("brick_2x2", 0, 0, 0)
    piece, _ = b.place("slope_inv_2x2", 0, 1, 3)  # back row (y=1) on studs
    assert piece.id in b.pieces
    b.place("brick_2x2", 8, 0, 0)
    with pytest.raises(PlacementError, match="FLOATING"):
        # rotation 180 puts the gripping row at y=3, off the support
        b.place("slope_inv_2x2", 8, 1, 3, rotation=180)


def test_stack_on_inverted_slope_top(b):
    b.place("brick_2x2", 0, 0, 0)
    b.place("slope_inv_2x2", 0, 1, 3)
    piece, _ = b.place("plate_2x2", 0, 1, 6)  # full studs on inverted top
    assert piece.id in b.pieces


def test_baseplate_needs_room(b):
    with pytest.raises(PlacementError, match="OUT_OF_BOUNDS"):
        b.place("baseplate_32x32", 0, 0, 0)  # build is only 16x16
