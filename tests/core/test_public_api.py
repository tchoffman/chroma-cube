import chroma_cube.core as core


def test_clue_language_is_exported_from_core() -> None:
    for name in [
        "Clue",
        "ColorRef",
        "Relation",
        "Property",
        "BoardRule",
        "Not",
        "And",
        "Or",
        "Exactly",
        "AtLeast",
        "RELATION_KINDS",
        "PROPERTY_KINDS",
        "BOARD_RULE_KINDS",
        "RelationKind",
        "PropertyKind",
        "ref",
        "relation",
        "prop",
        "Truth",
        "evaluate",
        "render",
        "parse_clue",
        "parse_clues",
        "ClueParseError",
        "clue_to_dict",
        "clue_from_dict",
        "Puzzle",
        "puzzle_to_dict",
        "puzzle_from_dict",
    ]:
        assert name in core.__all__
        assert hasattr(core, name)
