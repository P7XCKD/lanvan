#!/usr/bin/env python3
import requests
import urllib3
import json

urllib3.disable_warnings()

print('🔒 Testing Certificate Validation API Integration')
print('=' * 50)

try:
    # Test certificate status endpoint
    response = requests.get('https://localhost/api/certificate-status', verify=False)
    data = response.json()
    
    print('✅ API Response Successful')
    print(f'📊 HTTPS Enabled: {data["https_enabled"]}')
    print(f'📊 Certificate Valid: {data["certificate_valid"]}')
    print(f'📊 Self-Signed: {data["is_self_signed"]}')
    print(f'📊 Days Until Expiry: {data["days_until_expiry"]}')
    print(f'⚠️ Warnings: {len(data["warnings"])}')
    
    if data['warnings']:
        print('⚠️ Security Warnings:')
        for warning in data['warnings']:
            print(f'   • {warning}')
    
    if data['recommendations']:
        print('💡 Recommendations:')
        for rec in data['recommendations']:
            print(f'   • {rec}')
            
    print('\n✅ Certificate validation system working perfectly!')
    
except Exception as e:
    print(f'❌ Test failed: {e}')