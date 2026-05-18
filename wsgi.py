"""
WSGI entry point for production deployment
Compatible with Gunicorn, uWSGI, and other production WSGI servers
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import the Flask app from main.py.py
import importlib.util
spec = importlib.util.spec_from_file_location("main_app", Path(__file__).parent / "main.py.py")
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
app = main_module.app

if __name__ == "__main__":
    # This is only for local testing with 'python wsgi.py'
    # In production, use: gunicorn wsgi:app
    app.run()
