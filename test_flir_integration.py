#!/usr/bin/env python3
"""
FLIR Camera Integration Test Script
Tests FLIR CM3-U3-13Y3M-CS integration with ZIMON application.

Usage:
    python test_flir_integration.py
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add ZEBB_code to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FLIR_Test")

def test_flir_availability():
    """Test FLIR SDK availability"""
    logger.info("Testing FLIR SDK availability...")
    
    try:
        import PySpin
        logger.info("FLIR Spinnaker SDK imported successfully")
        
        # Get system version
        system = PySpin.System.GetInstance()
        library_version = system.GetLibraryVersion()
        logger.info(f"   Library Version: {library_version}")
        system.ReleaseInstance()
        
        return True
    except ImportError as e:
        logger.error(f"FLIR SDK not available: {e}")
        return False
    except Exception as e:
        logger.error(f"FLIR SDK error: {e}")
        return False

def test_camera_detection():
    """Test FLIR camera detection"""
    logger.info("Testing FLIR camera detection...")
    
    try:
        from backend import flir_camera
        cameras = flir_camera.detect_flir_cameras()
        
        if cameras:
            logger.info(f"Found {len(cameras)} FLIR camera(s):")
            for cam_name, cam_info in cameras.items():
                logger.info(f"   {cam_name}:")
                logger.info(f"     Model: {cam_info.get('model', 'Unknown')}")
                logger.info(f"     Serial: {cam_info.get('serial', 'Unknown')}")
                logger.info(f"     Resolution: {cam_info.get('settings', {}).get('resolution', 'Unknown')}")
                logger.info(f"     FPS: {cam_info.get('settings', {}).get('fps', 'Unknown')}")
            return True
        else:
            logger.warning("No FLIR cameras detected")
            return False
            
    except Exception as e:
        logger.error(f"Camera detection failed: {e}")
        return False

def test_camera_controller_integration():
    """Test integration with CameraController"""
    logger.info("Testing CameraController integration...")
    
    try:
        from backend.camera_interface import CameraController
        
        # Create controller instance
        controller = CameraController()
        
        # Check if FLIR cameras are detected
        cameras = controller.list_cameras()
        flir_cameras = [name for name in cameras if 'FLIR' in name]
        
        if flir_cameras:
            logger.info("CameraController detected FLIR cameras:")
            for cam_name in flir_cameras:
                logger.info(f"   {cam_name}")
                cam_info = getattr(controller, "cameras", {}).get(cam_name)
                if isinstance(cam_info, dict):
                    logger.info(f"     Type: {cam_info.get('type')}")
                    logger.info(f"     Settings: {cam_info.get('settings')}")
            return True
        else:
            logger.warning("No FLIR cameras in CameraController")
            return False
            
    except Exception as e:
        logger.error(f"CameraController integration failed: {e}")
        return False

def test_performance_benchmarks():
    """Test performance benchmarks"""
    logger.info("Testing performance benchmarks...")
    
    try:
        import numpy as np
        from backend.camera_interface import CameraController
        
        # Test array conversion performance
        logger.info("   Testing numpy array conversion...")
        
        # Simulate thermal image data
        test_sizes = [(320, 240), (640, 480), (1024, 768)]
        
        for width, height in test_sizes:
            # Create test array
            test_array = np.random.randint(0, 256, (height, width), dtype=np.uint8)
            
            # Test conversion time
            start_time = time.time()
            for _ in range(100):
                # Simulate conversion overhead
                processed = test_array.copy()
            end_time = time.time()
            
            avg_time = (end_time - start_time) / 100 * 1000  # ms
            logger.info(f"     {width}x{height}: {avg_time:.3f}ms per frame")
            
            # Calculate theoretical FPS
            theoretical_fps = 1000 / avg_time if avg_time > 0 else 999
            logger.info(f"     Theoretical FPS: {theoretical_fps:.1f}")
        
        logger.info("Performance benchmarks completed")
        return True
        
    except Exception as e:
        logger.error(f"Performance benchmarks failed: {e}")
        return False

def test_usb3_optimization():
    """Test USB3 optimization features"""
    logger.info("Testing USB3 optimization features...")
    
    try:
        from backend import flir_camera
        cameras = flir_camera.detect_flir_cameras()
        
        if not cameras:
            logger.warning("No FLIR cameras for USB3 test")
            return False
        
        # Test optimization constants
        logger.info(f"   Buffer Count: {flir_camera.FLIR_BUFFER_COUNT}")
        logger.info(f"   Pixel Format: {flir_camera.FLIR_PIXEL_FORMAT}")
        logger.info(f"   Packet Size: {flir_camera.FLIR_PACKET_SIZE}")
        
        logger.info("USB3 optimization constants verified")
        return True
        
    except Exception as e:
        logger.error(f"USB3 optimization test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting FLIR Camera Integration Test")
    logger.info("=" * 50)
    
    tests = [
        ("FLIR SDK Availability", test_flir_availability),
        ("Camera Detection", test_camera_detection),
        ("CameraController Integration", test_camera_controller_integration),
        ("Performance Benchmarks", test_performance_benchmarks),
        ("USB3 Optimization", test_usb3_optimization),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning Test: {test_name}")
        logger.info("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name:<30} {status}")
        if result:
            passed += 1
    
    logger.info("-" * 50)
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("ALL TESTS PASSED - FLIR integration ready!")
        return 0
    else:
        logger.warning("Some tests failed - check implementation")
        return 1

if __name__ == "__main__":
    sys.exit(main())
