#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

def check_dependency(name):
    return shutil.which(name) is not None

def main():
    print("MedCare Hospital Management System")
    
    print("\n[1] Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", 
                    "--break-system-packages", "-q"], check=False)
    
    print("\n[2] Setting up static files...")
    os.makedirs("frontend/dist", exist_ok=True)
    import shutil
    shutil.copy("frontend/index.html", "frontend/dist/index.html")
    print(" Frontend ready")
    
    print("\n[3] Starting Flask development server...")
    print("   URL: http://localhost:5000")
    print("   Admin credentials: admin / admin123")
    
    
    os.environ.setdefault('FLASK_ENV', 'development')
    
    from app import create_app
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
