#!/usr/bin/env python3
"""
Simple deployment script for awesh
Usage: python3 deploy.py [command]
Commands: syntax_check, build, kill, deploy, test, full_deploy
"""

import os
import subprocess
import signal
import time
import psutil
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
AWESH_DIR = PROJECT_ROOT
BACKEND_DIR = PROJECT_ROOT / "awesh_backend"
VENV_DIR = PROJECT_ROOT / "venv"
INSTALL_PATH = Path.home() / ".local" / "bin" / "awesh"

def log(message):
    """Log a message"""
    print(message)

def setup_venv():
    """Setup virtual environment for awesh"""
    try:
        if not VENV_DIR.exists():
            log("🐍 Creating virtual environment...")
            result = subprocess.run([
                "python3", "-m", "venv", str(VENV_DIR)
            ], capture_output=True, text=True, cwd=PROJECT_ROOT)
            
            if result.returncode != 0:
                log(f"❌ Failed to create venv: {result.stderr}")
                return False
            
            log("✅ Virtual environment created")
        else:
            log("✅ Virtual environment already exists")
        
        # Get venv python path
        if os.name == 'nt':  # Windows
            venv_python = VENV_DIR / "Scripts" / "python.exe"
            venv_pip = VENV_DIR / "Scripts" / "pip.exe"
        else:  # Unix/Linux/macOS
            venv_python = VENV_DIR / "bin" / "python"
            venv_pip = VENV_DIR / "bin" / "pip"
        
        # Upgrade pip in venv
        log("📦 Upgrading pip in virtual environment...")
        result = subprocess.run([
            str(venv_python), "-m", "pip", "install", "--upgrade", "pip"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"⚠️ Failed to upgrade pip: {result.stderr}")
        
        return True
        
    except Exception as e:
        log(f"❌ Error setting up venv: {e}")
        return False

def get_venv_python():
    """Get the python executable path from venv"""
    if os.name == 'nt':  # Windows
        return VENV_DIR / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        return VENV_DIR / "bin" / "python"

def get_venv_pip():
    """Get the pip executable path from venv"""
    if os.name == 'nt':  # Windows
        return VENV_DIR / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        return VENV_DIR / "bin" / "pip"

def get_venv_python():
    """Get the Python executable path from venv"""
    if os.name == 'nt':  # Windows
        return VENV_DIR / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        return VENV_DIR / "bin" / "python3"

def syntax_check():
    """Check C and Python syntax"""
    log("🔍 Checking C syntax...")
    
    # Check C files
    c_files = list(AWESH_DIR.glob("*.c"))
    for c_file in c_files:
        try:
            result = subprocess.run([
                "gcc", "-fsyntax-only", "-Wall", "-Wextra", "-std=c99",
                str(c_file)
            ], capture_output=True, text=True, cwd=AWESH_DIR)
            
            if result.returncode == 0:
                log(f"✅ {c_file.name}: Syntax OK")
            else:
                log(f"❌ {c_file.name}: Syntax errors:\n{result.stderr}")
                return False
        except Exception as e:
            log(f"❌ Error checking {c_file.name}: {e}")
            return False
    
    log("🔍 Checking Python syntax...")
    
    # Check Python files
    py_files = list(BACKEND_DIR.glob("*.py"))
    for py_file in py_files:
        try:
            with open(py_file, 'r') as f:
                compile(f.read(), py_file, 'exec')
            log(f"✅ {py_file.name}: Syntax OK")
        except SyntaxError as e:
            log(f"❌ {py_file.name}: Syntax error: {e}")
            return False
        except Exception as e:
            log(f"❌ Error checking {py_file.name}: {e}")
            return False
    
    return True

def build_project(clean=False):
    """Build awesh project"""
    try:
        # Setup virtual environment first
        if not setup_venv():
            log("❌ Failed to setup virtual environment")
            return False
        
        if clean:
            log("🧹 Cleaning build...")
            result = subprocess.run(["make", "clean"], capture_output=True, text=True, cwd=AWESH_DIR)
            if result.returncode != 0:
                log(f"❌ Clean failed: {result.stderr}")
                return False
        
        log("🔨 Building C components (frontend + Security Agent + Sandbox)...")
        result = subprocess.run(["make"], capture_output=True, text=True, cwd=AWESH_DIR)
        
        if result.returncode == 0:
            log("✅ C components built successfully")
            # Verify all binaries were built
            awesh_binary = AWESH_DIR / "awesh"
            security_agent_binary = AWESH_DIR / "awesh_sec"
            sandbox_binary = AWESH_DIR / "awesh_sandbox"
            
            if awesh_binary.exists():
                log("✅ Frontend binary (awesh) built")
            else:
                log("❌ Frontend binary (awesh) missing")
                return False
                
            if security_agent_binary.exists():
                log("✅ Security Agent binary (awesh_sec) built")
            else:
                log("❌ Security Agent binary (awesh_sec) missing")
                return False
                
            if sandbox_binary.exists():
                log("✅ Sandbox binary (awesh_sandbox) built")
            else:
                log("❌ Sandbox binary (awesh_sandbox) missing")
                return False
        else:
            log(f"❌ C build failed:\n{result.stderr}")
            return False
        
        log("📦 Installing Python backend in virtual environment...")
        venv_pip = get_venv_pip()
        result = subprocess.run([
            str(venv_pip), "install", "-e", "."
        ], capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode == 0:
            log("✅ Python backend installed")
        else:
            log(f"❌ Python backend install failed:\n{result.stderr}")
            return False
        
        return True
    
    except Exception as e:
        log(f"❌ Build error: {e}")
        return False

def kill_processes(force=False):
    """Kill running awesh processes"""
    killed_processes = []
    
    try:
        # Find and kill awesh processes by name
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in ['awesh', 'awesh_backend', 'awesh_sec', 'awesh_sandbox']:
                    pid = proc.info['pid']
                    name = proc.info['name']
                    
                    if force:
                        os.kill(pid, signal.SIGKILL)
                        log(f"💀 Force killed {name} (PID: {pid})")
                    else:
                        os.kill(pid, signal.SIGTERM)
                        log(f"🛑 Terminated {name} (PID: {pid})")
                    
                    killed_processes.append(pid)
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                continue
        
        # Also find and kill processes by command line (for stealth processes)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('awesh' in arg for arg in cmdline):
                    pid = proc.info['pid']
                    name = proc.info['name']
                    
                    # Skip if already killed
                    if pid in killed_processes:
                        continue
                    
                    if force:
                        os.kill(pid, signal.SIGKILL)
                        log(f"💀 Force killed {name} (PID: {pid}) - awesh process")
                    else:
                        os.kill(pid, signal.SIGTERM)
                        log(f"🛑 Terminated {name} (PID: {pid}) - awesh process")
                    
                    killed_processes.append(pid)
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                continue
        
        # Find processes using the awesh socket
        socket_path = Path.home() / ".awesh.sock"
        if socket_path.exists():
            try:
                # Use lsof to find processes using the socket
                result = subprocess.run([
                    "lsof", str(socket_path)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = int(parts[1])
                            if pid not in killed_processes:
                                if force:
                                    os.kill(pid, signal.SIGKILL)
                                    log(f"💀 Force killed socket process (PID: {pid})")
                                else:
                                    os.kill(pid, signal.SIGTERM)
                                    log(f"🛑 Terminated socket process (PID: {pid})")
                                killed_processes.append(pid)
            except (subprocess.SubprocessError, ValueError, ProcessLookupError):
                pass
        
        if not killed_processes:
            log("ℹ️  No awesh processes found running")
        
        # Clean up socket files
        socket_paths = [
            Path.home() / ".awesh.sock",
            Path.home() / ".awesh_security_agent.sock",
            Path.home() / ".awesh_frontend.sock",
            Path("/tmp/awesh.sock"),
            Path("/tmp/awesh_sandbox.sock")
        ]
        
        for socket_path in socket_paths:
            if socket_path.exists():
                socket_path.unlink()
                log(f"🧹 Removed socket: {socket_path}")
        
        if killed_processes:
            import time
            time.sleep(1)
            log("✅ Process cleanup complete")
        
        return True
    
    except Exception as e:
        log(f"❌ Error killing processes: {e}")
        return False

def deploy_binary(backup=True):
    """Deploy awesh and security_agent binaries to ~/.local/bin"""
    try:
        # Create ~/.local/bin if it doesn't exist
        install_dir = Path.home() / ".local" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Deploy frontend binary (awesh)
        if backup and INSTALL_PATH.exists():
            backup_path = INSTALL_PATH.with_suffix('.bak')
            INSTALL_PATH.rename(backup_path)
            log(f"💾 Backed up existing awesh to {backup_path}")
        
        awesh_binary_path = AWESH_DIR / "awesh"
        if not awesh_binary_path.exists():
            log("❌ awesh binary not found. Run build first.")
            return False
        
        import shutil
        shutil.copy2(awesh_binary_path, INSTALL_PATH)
        INSTALL_PATH.chmod(0o755)
        log(f"✅ Deployed awesh to {INSTALL_PATH}")
        
        # Deploy Security Agent binary
        security_agent_binary_path = AWESH_DIR / "awesh_sec"
        security_agent_install_path = install_dir / "awesh_sec"
        
        if not security_agent_binary_path.exists():
            log("❌ awesh_sec binary not found. Run build first.")
            return False
        
        # Backup existing Security Agent if it exists
        if backup and security_agent_install_path.exists():
            backup_path = security_agent_install_path.with_suffix('.bak')
            security_agent_install_path.rename(backup_path)
            log(f"💾 Backed up existing awesh_sec to {backup_path}")
        
        shutil.copy2(security_agent_binary_path, security_agent_install_path)
        security_agent_install_path.chmod(0o755)
        log(f"✅ Deployed awesh_sec to {security_agent_install_path}")
        
        # Deploy Sandbox binary
        sandbox_binary_path = AWESH_DIR / "awesh_sandbox"
        sandbox_install_path = install_dir / "awesh_sandbox"
        
        if not sandbox_binary_path.exists():
            log("❌ awesh_sandbox binary not found. Run build first.")
            return False
        
        # Backup existing Sandbox if it exists
        if backup and sandbox_install_path.exists():
            backup_path = sandbox_install_path.with_suffix('.bak')
            sandbox_install_path.rename(backup_path)
            log(f"💾 Backed up existing awesh_sandbox to {backup_path}")
        
        shutil.copy2(sandbox_binary_path, sandbox_install_path)
        sandbox_install_path.chmod(0o755)
        log(f"✅ Deployed awesh_sandbox to {sandbox_install_path}")
        
        # Verify deployment
        if (INSTALL_PATH.exists() and os.access(INSTALL_PATH, os.X_OK) and
            security_agent_install_path.exists() and os.access(security_agent_install_path, os.X_OK) and
            sandbox_install_path.exists() and os.access(sandbox_install_path, os.X_OK)):
            log("✅ All binaries are executable and ready")
            return True
        else:
            log("❌ Deployment verification failed")
            return False
    
    except Exception as e:
        log(f"❌ Deployment error: {e}")
        return False

def test_backend_sanity():
    """Test backend socket communication sanity"""
    import socket
    import time
    import threading
    
    log("🧪 Testing backend socket communication...")
    
    try:
        # Start backend in background using venv python
        venv_python = get_venv_python()
        backend_proc = subprocess.Popen([
            str(venv_python), "-m", "awesh_backend"
        ], cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for backend to start
        time.sleep(2)
        
        # Test socket connection
        socket_path = Path.home() / ".awesh.sock"
        if not socket_path.exists():
            log("❌ Backend socket not created")
            backend_proc.terminate()
            return False
        
        # Connect and test
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        
        try:
            sock.connect(str(socket_path))
            log("✅ Socket connection successful")
            
            # Test STATUS command
            sock.send(b"STATUS")
            response = sock.recv(1024).decode('utf-8')
            if response in ["AI_READY", "AI_LOADING"]:
                log(f"✅ STATUS command works: {response}")
            else:
                log(f"❌ Unexpected STATUS response: {response}")
                return False
            
            # Test simple command
            sock.send(b"echo test")
            sock.settimeout(10)  # Give more time for command
            response = sock.recv(4096).decode('utf-8')
            if "test" in response:
                log("✅ Command execution works")
            else:
                log(f"❌ Command failed or no response: {response}")
                return False
            
        except socket.timeout:
            log("❌ Socket communication timeout - backend hanging")
            return False
        except Exception as e:
            log(f"❌ Socket communication error: {e}")
            return False
        finally:
            sock.close()
            backend_proc.terminate()
            backend_proc.wait()
        
        log("✅ Backend sanity test passed")
        return True
        
    except Exception as e:
        log(f"❌ Backend sanity test error: {e}")
        if 'backend_proc' in locals():
            backend_proc.terminate()
        return False

def test_deployment():
    """Test the deployed awesh installation"""
    try:
        if not INSTALL_PATH.exists():
            log("❌ awesh binary not found at ~/.local/bin/awesh")
            return False
        
        if not os.access(INSTALL_PATH, os.X_OK):
            log("❌ awesh binary is not executable")
            return False
        
        log("✅ Binary exists and is executable")
        
        # Test backend sanity
        if not test_backend_sanity():
            log("❌ Backend sanity test failed")
            return False
        
        log("✅ Deployment test passed")
        return True
    
    except Exception as e:
        log(f"❌ Test error: {e}")
        return False

def git_pull():
    """Pull latest changes from git"""
    try:
        log("📥 Git: Pulling latest changes...")
        result = subprocess.run([
            "git", "pull"
        ], cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"❌ Git pull failed: {result.stderr}")
            return False
        
        log("✅ Git pull successful")
        return True
        
    except Exception as e:
        log(f"❌ Git pull error: {e}")
        return False

def git_commit_and_push():
    """Commit changes and push to git"""
    try:
        log("📝 Git: Adding changes...")
        result = subprocess.run([
            "git", "add", "."
        ], cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"❌ Git add failed: {result.stderr}")
            return False
        
        # Check if there are changes to commit
        result = subprocess.run([
            "git", "status", "--porcelain"
        ], cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if not result.stdout.strip():
            log("✅ No changes to commit")
            return True
        
        log("📝 Git: Committing changes...")
        commit_msg = f"Build awesh - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run([
            "git", "commit", "-m", commit_msg
        ], cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"❌ Git commit failed: {result.stderr}")
            return False
        
        log("📝 Git: Pushing to remote...")
        result = subprocess.run([
            "git", "push"
        ], cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"❌ Git push failed: {result.stderr}")
            return False
        
        log("✅ Changes committed and pushed successfully")
        return True
        
    except Exception as e:
        log(f"❌ Git operation error: {e}")
        return False

def install_dependencies():
    """Install all dependencies in virtual environment"""
    try:
        # Setup virtual environment first
        if not setup_venv():
            log("❌ Failed to setup virtual environment")
            return False
        
        log("📦 Installing dependencies in virtual environment...")
        venv_pip = get_venv_pip()
        
        # Install from requirements.txt
        requirements_file = PROJECT_ROOT / "requirements.txt"
        if requirements_file.exists():
            result = subprocess.run([
                str(venv_pip), "install", "-r", str(requirements_file)
            ], capture_output=True, text=True, cwd=PROJECT_ROOT)
            
            if result.returncode == 0:
                log("✅ Dependencies installed from requirements.txt")
            else:
                log(f"❌ Failed to install dependencies: {result.stderr}")
                return False
        else:
            log("⚠️ No requirements.txt found")
        
        # Install the project itself
        result = subprocess.run([
            str(venv_pip), "install", "-e", "."
        ], capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode == 0:
            log("✅ Project installed in virtual environment")
        else:
            log(f"❌ Failed to install project: {result.stderr}")
            return False
        
        return True
        
    except Exception as e:
        log(f"❌ Error installing dependencies: {e}")
        return False

def build_ci(skip_tests=False):
    """CI Build Pipeline: checks, bins, git push"""
    log("🚀 Starting CI build pipeline...")
    
    # Step 1: Syntax check
    log("\n📋 Step 1: Syntax Check")
    if not syntax_check():
        log("❌ Build aborted due to syntax errors")
        return False
    
    # Step 2: Build binaries
    log("\n🔨 Step 2: Build Binaries")
    if not build_project(clean=True):
        log("❌ Build aborted due to build errors")
        return False
    
    # Step 3: Git commit and push
    log("\n📝 Step 3: Git Commit & Push")
    if not git_commit_and_push():
        log("❌ Git operations failed")
        return False
    
    log("\n🎉 CI build pipeline completed successfully!")
    return True

def install_deploy(skip_tests=False):
    """Production Install Pipeline: git pull, build, kills procs, deploy"""
    log("🚀 Starting production install pipeline...")
    
    # Step 1: Git pull latest
    log("\n📥 Step 1: Git Pull Latest")
    if not git_pull():
        log("❌ Install aborted - git pull failed")
        return False
    
    # Step 2: Kill existing processes
    log("\n🛑 Step 2: Kill Existing Processes")
    kill_processes(force=False)
    
    # Step 3: Build binaries
    log("\n🔨 Step 3: Build Binaries")
    if not build_project(clean=True):
        log("❌ Install aborted due to build errors")
        return False
    
    # Step 4: Deploy binaries
    log("\n📦 Step 4: Deploy Binaries")
    if not deploy_binary(backup=True):
        log("❌ Installation failed")
        return False
    
    log("\n🎉 Production install completed successfully!")
    return True

def clean_install():
    """Clean Install: Build + Deploy (no git operations)"""
    log("🚀 Starting clean install pipeline...")
    
    # Step 1: Syntax check
    log("\n📋 Step 1: Syntax Check")
    if not syntax_check():
        log("❌ Clean install aborted due to syntax errors")
        return False
    
    # Step 2: Kill existing processes
    log("\n🛑 Step 2: Kill Existing Processes")
    kill_processes(force=False)
    
    # Step 3: Build binaries
    log("\n🔨 Step 3: Build Binaries")
    if not build_project(clean=True):
        log("❌ Clean install aborted due to build errors")
        return False
    
    # Step 4: Deploy
    log("\n📦 Step 4: Deploy")
    if not deploy_binary(backup=True):
        log("❌ Clean install failed")
        return False
    
    # Step 5: Git commit and push
    log("\n📝 Step 5: Git Commit & Push")
    if not git_commit_and_push():
        log("❌ Git operations failed")
        return False
    
    log("\n🎉 Clean install completed successfully!")
    return True

def rebuild_all():
    """Rebuild Everything: Remove venv, clean build, install deps, deploy"""
    log("🚀 Starting complete rebuild...")
    
    # Step 1: Kill existing processes
    log("\n🛑 Step 1: Kill Existing Processes")
    kill_processes(force=True)
    
    # Step 2: Remove venv
    log("\n🧹 Step 2: Remove Virtual Environment")
    if VENV_DIR.exists():
        import shutil
        shutil.rmtree(VENV_DIR)
        log("✅ Virtual environment removed")
    else:
        log("ℹ️  No virtual environment to remove")
    
    # Step 3: Setup fresh venv
    log("\n🐍 Step 3: Setup Fresh Virtual Environment")
    if not setup_venv():
        log("❌ Rebuild aborted - venv setup failed")
        return False
    
    # Step 4: Install dependencies
    log("\n📦 Step 4: Install Dependencies")
    if not install_dependencies():
        log("❌ Rebuild aborted - dependency install failed")
        return False
    
    # Step 5: Clean build
    log("\n🔨 Step 5: Clean Build")
    if not build_project(clean=True):
        log("❌ Rebuild aborted - build failed")
        return False
    
    # Step 6: Deploy
    log("\n📦 Step 6: Deploy")
    if not deploy_binary(backup=True):
        log("❌ Rebuild failed")
        return False
    
    log("\n🎉 Complete rebuild successful!")
    return True

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        log("Usage: python3 deployment_mcp.py [command]")
        log("\nCI/CD Commands:")
        log("  build          - CI pipeline: checks, bins, git push")
        log("  install        - Deploy pipeline: git pull, build, kills procs, deploy")
        log("  clean_install  - Build + deploy + git push (no git pull)")
        log("  rebuild_all    - Complete rebuild: remove venv, clean build, install deps, deploy")
        log("\nEnvironment Commands:")
        log("  setup_venv     - Create virtual environment")
        log("  install_deps   - Install all dependencies in venv")
        log("\nIndividual Commands:")
        log("  syntax_check   - Check C and Python syntax")
        log("  build_only     - Build awesh (incremental)")
        log("  build_clean    - Build awesh (clean)")
        log("  kill           - Kill running awesh processes")
        log("  kill_force     - Force kill processes (SIGKILL)")
        log("  deploy_only    - Deploy binary to ~/.local/bin")
        log("  test           - Test deployment and backend")
        log("  git_pull       - Pull latest changes from git")
        log("  git_push       - Commit and push changes to git")
        return
    
    command = sys.argv[1]
    
    # CI/CD Commands
    if command == "build":
        build_ci(skip_tests=False)
    elif command == "install":
        install_deploy(skip_tests=False)
    elif command == "clean_install":
        clean_install()
    elif command == "rebuild_all":
        rebuild_all()
    
    # Environment Commands
    elif command == "setup_venv":
        setup_venv()
    elif command == "install_deps":
        install_dependencies()
    
    # Individual Commands
    elif command == "syntax_check":
        syntax_check()
    elif command == "build_only":
        build_project(clean=False)
    elif command == "build_clean":
        build_project(clean=True)
    elif command == "kill":
        kill_processes(force=False)
    elif command == "kill_force":
        kill_processes(force=True)
    elif command == "deploy_only":
        kill_processes(force=False)  # Kill running processes first
        deploy_binary(backup=True)
    elif command == "test":
        test_deployment()
    elif command == "git_pull":
        git_pull()
    elif command == "git_push":
        git_commit_and_push()
    else:
        log(f"❌ Unknown command: {command}")
        log("Run 'python3 deployment_mcp.py' for usage help")

if __name__ == "__main__":
    main()
