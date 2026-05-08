"""
Zebrafish Larval Tracking System

A classical computer vision pipeline for tracking single zebrafish larvae in top-down view.
Designed for offline analysis of recorded videos.

Architecture:
- preprocessing.py: Frame preprocessing (grayscale, blur, contrast)
- background.py: Background modeling using median of first N frames
- detector.py: Foreground extraction and contour detection
- tracker.py: Temporal smoothing using 2D Kalman filter
- exporter.py: CSV export with tracking data

Data Flow:
1. Input video → Preprocess → Background subtraction → Detection → Tracking → Export
2. Analysis modules work on exported CSV data

Output Format:
frame_id,timestamp_ms,x_px,y_px,x_mm,y_mm,area_px,valid
"""

__version__ = "1.0.0"
__author__ = "ZEBB Lab"
