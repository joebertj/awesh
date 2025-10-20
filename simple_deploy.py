#!/usr/bin/env python3
"""
Simple deployment script for awesh - WSL/Cursor safe
Usage: python3 simple_deploy.py [command]
"""

import os
import subprocess
import sys
import time
from pathlib import Path

def log(message):
    """Log a message"""
    print(message)

def install_backend():
    """Install Python backend module"""
    log("📦 Installing Python backend...")
    try:
        result = subprocess.run(
            ["pip3", "install", "-e", "."],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            log("✅ Backend module installed")
            return True
        else:
            log(f"❌ Backend install failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log("❌ Backend install timeout")
        return False
    except Exception as e:
        log(f"❌ Backend install error: {e}")
        return False

def build():
    """Build awesh"""
    log("🔨 Building awesh...")
    try:
        result = subprocess.run(["make", "clean"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            log(f"⚠️ Clean warning: {result.stderr}")
        
        result = subprocess.run(["make"], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            log("✅ Build successful")
            
            # Install backend module after successful build
            if not install_backend():
                log("⚠️ Backend install failed, but C binaries built successfully")
            
            return True
        else:
            log(f"❌ Build failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log("❌ Build timeout")
        return False
    except Exception as e:
        log(f"❌ Build error: {e}")
        return False

def kill_processes():
    """Kill running awesh processes"""
    log("🛑 Killing awesh processes...")
    try:
        # Kill processes using pkill
        for proc in ['awesh', 'awesh_sec', 'awesh_sandbox']:
            subprocess.run(['pkill', '-9', proc], capture_output=True, timeout=5)
        time.sleep(1)
        log("✅ Processes killed")
        return True
    except Exception as e:
        log(f"⚠️ Kill warning: {e}")
        return True  # Continue even if kill fails

def deploy():
    """Deploy binaries to ~/.local/bin"""
    log("📦 Deploying binaries...")
    try:
        # Create ~/.local/bin if it doesn't exist
        install_dir = Path.home() / ".local" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy binaries
        binaries = ['awesh', 'awesh_sec', 'awesh_sandbox']
        for binary in binaries:
            src = Path(binary)
            dst = install_dir / binary
            if src.exists():
                import shutil
                shutil.copy2(src, dst)
                dst.chmod(0o755)
                log(f"✅ Deployed {binary}")
            else:
                log(f"❌ {binary} not found")
                return False
        
        log("✅ Deployment complete")
        return True
    except Exception as e:
        log(f"❌ Deploy error: {e}")
        return False

def git_commit():
    """Commit and push changes"""
    log("📝 Committing changes...")
    try:
        # Add changes
        subprocess.run(["git", "add", "."], check=True, timeout=10)
        
        # Check if there are changes
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10)
        if not result.stdout.strip():
            log("✅ No changes to commit")
            return True
        
        # Commit
        subprocess.run(["git", "commit", "-m", "Update awesh"], check=True, timeout=10)
        
        # Push
        subprocess.run(["git", "push"], check=True, timeout=30)
        
        log("✅ Git operations complete")
        return True
    except subprocess.TimeoutExpired:
        log("❌ Git timeout")
        return False
    except Exception as e:
        log(f"❌ Git error: {e}")
        return False

def run_tests():
    """Run comprehensive test suite"""
    log("🧪 Running awesh test suite...")
    try:
        result = subprocess.run(
            [sys.executable, "test_awesh.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Print test output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            log("✅ All tests passed!")
            return True
        else:
            log("❌ Some tests failed")
            return False
    except subprocess.TimeoutExpired:
        log("❌ Test suite timeout")
        return False
    except Exception as e:
        log(f"❌ Test suite error: {e}")
        return False

def full_deploy():
    """Full deployment: kill, build, deploy, commit"""
    log("🚀 Starting full deployment...")
    
    # Step 1: Kill processes
    if not kill_processes():
        log("⚠️ Process kill had issues, continuing...")
    
    # Step 2: Build
    if not build():
        log("❌ Build failed, aborting")
        return False
    
    # Step 3: Deploy
    if not deploy():
        log("❌ Deploy failed, aborting")
        return False
    
    # Step 4: Git commit
    if not git_commit():
        log("⚠️ Git operations failed, but deployment succeeded")
    
    log("🎉 Full deployment complete!")
    return True

def main():
    if len(sys.argv) < 2:
        log("Usage: python3 simple_deploy.py [command]")
        log("Commands:")
        log("  build       - Build awesh (includes backend install)")
        log("  install_backend - Install Python backend only")
        log("  kill        - Kill running processes")
        log("  deploy      - Deploy binaries")
        log("  commit      - Git commit and push")
        log("  test        - Run comprehensive test suite")
        log("  full        - Full deployment (kill + build + deploy + commit)")
        return
    
    command = sys.argv[1]
    
    if command == "build":
        build()
    elif command == "install_backend":
        install_backend()
    elif command == "kill":
        kill_processes()
    elif command == "deploy":
        deploy()
    elif command == "commit":
        git_commit()
    elif command == "test":
        run_tests()
    elif command == "full":
        full_deploy()
    else:
        log(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
