#!/usr/bin/env python3
"""
FLIR SDK Installation Script
Automates FLIR Spinnaker SDK installation and verification.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_admin_privileges():
    """Check if running with administrator privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def find_flir_installation():
    """Find existing FLIR installation"""
    possible_paths = [
        r"C:\Program Files\FLIR Systems\Spinnaker\Development\bin\Python",
        r"C:\Program Files (x86)\FLIR Systems\Spinnaker\Development\bin\Python",
        r"C:\Program Files\FLIR Systems\Spinnaker\Development",
        r"C:\Program Files (x86)\FLIR Systems\Spinnaker",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            python_path = os.path.join(path, "Python")
            if os.path.exists(python_path):
                return path
    
    return None

def check_pyspin_availability():
    """Check if PySpin is available"""
    try:
        import PySpin
        return True, f"✅ PySpin v{PySpin.__version__} available"
    except ImportError as e:
        return False, f"❌ PySpin not available: {e}"
    except Exception as e:
        return False, f"❌ Error checking PySpin: {e}"

def add_to_python_path(flir_path):
    """Add FLIR path to Python sys.path"""
    if flir_path and flir_path not in sys.path:
        sys.path.insert(0, flir_path)
        print(f"✅ Added FLIR path to Python: {flir_path}")
        return True
    return False

def install_requirements():
    """Install required Python packages"""
    print("🔧 Installing Python requirements...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "spinnaker"
        ])
        print("✅ FLIR Spinnaker SDK installed via pip")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install spinnaker: {e}")
        return False
    
    return True

def main():
    """Main installation function"""
    print("🚀 FLIR SDK Installation Script")
    print("=" * 50)
    
    # Check current status
    print("🔍 Checking current installation...")
    flir_path = find_flir_installation()
    
    if flir_path:
        print(f"✅ Found FLIR installation at: {flir_path}")
        
        # Check PySpin availability
        pyspin_available, message = check_pyspin_availability()
        print(message)
        
        if pyspin_available:
            print("🎉 FLIR SDK is properly installed and ready!")
            return 0
        else:
            print("🔧 Attempting to fix PySpin availability...")
            add_to_python_path(flir_path)
            
            # Check again
            pyspin_available, message = check_pyspin_availability()
            print(message)
            
            if pyspin_available:
                print("🎉 FLIR SDK fixed and ready!")
                return 0
            else:
                print("❌ Could not fix PySpin availability")
                return 1
    else:
        print("❌ FLIR SDK not found on system")
        print("\n📋 Installation Options:")
        print("1. Download FLIR Spinnaker SDK from: https://www.flir.com/support-center/downloads/spinnaker/")
        print("2. Run installer as Administrator")
        print("3. Ensure Python bindings are selected")
        print("4. Install to default directory")
        print("5. Run this script again after installation")
        
        # Try to install via pip
        print("\n🔧 Attempting pip installation...")
        if install_requirements():
            print("✅ Installation completed via pip")
            print("🔄 Please restart Python and run this script again")
            return 2
        else:
            print("❌ Pip installation failed")
            return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
