"""
Setup script for California Ballot Measures project
"""
from setuptools import setup, find_packages

setup(
    name="ca-ballot-measures",
    version="2.0.0",
    description="California Ballot Measures Database and API",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "pandas>=2.1.0",
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "ca-ballot-check=scripts.check_updates:main",
            "ca-ballot-update=scripts.update_db:main",
            "ca-ballot-scrape=scripts.scrape:main",
            "ca-ballot-website=scripts.generate_site:main",
        ],
    },
)
