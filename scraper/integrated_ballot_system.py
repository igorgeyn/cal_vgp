#!/usr/bin/env python3
"""
Integrated California Ballot Measures System
Runs the complete pipeline: Database setup → API → Website
"""

import subprocess
import sys
import time
from pathlib import Path
import webbrowser
import json

def check_requirements():
    """Check if all required packages are installed"""
    print("🔍 Checking requirements...")
    
    required = ['pandas', 'sqlite3', 'fastapi', 'uvicorn', 'matplotlib', 'seaborn']
    missing = []
    
    for package in required:
        try:
            if package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    
    print("✅ All requirements satisfied")
    return True

def setup_database():
    """Set up the ballot measures database"""
    print("\n📊 Setting up database...")
    
    try:
        result = subprocess.run([sys.executable, 'setup_ballot_database.py'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Database created successfully")
            return True
        else:
            print(f"❌ Database setup failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def start_api_server():
    """Start the FastAPI server in the background"""
    print("\n🚀 Starting API server...")
    
    try:
        # Start uvicorn in a subprocess
        process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'ballot_measures_api:app', 
             '--host', '0.0.0.0', '--port', '8000'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it time to start
        time.sleep(3)
        
        # Check if it's running
        if process.poll() is None:
            print("✅ API server started at http://localhost:8000")
            print("   API docs available at http://localhost:8000/docs")
            return process
        else:
            print("❌ API server failed to start")
            return None
            
    except Exception as e:
        print(f"❌ Error starting API: {e}")
        return None

def generate_website():
    """Generate the enhanced website"""
    print("\n🌐 Generating enhanced website...")
    
    # Copy the enhanced HTML to index.html
    enhanced_html = Path('enhanced_ballot_website.html')
    index_html = Path('../index.html')  # Save to root directory
    
    if enhanced_html.exists():
        with open(enhanced_html, 'r') as f:
            content = f.read()
        
        with open(index_html, 'w') as f:
            f.write(content)
        
        print(f"✅ Website generated at {index_html.absolute()}")
        return True
    else:
        print("❌ Enhanced website template not found")
        return False

def run_sample_analysis():
    """Run sample analyses"""
    print("\n📈 Running sample analyses...")
    
    try:
        result = subprocess.run([sys.executable, 'analysis_examples.py'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Analysis complete - check data/ folder for results")
            return True
        else:
            print(f"⚠️  Analysis had issues: {result.stderr}")
            return False
    except Exception as e:
        print(f"⚠️  Could not run analysis: {e}")
        return False

def create_deployment_guide():
    """Create deployment instructions"""
    print("\n📝 Creating deployment guide...")
    
    guide = """# California Ballot Measures System - Deployment Guide

## Local Development

1. **Start the API server:**
   ```bash
   cd scraper
   python -m uvicorn ballot_measures_api:app --reload
   ```

2. **Open the website:**
   - Open `index.html` in your browser
   - Or use a local server: `python -m http.server 8080`

## Production Deployment

### Option 1: GitHub Pages (Static Site Only)
1. The current `index.html` works as a static site
2. Update API_BASE in the HTML to point to your deployed API
3. Push to GitHub and enable Pages

### Option 2: Full Stack Deployment

#### Backend (API):
1. **Deploy to Railway/Render/Heroku:**
   ```bash
   # Create requirements.txt
   pip freeze > requirements.txt
   
   # Create Procfile
   echo "web: uvicorn ballot_measures_api:app --host 0.0.0.0 --port $PORT" > Procfile
   ```

2. **Or use Docker:**
   ```dockerfile
   FROM python:3.9
   WORKDIR /app
   COPY . .
   RUN pip install -r requirements.txt
   CMD ["uvicorn", "ballot_measures_api:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

#### Frontend:
1. Update `API_BASE` in the HTML to your deployed API URL
2. Deploy to any static host (Netlify, Vercel, GitHub Pages)

### Database Options:
- **SQLite** (current): Good for < 100k records
- **PostgreSQL**: For production scale
- **MySQL**: Alternative for production

## Environment Variables

Create `.env` file:
```
DATABASE_URL=sqlite:///data/ballot_measures.db
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:8080", "https://cal-vgp.igorgeyn.com"]
```

## Maintenance

1. **Update data:**
   ```bash
   python merge_historical_data.py
   python setup_ballot_database.py
   ```

2. **Backup database:**
   ```bash
   cp data/ballot_measures.db data/ballot_measures_backup_$(date +%Y%m%d).db
   ```

3. **Monitor API:**
   - Check `/stats` endpoint for health
   - Set up monitoring (UptimeRobot, etc.)
"""
    
    with open('DEPLOYMENT.md', 'w') as f:
        f.write(guide)
    
    print("✅ Deployment guide created: DEPLOYMENT.md")

def main():
    """Run the complete integrated system"""
    print("🎯 California Ballot Measures - Integrated System Setup")
    print("=" * 60)
    
    # Check requirements
    if not check_requirements():
        return 1
    
    # Run setup steps
    steps = [
        ("Database Setup", setup_database),
        ("Website Generation", generate_website),
        ("Sample Analysis", run_sample_analysis),
        ("Deployment Guide", create_deployment_guide)
    ]
    
    api_process = None
    
    for step_name, step_func in steps:
        print(f"\n{'='*60}")
        print(f"Step: {step_name}")
        print(f"{'='*60}")
        
        if not step_func():
            print(f"\n⚠️  {step_name} had issues, but continuing...")
    
    # Start API last
    api_process = start_api_server()
    
    # Summary
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    
    print("\n📊 Database: data/ballot_measures.db")
    print("🌐 Website: ../index.html")
    print("🔗 API: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("📈 Analysis Results: data/")
    
    print("\n🚀 Next Steps:")
    print("1. Open http://localhost:8000/docs to explore the API")
    print("2. Open ../index.html in your browser")
    print("3. Try the search and filter features")
    print("4. Export data for analysis")
    
    print("\n📝 For production deployment, see DEPLOYMENT.md")
    
    # Ask if user wants to open browser
    response = input("\n🌐 Open website in browser? (y/n): ")
    if response.lower() == 'y':
        index_path = Path('../index.html').absolute()
        webbrowser.open(f'file://{index_path}')
    
    if api_process:
        print("\n⚠️  API server is running. Press Ctrl+C to stop.")
        try:
            api_process.wait()
        except KeyboardInterrupt:
            print("\n👋 Shutting down API server...")
            api_process.terminate()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())