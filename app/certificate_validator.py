"""
[LOCK] Safe SSL Certificate Validator for Lanvan

This module provides certificate validation and security warnings
without breaking existing HTTPS functionality.

Features:
- Certificate expiry checking
- Self-signed certificate detection
- Security warnings for users
- Non-breaking validation
- Production readiness assessment
"""
import logging
import socket
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass
import ipaddress

logger = logging.getLogger(__name__)

@dataclass
class CertValidationResult:
    """Certificate validation result"""
    valid: bool
    is_self_signed: bool = False
    days_until_expiry: Optional[int] = None
    warnings: List[str] = None
    errors: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
        if self.recommendations is None:
            self.recommendations = []

class SafeCertificateValidator:
    """
    [SHIELD] Safe Certificate Validator
    
    Validates certificates without breaking HTTPS functionality.
    Provides warnings and recommendations for security improvements.
    """
    
    @staticmethod
    def validate_certificate_safe(cert_path: Path, key_path: Path) -> CertValidationResult:
        """
        [SEARCH] Safely validate certificate without breaking functionality
        
        This method uses built-in Python libraries only and gracefully
        handles missing dependencies.
        """
        result = CertValidationResult(valid=False)
        
        try:
            # Check if certificate files exist
            if not cert_path.exists():
                result.errors.append(f"Certificate file not found: {cert_path}")
                return result
                
            if not key_path.exists():
                result.errors.append(f"Private key file not found: {key_path}")
                return result
            
            # Try to load and validate certificate using cryptography library
            try:
                return SafeCertificateValidator._validate_with_cryptography(cert_path, key_path)
            except ImportError:
                # Fallback to basic validation without cryptography
                logger.info("cryptography library not available, using basic validation")
                return SafeCertificateValidator._validate_basic(cert_path, key_path)
                
        except Exception as e:
            result.errors.append(f"Certificate validation failed: {str(e)}")
            logger.error(f"Certificate validation error: {e}")
            return result
    
    @staticmethod
    def _validate_with_cryptography(cert_path: Path, key_path: Path) -> CertValidationResult:
        """Validate using cryptography library (full validation)"""
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            from cryptography.x509.oid import ExtensionOID
            
            result = CertValidationResult(valid=True)
            
            # Load certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            
            # Check expiry
            now = datetime.utcnow()
            days_until_expiry = (cert.not_valid_after - now).days
            result.days_until_expiry = days_until_expiry
            
            if days_until_expiry < 0:
                result.errors.append("Certificate has expired")
                result.valid = False
            elif days_until_expiry < 30:
                result.warnings.append(f"Certificate expires in {days_until_expiry} days")
            
            # Check if self-signed
            is_self_signed = cert.issuer == cert.subject
            result.is_self_signed = is_self_signed
            
            if is_self_signed:
                result.warnings.append("Using self-signed certificate")
                result.recommendations.append("Consider using certificates from a trusted CA for production")
            
            # Check Subject Alternative Names (SAN)
            try:
                san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                san_names = san_ext.value
                
                # Check for localhost/127.0.0.1
                has_localhost = any(
                    name.value in ['localhost', '127.0.0.1'] 
                    for name in san_names 
                    if hasattr(name, 'value')
                )
                
                if not has_localhost:
                    result.warnings.append("Certificate may not work with localhost")
                    
            except x509.ExtensionNotFound:
                result.warnings.append("No Subject Alternative Names found")
            
            # Check key strength
            public_key = cert.public_key()
            if hasattr(public_key, 'key_size'):
                if public_key.key_size < 2048:
                    result.warnings.append(f"Weak key size: {public_key.key_size} bits")
                    result.recommendations.append("Use at least 2048-bit RSA keys")
            
            return result
            
        except Exception as e:
            result = CertValidationResult(valid=False)
            result.errors.append(f"Cryptography validation failed: {str(e)}")
            return result
    
    @staticmethod
    def _validate_basic(cert_path: Path, key_path: Path) -> CertValidationResult:
        """Basic validation without cryptography library"""
        result = CertValidationResult(valid=True)
        
        # Check file sizes (basic sanity check)
        cert_size = cert_path.stat().st_size
        key_size = key_path.stat().st_size
        
        if cert_size < 100:
            result.warnings.append("Certificate file seems too small")
        if key_size < 100:
            result.warnings.append("Private key file seems too small")
        
        # Read certificate content for basic checks
        try:
            with open(cert_path, 'r') as f:
                cert_content = f.read()
            
            if 'BEGIN CERTIFICATE' not in cert_content:
                result.errors.append("Invalid certificate format")
                result.valid = False
            
            # Basic self-signed detection (heuristic)
            if cert_content.count('-----BEGIN CERTIFICATE-----') == 1:
                result.is_self_signed = True
                result.warnings.append("Likely self-signed certificate (basic check)")
                result.recommendations.append("Consider using certificates from a trusted CA")
        
        except Exception as e:
            result.warnings.append(f"Could not read certificate content: {str(e)}")
        
        return result
    
    @staticmethod
    def check_network_security(local_ip: str) -> Dict[str, any]:
        """Check network security context"""
        security_info = {
            'is_local_network': False,
            'is_localhost': False,
            'network_type': 'unknown',
            'recommendations': []
        }
        
        try:
            # Check if IP is localhost
            if local_ip in ['127.0.0.1', 'localhost', '::1']:
                security_info['is_localhost'] = True
                security_info['network_type'] = 'localhost'
                security_info['recommendations'].append("Localhost access is secure for development")
            
            # Check if IP is in private network ranges
            else:
                ip_obj = ipaddress.ip_address(local_ip)
                if ip_obj.is_private:
                    security_info['is_local_network'] = True
                    security_info['network_type'] = 'private_network'
                    security_info['recommendations'].append("Private network access is relatively secure")
                else:
                    security_info['network_type'] = 'public_network'
                    security_info['recommendations'].append("[WARN] Public network detected - use trusted certificates")
        
        except Exception:
            security_info['recommendations'].append("Could not determine network security level")
        
        return security_info

