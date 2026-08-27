import sys
import os
import unittest

# Add the project root to the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Discover and run tests
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=project_root, pattern='test_*.py')
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    # Exit with a non-zero status code if tests failed
    if not result.wasSuccessful():
        sys.exit(1)
