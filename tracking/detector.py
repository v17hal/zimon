"""
Fish detection module for zebrafish tracking

Handles foreground extraction, thresholding, and contour detection.
Optimized for single zebrafish larva detection.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional


class FishDetector:
    """Detect zebrafish larvae using classical computer vision"""
    
    def __init__(self, 
                 min_area: int = 100,
                 max_area: int = 5000,
                 min_circularity: float = 0.3,
                 min_inertia_ratio: float = 0.3):
        """
        Initialize detector
        
        Args:
            min_area: Minimum contour area (pixels)
            max_area: Maximum contour area (pixels)
            min_circularity: Minimum circularity (0-1)
            min_inertia_ratio: Minimum inertia ratio
        """
        self.min_area = min_area
        self.max_area = max_area
        self.min_circularity = min_circularity
        self.min_inertia_ratio = min_inertia_ratio
        
    def detect(self, foreground_mask: np.ndarray) -> Tuple[Optional[np.ndarray], bool]:
        """
        Detect fish in foreground mask
        
        Args:
            foreground_mask: Binary foreground mask
            
        Returns:
            Tuple of (centroid, valid_flag)
        """
        # Find contours
        contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None, False
        
        # Filter contours by area
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_area <= area <= self.max_area:
                valid_contours.append((contour, area))
        
        if not valid_contours:
            return None, False
        
        # Select largest contour (single fish assumption)
        largest_contour, largest_area = max(valid_contours, key=lambda x: x[1])
        
        # Additional shape filtering
        if self._is_valid_shape(largest_contour):
            # Calculate centroid
            M = cv2.moments(largest_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return np.array([cx, cy]), True
        
        return None, False
    
    def _is_valid_shape(self, contour: np.ndarray) -> bool:
        """
        Check if contour has valid fish-like shape
        
        Args:
            contour: Input contour
            
        Returns:
            True if shape is valid
        """
        # Calculate shape properties
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        if perimeter == 0:
            return False
        
        # Circularity
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        # Inertia ratio
        try:
            _, (w, h), _ = cv2.minAreaRect(contour)
            inertia_ratio = min(w, h) / max(w, h)
        except:
            inertia_ratio = 0
        
        return (circularity >= self.min_circularity and 
                inertia_ratio >= self.min_inertia_ratio)
    
    def get_detection_info(self, contour: np.ndarray) -> dict:
        """
        Get detailed information about detected contour
        
        Args:
            contour: Detected contour
            
        Returns:
            Dictionary with detection metrics
        """
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        # Bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Centroid
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
        else:
            cx, cy = x + w/2, y + h/2
        
        return {
            'area': area,
            'perimeter': perimeter,
            'centroid': (cx, cy),
            'bbox': (x, y, w, h),
            'contour': contour
        }
