#!/usr/bin/env python
"""Test accessing live dashboard on http://localhost:5000"""
import sys
import time

try:
    import requests
    
    print("Checking if Flask server is running on http://localhost:5000...")
    time.sleep(1)
    
    # Test home page
    try:
        r = requests.get("http://localhost:5000/", timeout=2)
        print("  Home page: {} OK".format(r.status_code))
    except:
        print("  ERROR: Server not responding")
        print("\n  To start server, run in another terminal:")
        print("  cd webapp && python app.py")
        sys.exit(1)
    
    # Try to access dashboard (will redirect to login if not authenticated)
    r = requests.get("http://localhost:5000/dashboard", timeout=2)
    if r.status_code == 302:
        print("  Dashboard: 302 Redirect (not logged in - expected)")
    elif r.status_code == 200:
        print("  Dashboard: 200 OK")
    else:
        print("  Dashboard: {} ERROR".format(r.status_code))
    
    print("\n[OK] Server is running and responding!")
    print("\nNext steps:")
    print("1. Open http://localhost:5000 in your browser")
    print("2. Log in with your credentials")
    print("3. Go to Profile and complete setup if needed")
    print("4. Then try Dashboard")
    
except ImportError:
    print("ERROR: requests module not installed")
    sys.exit(1)
