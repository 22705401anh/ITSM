"""
GLPI-like ITSM Platform

This is the main entry point for the ITSM system.
Run with: python ITSM.py
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.main import app
from app.db import init_db

if __name__ == "__main__":
    # Initialize database
    init_db()

    # Run the application with proper configuration
    # Using module string for reload support
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