def display_certificate_warnings(cert_result: CertValidationResult, network_info: Dict = None):
    """
    [!] Display certificate security warnings in a user-friendly way
    """
    if not cert_result.valid:
        print("[!] SSL Certificate Issues Detected:")
        for error in cert_result.errors:
            print(f"   [ERR] {error}")
        return
    
    # Show warnings
    if cert_result.warnings:
        print("[WARN]  SSL Certificate Warnings:")
        for warning in cert_result.warnings:
            print(f"   [WARN]  {warning}")
    
    # Show recommendations
    if cert_result.recommendations:
        print("[TIP] Security Recommendations:")
        for rec in cert_result.recommendations:
            print(f"   [TIP] {rec}")
    
    # Network context
    if network_info:
        print(f"[NET] Network Context: {network_info.get('network_type', 'unknown')}")
        for rec in network_info.get('recommendations', []):
            print(f"   [SHIELD]  {rec}")
    
    # Production warnings for self-signed certificates
    if cert_result.is_self_signed:
        print("\n[LOCK] Self-Signed Certificate Information:")
        print("   [OK] Secure for development and local networks")
        print("   [OK] Prevents eavesdropping on local traffic")
        print("   [WARN]  Will show browser warnings (this is normal)")
        print("   [INFO] For production: Use Let's Encrypt or commercial CA certificates")

def validate_and_warn_certificates(cert_dir: Path, local_ip: str = "127.0.0.1") -> CertValidationResult:
    """
    [SHIELD] Main certificate validation function
    
    Validates certificates and displays appropriate warnings without
    breaking HTTPS functionality.
    """
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"
    
    # Validate certificate
    cert_result = SafeCertificateValidator.validate_certificate_safe(cert_path, key_path)
    
    # Get network security context
    network_info = SafeCertificateValidator.check_network_security(local_ip)
    
    # Display warnings (non-blocking)
    display_certificate_warnings(cert_result, network_info)
    
    return cert_result

# Convenience function for easy integration
def quick_certificate_check(certs_dir: Path) -> bool:
    """
    Quick certificate check that returns True if certificates are usable
    (even if they have warnings)
    """
    try:
        cert_path = certs_dir / "cert.pem"
        key_path = certs_dir / "key.pem"
        
        if not cert_path.exists() or not key_path.exists():
            return False
        
        result = SafeCertificateValidator.validate_certificate_safe(cert_path, key_path)
        return result.valid
        
    except Exception:
        return False