"""
Tracking module for zebrafish larvae

Implements 2D Kalman filter for temporal smoothing.
Optimized for smooth zebrafish trajectory tracking.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional


class KalmanTracker:
    """2D Kalman filter for zebrafish position tracking"""
    
    def __init__(self, 
                 process_noise: float = 1e-3,
                 measurement_noise: float = 1e-1,
                 error_covariance: float = 1.0):
        """
        Initialize Kalman tracker
        
        Args:
            process_noise: Process noise covariance
            measurement_noise: Measurement noise covariance
            error_covariance: Initial error covariance
        """
        # Initialize Kalman filter for 2D position tracking
        self.kalman = cv2.KalmanFilter(4, 2, 0)
        
        # State: [x, y, vx, vy] (position and velocity)
        # Measurement: [x, y]
        
        # Transition matrix (constant velocity model)
        self.kalman.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], np.float32)
        
        # Measurement matrix (only position is measured)
        self.kalman.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], np.float32)
        
        # Process and measurement noise
        self.kalman.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise
        self.kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * measurement_noise
        
        # Initial error covariance
        self.kalman.errorCovPost = np.eye(4, dtype=np.float32) * error_covariance
        
        # Tracking state
        self.is_initialized = False
        self.last_position = None
        self.missing_count = 0
        self.max_missing_frames = 10
        
    def initialize(self, position: Tuple[float, float]):
        """
        Initialize tracker with first detection
        
        Args:
            position: Initial (x, y) position
        """
        x, y = position
        
        # Set initial state
        self.kalman.statePre = np.array([x, y, 0, 0], dtype=np.float32)
        self.kalman.statePost = np.array([x, y, 0, 0], dtype=np.float32)
        
        self.is_initialized = True
        self.last_position = np.array([x, y])
        self.missing_count = 0
    
    def predict(self) -> np.ndarray:
        """
        Predict next position
        
        Returns:
            Predicted position [x, y]
        """
        if not self.is_initialized:
            return None
        
        # Predict next state
        prediction = self.kalman.predict()
        
        # Return predicted position
        return np.array([prediction[0, 0], prediction[1, 0]])
    
    def update(self, measurement: Optional[Tuple[float, float]], area: float = 0) -> Tuple[np.ndarray, bool]:
        """
        Update tracker with new measurement
        
        Args:
            measurement: New (x, y) measurement or None if missing
            area: Detection area (for confidence)
            
        Returns:
            Tuple of (corrected_position, is_valid)
        """
        if not self.is_initialized:
            if measurement is not None:
                self.initialize(measurement)
                return np.array(measurement), True
            else:
                return None, False
        
        if measurement is not None:
            # Update with measurement
            measurement_array = np.array([[measurement[0]], [measurement[1]]], dtype=np.float32)
            self.kalman.correct(measurement_array)
            
            self.last_position = np.array(measurement)
            self.missing_count = 0
            
            return np.array(measurement), True
        else:
            # No measurement - use prediction only
            prediction = self.predict()
            self.missing_count += 1
            
            # Mark as invalid if missing for too long
            is_valid = self.missing_count < self.max_missing_frames
            
            return prediction, is_valid
    
    def get_velocity(self) -> np.ndarray:
        """
        Get current velocity estimate
        
        Returns:
            Velocity vector [vx, vy]
        """
        if not self.is_initialized:
            return np.array([0, 0])
        
        state = self.kalman.statePost
        return np.array([state[2, 0], state[3, 0]])
    
    def reset(self):
        """Reset tracker state"""
        self.is_initialized = False
        self.last_position = None
        self.missing_count = 0
        
        # Reset Kalman filter
        self.kalman.statePre = np.zeros((4, 1), dtype=np.float32)
        self.kalman.statePost = np.zeros((4, 1), dtype=np.float32)
        self.kalman.errorCovPost = np.eye(4, dtype=np.float32)


class ZebrafishTracker:
    """Main tracking coordinator for zebrafish larvae"""
    
    def __init__(self):
        """Initialize tracker"""
        self.kalman_tracker = KalmanTracker()
        self.trajectory = []
        self.frame_count = 0
        
    def track_frame(self, 
                  detection: Optional[Tuple[float, float]], 
                  area: float = 0,
                  timestamp_ms: int = 0) -> dict:
        """
        Track single frame
        
        Args:
            detection: Detected position (x, y) or None
            area: Detection area
            timestamp_ms: Frame timestamp
            
        Returns:
            Dictionary with tracking data
        """
        self.frame_count += 1
        
        # Update Kalman filter
        position, is_valid = self.kalman_tracker.update(detection, area)
        
        # Get velocity
        velocity = self.kalman_tracker.get_velocity()
        
        # Create tracking record
        record = {
            'frame_id': self.frame_count,
            'timestamp_ms': timestamp_ms,
            'x_px': position[0] if position is not None else None,
            'y_px': position[1] if position is not None else None,
            'area_px': area if is_valid else 0,
            'valid': is_valid,
            'velocity_x': velocity[0],
            'velocity_y': velocity[1]
        }
        
        # Add to trajectory
        self.trajectory.append(record)
        
        return record
    
    def get_trajectory(self) -> List[dict]:
        """
        Get complete trajectory
        
        Returns:
            List of tracking records
        """
        return self.trajectory.copy()
    
    def reset(self):
        """Reset tracker"""
        self.kalman_tracker.reset()
        self.trajectory = []
        self.frame_count = 0
