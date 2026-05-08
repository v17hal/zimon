"""
Analysis metrics module for zebrafish tracking

Provides comprehensive behavioral analysis functions.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from . import ZebrafishAnalyzer


def calculate_activity_bouts(trajectory: List[Dict], 
                          min_speed_threshold: float = 5.0,
                          min_duration_frames: int = 5) -> List[Dict]:
    """
    Detect activity bouts (periods of sustained movement)
    
    Args:
        trajectory: List of tracking records
        min_speed_threshold: Minimum speed to consider active (mm/s)
        min_duration_frames: Minimum frames for valid bout
        
    Returns:
        List of activity bout information
    """
    bouts = []
    current_bout = None
    
    for i, frame in enumerate(trajectory):
        if not frame['valid']:
            if current_bout:
                current_bout['end_frame'] = i - 1
                current_bout['duration_frames'] = current_bout['end_frame'] - current_bout['start_frame']
                if current_bout['duration_frames'] >= min_duration_frames:
                    bouts.append(current_bout)
                current_bout = None
            continue
        
        speed = frame.get('speed_mm_per_s', 0)
        
        if speed >= min_speed_threshold:
            if current_bout is None:
                # Start new bout
                current_bout = {
                    'start_frame': i,
                    'start_time_ms': frame['timestamp_ms'],
                    'max_speed': speed,
                    'mean_speed': speed,
                    'distance': 0
                }
            else:
                # Continue current bout
                current_bout['max_speed'] = max(current_bout['max_speed'], speed)
                current_bout['mean_speed'] = (current_bout['mean_speed'] + speed) / 2
                current_bout['distance'] += frame.get('displacement_mm', 0)
        else:
            if current_bout:
                # End current bout
                current_bout['end_frame'] = i - 1
                current_bout['end_time_ms'] = trajectory[i-1]['timestamp_ms']
                current_bout['duration_frames'] = current_bout['end_frame'] - current_bout['start_frame']
                current_bout['duration_ms'] = current_bout['end_time_ms'] - current_bout['start_time_ms']
                
                if current_bout['duration_frames'] >= min_duration_frames:
                    bouts.append(current_bout)
                current_bout = None
    
    return bouts


def calculate_thigmotaxis(trajectory: List[Dict], 
                        arena_center: Tuple[float, float],
                        arena_radius: float,
                        pixel_to_mm: float = 1.0) -> Dict:
    """
    Calculate thigmotaxis (wall preference) metric
    
    Args:
        trajectory: List of tracking records
        arena_center: (center_x, center_y) in pixels
        arena_radius: Arena radius in pixels
        pixel_to_mm: Conversion factor
        
    Returns:
        Dictionary with thigmotaxis metrics
    """
    valid_frames = [r for r in trajectory if r['valid'] and r['x_px'] is not None]
    
    if not valid_frames:
        return {'thigmotaxis_index': 0, 'time_in_center': 0, 'time_in_periphery': 0}
    
    center_x, center_y = arena_center
    center_zone_radius = arena_radius * 0.5  # Define center zone
    
    center_frames = 0
    periphery_frames = 0
    
    for frame in valid_frames:
        x, y = frame['x_px'], frame['y_px']
        
        # Calculate distance from center
        distance_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        if distance_from_center <= center_zone_radius:
            center_frames += 1
        else:
            periphery_frames += 1
    
    total_frames = len(valid_frames)
    time_in_center = center_frames / total_frames * 100 if total_frames > 0 else 0
    time_in_periphery = periphery_frames / total_frames * 100 if total_frames > 0 else 0
    
    # Thigmotaxis index (preference for periphery)
    thigmotaxis_index = time_in_periphery / 100 if total_frames > 0 else 0
    
    return {
        'thigmotaxis_index': thigmotaxis_index,
        'time_in_center': time_in_center,
        'time_in_periphery': time_in_periphery,
        'center_frames': center_frames,
        'periphery_frames': periphery_frames,
        'total_frames': total_frames
    }


def calculate_angular_velocity(trajectory: List[Dict]) -> List[Dict]:
    """
    Calculate angular velocity and turning behavior
    
    Args:
        trajectory: List of tracking records
        
    Returns:
        List with angular velocity information
    """
    for i in range(1, len(trajectory)):
        prev_frame = trajectory[i-1]
        curr_frame = trajectory[i]
        
        if (prev_frame['valid'] and curr_frame['valid'] and 
            prev_frame['x_px'] is not None and curr_frame['x_px'] is not None):
            
            # Calculate direction vectors
            prev_vx = prev_frame.get('velocity_x', 0)
            prev_vy = prev_frame.get('velocity_y', 0)
            curr_vx = curr_frame.get('velocity_x', 0)
            curr_vy = curr_frame.get('velocity_y', 0)
            
            # Calculate angles
            prev_angle = np.arctan2(prev_vy, prev_vx)
            curr_angle = np.arctan2(curr_vy, curr_vx)
            
            # Angular change
            angle_change = curr_angle - prev_angle
            
            # Normalize to [-pi, pi]
            while angle_change > np.pi:
                angle_change -= 2 * np.pi
            while angle_change < -np.pi:
                angle_change += 2 * np.pi
            
            # Angular velocity (rad/s)
            dt = (curr_frame['timestamp_ms'] - prev_frame['timestamp_ms']) / 1000.0
            angular_velocity = angle_change / dt if dt > 0 else 0
            
            # Convert to degrees/s
            angular_velocity_deg = np.degrees(angular_velocity)
            
            # Add to frame data
            trajectory[i]['angular_velocity_rad_per_s'] = angular_velocity
            trajectory[i]['angular_velocity_deg_per_s'] = angular_velocity_deg
            trajectory[i]['angle_change_rad'] = angle_change
            trajectory[i]['angle_change_deg'] = np.degrees(angle_change)
        else:
            trajectory[i]['angular_velocity_rad_per_s'] = 0
            trajectory[i]['angular_velocity_deg_per_s'] = 0
            trajectory[i]['angle_change_rad'] = 0
            trajectory[i]['angle_change_deg'] = 0
    
    return trajectory
