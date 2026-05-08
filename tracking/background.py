"""
Background modeling module for zebrafish tracking

Creates background model using median of first N frames.
Optimized for stable laboratory conditions.
"""

import cv2
import numpy as np
from typing import Optional, List


class BackgroundModel:
    """Background model using median of initial frames"""
    
    def __init__(self, num_frames: int = 30):
        """
        Initialize background model
        
        Args:
            num_frames: Number of frames to use for median calculation
        """
        self.num_frames = num_frames
        self.background_frame = None
        self.frame_buffer = []
        self.is_initialized = False
        
    def add_frame(self, frame: np.ndarray) -> bool:
        """
        Add frame to background model buffer
        
        Args:
            frame: Grayscale frame to add
            
        Returns:
            True if background model is ready, False otherwise
        """
        self.frame_buffer.append(frame.copy())
        
        if len(self.frame_buffer) >= self.num_frames:
            # Calculate median background
            self.background_frame = np.median(self.frame_buffer, axis=0).astype(np.uint8)
            self.is_initialized = True
            return True
        
        return False
    
    def get_background(self) -> Optional[np.ndarray]:
        """
        Get current background model
        
        Returns:
            Background frame or None if not initialized
        """
        return self.background_frame if self.is_initialized else None
    
    def subtract_background(self, frame: np.ndarray) -> np.ndarray:
        """
        Subtract background from frame
        
        Args:
            frame: Current grayscale frame
            
        Returns:
            Background subtracted frame (foreground mask)
        """
        if not self.is_initialized:
            return frame.copy()
        
        # Background subtraction
        diff = cv2.absdiff(frame, self.background_frame)
        
        # Threshold to create binary mask
        _, foreground_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        return foreground_mask
    
    def update_background(self, new_frames: List[np.ndarray]):
        """
        Update background model with new frames
        
        Args:
            new_frames: List of new frames for background update
        """
        if len(new_frames) >= self.num_frames:
            self.frame_buffer = new_frames.copy()
            self.background_frame = np.median(self.frame_buffer, axis=0).astype(np.uint8)
    
    def reset(self):
        """Reset background model"""
        self.frame_buffer = []
        self.background_frame = None
        self.is_initialized = False
    
    def get_progress(self) -> float:
        """
        Get background model initialization progress
        
        Returns:
            Progress percentage (0.0 to 1.0)
        """
        return min(len(self.frame_buffer) / self.num_frames, 1.0)
