#!/usr/bin/env python3
"""
FLIR SDK Auto-Installer and Setup
Automated installation and configuration for FLIR Spinnaker SDK
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def check_admin_privileges():
    """Check if running with administrator privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def open_flir_download_page():
    """Open FLIR download page in browser"""
    print("🌐 Opening FLIR Spinnaker SDK download page...")
    webbrowser.open("https://www.flir.com/support-center/downloads/spinnaker/")

def create_installation_guide():
    """Create detailed installation guide"""
    guide = """
# FLIR Spinnaker SDK Installation Guide

## 🚨 IMPORTANT: You must install FLIR Spinnaker SDK with Python bindings

### Step 1: Download FLIR Spinnaker SDK
1. Go to: https://www.flir.com/support-center/downloads/spinnaker/
2. Select your operating system (Windows 64-bit)
3. Download the latest Spinnaker SDK (version 1.26.0 or later)

### Step 2: Install with Python Bindings
1. Right-click the installer and "Run as administrator"
2. Select "Custom" installation (not "Typical")
3. **CRITICAL**: Check the "Python Bindings" option
4. Ensure installation path includes Python components
5. Complete the installation

### Step 3: Verify Installation
1. Open Command Prompt as administrator
2. Run: python -c "import PySpin; print('PySpin version:', PySpin.__version__)"

### Step 4: Test with ZIMON
1. Launch ZIMON application
2. Check camera dropdown for FLIR camera
3. Camera should appear as "FLIR_[Model]_[Serial]"

## 🔧 Manual Installation (if automatic fails)

### Find FLIR Installation
Check these locations:
- C:\\Program Files\\FLIR Systems\\Spinnaker\\Development\\bin\\Python
- C:\\Program Files (x86)\\FLIR Systems\\Spinnaker\\Development\\bin\\Python

### Add to Python Path
Add the Python path to your system environment variables:
1. Go to System Properties → Environment Variables
2. Add to PATH: C:\\Program Files\\FLIR Systems\\Spinnaker\\Development\\bin\\Python

## 📞 Support
If issues persist:
- FLIR Support: https://www.flir.com/support/
- Check camera compatibility with your FLIR model
- Ensure USB3 connection and proper drivers
"""
    
    with open("FLIR_INSTALLATION_GUIDE.txt", "w") as f:
        f.write(guide)
    
    print("📋 Created FLIR_INSTALLATION_GUIDE.txt")

def check_pyspin_after_install():
    """Check if PySpin is available after installation"""
    print("🔍 Checking PySpin availability...")
    
    try:
        import PySpin
        print("✅ PySpin is available!")
        print(f"📋 Version: {getattr(PySpin, '__version__', 'Unknown')}")
        
        # Test camera detection
        try:
            system = PySpin.System.GetInstance()
            cam_list = system.GetCameras()
            num_cameras = cam_list.GetSize()
            print(f"📹 Found {num_cameras} FLIR camera(s)")
            
            for i in range(num_cameras):
                cam = cam_list.GetByIndex(i)
                cam.Init()
                model = cam.DeviceModelName.GetValue()
                serial = cam.DeviceSerialNumber.GetValue()
                print(f"  📷 Camera {i+1}: {model} (SN: {serial})")
                cam.DeInit()
            
            cam_list.Clear()
            system.ReleaseInstance()
            
            if num_cameras > 0:
                print("🎉 FLIR cameras are ready for use with ZIMON!")
                return True
            else:
                print("⚠️ PySpin is installed but no cameras detected")
                print("📋 Check camera connections and try again")
                return False
                
        except Exception as e:
            print(f"❌ Camera detection failed: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ PySpin still not available: {e}")
        return False

def main():
    """Main installation process"""
    print("🚀 FLIR Spinnaker SDK Setup Assistant")
    print("=" * 50)
    
    # Check admin privileges
    if not check_admin_privileges():
        print("⚠️ Running without administrator privileges")
        print("📋 Some installation steps may require admin rights")
    
    # Check current PySpin status
    if check_pyspin_after_install():
        print("✅ FLIR SDK is already properly installed!")
        print("🎯 You can now use FLIR cameras with ZIMON")
        return
    
    print("\n🔧 FLIR Spinnaker SDK is not installed or Python bindings missing")
    print("📋 This is required for FLIR camera detection in ZIMON")
    
    # Create installation guide
    create_installation_guide()
    
    # Open download page
    open_flir_download_page()
    
    print("\n📋 Installation Instructions:")
    print("1. Download FLIR Spinnaker SDK from the opened browser page")
    print("2. Run installer as Administrator")
    print("3. Select 'Custom' installation")
    print("4. **IMPORTANT**: Check 'Python Bindings' option")
    print("5. Complete installation")
    print("6. Run this script again to verify")
    print("7. Launch ZIMON to test camera detection")
    
    print(f"\n📄 Detailed guide saved to: FLIR_INSTALLATION_GUIDE.txt")
    print("\n🌐 Browser opened to FLIR download page...")
    print("🎯 After installation, your FLIR camera should appear in ZIMON!")

if __name__ == "__main__":
    main()
