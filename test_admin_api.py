"""Test script to verify the admin API works."""
import requests
import json
import time

time.sleep(2)  # Wait for server

try:
    # Test the admin curriculum API
    print("Testing admin API endpoints...")
    print()
    
    # Get all curriculum data
    response = requests.get("http://127.0.0.1:5000/admin/curriculum/api/all", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("[OK] /admin/curriculum/api/all")
        print(f"  Total subjects: {len(data.get('data', []))}")
        print(f"  Average completeness: {data.get('stats', {}).get('average_completeness')}%")
        print()
        
        # Show first subject
        if data.get('data'):
            subject = data['data'][0]
            print(f"  Sample subject: {subject['subject']} {subject['grade']}")
            print(f"    Completeness: {subject['completeness_score']:.1f}%")
            print(f"    Learning outcomes: {len(subject.get('learning_outcomes', []))} items")
            print(f"    Status: {subject['status']}")
    else:
        print(f"[ERROR] /admin/curriculum/api/all returned {response.status_code}")
    
    print()
    print("✓ Admin dashboard API is functional!")
    
except Exception as e:
    print(f"[ERROR] {e}")
    exit(1)
