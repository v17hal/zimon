#!/usr/bin/env python3
"""
FLIR SDK Installation and Detection Fix
Comprehensive solution for PySpin installation issues
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def find_flir_installation():
    """Find FLIR Spinnaker installation"""
    possible_paths = [
        r"C:\Program Files\FLIR Systems\Spinnaker",
        r"C:\Program Files (x86)\FLIR Systems\Spinnaker",
        r"C:\FLIR Systems\Spinnaker",
        r"C:\Spinnaker",
    ]
    
    for base_path in possible_paths:
        if os.path.exists(base_path):
            print(f"📁 Found FLIR installation at: {base_path}")
            
            # Look for Python bindings
            python_paths = [
                os.path.join(base_path, "Development", "bin", "Python"),
                os.path.join(base_path, "Python"),
                os.path.join(base_path, "Lib", "Python"),
            ]
            
            for python_path in python_paths:
                if os.path.exists(python_path):
                    print(f"🐍 Found Python bindings at: {python_path}")
                    return python_path
    
    return None

def install_pyspin_manually():
    """Try to install PySpin manually"""
    print("🔧 Attempting to install PySpin...")
    
    try:
        # Method 1: Try pip install
        print("📦 Trying pip install spinnaker...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "spinnaker"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ PySpin installed via pip")
            return True
        else:
            print(f"❌ pip install failed: {result.stderr}")
    
    except Exception as e:
        print(f"❌ pip install error: {e}")
    
    return False

def setup_flir_path():
    """Setup FLIR Python path manually"""
    flir_path = find_flir_installation()
    
    if flir_path:
        print(f"🔧 Setting up FLIR path: {flir_path}")
        
        # Add to Python path
        if flir_path not in sys.path:
            sys.path.insert(0, flir_path)
            print(f"➕ Added {flir_path} to Python path")
        
        # Look for PySpin files
        pyspin_files = []
        for file in os.listdir(flir_path):
            if "PySpin" in file:
                pyspin_files.append(file)
        
        print(f"📄 Found PySpin files: {pyspin_files}")
        
        # Try to import
        try:
            import PySpin
            print(f"✅ PySpin imported successfully!")
            print(f"📋 PySpin version: {getattr(PySpin, '__version__', 'Unknown')}")
            return True
        except ImportError as e:
            print(f"❌ Import failed: {e}")
            
            # Try to copy files if needed
            for file in pyspin_files:
                src = os.path.join(flir_path, file)
                dst = os.path.join(os.path.dirname(__file__), file)
                try:
                    shutil.copy2(src, dst)
                    print(f"📋 Copied {file} to project directory")
                except Exception as copy_error:
                    print(f"❌ Failed to copy {file}: {copy_error}")
    
    return False

def check_camera_detection():
    """Check if FLIR cameras are detected"""
    try:
        import PySpin
        
        print("🔍 Scanning for FLIR cameras...")
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        
        num_cameras = cam_list.GetSize()
        print(f"📹 Found {num_cameras} FLIR camera(s)")
        
        for i in range(num_cameras):
            try:
                cam = cam_list.GetByIndex(i)
                cam.Init()
                
                model = cam.DeviceModelName.GetValue()
                serial = cam.DeviceSerialNumber.GetValue()
                
                print(f"  📷 Camera {i+1}: {model} (SN: {serial})")
                
                cam.DeInit()
            except Exception as e:
                print(f"  ❌ Camera {i+1}: Error - {e}")
        
        cam_list.Clear()
        system.ReleaseInstance()
        
        return num_cameras > 0
        
    except Exception as e:
        print(f"❌ Camera detection failed: {e}")
        return False

def main():
    """Main installation and detection process"""
    print("🚀 FLIR SDK Setup and Detection Tool")
    print("=" * 50)
    
    # Step 1: Try to install PySpin
    print("\n📦 Step 1: Installing PySpin...")
    if install_pyspin_manually():
        print("✅ PySpin installed successfully")
    else:
        print("❌ Automatic installation failed")
    
    # Step 2: Setup FLIR path
    print("\n🔧 Step 2: Setting up FLIR Python path...")
    if setup_flir_path():
        print("✅ FLIR path configured")
    else:
        print("❌ FLIR path setup failed")
    
    # Step 3: Check camera detection
    print("\n📹 Step 3: Checking camera detection...")
    if check_camera_detection():
        print("✅ FLIR cameras detected successfully!")
    else:
        print("❌ No FLIR cameras detected")
    
    print("\n🎯 Setup complete!")
    print("📋 If cameras are still not detected, please:")
    print("   1. Ensure FLIR Spinnaker SDK is installed")
    print("   2. Restart the application")
    print("   3. Check camera connections")

if __name__ == "__main__":
    main()
