"""Amateur radio frequency band determination."""

from typing import List, Tuple

# Frequency ranges in Hz: (min_freq, max_freq, band_name)
AMATEUR_BANDS: List[Tuple[int, int, str]] = [
    (135_700, 137_800, "2200m"),
    (472_000, 479_000, "630m"),
    (1_800_000, 2_000_000, "160m"),
    (3_500_000, 3_800_000, "80m"),
    (5_351_500, 5_366_500, "60m"),
    (7_000_000, 7_200_000, "40m"),
    (10_100_000, 10_150_000, "30m"),
    (14_000_000, 14_350_000, "20m"),
    (18_068_000, 18_168_000, "17m"),
    (21_000_000, 21_450_000, "15m"),
    (24_890_000, 24_990_000, "12m"),
    (28_000_000, 29_700_000, "10m"),
    (50_000_000, 52_000_000, "6m"),
    (70_000_000, 70_500_000, "4m"),
    (144_000_000, 146_000_000, "2m"),
    (430_000_000, 440_000_000, "70cm"),
]


def frequency_to_band(freq_hz: int | float) -> str:
    """Map a frequency in Hz to its amateur radio band or generic designation."""
    try:
        freq = int(freq_hz)
    except (ValueError, TypeError):
        return "Unknown"

    for min_f, max_f, name in AMATEUR_BANDS:
        if min_f <= freq <= max_f:
            return name

    # Fallback to coarse classification if slightly outside exact IARU band boundaries
    mhz = freq / 1_000_000
    if 1.5 <= mhz <= 2.2:
        return "160m"
    if 3.4 <= mhz <= 4.1:
        return "80m"
    if 5.0 <= mhz <= 5.5:
        return "60m"
    if 6.9 <= mhz <= 7.4:
        return "40m"
    if 10.0 <= mhz <= 10.3:
        return "30m"
    if 13.9 <= mhz <= 14.5:
        return "20m"
    if 17.9 <= mhz <= 18.3:
        return "17m"
    if 20.9 <= mhz <= 21.6:
        return "15m"
    if 24.7 <= mhz <= 25.1:
        return "12m"
    if 27.9 <= mhz <= 30.0:
        return "10m"
    if 49.0 <= mhz <= 55.0:
        return "6m"
    if 69.0 <= mhz <= 71.0:
        return "4m"
    if 143.0 <= mhz <= 148.0:
        return "2m"
    if 420.0 <= mhz <= 450.0:
        return "70cm"

    return "Other"
