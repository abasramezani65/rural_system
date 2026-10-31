"""WSGI configuration for PythonAnywhere.

This file is what PythonAnywhere uses to launch the Flask app.
On PythonAnywhere, in the Web tab, set the WSGI configuration file
to point to this file (or copy its contents into the auto-generated
/var/www/<username>_pythonanywhere_com_wsgi.py).
"""
import sys
import os

# Add the project folder to the Python path so imports work
project_home = '/home/ruraladmin/rural_system'  # ← CHANGE 'ruraladmin' to your PythonAnywhere username
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables if needed
os.environ.setdefault('FLASK_ENV', 'production')

# Import the Flask app
from app import app as application  # noqa: E402

# Note: PythonAnywhere expects the WSGI application to be named 'application'
