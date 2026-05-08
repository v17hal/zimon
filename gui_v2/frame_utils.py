"""Efficient numpy (OpenCV) → QImage for live preview."""

from __future__ import annotations

import numpy as np
from PyQt6.QtGui import QImage


def numpy_to_qimage(frame: np.ndarray) -> QImage:
    """
    Convert BGR, BGRA, or single-channel uint8/uint16 to QImage (RGB888 or Grayscale8).
    Shares memory where possible (no copy if already contiguous RGB).
    """
    if frame is None or frame.size == 0:
        return QImage()

    if frame.ndim == 2:
        h, w = frame.shape
        if frame.dtype == np.uint16:
            # scale 16-bit mono to 8-bit for display
            g = (frame >> 8).astype(np.uint8)
            g = np.ascontiguousarray(g)
            return QImage(g.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        g = np.ascontiguousarray(frame)
        return QImage(g.data, w, h, w, QImage.Format.Format_Grayscale8).copy()

    if frame.ndim == 3:
        h, w, ch = frame.shape
        if ch == 3:
            rgb = np.ascontiguousarray(frame[:, :, ::-1])  # BGR -> RGB
            bytes_per_line = w * 3
            return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        if ch == 4:
            rgb = np.ascontiguousarray(frame[:, :, [2, 1, 0]])  # BGRA -> RGB drop A for QLabel
            bytes_per_line = w * 3
            return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

    return QImage()
