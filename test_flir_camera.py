#!/usr/bin/env python3
"""
Simple FLIR Camera Detection Test
Test if FLIR camera is properly installed and detected
"""

import sys
import os

def test_pyspin_import():
    """Test PySpin import"""
    print("Testing PySpin import...")
    try:
        import PySpin
        print("SUCCESS: PySpin imported successfully")
        print(f"PySpin version: {getattr(PySpin, '__version__', 'Unknown')}")
        return True
    except ImportError as e:
        print(f"FAILED: PySpin not available - {e}")
        return False

def test_camera_detection():
    """Test FLIR camera detection"""
    print("\nTesting FLIR camera detection...")
    try:
        import PySpin
        
        # Get system instance
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        
        num_cameras = cam_list.GetSize()
        print(f"Found {num_cameras} FLIR camera(s)")
        
        if num_cameras == 0:
            print("No FLIR cameras detected")
            print("Check:")
            print("1. Camera is connected via USB3")
            print("2. Camera drivers are installed")
            print("3. Camera is not in use by other applications")
        else:
            for i in range(num_cameras):
                cam = cam_list.GetByIndex(i)
                cam.Init()
                
                model = cam.DeviceModelName.GetValue()
                serial = cam.DeviceSerialNumber.GetValue()
                
                print(f"Camera {i+1}: {model} (SN: {serial})")
                cam.DeInit()
        
        cam_list.Clear()
        system.ReleaseInstance()
        
        return num_cameras > 0
        
    except Exception as e:
        print(f"Camera detection failed: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 50)
    print("FLIR Camera Detection Test")
    print("=" * 50)
    
    # Test PySpin import
    if not test_pyspin_import():
        print("\nSOLUTION:")
        print("1. Install FLIR Spinnaker SDK from:")
        print("   https://www.flir.com/support-center/downloads/spinnaker/")
        print("2. Run installer as Administrator")
        print("3. Select 'Custom' installation")
        print("4. Check 'Python Bindings' option")
        print("5. Complete installation")
        print("6. Run this test again")
        return False
    
    # Test camera detection
    if test_camera_detection():
        print("\nSUCCESS: FLIR camera is ready for use with ZIMON!")
        print("You should now see the FLIR camera in ZIMON's camera dropdown.")
        return True
    else:
        print("\nISSUE: PySpin installed but no cameras detected")
        print("Check camera connections and try again")
        return False

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
