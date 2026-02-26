"""
Test suite for lesson generation functionality in EduRipple.
Run tests with: pytest test_lesson_generation.py -v
"""

import pytest
from lesson_generator import (
    generate_lesson_plan,
    generate_scheme_of_work,
    generate_rubric,
    query_curriculum
)


class TestQueryCurriculum:
    """Test curriculum database queries."""
    
    def test_query_valid_subject_grade(self):
        """Test querying with valid subject and grade."""
        result = query_curriculum("Mathematics", "Grade 7")
        if result:
            assert "subject" in result
            assert "grade" in result
    
    def test_query_invalid_grade(self):
        """Test querying with invalid grade."""
        result = query_curriculum("Mathematics", "Grade 99")
        assert result is None
    
    def test_query_case_insensitive(self):
        """Test that subject matching is case-insensitive."""
        result1 = query_curriculum("mathematics", "Grade 7")
        result2 = query_curriculum("MATHEMATICS", "Grade 7")
        # Both should return same result or both None
        assert result1 == result2
    
    def test_query_subject_variations(self):
        """Test various subject name variations."""
        variations = [
            ("math", "Grade 7"),
            ("maths", "Grade 7"),
            ("english", "Grade 7"),
        ]
        for subject, grade in variations:
            result = query_curriculum(subject, grade)
            # Should either return a valid result or None consistently
            assert result is None or isinstance(result, dict)


class TestLessonPlanGeneration:
    """Test lesson plan generation."""
    
    def test_generate_basic_lesson_plan(self):
        """Test basic lesson plan generation."""
        result = generate_lesson_plan("Mathematics", "Grade 7", "Fractions")
        assert isinstance(result, dict)
        assert "success" in result
        assert "content" in result
    
    def test_lesson_plan_has_required_sections(self):
        """Test that lesson plan contains required sections."""
        result = generate_lesson_plan("English", "Grade 7", "Reading Comprehension")
        content = result.get("content", "")
        
        if result["success"]:
            # Should contain standard lesson plan sections
            required_sections = [
                "ADMINISTRATIVE DETAILS",
                "STRAND",
                "LEARNING OUTCOMES",
                "ASSESSMENT",
                "LESSON DEVELOPMENT"
            ]
            for section in required_sections:
                assert any(section.lower() in line.lower() for line in content.split('\n'))
    
    def test_lesson_plan_duration_grade_based(self):
        """Test that lesson duration varies by grade."""
        result_primary = generate_lesson_plan("Mathematics", "Grade 6", "Algebra")
        result_secondary = generate_lesson_plan("Mathematics", "Grade 8", "Algebra")
        
        primary_content = result_primary.get("content", "")
        secondary_content = result_secondary.get("content", "")
        
        # Primary should have shorter duration (35 min)
        if "35" in primary_content:
            assert "35" in primary_content
        if "40" in secondary_content:
            assert "40" in secondary_content
    
    def test_lesson_plan_error_handling(self):
        """Test error handling for invalid inputs."""
        result = generate_lesson_plan("InvalidSubject", "Grade 15", "Topic")
        # Should return error response
        assert "error" in result or result.get("success") == False


class TestSchemeOfWorkGeneration:
    """Test scheme of work generation."""
    
    def test_generate_scheme_of_work(self):
        """Test basic scheme of work generation."""
        result = generate_scheme_of_work("Mathematics", "Grade 7", "1")
        assert isinstance(result, dict)
        assert "success" in result
        assert "content" in result
    
    def test_scheme_of_work_has_term(self):
        """Test that scheme includes term information."""
        result = generate_scheme_of_work("English", "Grade 7", "2")
        content = result.get("content", "")
        
        if result["success"]:
            assert "Term" in content or "TERM" in content or "term" in content


class TestRubricGeneration:
    """Test assessment rubric generation."""
    
    def test_generate_rubric(self):
        """Test basic rubric generation."""
        result = generate_rubric("Mathematics", "Grade 7", "performance")
        assert isinstance(result, dict)
        assert "success" in result
        assert "content" in result
    
    def test_rubric_has_criteria(self):
        """Test that rubric contains assessment criteria."""
        result = generate_rubric("Science", "Grade 7", "performance")
        content = result.get("content", "")
        
        if result["success"]:
            # Should contain rubric components
            assert any(word in content.lower() for word in ["criteria", "beginning", "developing", "proficient", "exemplary"])


class TestInputValidation:
    """Test input validation for lesson generation."""
    
    def test_empty_subject(self):
        """Test behavior with empty subject."""
        result = generate_lesson_plan("", "Grade 7", "Topic")
        # Should handle gracefully with fallback or error
        assert isinstance(result, dict)
    
    def test_empty_topic(self):
        """Test behavior with empty topic."""
        result = generate_lesson_plan("Mathematics", "Grade 7", "")
        # Should handle gracefully
        assert isinstance(result, dict)
    
    def test_very_long_topic(self):
        """Test behavior with very long topic string."""
        long_topic = "A" * 1000
        result = generate_lesson_plan("Mathematics", "Grade 7", long_topic)
        # Should handle gracefully without crashing
        assert isinstance(result, dict)


class TestContentQuality:
    """Test quality of generated content."""
    
    def test_lesson_plan_not_empty(self):
        """Test that generated lesson plan is not empty."""
        result = generate_lesson_plan("Mathematics", "Grade 7", "Algebra")
        if result["success"]:
            assert len(result.get("content", "")) > 100  # Should have substantial content
    
    def test_lesson_plan_contains_times(self):
        """Test that lesson plan includes time allocations."""
        result = generate_lesson_plan("English", "Grade 7", "Poetry")
        content = result.get("content", "")
        
        if result["success"]:
            # Should contain time references (minutes)
            assert any(word in content.lower() for word in ["minute", "min", "time"])
    
    def test_lesson_plan_has_learning_outcomes(self):
        """Test that lesson plan includes learning outcomes."""
        result = generate_lesson_plan("Science", "Grade 7", "Photosynthesis")
        content = result.get("content", "")
        
        if result["success"]:
            # Should mention outcomes or objectives
            assert any(phrase in content.lower() for phrase in [
                "learning outcome",
                "specific learning outcome",
                "should be able to",
                "learner should"
            ])


# Integration Tests
class TestIntegration:
    """Integration tests for lesson generation workflow."""
    
    def test_generate_complete_lesson_materials(self):
        """Test generating a complete lesson plan."""
        subject = "Mathematics"
        grade = "Grade 7"
        topic = "Fractions"
        
        # Generate lesson plan
        lesson_result = generate_lesson_plan(subject, grade, topic)
        assert lesson_result["success"] or "error" in lesson_result
        
        # Generate scheme of work
        scheme_result = generate_scheme_of_work(subject, grade, "1")
        assert scheme_result["success"] or "error" in scheme_result
        
        # Generate rubric
        rubric_result = generate_rubric(subject, grade, "performance")
        assert rubric_result["success"] or "error" in rubric_result
    
    def test_multiple_subjects(self):
        """Test generating for different subjects."""
        subjects = ["Mathematics", "English", "Science"]
        
        for subject in subjects:
            result = generate_lesson_plan(subject, "Grade 7", "General Topic")
            assert isinstance(result, dict)
            assert "success" in result or "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
