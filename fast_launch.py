#!/usr/bin/env python3
"""
ZIMON Fast Launch Script
Optimized startup with performance improvements
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging for faster startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override existing configuration
)

# Disable unnecessary logging for faster startup
logging.getLogger("PyQt6").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

def optimize_python_performance():
    """Apply Python performance optimizations"""
    import gc
    gc.set_threshold(700, 10, 10)  # Optimize garbage collection
    
    # Set environment variables for better performance
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    os.environ['QT_SCALE_FACTOR'] = '1'

def check_dependencies():
    """Quick dependency check"""
    try:
        import PyQt6
        import cv2
        import numpy
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def main():
    """Main launch function"""
    print("🚀 ZIMON - Fast Launch")
    print("=" * 40)
    
    # Apply performance optimizations
    optimize_python_performance()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    try:
        # Import main application
        from gui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Create application with optimized settings
        app = QApplication(sys.argv)
        
        # Set application style for better performance
        app.setStyle('Fusion')
        
        print("✅ Starting ZIMON application...")
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        print("✅ ZIMON application started successfully!")
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Failed to start ZIMON: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
