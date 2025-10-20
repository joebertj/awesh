#!/usr/bin/env python3
"""
Entry point for awesh backend server
Usage: python -m awesh_backend
"""

import asyncio
from .server import AweshSocketBackend

async def main():
    backend = AweshSocketBackend()
    
    try:
        await backend.run_server()
    except KeyboardInterrupt:
        import sys
        print("Backend: Shutting down...", file=sys.stderr)
    finally:
        backend.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
