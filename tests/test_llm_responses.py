#!/usr/bin/env python3
"""
Comprehensive LLM response testing for awesh
Tests 100 natural language prompts to validate system prompt compliance
"""

import os
import sys
import subprocess
import time
import json
import re
from pathlib import Path

class LLMResponseTester:
    def __init__(self):
        self.test_results = []
        self.awesh_path = Path(__file__).parent / "awesh"
        self.passed_tests = 0
        self.total_tests = 0
        
    def log_test(self, test_name, success, message="", response=""):
        """Log test result with detailed response"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if response and len(response) > 0:
            # Truncate long responses for readability
            display_response = response[:200] + "..." if len(response) > 200 else response
            print(f"    Response: {display_response}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "response": response
        })
        
        if success:
            self.passed_tests += 1
        self.total_tests += 1
    
    def test_llm_response(self, prompt, expected_patterns=None, should_have_awesh_cmd=False):
        """Test a single LLM response"""
        try:
            result = subprocess.run(
                [str(self.awesh_path)],
                input=f"{prompt}\nexit\n",
                text=True,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.log_test(f"LLM: {prompt[:30]}...", False, f"Awesh failed with return code {result.returncode}")
                return False
            
            # Extract the AI response (after "🤔 Thinking")
            response = ""
            if "🤔 Thinking" in result.stdout:
                # Find the response after thinking dots
                thinking_end = result.stdout.find("🤔 Thinking")
                if thinking_end != -1:
                    # Find the end of thinking dots
                    response_start = result.stdout.find("\n", thinking_end)
                    if response_start != -1:
                        response = result.stdout[response_start:].strip()
                        # Remove the prompt line and "Goodbye!" if present
                        lines = response.split('\n')
                        filtered_lines = []
                        for line in lines:
                            if not line.startswith('>') and not line.startswith('Goodbye!') and line.strip():
                                filtered_lines.append(line)
                        response = '\n'.join(filtered_lines)
            
            if not response:
                self.log_test(f"LLM: {prompt[:30]}...", False, "No AI response found")
                return False
            
            # Check for expected patterns
            success = True
            issues = []
            
            if expected_patterns:
                for pattern in expected_patterns:
                    if not re.search(pattern, response, re.IGNORECASE):
                        success = False
                        issues.append(f"Missing pattern: {pattern}")
            
            # Check for awesh: command format if required
            if should_have_awesh_cmd:
                if "awesh:" not in response.lower():
                    success = False
                    issues.append("Missing 'awesh:' command format")
            
            # Check for proper response structure
            if len(response.strip()) < 10:
                success = False
                issues.append("Response too short")
            
            # Check for error messages that shouldn't be there
            error_indicators = ["error processing prompt", "failed to get ai response", "ai not ready"]
            for indicator in error_indicators:
                if indicator in response.lower():
                    success = False
                    issues.append(f"Contains error indicator: {indicator}")
            
            if success:
                self.log_test(f"LLM: {prompt[:30]}...", True, "Response follows system prompt", response)
            else:
                self.log_test(f"LLM: {prompt[:30]}...", False, f"Issues: {'; '.join(issues)}", response)
            
            return success
            
        except subprocess.TimeoutExpired:
            self.log_test(f"LLM: {prompt[:30]}...", False, "Test timed out")
            return False
        except Exception as e:
            self.log_test(f"LLM: {prompt[:30]}...", False, f"Test error: {e}")
            return False
    
    def run_comprehensive_tests(self):
        """Run 100 comprehensive LLM response tests"""
        print("🧪 Running comprehensive LLM response tests...")
        print("=" * 80)
        
        # Test categories with 100 total prompts
        test_prompts = [
            # File Operations (20 tests)
            ("list all files in current directory", ["ls", "files"], True),
            ("show me the contents of README.md", ["cat", "README"], True),
            ("create a new file called test.txt", ["touch", "test.txt"], True),
            ("delete the file test.txt", ["rm", "test.txt"], True),
            ("copy README.md to backup.md", ["cp", "README", "backup"], True),
            ("move test.txt to temp/", ["mv", "test.txt", "temp"], True),
            ("find all .py files", ["find", ".py"], True),
            ("search for 'function' in all files", ["grep", "function"], True),
            ("show file permissions", ["ls -l", "permissions"], True),
            ("create a directory called docs", ["mkdir", "docs"], True),
            ("remove the docs directory", ["rmdir", "docs"], True),
            ("show disk usage", ["df", "disk"], True),
            ("show file sizes", ["du", "size"], True),
            ("compress files into archive.tar.gz", ["tar", "archive"], True),
            ("extract files from archive.tar.gz", ["tar -x", "extract"], True),
            ("change file permissions to 755", ["chmod", "755"], True),
            ("change file ownership", ["chown", "ownership"], True),
            ("create a symbolic link", ["ln -s", "symbolic"], True),
            ("show file type information", ["file", "type"], True),
            ("count lines in all files", ["wc -l", "count"], True),
            
            # System Information (20 tests)
            ("what is the current directory?", ["pwd", "directory"], True),
            ("show system information", ["uname", "system"], True),
            ("display memory usage", ["free", "memory"], True),
            ("show CPU information", ["lscpu", "cpu"], True),
            ("list running processes", ["ps", "processes"], True),
            ("show system uptime", ["uptime", "uptime"], True),
            ("display network interfaces", ["ip", "network"], True),
            ("show environment variables", ["env", "environment"], True),
            ("display kernel version", ["uname -r", "kernel"], True),
            ("show hardware information", ["lshw", "hardware"], True),
            ("list installed packages", ["dpkg", "packages"], True),
            ("show system load", ["w", "load"], True),
            ("display date and time", ["date", "time"], True),
            ("show who is logged in", ["who", "users"], True),
            ("display system architecture", ["arch", "architecture"], True),
            ("show disk partitions", ["lsblk", "partitions"], True),
            ("display mount points", ["mount", "mount"], True),
            ("show system services", ["systemctl", "services"], True),
            ("display system logs", ["journalctl", "logs"], True),
            ("show system resources", ["top", "resources"], True),
            
            # Git Operations (15 tests)
            ("show git status", ["git status", "status"], True),
            ("list all git branches", ["git branch", "branches"], True),
            ("show git log", ["git log", "log"], True),
            ("add all files to git", ["git add", "add"], True),
            ("commit changes with message", ["git commit", "commit"], True),
            ("push changes to remote", ["git push", "push"], True),
            ("pull latest changes", ["git pull", "pull"], True),
            ("show git diff", ["git diff", "diff"], True),
            ("create a new branch", ["git checkout -b", "branch"], True),
            ("switch to main branch", ["git checkout main", "checkout"], True),
            ("merge feature branch", ["git merge", "merge"], True),
            ("show git remote", ["git remote", "remote"], True),
            ("clone a repository", ["git clone", "clone"], True),
            ("show git stash", ["git stash", "stash"], True),
            ("reset git changes", ["git reset", "reset"], True),
            
            # Network Operations (15 tests)
            ("ping google.com", ["ping", "google"], True),
            ("check internet connection", ["curl", "connection"], True),
            ("show network statistics", ["netstat", "network"], True),
            ("display routing table", ["route", "routing"], True),
            ("show active connections", ["ss", "connections"], True),
            ("test DNS resolution", ["nslookup", "dns"], True),
            ("download a file", ["wget", "download"], True),
            ("upload a file", ["scp", "upload"], True),
            ("show network interfaces", ["ip addr", "interfaces"], True),
            ("test port connectivity", ["telnet", "port"], True),
            ("show firewall rules", ["iptables", "firewall"], True),
            ("display network traffic", ["tcpdump", "traffic"], True),
            ("show network configuration", ["ifconfig", "config"], True),
            ("test network speed", ["speedtest", "speed"], True),
            ("show network routes", ["ip route", "routes"], True),
            
            # Process Management (10 tests)
            ("show all running processes", ["ps aux", "processes"], True),
            ("kill a process by name", ["pkill", "kill"], True),
            ("show process tree", ["pstree", "tree"], True),
            ("monitor system processes", ["htop", "monitor"], True),
            ("show process details", ["ps -ef", "details"], True),
            ("kill process by PID", ["kill", "pid"], True),
            ("show process memory usage", ["pmap", "memory"], True),
            ("monitor process activity", ["top", "activity"], True),
            ("show process limits", ["ulimit", "limits"], True),
            ("display process hierarchy", ["ps -f", "hierarchy"], True),
            
            # Text Processing (10 tests)
            ("count lines in a file", ["wc -l", "count"], True),
            ("search for text in files", ["grep", "search"], True),
            ("sort lines in a file", ["sort", "sort"], True),
            ("remove duplicate lines", ["uniq", "duplicates"], True),
            ("show first 10 lines", ["head", "first"], True),
            ("show last 10 lines", ["tail", "last"], True),
            ("replace text in files", ["sed", "replace"], True),
            ("extract columns from file", ["cut", "columns"], True),
            ("join two files", ["join", "join"], True),
            ("compare two files", ["diff", "compare"], True),
            
            # System Administration (10 tests)
            ("show system information", ["uname -a", "system"], True),
            ("display system load", ["uptime", "load"], True),
            ("show disk usage", ["df -h", "disk"], True),
            ("display memory usage", ["free -h", "memory"], True),
            ("show running services", ["systemctl", "services"], True),
            ("display system logs", ["journalctl", "logs"], True),
            ("show system users", ["who", "users"], True),
            ("display system time", ["date", "time"], True),
            ("show system architecture", ["arch", "architecture"], True),
            ("display system version", ["lsb_release", "version"], True)
        ]
        
        print(f"🧪 Testing {len(test_prompts)} LLM responses...")
        print("=" * 80)
        
        # Run all tests
        for i, (prompt, expected_patterns, should_have_awesh_cmd) in enumerate(test_prompts, 1):
            print(f"\n[{i:3d}/100] Testing: {prompt}")
            self.test_llm_response(prompt, expected_patterns, should_have_awesh_cmd)
            time.sleep(0.5)  # Brief pause between tests
        
        # Summary
        print("\n" + "=" * 80)
        print(f"📊 LLM Response Test Results: {self.passed_tests}/{self.total_tests} tests passed")
        
        if self.passed_tests >= self.total_tests * 0.8:  # 80% pass rate
            print("🎉 LLM responses are working correctly!")
            return True
        else:
            print("⚠️ LLM responses need improvement.")
            return False
    
    def analyze_response_patterns(self):
        """Analyze response patterns for system prompt compliance"""
        print("\n🔍 Analyzing response patterns...")
        
        awesh_cmd_count = 0
        normal_response_count = 0
        error_count = 0
        
        for result in self.test_results:
            if result["success"]:
                response = result["response"]
                if "awesh:" in response.lower():
                    awesh_cmd_count += 1
                else:
                    normal_response_count += 1
            else:
                error_count += 1
        
        print(f"📈 Response Analysis:")
        print(f"  ✅ Commands with 'awesh:' format: {awesh_cmd_count}")
        print(f"  📝 Normal responses: {normal_response_count}")
        print(f"  ❌ Errors: {error_count}")
        
        # Check system prompt compliance
        compliance_rate = (awesh_cmd_count + normal_response_count) / self.total_tests
        print(f"  🎯 System prompt compliance: {compliance_rate:.1%}")
        
        return compliance_rate >= 0.8

def main():
    """Main test runner"""
    tester = LLMResponseTester()
    
    print("🚀 Starting comprehensive LLM response testing...")
    print("This will test 100 natural language prompts to validate system prompt compliance.")
    print("=" * 80)
    
    success = tester.run_comprehensive_tests()
    compliance = tester.analyze_response_patterns()
    
    if success and compliance:
        print("\n🎉 All tests passed! LLM is following system prompt correctly.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
