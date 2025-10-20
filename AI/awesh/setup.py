#!/usr/bin/env python3
"""
Setup script for awesh_backend module
"""

from setuptools import setup, find_packages

setup(
    name="awesh_backend",
    version="0.1.0",
    description="Backend module for awesh shell",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "openai>=1.0.0",
        "chromadb>=0.4.0",
        "sentence-transformers>=2.2.0",
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "awesh_backend=awesh_backend.__main__:main",
        ],
    },
)















