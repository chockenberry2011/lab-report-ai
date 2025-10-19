#!/usr/bin/env python3
"""
Entry point for CLI commands
"""

import sys
import os

# Add current directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .cli import cli

if __name__ == '__main__':
    cli()