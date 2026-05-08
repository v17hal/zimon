"""
Install Dependencies Script

This script installs all required dependencies for ZIMON.
Run this script using the same Python interpreter that runs ZIMON.
"""
import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ {package} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {package}: {e}")
        return False

def main():
    print("=" * 60)
    print("ZIMON Dependency Installer")
    print("=" * 60)
    print(f"Using Python: {sys.executable}")
    print(f"Python version: {sys.version}")
    print()
    
    # Required packages
    packages = [
        "pyqt6",
        "pyserial",
        "opencv-python",
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "h5py"
    ]
    
    print("Installing dependencies...")
    print("-" * 60)
    
    failed = []
    for package in packages:
        if not install_package(package):
            failed.append(package)
    
    print()
    print("=" * 60)
    if failed:
        print(f"Installation completed with {len(failed)} error(s)")
        print(f"Failed packages: {', '.join(failed)}")
        print("\nYou may need to run this script as administrator or")
        print("install the packages manually using:")
        print(f"  {sys.executable} -m pip install {' '.join(failed)}")
    else:
        print("All dependencies installed successfully!")
        print("\nYou can now run ZIMON and use ZebraZoom integration.")
    print("=" * 60)

if __name__ == "__main__":
    main()

