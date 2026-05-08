"""
Future: draw tracks, bounding boxes, trajectories on top of video.
For now returns the frame unchanged (hook for OpenCV or QPainter overlay).
"""

from __future__ import annotations

import numpy as np


def draw_tracking_overlay(frame: np.ndarray) -> np.ndarray:
    """Placeholder — pass-through. Wire CV drawing or ROI layers here later."""
    return frame
