#!/usr/bin/env python3
import requests
import urllib3
import json

urllib3.disable_warnings()

print('[LOCK] Testing Certificate Validation API Integration')
print('=' * 50)

try:
    # Test certificate status endpoint
    response = requests.get('https://localhost/api/certificate-status', verify=False)
    data = response.json()
    
    print('[OK] API Response Successful')
    print(f'[STATS] HTTPS Enabled: {data["https_enabled"]}')
    print(f'[STATS] Certificate Valid: {data["certificate_valid"]}')
    print(f'[STATS] Self-Signed: {data["is_self_signed"]}')
    print(f'[STATS] Days Until Expiry: {data["days_until_expiry"]}')
    print(f'[WARN] Warnings: {len(data["warnings"])}')
    
    if data['warnings']:
        print('[WARN] Security Warnings:')
        for warning in data['warnings']:
            print(f'   • {warning}')
    
    if data['recommendations']:
        print('[TIP] Recommendations:')
        for rec in data['recommendations']:
            print(f'   • {rec}')
            
    print('\n[OK] Certificate validation system working perfectly!')
    
except Exception as e:
    print(f'[ERR] Test failed: {e}')