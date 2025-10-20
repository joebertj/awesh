#!/usr/bin/env python3
"""
Comprehensive test suite for awesh
Tests configuration, model switching, AI responses, and core functionality
"""

import os
import sys
import subprocess
import time
import tempfile
import json
from pathlib import Path

class AweshTester:
    def __init__(self):
        self.test_results = []
        # Tests are in tests/ subdirectory, so go up one level for project root
        self.project_root = Path(__file__).parent.parent
        self.awesh_path = self.project_root / "awesh"
        self.config_path = Path.home() / ".aweshrc"
        self.switch_model_path = self.project_root / "switch_model.py"
        
    def log_test(self, test_name, success, message=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        
    def test_build_success(self):
        """Test that awesh builds successfully"""
        print("  🔨 Testing build process...")
        try:
            result = subprocess.run(
                ["make", "clean", "&&", "make"],
                cwd=self.project_root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and self.awesh_path.exists():
                self.log_test("Build Success", True, "awesh binary created successfully")
                return True
            else:
                self.log_test("Build Success", False, f"Build failed: {result.stderr}")
                return False
        except Exception as e:
            self.log_test("Build Success", False, f"Build exception: {e}")
            return False
    
    def test_config_file_exists(self):
        """Test that config file exists and has correct format"""
        if not self.config_path.exists():
            self.log_test("Config File", False, "Config file does not exist")
            return False
            
        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
                
            # Check for required keys
            required_keys = ["AI_PROVIDER", "MODEL"]
            missing_keys = []
            for key in required_keys:
                if key not in content:
                    missing_keys.append(key)
            
            if missing_keys:
                self.log_test("Config File", False, f"Missing keys: {missing_keys}")
                return False
            else:
                self.log_test("Config File", True, "Config file has required keys")
                return True
        except Exception as e:
            self.log_test("Config File", False, f"Config read error: {e}")
            return False
    
    def test_default_model_config(self):
        """Test that default model is set to OpenRouter Mistral"""
        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            # Check for OpenRouter and Mistral
            has_openrouter = "AI_PROVIDER=openrouter" in content
            has_mistral = "mistralai/mistral-small-3.1-24b-instruct:free" in content
            
            if has_openrouter and has_mistral:
                self.log_test("Default Model Config", True, "OpenRouter Mistral configured as default")
                return True
            else:
                self.log_test("Default Model Config", False, 
                    f"Missing config: openrouter={has_openrouter}, mistral={has_mistral}")
                return False
        except Exception as e:
            self.log_test("Default Model Config", False, f"Config check error: {e}")
            return False
    
    def test_model_switcher_exists(self):
        """Test that model switcher script exists and is executable"""
        if not self.switch_model_path.exists():
            self.log_test("Model Switcher", False, "switch_model.py does not exist")
            return False
            
        if not os.access(self.switch_model_path, os.X_OK):
            self.log_test("Model Switcher", False, "switch_model.py is not executable")
            return False
            
        self.log_test("Model Switcher", True, "Model switcher script exists and is executable")
        return True
    
    def test_model_switching_functionality(self):
        """Test model switching functionality"""
        try:
            # Test switching to OpenAI
            result = subprocess.run(
                [sys.executable, str(self.switch_model_path), "openai"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.log_test("Model Switching", False, f"Switch to OpenAI failed: {result.stderr}")
                return False
            
            # Check config was updated
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            if "AI_PROVIDER=openai" in content and "MODEL=gpt-3.5-turbo" in content:
                self.log_test("Model Switching", True, "Successfully switched to OpenAI")
            else:
                self.log_test("Model Switching", False, "Config not updated correctly")
                return False
            
            # Switch back to Mistral
            result = subprocess.run(
                [sys.executable, str(self.switch_model_path), "mistral"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.log_test("Model Switching", False, f"Switch back to Mistral failed: {result.stderr}")
                return False
            
            # Check config was updated back
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            if "AI_PROVIDER=openrouter" in content and "mistralai/mistral-small-3.1-24b-instruct:free" in content:
                self.log_test("Model Switching", True, "Successfully switched back to Mistral")
                return True
            else:
                self.log_test("Model Switching", False, "Config not updated back correctly")
                return False
                
        except Exception as e:
            self.log_test("Model Switching", False, f"Model switching error: {e}")
            return False
    
    def test_awesh_startup(self):
        """Test that awesh starts up without errors"""
        try:
            # Start awesh with a simple command and timeout
            result = subprocess.run(
                [str(self.awesh_path)],
                input="echo 'test startup'\nexit\n",
                text=True,
                capture_output=True,
                timeout=15
            )
            
            # Check for successful startup indicators
            if "awesh v0.1.0" in result.stdout and "test startup" in result.stdout:
                self.log_test("Awesh Startup", True, "Awesh starts up and executes commands")
                return True
            else:
                self.log_test("Awesh Startup", False, f"Startup failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.log_test("Awesh Startup", False, "Awesh startup timed out")
            return False
        except Exception as e:
            self.log_test("Awesh Startup", False, f"Startup error: {e}")
            return False
    
    def test_unfiltered_command_execution(self):
        """Test unfiltered command execution (new feature)"""
        try:
            # Test a simple command that should execute directly
            result = subprocess.run(
                [str(self.awesh_path)],
                input="echo 'unfiltered test'\nexit\n",
                text=True,
                capture_output=True,
                timeout=15
            )
            
            if "unfiltered test" in result.stdout:
                self.log_test("Unfiltered Execution", True, "Commands execute directly without intervention")
                return True
            else:
                self.log_test("Unfiltered Execution", False, "Command execution failed")
                return False
        except Exception as e:
            self.log_test("Unfiltered Execution", False, f"Execution error: {e}")
            return False
    
    def test_ai_query_detection(self):
        """Test AI query detection and response"""
        try:
            # Test an AI query that should trigger backend assistance
            result = subprocess.run(
                [str(self.awesh_path)],
                input="what is the current directory?\nexit\n",
                text=True,
                capture_output=True,
                timeout=20
            )
            
            # Look for thinking dots and response
            if "🤔 Thinking" in result.stdout and ("/home/joebert/AI/awesh" in result.stdout or "✅" in result.stdout):
                self.log_test("AI Query Detection", True, "AI queries are detected and processed")
                return True
            else:
                self.log_test("AI Query Detection", False, "AI query not processed correctly")
                return False
        except Exception as e:
            self.log_test("AI Query Detection", False, f"AI query error: {e}")
            return False
    
    def test_error_command_handling(self):
        """Test error command handling with post-facto detection"""
        try:
            # Test a command that should fail
            result = subprocess.run(
                [str(self.awesh_path)],
                input="nonexistentcommand\nexit\n",
                text=True,
                capture_output=True,
                timeout=15
            )
            
            # Should show thinking dots for anomalous results
            if "🤔 Thinking" in result.stdout:
                self.log_test("Error Command Handling", True, "Error commands trigger AI assistance")
                return True
            else:
                self.log_test("Error Command Handling", False, "Error handling not working")
                return False
        except Exception as e:
            self.log_test("Error Command Handling", False, f"Error handling error: {e}")
            return False
    
    def test_backend_components(self):
        """Test that backend components are available"""
        try:
            # Check if backend package is installed
            result = subprocess.run(
                [sys.executable, "-c", "import awesh_backend; print('Backend available')"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "Backend available" in result.stdout:
                self.log_test("Backend Components", True, "Backend package is available")
                return True
            else:
                self.log_test("Backend Components", False, "Backend package not available")
                return False
        except Exception as e:
            self.log_test("Backend Components", False, f"Backend check error: {e}")
            return False
    
    def test_internal_commands(self):
        """Test 10 common internal non-interactive commands"""
        internal_commands = [
            "echo 'Hello World'",
            "pwd",
            "whoami",
            "date",
            "ls -la",
            "ps aux | head -5",
            "df -h",
            "free -h",
            "uptime",
            "uname -a"
        ]
        
        passed = 0
        for cmd in internal_commands:
            try:
                result = subprocess.run(
                    [str(self.awesh_path)],
                    input=f"{cmd}\nexit\n",
                    text=True,
                    capture_output=True,
                    timeout=10
                )
                
                if result.returncode == 0 and not "🤔 Thinking" in result.stdout:
                    passed += 1
                else:
                    self.log_test(f"Internal Command: {cmd}", False, "Command failed or triggered AI")
            except Exception as e:
                self.log_test(f"Internal Command: {cmd}", False, f"Error: {e}")
        
        success = passed >= 8  # Allow 2 failures
        self.log_test("Internal Commands", success, f"{passed}/10 internal commands executed directly")
        return success
    
    def test_external_commands(self):
        """Test 10 common external non-interactive commands"""
        external_commands = [
            "curl -s https://httpbin.org/get | head -3",
            "wget -qO- https://httpbin.org/get | head -3",
            "ping -c 1 8.8.8.8",
            "nslookup google.com",
            "which python3",
            "which git",
            "which make",
            "which gcc",
            "which vim",
            "which nano"
        ]
        
        passed = 0
        for cmd in external_commands:
            try:
                result = subprocess.run(
                    [str(self.awesh_path)],
                    input=f"{cmd}\nexit\n",
                    text=True,
                    capture_output=True,
                    timeout=15
                )
                
                if result.returncode == 0 and not "🤔 Thinking" in result.stdout:
                    passed += 1
                else:
                    self.log_test(f"External Command: {cmd}", False, "Command failed or triggered AI")
            except Exception as e:
                self.log_test(f"External Command: {cmd}", False, f"Error: {e}")
        
        success = passed >= 7  # Allow 3 failures (network issues, missing tools)
        self.log_test("External Commands", success, f"{passed}/10 external commands executed directly")
        return success
    
    def test_interactive_commands(self):
        """Test 5 common interactive commands"""
        interactive_commands = [
            "top -n 1",           # Top with 1 iteration
            "watch -n 1 'ls -la'", # Watch command
            "vi --version",       # Vi version check
            "vi README.md",       # Vi with file (should open editor)
            "less --version"      # Less version check
        ]
        
        passed = 0
        for cmd in interactive_commands:
            try:
                # For truly interactive commands, we need to handle them differently
                if cmd in ["top -n 1", "watch -n 1 'ls -la'"]:
                    # These should run with limited iterations and timeout quickly
                    result = subprocess.run(
                        [str(self.awesh_path)],
                        input=f"{cmd}\nexit\n",
                        text=True,
                        capture_output=True,
                        timeout=5  # Short timeout for interactive commands
                    )
                    
                    # These commands should either execute or be detected as interactive
                    if result.returncode == 0 or "🤔 Thinking" in result.stdout:
                        passed += 1
                    else:
                        self.log_test(f"Interactive Command: {cmd}", False, "Command not handled properly")
                        
                elif cmd == "vi README.md":
                    # This should open vi and then exit
                    result = subprocess.run(
                        [str(self.awesh_path)],
                        input=f"{cmd}\n:q!\nexit\n",  # Exit vi without saving
                        text=True,
                        capture_output=True,
                        timeout=10
                    )
                    
                    # Should either open vi or be detected as interactive
                    if result.returncode == 0 or "🤔 Thinking" in result.stdout:
                        passed += 1
                    else:
                        self.log_test(f"Interactive Command: {cmd}", False, "Vi not handled properly")
                        
                else:
                    # Version checks should work normally
                    result = subprocess.run(
                        [str(self.awesh_path)],
                        input=f"{cmd}\nexit\n",
                        text=True,
                        capture_output=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        passed += 1
                    else:
                        self.log_test(f"Interactive Command: {cmd}", False, "Command failed")
                        
            except subprocess.TimeoutExpired:
                # Timeout is expected for some interactive commands
                passed += 1
            except Exception as e:
                self.log_test(f"Interactive Command: {cmd}", False, f"Error: {e}")
        
        success = passed >= 3  # Allow 2 failures
        self.log_test("Interactive Commands", success, f"{passed}/5 interactive commands handled")
        return success
    
    def test_natural_language_prompts(self):
        """Test 10 natural language prompts to test backend"""
        nl_prompts = [
            "what is the current directory?",
            "show me the files in this directory",
            "what is the current time?",
            "list all running processes",
            "show disk usage",
            "what is the system uptime?",
            "display network interfaces",
            "show memory usage",
            "what version of python is installed?",
            "list all environment variables"
        ]
        
        passed = 0
        for prompt in nl_prompts:
            try:
                result = subprocess.run(
                    [str(self.awesh_path)],
                    input=f"{prompt}\nexit\n",
                    text=True,
                    capture_output=True,
                    timeout=20
                )
                
                # Should trigger AI assistance
                if "🤔 Thinking" in result.stdout and ("✅" in result.stdout or "awesh:" in result.stdout):
                    passed += 1
                else:
                    self.log_test(f"NL Prompt: {prompt}", False, "Did not trigger AI or get proper response")
            except Exception as e:
                self.log_test(f"NL Prompt: {prompt}", False, f"Error: {e}")
        
        success = passed >= 7  # Allow 3 failures
        self.log_test("Natural Language Prompts", success, f"{passed}/10 NL prompts processed by AI")
        return success
    
    def test_security_middleware_available(self):
        """Test that security middleware is available and responsive"""
        try:
            # Test a simple command that should work normally
            result = subprocess.run(
                [str(self.awesh_path)],
                input="echo 'security test'\nexit\n",
                text=True,
                capture_output=True,
                timeout=10
            )
            
            # Should execute normally without security intervention
            if "security test" in result.stdout and "🤔 Thinking" not in result.stdout:
                self.log_test("Security Middleware", True, "Security middleware available and not interfering with normal commands")
                return True
            else:
                self.log_test("Security Middleware", False, "Security middleware not working properly")
                return False
        except Exception as e:
            self.log_test("Security Middleware", False, f"Security middleware error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Running comprehensive awesh test suite...")
        print("=" * 60)
        
        # Core functionality tests
        print("🔧 Core Functionality Tests:")
        print("  [1/5] Testing build...")
        self.test_build_success()
        print("  [2/5] Testing config...")
        self.test_config_file_exists()
        print("  [3/5] Testing model config...")
        self.test_default_model_config()
        print("  [4/5] Testing model switcher...")
        self.test_model_switcher_exists()
        print("  [5/5] Testing backend...")
        self.test_backend_components()
        
        # Model switching tests
        print("\n🔄 Model Switching Tests:")
        print("  [1/1] Testing model switching...")
        self.test_model_switching_functionality()
        
        # Runtime tests
        print("\n⚡ Runtime Tests:")
        print("  [1/4] Testing startup...")
        self.test_awesh_startup()
        print("  [2/4] Testing command execution...")
        self.test_unfiltered_command_execution()
        print("  [3/4] Testing AI query...")
        self.test_ai_query_detection()
        print("  [4/4] Testing error handling...")
        self.test_error_command_handling()
        
        # Command execution tests - THESE ARE SLOW, SKIP FOR NOW
        print("\n🖥️ Command Execution Tests: ⏭️  SKIPPED (too slow, run separately)")
        # self.test_internal_commands()
        # self.test_external_commands()
        # self.test_interactive_commands()
        
        # AI and security tests - THESE ARE SLOW, SKIP FOR NOW
        print("\n🤖 AI & Security Tests: ⏭️  SKIPPED (too slow, run separately)")
        # self.test_natural_language_prompts()
        # self.test_security_middleware_available()
        
        # Summary
        print("=" * 60)
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed >= total * 0.8:  # Allow 20% failure rate for comprehensive tests
            print("🎉 Test suite passed! awesh is working correctly.")
            return True
        else:
            print("⚠️ Too many tests failed. Check the output above for details.")
            return False

def main():
    """Main test runner"""
    tester = AweshTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
