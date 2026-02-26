"""Test script to verify Gemini API integration"""

import os
import sys
import json

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from gemini_integration import (
    is_gemini_available,
    generate_activities,
    generate_questions,
    generate_outcomes,
    chat,
    GeminiAI
)

def test_gemini_status():
    """Test if Gemini is available"""
    print("=" * 60)
    print("TEST 1: Checking Gemini AI Status")
    print("=" * 60)
    available = is_gemini_available()
    print(f"✓ Gemini Available: {available}\n")
    return available


def test_gemini_chat():
    """Test basic chat functionality"""
    print("=" * 60)
    print("TEST 2: Testing Chat with Gemini")
    print("=" * 60)
    
    response = chat("What are the best teaching strategies for Grade 5 Mathematics?")
    
    if response and response.get("success"):
        print("✓ Chat successful!")
        print(f"Response:\n{response['response'][:300]}...\n")
        return True
    else:
        print(f"✗ Chat failed: {response.get('error')}\n")
        return False


def test_generate_activities():
    """Test activity generation"""
    print("=" * 60)
    print("TEST 3: Testing Activity Generation")
    print("=" * 60)
    
    result = generate_activities("Mathematics", "Grade 5", "Fractions")
    
    if result and result.get("success"):
        print("✓ Activities generated successfully!")
        print(f"Response keys: {list(result.keys())}")
        if "data" in result:
            print(f"Activities count: {len(result['data'].get('activities', []))}\n")
        return True
    else:
        if "raw_content" in result:
            print(f"✓ Generated (raw format):\n{result['raw_content'][:200]}...\n")
            return True
        print(f"✗ Generation failed: {result.get('error')}\n")
        return False


def test_generate_questions():
    """Test question generation"""
    print("=" * 60)
    print("TEST 4: Testing Question Generation")
    print("=" * 60)
    
    result = generate_questions("Science", "Grade 6", "Photosynthesis")
    
    if result and result.get("success"):
        print("✓ Questions generated successfully!")
        if "data" in result:
            print(f"Questions count: {len(result['data'].get('questions', []))}\n")
        return True
    else:
        if "raw_content" in result:
            print(f"✓ Generated (raw format):\n{result['raw_content'][:200]}...\n")
            return True
        print(f"✗ Generation failed: {result.get('error')}\n")
        return False


def test_generate_outcomes():
    """Test learning outcomes generation"""
    print("=" * 60)
    print("TEST 5: Testing Learning Outcomes Generation")
    print("=" * 60)
    
    result = generate_outcomes("English", "Grade 7", "Creative Writing")
    
    if result and result.get("success"):
        print("✓ Learning outcomes generated successfully!")
        if "data" in result:
            print(f"Outcomes count: {len(result['data'].get('learning_outcomes', []))}\n")
        return True
    else:
        if "raw_content" in result:
            print(f"✓ Generated (raw format):\n{result['raw_content'][:200]}...\n")
            return True
        print(f"✗ Generation failed: {result.get('error')}\n")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("GEMINI API INTEGRATION TEST SUITE")
    print("=" * 60 + "\n")
    
    # Check if Gemini is available
    if not test_gemini_status():
        print("✗ Gemini API is not available. Please ensure:")
        print("  1. google-generativeai package is installed")
        print("  2. GEMINI_API_KEY is set in .env file")
        print("  3. API key is valid")
        sys.exit(1)
    
    # Run tests
    tests = [
        ("Chat", test_gemini_chat),
        ("Activities", test_generate_activities),
        ("Questions", test_generate_questions),
        ("Learning Outcomes", test_generate_outcomes),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} test failed with exception: {str(e)}\n")
            results[test_name] = False
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:20} {status}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✓ All tests passed! Gemini API integration is working correctly.")
    else:
        print(f"\n✗ {total_count - passed_count} test(s) failed. Please check the errors above.")


if __name__ == "__main__":
    main()
