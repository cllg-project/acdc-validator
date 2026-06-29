import sys
import os

# Ensure the project root is on sys.path so `app` is always importable,
# regardless of which test file pytest discovers first.
sys.path.insert(0, os.path.dirname(__file__))
