from chroma_cube.generator.profiles import DIFFICULTIES, PROFILES


def test_profiles_exist_for_every_difficulty() -> None:
    assert DIFFICULTIES == ("easy", "medium", "hard", "expert")
    assert set(PROFILES) == set(DIFFICULTIES)


def test_harder_profiles_allow_more_and_give_less() -> None:
    for easier, harder in zip(DIFFICULTIES, DIFFICULTIES[1:], strict=False):
        assert PROFILES[easier].features < PROFILES[harder].features
        assert PROFILES[easier].givens[0] >= PROFILES[harder].givens[1]


def test_documented_given_ranges() -> None:
    assert PROFILES["easy"].givens == (5, 7)
    assert PROFILES["medium"].givens == (2, 4)
    assert PROFILES["hard"].givens == (0, 1)
    assert PROFILES["expert"].givens == (0, 0)


def test_easy_is_positions_only() -> None:
    assert PROFILES["easy"].features == {
        "same_row",
        "same_column",
        "next_to",
        "above",
        "below",
        "left_of",
        "right_of",
        "directly_above",
        "directly_below",
        "directly_left_of",
        "directly_right_of",
    }
