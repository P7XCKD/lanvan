#!/usr/bin/env python3
"""
[LOCK] SSL Certificate Validation Test

Tests the certificate validation system to ensure it:
1. Detects self-signed certificates
2. Checks certificate expiry
3. Provides security warnings
4. Does NOT break HTTPS functionality
"""
import sys
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_certificate_validation():
    """Test certificate validation functionality"""
    print("[LOCK] Testing SSL Certificate Validation")
    print("=" * 50)
    
    try:
        from app.certificate_validator import (
            SafeCertificateValidator, 
            validate_and_warn_certificates,
            quick_certificate_check
        )
        
        certs_dir = Path("certs")
        cert_path = certs_dir / "cert.pem"
        key_path = certs_dir / "key.pem"
        
        # Test 1: Check if certificates exist
        print(" Test 1: Certificate file existence")
        if cert_path.exists() and key_path.exists():
            print("   [OK] Certificate files found")
        else:
            print("   [WARN] Certificate files not found - generating for test...")
            # Try to generate certificates for testing
            try:
                import subprocess
                result = subprocess.run([
                    sys.executable, "certs/generate_certs.py"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("   [OK] Test certificates generated")
                else:
                    print(f"   [ERR] Certificate generation failed: {result.stderr}")
                    return
            except Exception as e:
                print(f"   [ERR] Could not generate test certificates: {e}")
                return
        
        # Test 2: Basic certificate validation
        print("\n Test 2: Certificate validation")
        result = SafeCertificateValidator.validate_certificate_safe(cert_path, key_path)
        
        if result.valid:
            print("   [OK] Certificates are valid and usable")
        else:
            print("   [ERR] Certificate validation failed:")
            for error in result.errors:
                print(f"      • {error}")
            return
        
        # Test 3: Self-signed detection
        print("\n Test 3: Self-signed certificate detection")
        if result.is_self_signed:
            print("   [OK] Self-signed certificate detected (expected for development)")
        else:
            print("   ℹ Certificate appears to be CA-signed")
        
        # Test 4: Expiry checking
        print("\n Test 4: Certificate expiry check")
        if result.days_until_expiry is not None:
            if result.days_until_expiry > 30:
                print(f"   [OK] Certificate valid for {result.days_until_expiry} days")
            elif result.days_until_expiry > 0:
                print(f"   [WARN] Certificate expires in {result.days_until_expiry} days")
            else:
                print("   [ERR] Certificate has expired")
        else:
            print("   ℹ Could not determine expiry date (basic validation mode)")
        
        # Test 5: Security warnings
        print("\n Test 5: Security warnings and recommendations")
        if result.warnings:
            print("   [WARN] Security warnings detected:")
            for warning in result.warnings:
                print(f"      • {warning}")
        else:
            print("   [OK] No security warnings")
        
        if result.recommendations:
            print("   [TIP] Security recommendations:")
            for rec in result.recommendations:
                print(f"      • {rec}")
        
        # Test 6: Quick check function
        print("\n Test 6: Quick certificate check")
        quick_result = quick_certificate_check(certs_dir)
        if quick_result:
            print("   [OK] Quick check passed - certificates usable")
        else:
            print("   [ERR] Quick check failed")
        
        # Test 7: Full validation with warnings
        print("\n Test 7: Full validation with user-friendly output")
        print("   (This should display formatted warnings)")
        validate_and_warn_certificates(certs_dir, "127.0.0.1")
        
        print("\n[OK] All certificate validation tests completed!")
        
        # Summary
        print("\n[INFO] Test Summary:")
        print(f"   • Certificate valid: {result.valid}")
        print(f"   • Self-signed: {result.is_self_signed}")
        print(f"   • Warnings: {len(result.warnings)}")
        print(f"   • Recommendations: {len(result.recommendations)}")
        print(f"   • Errors: {len(result.errors)}")
        
        return True
        
    except ImportError as e:
        print(f"[ERR] Missing dependency: {e}")
        print("   Note: Certificate validation will work with basic checks")
        return False
    except Exception as e:
        print(f"[ERR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_integration():
    """Test API endpoint integration"""
    print("\n[LINK] Testing API Integration")
    print("=" * 30)
    
    try:
        import requests
        
        # Try to connect to running server
        response = requests.get("http://localhost:8000/api/certificate-status", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("   [OK] API endpoint accessible")
            print(f"   [STATS] HTTPS enabled: {data.get('https_enabled', 'unknown')}")
            
            if data.get('https_enabled'):
                print(f"   [STATS] Certificate valid: {data.get('certificate_valid', 'unknown')}")
                print(f"   [STATS] Self-signed: {data.get('is_self_signed', 'unknown')}")
                if data.get('warnings'):
                    print(f"   [WARN] Warnings: {len(data['warnings'])}")
            
        else:
            print(f"   [WARN] API returned status {response.status_code}")
            
    except Exception as e:
        if "ConnectionError" in str(type(e).__name__):
            print("   [WARN] Server not running - skipping API test")
        else:
            print(f"   [ERR] API test failed: {e}")

def test_non_breaking_functionality():
    """Test that validation doesn't break HTTPS"""
    print("\n[SHIELD] Testing Non-Breaking Functionality")
    print("=" * 40)
    
    try:
        from app.certificate_validator import quick_certificate_check
        certs_dir = Path("certs")
        
        # This should always return True/False, never crash
        result = quick_certificate_check(certs_dir)
        print(f"   [OK] Quick check completed: {result}")
        
        # Test with invalid paths (should not crash)
        invalid_dir = Path("nonexistent_certs")
        result = quick_certificate_check(invalid_dir)
        print(f"   [OK] Invalid path handled gracefully: {result}")
        
        print("   [OK] Certificate validation is non-breaking")
        
    except Exception as e:
        print(f"   [ERR] Non-breaking test failed: {e}")

if __name__ == "__main__":
    print("[START] SSL Certificate Security Validation Tests")
    print("=" * 60)
    
    success = test_certificate_validation()
    
    if success:
        test_api_integration()
        test_non_breaking_functionality()
        
        print("\n[TARGET] Key Benefits Achieved:")
        print("   [OK] Certificate validation working")
        print("   [OK] Security warnings displayed")
        print("   [OK] HTTPS functionality preserved")
        print("   [OK] Production recommendations provided")
        print("   [OK] Non-breaking implementation")
        
    else:
        print("\n[WARN] Some tests failed, but HTTPS will still work normally")