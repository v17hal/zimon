try:
    import PySpin
    # PySpin may not expose __version__ on some releases
    print('PySpin imported')
    print('FLIR SDK available')
    
    # Try to get system instance
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    print('Found', cam_list.GetSize(), 'FLIR cameras')
    
    for i in range(cam_list.GetSize()):
        cam = cam_list.GetByIndex(i)
        try:
            cam.Init()
            model = cam.DeviceModelName.GetValue()
            serial = cam.DeviceSerialNumber.GetValue()
            print(f'  Camera {i+1}: {model} (SN: {serial})')
            cam.DeInit()
        except Exception as e:
            print(f'  Camera {i+1}: Error - {e}')
        finally:
            # Explicitly delete references so the system can release
            try:
                del cam
            except Exception:
                pass
    
    cam_list.Clear()
    del cam_list
    system.ReleaseInstance()
    
except ImportError as e:
    print('PySpin not available:', e)
    print('Checking FLIR SDK installation...')
    
    # Check common FLIR installation paths
    import os
    import sys
    
    flir_paths = [
        r"C:\Program Files\FLIR Systems\Spinnaker\Development\bin\Python",
        r"C:\Program Files (x86)\FLIR Systems\Spinnaker\Development\bin\Python",
        os.path.join(os.environ.get("PROGRAMFILES", ""), "FLIR Systems", "Spinnaker", "Development", "bin", "Python"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "FLIR Systems", "Spinnaker", "Development", "bin", "Python"),
    ]
    
    for path in flir_paths:
        if os.path.exists(path):
            print(f'Found FLIR path: {path}')
            if path not in sys.path:
                sys.path.insert(0, path)
                print(f'Added to Python path')
                
                # Try import again
                try:
                    import PySpin
                    print('PySpin now available after path fix!')
                except ImportError as e2:
                    print(f'Still not available: {e2}')
            break
    else:
        print('FLIR SDK not found in common locations')
        print('Please install FLIR Spinnaker SDK from:')
        print('   https://www.flir.com/support-center/downloads/spinnaker/')
