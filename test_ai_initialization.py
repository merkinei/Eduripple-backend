#!/usr/bin/env python3
"""
Test script to verify AI services initialization including OpenRouter fallback
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging for clear output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Import AI services
from gemini_integration import (
    is_gemini_available,
    is_openrouter_available,
    get_active_ai_name,
    get_ai_services_status,
)

def test_ai_initialization():
    """Test AI services initialization"""
    print("\n" + "=" * 60)
    print("EduRipple AI Services Initialization Test")
    print("=" * 60)
    
    # Print API key status (without revealing full keys)
    print("\nAPI Key Configuration:")
    print(f"  GEMINI_API_KEY:      {'✓ Configured' if os.getenv('GEMINI_API_KEY') else '✗ Not configured'}")
    print(f"  OPENROUTER_API_KEY:  {'✓ Configured' if os.getenv('OPENROUTER_API_KEY') else '✗ Not configured'}")
    
    # Test individual services
    print("\nService Availability:")
    print(f"  Gemini:              {'✓ Available' if is_gemini_available() else '✗ Not available'}")
    print(f"  OpenRouter:          {'✓ Available' if is_openrouter_available() else '✗ Not available'}")
    
    # Get active service
    active_service = get_active_ai_name()
    print(f"\nActive Service: {active_service or 'NONE'}")
    
    # Get full status
    status = get_ai_services_status()
    print(f"\nFull Status Report:")
    print(f"  {status}")
    
    # Overall status
    has_service = is_gemini_available() or is_openrouter_available()
    print(f"\n{'✓ Overall Status' if has_service else '✗ Overall Status'}: {'AI services ready' if has_service else 'No AI services available'}")
    
    if has_service:
        print(f"  Fallback chain: Gemini → OpenRouter")
        print(f"  Currently using: {active_service}")
    else:
        print("\n  ⚠ WARNING: No AI services configured!")
        print("  To use AI features, please:")
        print("  1. Install google-generativeai: pip install google-generativeai")
        print("  2. Configure GEMINI_API_KEY in .env file")
        print("  OR")
        print("  1. Configure OPENROUTER_API_KEY in .env file (as fallback)")
    
    print("\n" + "=" * 60 + "\n")
    
    return has_service


def test_api_endpoints():
    """Test that Flask endpoints can access the AI services"""
    print("Testing Flask Integration...")
    print("-" * 60)
    
    try:
        from gemini_integration import get_ai_services_status
        
        # Simulate endpoint call
        status = get_ai_services_status()
        
        print("✓ API Status Endpoint would return:")
        print(f"  Gemini available: {status['gemini']}")
        print(f"  OpenRouter available: {status['openrouter']}")
        print(f"  Active service: {status['active']}")
        
        return True
    except Exception as e:
        print(f"✗ Error testing API endpoints: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n🔍 Running AI Initialization Tests...\n")
    
    # Test initialization
    has_service = test_ai_initialization()
    
    # Test API endpoints
    api_ok = test_api_endpoints()
    
    # Exit with appropriate code
    sys.exit(0 if (has_service or api_ok) else 1)
