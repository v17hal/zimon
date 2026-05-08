"""
Plotting module for zebrafish tracking analysis

Generates trajectory plots, heatmaps, and behavioral visualizations.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import seaborn as sns
from typing import List, Dict, Tuple, Optional
from . import ZebrafishAnalyzer


def plot_trajectory(trajectory: List[Dict], 
                  output_path: str,
                  arena_size: Tuple[float, float] = (100, 100),
                  pixel_to_mm: float = 1.0,
                  show_invalid: bool = False) -> bool:
    """
    Plot zebrafish trajectory
    
    Args:
        trajectory: List of tracking records
        output_path: Output image path
        arena_size: (width_mm, height_mm) of arena
        pixel_to_mm: Conversion factor
        show_invalid: Whether to show invalid tracking points
        
    Returns:
        True if plot saved successfully
    """
    try:
        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        
        # Separate valid and invalid points
        valid_frames = [r for r in trajectory if r['valid']]
        invalid_frames = [r for r in trajectory if not r['valid']] if show_invalid else []
        
        # Convert to mm coordinates
        if valid_frames:
            valid_x = [(r['x_px'] / pixel_to_mm) for r in valid_frames if r['x_px'] is not None]
            valid_y = [(r['y_px'] / pixel_to_mm) for r in valid_frames if r['y_px'] is not None]
            ax.scatter(valid_x, valid_y, c='blue', s=1, alpha=0.6, label='Valid tracking')
        
        if invalid_frames and show_invalid:
            invalid_x = [(r['x_px'] / pixel_to_mm) for r in invalid_frames if r['x_px'] is not None]
            invalid_y = [(r['y_px'] / pixel_to_mm) for r in invalid_frames if r['y_px'] is not None]
            ax.scatter(invalid_x, invalid_y, c='red', s=1, alpha=0.3, label='Invalid tracking')
        
        # Plot arena boundary
        arena_width, arena_height = arena_size
        arena_rect = patches.Rectangle((0, 0), arena_width, arena_height, 
                                 linewidth=2, edgecolor='black', facecolor='none')
        ax.add_patch(arena_rect)
        
        # Formatting
        ax.set_xlim(0, arena_width)
        ax.set_ylim(0, arena_height)
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')
        ax.set_title('Zebrafish Trajectory')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error plotting trajectory: {e}")
        return False


def plot_heatmap(trajectory: List[Dict], 
                output_path: str,
                arena_size: Tuple[float, float] = (100, 100),
                pixel_to_mm: float = 1.0,
                grid_size: int = 50) -> bool:
    """
    Plot position heatmap
    
    Args:
        trajectory: List of tracking records
        output_path: Output image path
        arena_size: (width_mm, height_mm) of arena
        pixel_to_mm: Conversion factor
        grid_size: Grid resolution for heatmap
        
    Returns:
        True if plot saved successfully
    """
    try:
        # Get valid positions
        valid_frames = [r for r in trajectory if r['valid']]
        
        if not valid_frames:
            return False
        
        # Convert to mm coordinates
        x_positions = [(r['x_px'] / pixel_to_mm) for r in valid_frames if r['x_px'] is not None]
        y_positions = [(r['y_px'] / pixel_to_mm) for r in valid_frames if r['y_px'] is not None]
        
        # Create 2D histogram
        arena_width, arena_height = arena_size
        
        heatmap, xedges, yedges = np.histogram2d(
            x_positions, y_positions,
            bins=grid_size,
            range=[[0, arena_width], [0, arena_height]]
        )
        
        # Plot heatmap
        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        
        im = ax.imshow(heatmap.T, origin='lower', cmap='hot', interpolation='gaussian',
                     extent=[0, arena_width, 0, arena_height])
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Time Spent (arbitrary units)')
        
        # Formatting
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')
        ax.set_title('Zebrafish Position Heatmap')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error plotting heatmap: {e}")
        return False


def plot_speed_over_time(trajectory: List[Dict], 
                       output_path: str,
                       fps: float = 30.0) -> bool:
    """
    Plot speed vs time
    
    Args:
        trajectory: List of tracking records
        output_path: Output image path
        fps: Video frame rate
        
    Returns:
        True if plot saved successfully
    """
    try:
        # Prepare data
        valid_frames = [r for r in trajectory if r['valid']]
        
        if not valid_frames:
            return False
        
        # Convert to time in seconds
        times = [(r['timestamp_ms'] / 1000.0) for r in valid_frames]
        speeds = [r.get('speed_mm_per_s', 0) for r in valid_frames]
        
        # Plot
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        
        ax.plot(times, speeds, 'b-', linewidth=1, alpha=0.7)
        ax.fill_between(times, 0, speeds, alpha=0.3)
        
        # Formatting
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Speed (mm/s)')
        ax.set_title('Zebrafish Speed Over Time')
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        mean_speed = np.mean(speeds)
        ax.axhline(y=mean_speed, color='r', linestyle='--', alpha=0.7, label=f'Mean: {mean_speed:.2f} mm/s')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error plotting speed: {e}")
        return False


def plot_behavioral_summary(trajectory: List[Dict], 
                         analyzer: ZebrafishAnalyzer,
                         output_dir: str,
                         pixel_to_mm: float = 1.0) -> bool:
    """
    Generate comprehensive behavioral summary plots
    
    Args:
        trajectory: List of tracking records
        analyzer: ZebrafishAnalyzer instance
        output_dir: Directory to save plots
        pixel_to_mm: Conversion factor
        
    Returns:
        True if all plots saved successfully
    """
    try:
        # Calculate metrics
        summary = analyzer.generate_summary_report(trajectory)
        
        # Create multi-panel figure
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Zebrafish Behavioral Analysis Summary', fontsize=16)
        
        # 1. Trajectory plot
        ax1 = axes[0, 0]
        valid_frames = [r for r in trajectory if r['valid']]
        if valid_frames:
            x_pos = [(r['x_px'] / pixel_to_mm) for r in valid_frames if r['x_px'] is not None]
            y_pos = [(r['y_px'] / pixel_to_mm) for r in valid_frames if r['y_px'] is not None]
            ax1.scatter(x_pos, y_pos, c='blue', s=0.5, alpha=0.6)
        ax1.set_xlabel('X Position (mm)')
        ax1.set_ylabel('Y Position (mm)')
        ax1.set_title('Trajectory')
        ax1.grid(True, alpha=0.3)
        
        # 2. Speed distribution
        ax2 = axes[0, 1]
        speeds = [r.get('speed_mm_per_s', 0) for r in valid_frames]
        if speeds:
            ax2.hist(speeds, bins=30, alpha=0.7, color='green', edgecolor='black')
            ax2.axvline(np.mean(speeds), color='red', linestyle='--', label=f'Mean: {np.mean(speeds):.2f}')
            ax2.legend()
        ax2.set_xlabel('Speed (mm/s)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Speed Distribution')
        ax2.grid(True, alpha=0.3)
        
        # 3. Distance metrics bar chart
        ax3 = axes[1, 0]
        distance_metrics = summary['distance_metrics']
        metrics = ['Total Distance\n(mm)', 'Net Displacement\n(mm)', 'Mean Speed\n(mm/s)', 'Max Speed\n(mm/s)']
        values = [
            distance_metrics['total_distance_mm'],
            distance_metrics['net_displacement_mm'],
            distance_metrics['mean_speed_mm_per_s'],
            distance_metrics['max_speed_mm_per_s']
        ]
        colors = ['blue', 'green', 'orange', 'red']
        
        bars = ax3.bar(metrics, values, color=colors, alpha=0.7)
        ax3.set_ylabel('Value')
        ax3.set_title('Distance & Speed Metrics')
        ax3.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                     f'{value:.1f}', ha='center', va='bottom')
        
        # 4. Immobility pie chart
        ax4 = axes[1, 1]
        immobility_metrics = summary['immobility_metrics']
        sizes = [immobility_metrics['mobile_frames'], immobility_metrics['immobile_frames']]
        labels = ['Mobile', 'Immobile']
        colors = ['lightgreen', 'lightcoral']
        
        wedges, texts, autotexts = ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%')
        ax4.set_title(f'Imobility (Threshold: {immobility_metrics["threshold_mm_per_s"]} mm/s)')
        
        plt.tight_layout()
        
        # Save combined plot
        summary_path = f"{output_dir}/behavioral_summary.png"
        plt.savefig(summary_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error creating summary plots: {e}")
        return False
