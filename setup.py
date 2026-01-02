"""
Setup configuration for Google Scholar API
"""
from setuptools import setup, find_packages

setup(
    name="google-scholar-api",
    version="1.0.0",
    description="REST API for Google Scholar searches with Selenium backend pool",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "selenium>=4.15.0",
        "webdriver-manager>=4.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "redis>=5.0.0",
        "loguru>=0.7.0",
        "gspread>=5.11.0",
        "google-auth>=2.23.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "httpx>=0.25.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "google-scholar-api=api.main:main",
        ],
    },
)
