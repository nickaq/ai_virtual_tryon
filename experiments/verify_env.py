import sys
import pkg_resources

print("-" * 50)
print(f"Python Version: {sys.version}")
print(f"Executable: {sys.executable}")

packages = [dist.project_name for dist in pkg_resources.working_set]
print(f"Installed packages: {len(packages)}")

try:
    import cv2
    print(f"OpenCV version: {cv2.__version__}")
except ImportError:
    print("❌ OpenCV not found")

try:
    import mediapipe
    print("✅ Mediapipe import successful")
except ImportError:
    print("❌ Mediapipe not found")

print("-" * 50)
