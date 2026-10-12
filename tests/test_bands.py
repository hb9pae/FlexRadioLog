"""Tests for amateur band detection."""

import pytest
from flexradiolog.radio.bands import frequency_to_band


@pytest.mark.parametrize(
    "freq,expected_band",
    [
        (1_840_000, "160m"),
        (3_573_000, "80m"),
        (5_357_000, "60m"),
        (7_074_000, "40m"),
        (10_136_000, "30m"),
        (14_074_000, "20m"),
        (18_100_000, "17m"),
        (21_074_000, "15m"),
        (24_915_000, "12m"),
        (28_074_000, "10m"),
        (50_313_000, "6m"),
        (70_100_000, "4m"),
        (144_300_000, "2m"),
        (432_200_000, "70cm"),
        (100_000_000, "Other"),
    ],
)
def test_frequency_to_band(freq, expected_band):
    assert frequency_to_band(freq) == expected_band
