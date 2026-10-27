"""
Vercel Serverless Function entrypoint bridge.
Allows Vercel to load the Flask app whether it looks for /app.py or /api/index.py.
"""
import sys
import os

# Ensure project root directory is on Python search path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, application
