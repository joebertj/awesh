#!/usr/bin/env python3
"""
Agent-specific test suite for awesh
Tests each agent individually with clear pass/fail indicators
"""

import os
import sys
import subprocess
import time
from pathlib import Path

class AgentTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.awesh_path = self.project_root / "awesh"
        self.passed = 0
        self.failed = 0
        
    def log(self, emoji, message):
        """Log a message"""
        print(f"{emoji} {message}")
    
    def test_agent(self, name, prompt, expected_indicators, timeout=30):
        """Test a specific agent"""
        print(f"\n{'='*60}")
        print(f"🧪 Testing: {name}")
        print(f"📝 Prompt: {prompt}")
        print(f"⏱️  Timeout: {timeout}s")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                [str(self.awesh_path)],
                input=f"{prompt}\nexit\n",
                text=True,
                capture_output=True,
                timeout=timeout
            )
            
            output = result.stdout
            print(f"\n📤 Output preview:")
            # Show relevant part of output
            lines = output.split('\n')
            for line in lines:
                if '>' in line and (prompt[:20] in line):
                    # Find the response after the prompt
                    idx = lines.index(line)
                    for i in range(idx+1, min(idx+15, len(lines))):
                        if lines[i].strip():
                            print(f"   {lines[i]}")
                    break
            
            # Check for expected indicators
            missing = []
            for indicator in expected_indicators:
                if indicator not in output:
                    missing.append(indicator)
            
            if not missing:
                self.log("✅", f"{name} PASSED")
                self.passed += 1
                return True
            else:
                self.log("❌", f"{name} FAILED - Missing: {missing}")
                self.failed += 1
                return False
                
        except subprocess.TimeoutExpired:
            self.log("❌", f"{name} FAILED - Timeout after {timeout}s")
            self.failed += 1
            return False
        except Exception as e:
            self.log("❌", f"{name} FAILED - Error: {e}")
            self.failed += 1
            return False
    
    def run_all_tests(self):
        """Run all agent tests"""
        print("🚀 Agent-Specific Test Suite")
        print("Testing each awesh agent individually")
        print("="*60)
        
        # Test 1: AI Client (basic query)
        self.test_agent(
            name="AI Client",
            prompt="what is 2+2?",
            expected_indicators=["🤔 Thinking", "4"],
            timeout=25
        )
        
        # Test 2: File Agent (file context injection)
        self.test_agent(
            name="File Agent",
            prompt="what is in README.md?",
            expected_indicators=["🤔 Thinking", "awesh"],
            timeout=30
        )
        
        # Test 3: File Editor (create new file)
        self.test_agent(
            name="File Editor (Create)",
            prompt="create a script named test_script.sh that echoes hello",
            expected_indicators=["📝", "test_script.sh"],
            timeout=35
        )
        
        # Test 4: File Editor (edit existing file)
        if (self.project_root / "test_edit.txt").exists():
            self.test_agent(
                name="File Editor (Edit)",
                prompt="change Port to 9000 in test_edit.txt",
                expected_indicators=["📝", "test_edit.txt"],
                timeout=35
            )
        else:
            self.log("⏭️ ", "File Editor (Edit) - SKIPPED (test_edit.txt not found)")
        
        # Test 5: Command Execution (awesh: format)
        self.test_agent(
            name="Command Mode",
            prompt="show me the current directory",
            expected_indicators=["awesh:", "pwd"],
            timeout=30
        )
        
        # Test 6: Normal Mode (information)
        self.test_agent(
            name="Normal Mode",
            prompt="what does ls command do?",
            expected_indicators=["🤔 Thinking", "list", "files"],
            timeout=25
        )
        
        # Test 7: Security Middleware Heartbeat
        print(f"\n{'='*60}")
        print(f"🧪 Testing: Security Middleware Heartbeat")
        print(f"📝 Prompt: what is 2+2?")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                [str(self.awesh_path)],
                input="what is 2+2?\nexit\n",
                text=True,
                capture_output=True,
                timeout=30
            )
            
            # Combine stdout and stderr to check for heartbeat
            full_output = result.stdout + result.stderr
            
            # Check for security heartbeat token
            if "🔒✓" in full_output:
                self.log("✅", "Security Middleware ACTIVE (heartbeat detected: 🔒✓)")
                self.passed += 1
            elif "SECURITY_BLOCKED" in full_output or "blocked" in full_output.lower():
                # If command was blocked, that also proves security is working
                self.log("✅", "Security Middleware ACTIVE (command blocked)")
                self.passed += 1
            else:
                self.log("❌", "Security Middleware heartbeat NOT detected (might be inactive)")
                self.failed += 1
                
        except Exception as e:
            self.log("❌", f"Security Middleware test error: {e}")
            self.failed += 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Test Summary")
        print(f"{'='*60}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        total = self.passed + self.failed
        if total > 0:
            success_rate = (self.passed / total) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.failed == 0:
            print(f"\n🎉 All agent tests passed!")
            return True
        else:
            print(f"\n⚠️  Some agent tests failed. Check output above.")
            return False

def main():
    tester = AgentTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

