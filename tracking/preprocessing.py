"""
Frame preprocessing module for zebrafish tracking

Handles grayscale conversion, blur, and contrast enhancement.
Optimized for zebrafish larvae detection in top-down view.
"""

import cv2
import numpy as np
from typing import Tuple, Optional


class FramePreprocessor:
    """Preprocess frames for zebrafish larvae detection"""
    
    def __init__(self, 
                 blur_kernel: int = 5,
                 contrast_alpha: float = 1.0,
                 contrast_beta: int = 0):
        """
        Initialize preprocessor
        
        Args:
            blur_kernel: Gaussian blur kernel size (must be odd)
            contrast_alpha: Contrast scaling factor (1.0 = no change)
            contrast_beta: Brightness offset (0 = no change)
        """
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        self.contrast_alpha = contrast_alpha
        self.contrast_beta = contrast_beta
        
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply full preprocessing pipeline
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Preprocessed grayscale frame
        """
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        
        # Apply contrast enhancement
        enhanced = cv2.convertScaleAbs(blurred, alpha=self.contrast_alpha, beta=self.contrast_beta)
        
        return enhanced
    
    def preprocess_batch(self, frames: list) -> list:
        """
        Preprocess multiple frames (for background modeling)
        
        Args:
            frames: List of input frames
            
        Returns:
            List of preprocessed frames
        """
        return [self.preprocess(frame) for frame in frames]
    
    def set_parameters(self, 
                    blur_kernel: Optional[int] = None,
                    contrast_alpha: Optional[float] = None,
                    contrast_beta: Optional[int] = None):
        """
        Update preprocessing parameters
        
        Args:
            blur_kernel: New blur kernel size
            contrast_alpha: New contrast scaling factor
            contrast_beta: New brightness offset
        """
        if blur_kernel is not None:
            self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        if contrast_alpha is not None:
            self.contrast_alpha = contrast_alpha
        if contrast_beta is not None:
            self.contrast_beta = contrast_beta
