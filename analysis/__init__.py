"""
Analysis module for zebrafish tracking

Calculates behavioral metrics from tracking data.
Includes speed, distance, and immobility analysis.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional


class ZebrafishAnalyzer:
    """Analyze zebrafish tracking data"""
    
    def __init__(self, pixel_to_mm: float = 1.0, fps: float = 30.0):
        """
        Initialize analyzer
        
        Args:
            pixel_to_mm: Conversion factor (pixels per mm)
            fps: Video frame rate for time calculations
        """
        self.pixel_to_mm = pixel_to_mm
        self.fps = fps
        
    def calculate_speed(self, trajectory: List[Dict]) -> List[Dict]:
        """
        Calculate instantaneous speed for each frame
        
        Args:
            trajectory: List of tracking records
            
        Returns:
            List with speed information added
        """
        if len(trajectory) < 2:
            return trajectory
        
        # Calculate speed for each frame
        for i in range(1, len(trajectory)):
            prev_frame = trajectory[i-1]
            curr_frame = trajectory[i]
            
            if (prev_frame['valid'] and curr_frame['valid'] and 
                prev_frame['x_px'] is not None and curr_frame['x_px'] is not None):
                
                # Calculate displacement in pixels
                dx = curr_frame['x_px'] - prev_frame['x_px']
                dy = curr_frame['y_px'] - prev_frame['y_px']
                displacement_px = np.sqrt(dx*dx + dy*dy)
                
                # Convert to mm
                displacement_mm = displacement_px / self.pixel_to_mm
                
                # Calculate time difference (seconds)
                dt = (curr_frame['timestamp_ms'] - prev_frame['timestamp_ms']) / 1000.0
                if dt <= 0:
                    dt = 1.0 / self.fps  # Fallback to frame rate
                
                # Calculate speed (mm/s)
                speed_mm_per_s = displacement_mm / dt if dt > 0 else 0
                speed_cm_per_s = speed_mm_per_s / 10.0
                
                # Add to frame data
                trajectory[i]['speed_mm_per_s'] = speed_mm_per_s
                trajectory[i]['speed_cm_per_s'] = speed_cm_per_s
                trajectory[i]['displacement_px'] = displacement_px
                trajectory[i]['displacement_mm'] = displacement_mm
            else:
                trajectory[i]['speed_mm_per_s'] = 0
                trajectory[i]['speed_cm_per_s'] = 0
                trajectory[i]['displacement_px'] = 0
                trajectory[i]['displacement_mm'] = 0
        
        return trajectory
    
    def calculate_distance_metrics(self, trajectory: List[Dict]) -> Dict:
        """
        Calculate distance-related metrics
        
        Args:
            trajectory: List of tracking records
            
        Returns:
            Dictionary with distance metrics
        """
        valid_frames = [r for r in trajectory if r['valid']]
        
        if len(valid_frames) < 2:
            return {
                'total_distance_mm': 0,
                'net_displacement_mm': 0,
                'mean_speed_mm_per_s': 0,
                'max_speed_mm_per_s': 0,
                'total_duration_s': 0
            }
        
        # Calculate total distance traveled
        total_distance_px = 0
        speeds = []
        
        for i in range(1, len(valid_frames)):
            prev_frame = valid_frames[i-1]
            curr_frame = valid_frames[i]
            
            # Distance in pixels
            dx = curr_frame['x_px'] - prev_frame['x_px']
            dy = curr_frame['y_px'] - prev_frame['y_px']
            distance_px = np.sqrt(dx*dx + dy*dy)
            total_distance_px += distance_px
            
            # Speed (if available)
            if 'speed_mm_per_s' in curr_frame:
                speeds.append(curr_frame['speed_mm_per_s'])
        
        # Convert to mm
        total_distance_mm = total_distance_px / self.pixel_to_mm
        
        # Net displacement (start to end)
        if len(valid_frames) >= 2:
            start_x = valid_frames[0]['x_px']
            start_y = valid_frames[0]['y_px']
            end_x = valid_frames[-1]['x_px']
            end_y = valid_frames[-1]['y_px']
            
            net_dx = end_x - start_x
            net_dy = end_y - start_y
            net_displacement_px = np.sqrt(net_dx*net_dx + net_dy*net_dy)
            net_displacement_mm = net_displacement_px / self.pixel_to_mm
        else:
            net_displacement_mm = 0
        
        # Duration
        start_time = valid_frames[0]['timestamp_ms'] / 1000.0
        end_time = valid_frames[-1]['timestamp_ms'] / 1000.0
        total_duration_s = end_time - start_time
        
        # Speed statistics
        mean_speed_mm_per_s = np.mean(speeds) if speeds else 0
        max_speed_mm_per_s = max(speeds) if speeds else 0
        
        return {
            'total_distance_mm': total_distance_mm,
            'net_displacement_mm': net_displacement_mm,
            'mean_speed_mm_per_s': mean_speed_mm_per_s,
            'max_speed_mm_per_s': max_speed_mm_per_s,
            'total_duration_s': total_duration_s,
            'tracking_efficiency': (net_displacement_mm / total_distance_mm * 100) if total_distance_mm > 0 else 0
        }
    
    def calculate_immobility(self, trajectory: List[Dict], threshold_mm_per_s: float = 1.0) -> Dict:
        """
        Calculate immobility metrics
        
        Args:
            trajectory: List of tracking records
            threshold_mm_per_s: Speed threshold for immobility (mm/s)
            
        Returns:
            Dictionary with immobility metrics
        """
        valid_frames = [r for r in trajectory if r['valid']]
        
        if not valid_frames:
            return {
                'immobile_frames': 0,
                'mobile_frames': 0,
                'immobility_percentage': 0,
                'total_frames': len(trajectory)
            }
        
        # Count immobile frames
        immobile_count = 0
        for frame in valid_frames:
            speed = frame.get('speed_mm_per_s', 0)
            if speed <= threshold_mm_per_s:
                immobile_count += 1
        
        mobile_count = len(valid_frames) - immobile_count
        total_frames = len(trajectory)
        immobility_percentage = (immobile_count / total_frames * 100) if total_frames > 0 else 0
        
        return {
            'immobile_frames': immobile_count,
            'mobile_frames': mobile_count,
            'immobility_percentage': immobility_percentage,
            'total_frames': total_frames,
            'threshold_mm_per_s': threshold_mm_per_s
        }
    
    def generate_summary_report(self, trajectory: List[Dict]) -> Dict:
        """
        Generate comprehensive analysis summary
        
        Args:
            trajectory: List of tracking records
            
        Returns:
            Dictionary with all metrics
        """
        # Calculate all metrics
        trajectory_with_speed = self.calculate_speed(trajectory)
        distance_metrics = self.calculate_distance_metrics(trajectory_with_speed)
        immobility_metrics = self.calculate_immobility(trajectory_with_speed)
        
        # Combine all metrics
        summary = {
            'tracking_summary': {
                'total_frames': len(trajectory),
                'valid_frames': len([r for r in trajectory if r['valid']]),
                'tracking_success_rate': len([r for r in trajectory if r['valid']]) / len(trajectory) * 100
            },
            'distance_metrics': distance_metrics,
            'immobility_metrics': immobility_metrics
        }
        
        return summary
