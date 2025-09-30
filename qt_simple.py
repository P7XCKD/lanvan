#!/usr/bin/env python3
"""
LANVAN Project Quick Test (Simple Version)
A simplified testing framework that avoids emoji character issues
"""

import sys
import os
import asyncio
import importlib
import time
import argparse
from pathlib import Path

# Add app directory to path for imports
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

class LANVANSimpleScanner:
    def __init__(self):
        self.components = {}
        self.start_time = time.time()
        
    def test_core_imports(self):
        """Test core module imports"""
        print("[TESTING] Core module imports...")
        
        # Core modules that should always work
        core_modules = [
            'config',
            'validation', 
            'aes_config',
            'aes_utils',
            'performance_config',
            'platform_detector',
            'universal_optimizer',
            'simple_platform'
        ]
        
        for module in core_modules:
            try:
                importlib.import_module(module)
                self.components[module] = True
                print(f"   [OK] {module}")
            except Exception as e:
                self.components[module] = False
                print(f"   [FAIL] {module}: {str(e)[:60]}...")
    
    def test_advanced_imports(self):
        """Test advanced module imports"""
        print("\n[TESTING] Advanced module imports...")
        
        advanced_modules = [
            'concurrent_upload_manager',
            'streaming_assembly',
            'thread_manager',
            'responsiveness_monitor',
            'android_optimizer',
            'termux_compat',
            'metadata_protection'
        ]
        
        for module in advanced_modules:
            try:
                importlib.import_module(module)
                self.components[module] = True
                print(f"   [OK] {module}")
            except Exception as e:
                self.components[module] = False
                print(f"   [FAIL] {module}: {str(e)[:60]}...")
    
    def test_network_modules(self):
        """Test network-related modules"""
        print("\n[TESTING] Network modules...")
        
        network_modules = [
            'simple_mdns',
            'mdns_manager',
            'https_redirect_server',
            'clipboard_ws'
        ]
        
        for module in network_modules:
            try:
                importlib.import_module(module)
                self.components[module] = True
                print(f"   [OK] {module}")
            except Exception as e:
                self.components[module] = False
                print(f"   [FAIL] {module}: {str(e)[:60]}...")
    
    def test_file_operations(self):
        """Test file operation capabilities"""
        print("\n[TESTING] File operations...")
        
        # Test basic file operations
        try:
            test_dir = Path("app/uploads")
            test_dir.mkdir(exist_ok=True)
            
            # Test file creation
            test_file = test_dir / "qt_test.txt"
            test_file.write_text("LANVAN test file")
            
            # Test file reading
            content = test_file.read_text()
            assert "LANVAN" in content
            
            # Cleanup
            test_file.unlink()
            
            self.components['file_operations'] = True
            print("   [OK] File operations")
            
        except Exception as e:
            self.components['file_operations'] = False
            print(f"   [FAIL] File operations: {str(e)[:60]}...")
    
    def test_path_structure(self):
        """Test project structure"""
        print("\n[TESTING] Project structure...")
        
        required_paths = [
            "app",
            "app/static",
            "app/templates", 
            "app/uploads",
            "requirements.txt"
        ]
        
        all_good = True
        for path_str in required_paths:
            path = Path(path_str)
            if path.exists():
                print(f"   [OK] {path_str}")
            else:
                print(f"   [FAIL] Missing: {path_str}")
                all_good = False
        
        self.components['project_structure'] = all_good
    
    def test_dependencies(self):
        """Test critical dependencies"""
        print("\n[TESTING] Dependencies...")
        
        deps = [
            ('fastapi', 'FastAPI'),
            ('uvicorn', 'Uvicorn'),
            ('jinja2', 'Jinja2'),
            ('cryptography', 'Cryptography'),
            ('aiofiles', 'AIO Files')
        ]
        
        for dep, name in deps:
            try:
                importlib.import_module(dep)
                self.components[f'dep_{dep}'] = True
                print(f"   [OK] {name}")
            except ImportError:
                self.components[f'dep_{dep}'] = False
                print(f"   [FAIL] {name} not installed")
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.components)
        passed_tests = sum(1 for v in self.components.values() if v)
        failed_tests = total_tests - passed_tests
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        test_time = time.time() - self.start_time
        
        print(f"\n{'='*60}")
        print(f"LANVAN PROJECT TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests:    {total_tests}")
        print(f"Passed:         {passed_tests}")
        print(f"Failed:         {failed_tests}")
        print(f"Success Rate:   {success_rate:.1f}%")
        print(f"Test Time:      {test_time:.1f}s")
        
        # Status assessment
        if success_rate >= 90:
            print(f"Status:         [EXCELLENT] Ready for deployment!")
        elif success_rate >= 75:
            print(f"Status:         [GOOD] Minor issues to resolve")
        elif success_rate >= 50:
            print(f"Status:         [FAIR] Several issues need attention")
        else:
            print(f"Status:         [POOR] Major issues - not ready")
        
        print(f"{'='*60}")
        
        # List failures
        if failed_tests > 0:
            print(f"\nFAILED COMPONENTS:")
            for component, status in self.components.items():
                if not status:
                    print(f"   - {component}")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("LANVAN Simple Project Scanner Starting...")
        print("=========================================")
        
        self.test_core_imports()
        self.test_advanced_imports()  
        self.test_network_modules()
        self.test_file_operations()
        self.test_path_structure()
        self.test_dependencies()
        
        self.print_summary()

async def main():
    """Main runner"""
    parser = argparse.ArgumentParser(description="LANVAN Simple Project Scanner")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    scanner = LANVANSimpleScanner()
    await scanner.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())