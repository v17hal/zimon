"""
CSV export module for zebrafish tracking

Exports tracking data to CSV format with pixel-to-mm conversion.
Handles coordinate transformation and validation.
"""

import csv
import numpy as np
from typing import List, Dict, Optional, Tuple


class TrackingExporter:
    """Export zebrafish tracking data to CSV"""
    
    def __init__(self, pixel_to_mm: float = 1.0, origin_offset: Tuple[float, float] = (0, 0)):
        """
        Initialize exporter
        
        Args:
            pixel_to_mm: Conversion factor (pixels per mm)
            origin_offset: (x_offset, y_offset) for coordinate system origin
        """
        self.pixel_to_mm = pixel_to_mm
        self.origin_x, self.origin_y = origin_offset
        
    def export_trajectory(self, 
                      trajectory: List[Dict], 
                      output_path: str,
                      include_velocity: bool = False) -> bool:
        """
        Export trajectory to CSV file
        
        Args:
            trajectory: List of tracking records
            output_path: Output CSV file path
            include_velocity: Whether to include velocity columns
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            with open(output_path, 'w', newline='') as csvfile:
                # Define CSV headers
                headers = ['frame_id', 'timestamp_ms', 'x_px', 'y_px', 'x_mm', 'y_mm', 'area_px', 'valid']
                
                if include_velocity:
                    headers.extend(['velocity_x_px', 'velocity_y_px'])
                
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                
                # Write tracking data
                for record in trajectory:
                    # Convert pixel coordinates to mm
                    if record['x_px'] is not None and record['y_px'] is not None:
                        x_mm = (record['x_px'] - self.origin_x) / self.pixel_to_mm
                        y_mm = (record['y_px'] - self.origin_y) / self.pixel_to_mm
                    else:
                        x_mm = None
                        y_mm = None
                    
                    # Create CSV row
                    row = {
                        'frame_id': record['frame_id'],
                        'timestamp_ms': record['timestamp_ms'],
                        'x_px': record['x_px'],
                        'y_px': record['y_px'],
                        'x_mm': x_mm,
                        'y_mm': y_mm,
                        'area_px': record['area_px'],
                        'valid': record['valid']
                    }
                    
                    if include_velocity:
                        row['velocity_x_px'] = record.get('velocity_x', 0)
                        row['velocity_y_px'] = record.get('velocity_y', 0)
                    
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting trajectory: {e}")
            return False
    
    def export_summary(self, 
                   trajectory: List[Dict], 
                   output_path: str) -> bool:
        """
        Export tracking summary statistics
        
        Args:
            trajectory: List of tracking records
            output_path: Output summary file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            # Calculate statistics
            valid_frames = [r for r in trajectory if r['valid']]
            total_frames = len(trajectory)
            
            if valid_frames:
                x_positions = [r['x_px'] for r in valid_frames if r['x_px'] is not None]
                y_positions = [r['y_px'] for r in valid_frames if r['y_px'] is not None]
                areas = [r['area_px'] for r in valid_frames]
                
                # Movement statistics
                if len(x_positions) > 1:
                    distances = []
                    for i in range(1, len(x_positions)):
                        dx = x_positions[i] - x_positions[i-1]
                        dy = y_positions[i] - y_positions[i-1]
                        distance = np.sqrt(dx*dx + dy*dy)
                        distances.append(distance)
                    
                    total_distance = sum(distances)
                    avg_distance = np.mean(distances)
                    max_distance = max(distances) if distances else 0
                else:
                    total_distance = avg_distance = max_distance = 0
                
                summary = {
                    'total_frames': total_frames,
                    'valid_frames': len(valid_frames),
                    'tracking_success_rate': len(valid_frames) / total_frames * 100,
                    'total_distance_px': total_distance,
                    'avg_distance_per_frame_px': avg_distance,
                    'max_distance_per_frame_px': max_distance,
                    'avg_area_px': np.mean(areas) if areas else 0,
                    'min_area_px': min(areas) if areas else 0,
                    'max_area_px': max(areas) if areas else 0
                }
            else:
                summary = {
                    'total_frames': total_frames,
                    'valid_frames': 0,
                    'tracking_success_rate': 0,
                    'total_distance_px': 0,
                    'avg_distance_per_frame_px': 0,
                    'max_distance_per_frame_px': 0,
                    'avg_area_px': 0,
                    'min_area_px': 0,
                    'max_area_px': 0
                }
            
            # Write summary to CSV
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=summary.keys())
                writer.writeheader()
                writer.writerow(summary)
            
            return True
            
        except Exception as e:
            print(f"Error exporting summary: {e}")
            return False
    
    def set_calibration(self, pixel_to_mm: float, origin_offset: Tuple[float, float] = (0, 0)):
        """
        Update calibration parameters
        
        Args:
            pixel_to_mm: New pixels per mm conversion
            origin_offset: New (x_offset, y_offset) for origin
        """
        self.pixel_to_mm = pixel_to_mm
        self.origin_x, self.origin_y = origin_offset
