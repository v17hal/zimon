#!/usr/bin/env python3
"""
Zebrafish Larval Tracking System

Offline classical computer vision tracking for single zebrafish larva.
Processes recorded video files and exports tracking data to CSV.

Usage:
    python track_zebrafish.py input_video.mp4 --output results.csv --pixel-to-mm 0.1

Architecture:
    Input Video → Preprocessing → Background Subtraction → Detection → Tracking → Export
    Analysis modules work on exported CSV data for metrics and visualization
"""

import argparse
import cv2
import numpy as np
import os
import sys
import time
from typing import Tuple, Optional

# Import tracking modules
from tracking.preprocessing import FramePreprocessor
from tracking.background import BackgroundModel
from tracking.detector import FishDetector
from tracking.tracker import ZebrafishTracker
from tracking.exporter import TrackingExporter

# Import analysis modules
from analysis.metrics import ZebrafishAnalyzer
from analysis.plots import plot_trajectory, plot_heatmap, plot_speed_over_time, plot_behavioral_summary


class ZebrafishTrackingPipeline:
    """Main tracking pipeline coordinator"""
    
    def __init__(self, 
                 pixel_to_mm: float = 0.1,
                 roi_mask: Optional[np.ndarray] = None,
                 background_frames: int = 30):
        """
        Initialize tracking pipeline
        
        Args:
            pixel_to_mm: Pixels per millimeter conversion
            roi_mask: Region of interest mask (None = full frame)
            background_frames: Number of frames for background modeling
        """
        self.pixel_to_mm = pixel_to_mm
        self.roi_mask = roi_mask
        
        # Initialize pipeline components
        self.preprocessor = FramePreprocessor(
            blur_kernel=5,
            contrast_alpha=1.2,
            contrast_beta=10
        )
        
        self.background_model = BackgroundModel(num_frames=background_frames)
        
        self.detector = FishDetector(
            min_area=100,
            max_area=3000,
            min_circularity=0.3,
            min_inertia_ratio=0.3
        )
        
        self.tracker = ZebrafishTracker()
        self.exporter = TrackingExporter(
            pixel_to_mm=pixel_to_mm,
            origin_offset=(0, 0)
        )
        
        self.analyzer = ZebrafishAnalyzer(
            pixel_to_mm=pixel_to_mm,
            fps=30.0  # Will be updated from video
        )
    
    def process_video(self, video_path: str, output_dir: str) -> bool:
        """
        Process entire video file
        
        Args:
            video_path: Input video file path
            output_dir: Output directory for results
            
        Returns:
            True if processing successful
        """
        print(f"Processing video: {video_path}")
        print(f"Output directory: {output_dir}")
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video {video_path}")
            return False
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Video properties: {width}x{height}, {fps:.2f} FPS, {frame_count} frames")
        
        # Update analyzer FPS
        self.analyzer.fps = fps
        
        # Initialize background model
        print("Initializing background model...")
        frame_idx = 0
        
        while frame_idx < self.background_model.num_frames and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Apply ROI mask if provided
            if self.roi_mask is not None:
                frame = cv2.bitwise_and(frame, frame, mask=self.roi_mask)
            
            # Preprocess for background modeling
            processed_frame = self.preprocessor.preprocess(frame)
            
            # Add to background model
            if self.background_model.add_frame(processed_frame):
                print(f"Background model initialized with {self.background_model.num_frames} frames")
                break
            
            frame_idx += 1
        
        if not self.background_model.is_initialized:
            print("Error: Could not initialize background model")
            cap.release()
            return False
        
        # Main tracking loop
        print("Starting tracking...")
        trajectory = []
        start_time = time.time()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Get timestamp
            timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
            
            # Apply ROI mask if provided
            if self.roi_mask is not None:
                frame = cv2.bitwise_and(frame, frame, mask=self.roi_mask)
            
            # Preprocess frame
            processed_frame = self.preprocessor.preprocess(frame)
            
            # Background subtraction
            foreground_mask = self.background_model.subtract_background(processed_frame)
            
            # Detect fish
            position, is_valid = self.detector.detect(foreground_mask)
            
            # Track position
            tracking_record = self.tracker.track_frame(
                detection=tuple(position) if position is not None else None,
                area=cv2.contourArea(self.detector._is_valid_shape.__self__) if is_valid else 0,
                timestamp_ms=timestamp_ms
            )
            
            trajectory.append(tracking_record)
            
            # Progress update
            if frame_idx % 100 == 0:
                progress = (frame_idx / frame_count) * 100
                elapsed = time.time() - start_time
                eta = (elapsed / frame_idx) * (frame_count - frame_idx) if frame_idx > 0 else 0
                print(f"Progress: {progress:.1f}% ({frame_idx}/{frame_count}), ETA: {eta:.0f}s")
            
            frame_idx += 1
        
        # Cleanup
        cap.release()
        print(f"Tracking complete. Processed {len(trajectory)} frames.")
        
        # Export results
        return self._export_results(trajectory, output_dir, video_path)
    
    def _export_results(self, trajectory: list, output_dir: str, video_path: str) -> bool:
        """
        Export tracking results and generate analysis
        
        Args:
            trajectory: List of tracking records
            output_dir: Output directory
            video_path: Original video path
            
        Returns:
            True if export successful
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Export raw trajectory
            csv_path = f"{output_dir}/trajectory.csv"
            success = self.exporter.export_trajectory(trajectory, csv_path, include_velocity=True)
            
            if success:
                print(f"Trajectory exported to: {csv_path}")
            else:
                print("Error: Failed to export trajectory")
                return False
            
            # Export summary
            summary_path = f"{output_dir}/summary.csv"
            success = self.exporter.export_summary(trajectory, summary_path)
            
            if success:
                print(f"Summary exported to: {summary_path}")
            
            # Generate plots
            print("Generating analysis plots...")
            
            # Trajectory plot
            traj_plot_path = f"{output_dir}/trajectory.png"
            plot_trajectory(trajectory, traj_plot_path, 
                         pixel_to_mm=self.pixel_to_mm, 
                         show_invalid=False)
            
            # Heatmap
            heatmap_path = f"{output_dir}/heatmap.png"
            plot_heatmap(trajectory, heatmap_path, 
                        pixel_to_mm=self.pixel_to_mm)
            
            # Speed plot
            speed_plot_path = f"{output_dir}/speed_over_time.png"
            plot_speed_over_time(trajectory, speed_plot_path, fps=self.analyzer.fps)
            
            # Behavioral summary
            summary_plot_path = f"{output_dir}/behavioral_summary.png"
            plot_behavioral_summary(trajectory, self.analyzer, output_dir, self.pixel_to_mm)
            
            print(f"Analysis plots saved to: {output_dir}")
            
            # Print summary statistics
            summary = self.analyzer.generate_summary_report(trajectory)
            self._print_summary(summary, video_path)
            
            return True
            
        except Exception as e:
            print(f"Error during export: {e}")
            return False
    
    def _print_summary(self, summary: dict, video_path: str):
        """
        Print tracking summary to console
        
        Args:
            summary: Analysis summary dictionary
            video_path: Original video path
        """
        print("\n" + "="*50)
        print("ZEBRAFISH TRACKING SUMMARY")
        print("="*50)
        print(f"Video: {os.path.basename(video_path)}")
        
        # Tracking summary
        tracking = summary['tracking_summary']
        print(f"\nTracking Performance:")
        print(f"  Total frames: {tracking['total_frames']}")
        print(f"  Valid tracks: {tracking['valid_frames']}")
        print(f"  Success rate: {tracking['tracking_success_rate']:.1f}%")
        
        # Distance metrics
        distance = summary['distance_metrics']
        print(f"\nMovement Metrics:")
        print(f"  Total distance: {distance['total_distance_mm']:.2f} mm")
        print(f"  Net displacement: {distance['net_displacement_mm']:.2f} mm")
        print(f"  Mean speed: {distance['mean_speed_mm_per_s']:.2f} mm/s")
        print(f"  Max speed: {distance['max_speed_mm_per_s']:.2f} mm/s")
        print(f"  Tracking efficiency: {distance['tracking_efficiency']:.1f}%")
        
        # Immobility
        immobility = summary['immobility_metrics']
        print(f"\nImmobility Analysis:")
        print(f"  Immobile frames: {immobility['immobile_frames']}")
        print(f"  Mobile frames: {immobility['mobile_frames']}")
        print(f"  Immobility: {immobility['immobility_percentage']:.1f}%")
        print(f"  Threshold: {immobility['threshold_mm_per_s']} mm/s")
        
        print("="*50)


def main():
    """Main function for zebrafish tracking"""
    parser = argparse.ArgumentParser(
        description="Zebrafish Larval Tracking System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python track_zebrafish.py video.mp4
  python track_zebrafish.py video.mp4 --output results.csv --pixel-to-mm 0.1
  python track_zebrafish.py video.mp4 --roi-mask roi.png --background-frames 50
        """
    )
    
    parser.add_argument('video_path', help='Input video file path')
    parser.add_argument('--output', '-o', default='trajectory.csv',
                       help='Output CSV file path (default: trajectory.csv)')
    parser.add_argument('--pixel-to-mm', type=float, default=0.1,
                       help='Pixels per millimeter conversion (default: 0.1)')
    parser.add_argument('--roi-mask', help='ROI mask image path (optional)')
    parser.add_argument('--background-frames', type=int, default=30,
                       help='Number of frames for background modeling (default: 30)')
    parser.add_argument('--output-dir', default='tracking_results',
                       help='Output directory for results (default: tracking_results)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.video_path):
        print(f"Error: Video file not found: {args.video_path}")
        sys.exit(1)
    
    # Load ROI mask if provided
    roi_mask = None
    if args.roi_mask:
        if os.path.exists(args.roi_mask):
            roi_mask = cv2.imread(args.roi_mask, cv2.IMREAD_GRAYSCALE)
            roi_mask = (roi_mask > 128).astype(np.uint8) * 255
            print(f"Loaded ROI mask: {args.roi_mask}")
        else:
            print(f"Warning: ROI mask not found: {args.roi_mask}")
    
    # Create tracking pipeline
    pipeline = ZebrafishTrackingPipeline(
        pixel_to_mm=args.pixel_to_mm,
        roi_mask=roi_mask,
        background_frames=args.background_frames
    )
    
    # Process video
    success = pipeline.process_video(args.video_path, args.output_dir)
    
    if success:
        print(f"\nTracking completed successfully!")
        print(f"Results saved to: {args.output_dir}")
        sys.exit(0)
    else:
        print(f"\nTracking failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
