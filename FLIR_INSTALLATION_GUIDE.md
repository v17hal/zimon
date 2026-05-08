# FLIR Camera Installation Guide

## 🚨 **PROBLEM IDENTIFIED**

Your FLIR camera is not detected in ZIMON because **PySpin Python bindings are not installed**, even though FLIR SpinView works.

## 🔍 **Root Cause**

- ✅ FLIR SpinView works (standalone application)
- ❌ PySpin Python bindings missing (required for ZIMON)
- ❌ FLIR Spinnaker SDK not installed with Python support

## 📋 **SOLUTION: Install FLIR Spinnaker SDK**

### **Step 1: Download FLIR Spinnaker SDK**
1. Go to: https://www.flir.com/support-center/downloads/spinnaker/
2. Select: Windows 64-bit
3. Download: Latest Spinnaker SDK (version 1.26.0 or later)

### **Step 2: Install with Python Bindings (CRITICAL)**
1. **Right-click** the installer and **"Run as administrator"**
2. Select **"Custom"** installation (NOT "Typical")
3. **IMPORTANT**: Check **"Python Bindings"** option
4. Ensure installation includes Python components
5. Complete the installation

### **Step 3: Verify Installation**
Open Command Prompt and run:
```bash
python -c "import PySpin; print('PySpin version:', PySpin.__version__)"
```

Expected output:
```
PySpin version: 1.26.0.123
```

### **Step 4: Test with ZIMON**
1. Launch ZIMON application
2. Check camera dropdown
3. FLIR camera should appear as: `FLIR_[Model]_[Serial]`

## 🔧 **Troubleshooting**

### **If PySpin Import Fails**
1. **Check FLIR Installation Path**:
   ```
   C:\Program Files\FLIR Systems\Spinnaker\Development\bin\Python
   ```

2. **Add to System PATH**:
   - Go to System Properties → Environment Variables
   - Add to PATH: `C:\Program Files\FLIR Systems\Spinnaker\Development\bin\Python`

3. **Alternative Path**:
   ```
   C:\Program Files (x86)\FLIR Systems\Spinnaker\Development\bin\Python
   ```

### **If Camera Still Not Detected**
1. **Check USB Connection**:
   - Use USB3 port (not USB2)
   - Try different USB3 port
   - Check cable is securely connected

2. **Check Device Manager**:
   - Look for FLIR camera under "Imaging devices"
   - Ensure drivers are properly installed

3. **Close Other Applications**:
   - Close FLIR SpinView
   - Close other camera software
   - Restart ZIMON

4. **Restart Computer**:
   - Sometimes requires restart after SDK installation

## 🧪 **Testing Tools**

### **Simple Test Script**
Run the provided test script:
```bash
python test_flir_camera.py
```

This will:
- Test PySpin import
- Detect FLIR cameras
- Provide troubleshooting guidance

### **ZIMON Integration Test**
After PySpin installation:
```bash
python main.py
```
Check camera dropdown for FLIR camera.

## 📋 **Important Notes**

### **Why SpinView Works But ZIMON Doesn't**
- **SpinView**: Standalone FLIR application
- **ZIMON**: Python application requiring PySpin bindings
- **Solution**: Install FLIR Spinnaker SDK with Python bindings

### **Installation Requirements**
- Windows 10/11 64-bit
- Administrator privileges
- USB3 connection for FLIR camera
- Python 3.8+ (already installed)

### **Camera Compatibility**
Ensure your FLIR camera model supports Spinnaker SDK:
- Most USB3 FLIR cameras are supported
- Check FLIR website for compatibility
- CM3-U3-13Y3M-CS is fully supported

## 🎯 **Expected Result**

After successful installation:
- ✅ PySpin imports without errors
- ✅ FLIR camera appears in ZIMON dropdown
- ✅ Camera preview works in ZIMON
- ✅ Full thermal imaging capabilities available

## 📞 **Support Resources**

- **FLIR Download Page**: https://www.flir.com/support-center/downloads/spinnaker/
- **FLIR Documentation**: https://www.flir.com/support/
- **Spinnaker SDK Guide**: Included with installation
- **Test Script**: `test_flir_camera.py`

---

## 🚀 **Quick Start Summary**

1. **Download**: FLIR Spinnaker SDK from FLIR website
2. **Install**: As Administrator with Python bindings
3. **Verify**: `python -c "import PySpin; print(PySpin.__version__)"`
4. **Test**: `python test_flir_camera.py`
5. **Launch**: `python main.py` and check camera dropdown

**Your FLIR camera should appear in ZIMON after completing these steps!** 🎯
