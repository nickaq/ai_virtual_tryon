#!/usr/bin/env python3
"""
Quick test script to verify the AI Try-On service setup.
Run this to check if all dependencies are properly installed.
"""
import sys

def check_imports():
    """Check if all required packages can be imported."""
    print("Checking imports...")
    
    try:
        import fastapi
        print(f"✓ FastAPI {fastapi.__version__}")
    except ImportError as e:
        print(f"✗ FastAPI import failed: {e}")
        return False
    
    try:
        import cv2
        print(f"✓ OpenCV {cv2.__version__}")
    except ImportError as e:
        print(f"✗ OpenCV import failed: {e}")
        return False
    
    try:
        import numpy
        print(f"✓ NumPy {numpy.__version__}")
    except ImportError as e:
        print(f"✗ NumPy import failed: {e}")
        return False
    
    try:
        from PIL import Image
        print(f"✓ Pillow (PIL)")
    except ImportError as e:
        print(f"✗ Pillow import failed: {e}")
        return False
    
    try:
        import mediapipe
        print(f"✓ MediaPipe {mediapipe.__version__}")
    except ImportError as e:
        print(f"✗ MediaPipe import failed: {e}")
        return False
    
    try:
        import rembg
        print(f"✓ rembg")
    except ImportError as e:
        print(f"✗ rembg import failed: {e}")
        return False
    
    try:
        import httpx
        print(f"✓ httpx {httpx.__version__}")
    except ImportError as e:
        print(f"✗ httpx import failed: {e}")
        return False
    
    try:
        import pydantic
        print(f"✓ Pydantic {pydantic.__version__}")
    except ImportError as e:
        print(f"✗ Pydantic import failed: {e}")
        return False
    
    try:
        import uvicorn
        print(f"✓ Uvicorn {uvicorn.__version__}")
    except ImportError as e:
        print(f"✗ Uvicorn import failed: {e}")
        return False
    
    return True


def check_config():
    """Check if configuration is valid."""
    print("\nChecking configuration...")
    
    try:
        from app.config import settings
        print(f"✓ Configuration loaded")
        print(f"  - Storage path: {settings.storage_path}")
        print(f"  - API URL: {settings.nano_banana_api_url}")
        print(f"  - Debug mode: {settings.debug}")
        
        if settings.nano_banana_api_key == "your_api_key_here":
            print("  ⚠ Warning: Nano Banana API key not configured (using placeholder)")
            print("    Edit .env and add your API key for production use")
        else:
            print(f"  ✓ API key configured")
        
        return True
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        return False


def check_directories():
    """Check if storage directories exist."""
    print("\nChecking directories...")
    
    try:
        from pathlib import Path
        from app.config import settings
        
        settings.ensure_directories()
        
        for name, path in [
            ("Uploads", settings.uploads_path),
            ("Products", settings.products_path),
            ("Results", settings.results_path),
            ("Artifacts", settings.artifacts_path)
        ]:
            if path.exists():
                print(f"✓ {name} directory: {path}")
            else:
                print(f"✗ {name} directory missing: {path}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Directory check failed: {e}")
        return False


def test_app_import():
    """Test importing the FastAPI app."""
    print("\nTesting app import...")
    
    try:
        from app.main import app
        print(f"✓ FastAPI app imported successfully")
        print(f"  - Title: {app.title}")
        print(f"  - Version: {app.version}")
        return True
    except Exception as e:
        print(f"✗ App import failed: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("AI Virtual Try-On Service - Setup Verification")
    print("=" * 60)
    
    checks = [
        ("Package Imports", check_imports),
        ("Configuration", check_config),
        ("Directories", check_directories),
        ("App Import", test_app_import)
    ]
    
    results = []
    for name, check_func in checks:
        print()
        result = check_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✓ All checks passed! Service is ready to run.")
        print("\nTo start the service, run:")
        print("  python -m app.main")
        print("  or")
        print("  uvicorn app.main:app --reload")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
