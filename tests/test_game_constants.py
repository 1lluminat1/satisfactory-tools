"""Quick checks for the game-constants helpers."""

from src.game_constants import default_extraction_rate, minimum_belt_tier


class TestExtractorMath:
    def test_mk1_impure(self):
        assert default_extraction_rate("Mk1", "IMPURE") == 30.0

    def test_mk2_normal(self):
        assert default_extraction_rate("Mk2", "NORMAL") == 120.0

    def test_mk3_pure(self):
        assert default_extraction_rate("Mk3", "PURE") == 480.0


class TestBeltTier:
    def test_fits_mk1(self):
        assert minimum_belt_tier(30) == "Mk1"

    def test_fits_mk3(self):
        assert minimum_belt_tier(270) == "Mk3"

    def test_overflow(self):
        assert minimum_belt_tier(2000) is None
