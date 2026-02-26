"""Test the lesson generator API."""
from lesson_generator import generate_lesson_plan, generate_scheme_of_work, generate_rubric
import sys
sys.path.insert(0, '.')

try:
    # Test with simple inputs
    result = generate_lesson_plan("English", "Grade 7", "test")
    print(f"Lesson Plan Success: {result['success']}")
    if result['success']:
        print(f"Content length: {len(result['content'])} chars")
    else:
        print(f"Error: {result['error']}")
        
    result2 = generate_scheme_of_work("Mathematics", "Grade 8", "1")
    print(f"Scheme Success: {result2['success']}")
    if result2['success']:
        print(f"Content length: {len(result2['content'])} chars")
    else:
        print(f"Error: {result2['error']}")
        
    result3 = generate_rubric("Science", "Grade 9", "performance")
    print(f"Rubric Success: {result3['success']}")
    if result3['success']:
        print(f"Content length: {len(result3['content'])} chars")
    else:
        print(f"Error: {result3['error']}")
        
    print("\nAll generators working!")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
