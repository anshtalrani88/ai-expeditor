import sys
import os

print(f"--- Running with Python: {sys.executable} ---")

# Get the absolute path of the project's root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))

# Add the project root to the Python path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("--- Locating the 'google' package ---")
try:
    import google
    print(f"\033[92mSuccessfully imported the top-level 'google' package.\033[0m")
    print(f"  - Location: {google.__file__}")
    print(f"  - Path: {google.__path__}")
except ImportError as e:
    print(f"\033[91mFailed to import the 'google' package: {e}\033[0m")
except Exception as e:
    print(f"\033[91mAn unexpected error occurred: {e}\033[0m")
