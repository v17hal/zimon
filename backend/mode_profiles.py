"""Adult vs larval mode: default acquisition hints (same UI, different parameters)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeProfile:
    label: str
    default_fps: float
    default_exposure_us: float
    default_gain: float
    resolution_hint: tuple[int, int]


ADULT = ModeProfile(
    label="adult",
    default_fps=120.0,
    default_exposure_us=8000.0,
    default_gain=12.0,
    resolution_hint=(1440, 1080),
)

LARVAL = ModeProfile(
    label="larval",
    default_fps=180.0,
    default_exposure_us=5000.0,
    default_gain=8.0,
    resolution_hint=(1024, 1024),
)


def profile_for_mode(mode: str) -> ModeProfile:
    m = (mode or "adult").strip().lower()
    return LARVAL if m == "larval" else ADULT
