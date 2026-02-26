"""Gemini AI API Integration for EduRipple Backend with OpenRouter Fallback"""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-generativeai package not installed. Install with: pip install google-generativeai")

logger = logging.getLogger(__name__)


class OpenRouterAI:
    """Wrapper class for OpenRouter API interaction"""
    
    def __init__(self):
        """Initialize OpenRouter client"""
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model_name = "openai/gpt-3.5-turbo"  # Reliable and cost-effective model
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found in environment variables")
            self.initialized = False
            return
        
        try:
            # Test connectivity
            response = requests.get("https://openrouter.ai/api/v1/auth/key",
                                  headers={"Authorization": f"Bearer {self.api_key}"})
            if response.status_code == 200:
                self.initialized = True
                logger.info("OpenRouter AI initialized successfully")
            else:
                logger.error(f"OpenRouter authentication failed: {response.status_code}")
                self.initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter AI: {str(e)}")
            self.initialized = False
    
    def _make_request(self, prompt: str) -> Optional[str]:
        """Make API request to OpenRouter"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("APP_URL", "https://eduripple.com"),
                "X-Title": "EduRipple"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error making OpenRouter request: {str(e)}")
            return None
    
    def generate_starter_activities(self, subject: str, grade: str, topic: str, count: int = 3) -> Optional[Dict[str, Any]]:
        """Generate creative starter activities for a lesson"""
        if not self.initialized:
            return {"success": False, "error": "OpenRouter AI not initialized"}
        
        try:
            prompt = f"""Generate {count} engaging starter activities for a {subject} lesson with {grade} students on "{topic}".

Each activity should:
- Take 5-10 minutes
- Require minimal resources
- Hook student interest
- Connect to prior knowledge or real-world contexts

Format as JSON with the following structure:
{{
  "activities": [
    {{
      "title": "Activity name",
      "description": "Brief description",
      "instructions": "Step-by-step instructions",
      "materials_needed": "List of materials",
      "engagement_level": "High/Medium/Low"
    }}
  ]
}}"""

            content = self._make_request(prompt)
            
            if content:
                try:
                    # Try to extract JSON from response
                    json_str = content
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": content}
            
            return {"success": False, "error": "No response from OpenRouter"}
            
        except Exception as e:
            logger.error(f"Error generating starter activities: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_assessment_questions(self, subject: str, grade: str, topic: str, count: int = 5) -> Optional[Dict[str, Any]]:
        """Generate formative and summative assessment questions"""
        if not self.initialized:
            return {"success": False, "error": "OpenRouter AI not initialized"}
        
        try:
            prompt = f"""Generate {count} assessment questions for {subject} {grade} students on "{topic}".

Include:
- 2 recall/knowledge questions
- 2 comprehension/application questions  
- 1 analysis/critical thinking question

Format as JSON:
{{
  "questions": [
    {{
      "question": "Question text",
      "type": "recall/comprehension/analysis",
      "expected_answer": "Model answer",
      "marks": "Number of marks"
    }}
  ]
}}"""

            content = self._make_request(prompt)
            
            if content:
                try:
                    json_str = content
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": content}
            
            return {"success": False, "error": "No response from OpenRouter"}
            
        except Exception as e:
            logger.error(f"Error generating assessment questions: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_learning_outcomes(self, subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
        """Generate Bloom's taxonomy-aligned learning outcomes"""
        if not self.initialized:
            return {"success": False, "error": "OpenRouter AI not initialized"}
        
        try:
            prompt = f"""Generate learning outcomes for {subject} {grade} on "{topic}" aligned to Bloom's taxonomy.

Provide outcomes at each level:
1. Remember
2. Understand
3. Apply
4. Analyze
5. Evaluate
6. Create

Each outcome should be specific, measurable, and age-appropriate for {grade} students.

Format as JSON:
{{
  "learning_outcomes": [
    {{
      "level": "Remember/Understand/Apply/Analyze/Evaluate/Create",
      "outcome": "Specific learning outcome",
      "verb": "Action verb used"
    }}
  ]
}}"""

            content = self._make_request(prompt)
            
            if content:
                try:
                    json_str = content
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": content}
            
            return {"success": False, "error": "No response from OpenRouter"}
            
        except Exception as e:
            logger.error(f"Error generating learning outcomes: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def chat_with_ai(self, message: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Simple chat interface with OpenRouter"""
        if not self.initialized:
            return {"success": False, "error": "OpenRouter AI not initialized"}
        
        try:
            full_prompt = message
            if context:
                full_prompt = f"{context}\n\nUser query: {message}"
            
            content = self._make_request(full_prompt)
            
            if content:
                return {"success": True, "response": content}
            return {"success": False, "error": "No response from OpenRouter"}
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return {"success": False, "error": str(e)}

class GeminiAI:
    """Wrapper class for Gemini API interaction"""
    
    def __init__(self):
        """Initialize Gemini client"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-2.0-flash"  # Using latest fast model for educational content
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.initialized = False
            return
        
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai is not installed")
            self.initialized = False
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model_name)
            self.initialized = True
            logger.info("Gemini AI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI: {str(e)}")
            self.initialized = False
    
    def enhance_lesson_plan(self, subject: str, grade: str, topic: str, duration: int, base_content: str) -> Optional[str]:
        """Enhance lesson plan with AI-generated content"""
        if not self.initialized:
            logger.warning("Gemini AI not initialized, returning base content")
            return base_content
        
        try:
            prompt = f"""You are an expert educational content creator. Enhance this lesson plan with creative, practical teaching strategies:

Subject: {subject}
Grade: {grade}
Topic: {topic}
Duration: {duration} minutes

Current Lesson Plan Structure:
{base_content[:1500]}

Please provide:
1. 3 innovative starter activities (choose the best for engaging {grade} students)
2. 2 interactive teaching strategies specific to {subject}
3. 2-3 real-world examples or case studies relevant to {topic}
4. 2 differentiation strategies (for advanced and struggling learners)
5. 1-2 formative assessment ideas

Format as clear, actionable bullet points that a teacher can immediately use."""

            response = self.client.generate_content(prompt)
            
            if response and response.text:
                return response.text
            return base_content
            
        except Exception as e:
            logger.error(f"Error enhancing lesson plan: {str(e)}")
            return base_content
    
    def generate_starter_activities(self, subject: str, grade: str, topic: str, count: int = 3) -> Optional[Dict[str, Any]]:
        """Generate creative starter activities for a lesson"""
        if not self.initialized:
            return {"success": False, "error": "Gemini AI not initialized"}
        
        try:
            prompt = f"""Generate {count} engaging starter activities for a {subject} lesson with {grade} students on "{topic}".

Each activity should:
- Take 5-10 minutes
- Require minimal resources
- Hook student interest
- Connect to prior knowledge or real-world contexts

Format as JSON with the following structure:
{{
  "activities": [
    {{
      "title": "Activity name",
      "description": "Brief description",
      "instructions": "Step-by-step instructions",
      "materials_needed": "List of materials",
      "engagement_level": "High/Medium/Low"
    }}
  ]
}}"""

            response = self.client.generate_content(prompt)
            
            if response and response.text:
                try:
                    # Try to extract JSON from response
                    json_str = response.text
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": response.text}
            
            return {"success": False, "error": "No response from Gemini"}
            
        except Exception as e:
            logger.error(f"Error generating starter activities: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_assessment_questions(self, subject: str, grade: str, topic: str, count: int = 5) -> Optional[Dict[str, Any]]:
        """Generate formative and summative assessment questions"""
        if not self.initialized:
            return {"success": False, "error": "Gemini AI not initialized"}
        
        try:
            prompt = f"""Generate {count} assessment questions for {subject} {grade} students on "{topic}".

Include:
- 2 recall/knowledge questions
- 2 comprehension/application questions  
- 1 analysis/critical thinking question

Format as JSON:
{{
  "questions": [
    {{
      "question": "Question text",
      "type": "recall/comprehension/analysis",
      "expected_answer": "Model answer",
      "marks": "Number of marks"
    }}
  ]
}}"""

            response = self.client.generate_content(prompt)
            
            if response and response.text:
                try:
                    json_str = response.text
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": response.text}
            
            return {"success": False, "error": "No response from Gemini"}
            
        except Exception as e:
            logger.error(f"Error generating assessment questions: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_learning_outcomes(self, subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
        """Generate Bloom's taxonomy-aligned learning outcomes"""
        if not self.initialized:
            return {"success": False, "error": "Gemini AI not initialized"}
        
        try:
            prompt = f"""Generate learning outcomes for {subject} {grade} on "{topic}" aligned to Bloom's taxonomy.

Provide outcomes at each level:
1. Remember
2. Understand
3. Apply
4. Analyze
5. Evaluate
6. Create

Each outcome should be specific, measurable, and age-appropriate for {grade} students.

Format as JSON:
{{
  "learning_outcomes": [
    {{
      "level": "Remember/Understand/Apply/Analyze/Evaluate/Create",
      "outcome": "Specific learning outcome",
      "verb": "Action verb used"
    }}
  ]
}}"""

            response = self.client.generate_content(prompt)
            
            if response and response.text:
                try:
                    json_str = response.text
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0]
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0]
                    
                    data = json.loads(json_str)
                    return {"success": True, "data": data}
                except json.JSONDecodeError:
                    return {"success": True, "raw_content": response.text}
            
            return {"success": False, "error": "No response from Gemini"}
            
        except Exception as e:
            logger.error(f"Error generating learning outcomes: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def chat_with_ai(self, message: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Simple chat interface with Gemini"""
        if not self.initialized:
            return {"success": False, "error": "Gemini AI not initialized"}
        
        try:
            full_prompt = message
            if context:
                full_prompt = f"{context}\n\nUser query: {message}"
            
            response = self.client.generate_content(full_prompt)
            
            if response and response.text:
                return {"success": True, "response": response.text}
            return {"success": False, "error": "No response from Gemini"}
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return {"success": False, "error": str(e)}


# ===== Global AI Service Initialization =====
# Initialize AI services with fallback support
gemini_ai = GeminiAI()
openrouter_ai = OpenRouterAI()

# Initialize service availability tracker
_ai_services = {
    "gemini": gemini_ai,
    "openrouter": openrouter_ai
}

# Log initialization status
def _log_ai_initialization_status():
    """Log the status of AI service initialization"""
    logger.info("=" * 50)
    logger.info("EduRipple AI Services Initialization Status")
    logger.info("=" * 50)
    
    for service_name, service_instance in _ai_services.items():
        status = "✓ READY" if service_instance.initialized else "✗ UNAVAILABLE"
        logger.info(f"{service_name.upper():15s}: {status}")
    
    active_ai, active_name = _get_active_ai()
    if active_ai:
        logger.info(f"\nACTIVE SERVICE   : {active_name.upper()}")
        logger.info("Fallback chain  : Gemini → OpenRouter")
    else:
        logger.warning("No AI services available! Some features will be limited.")
    
    logger.info("=" * 50)

# Determine which AI to use with fallback chain
def _get_active_ai():
    """Get the active AI client (Gemini preferred, OpenRouter fallback)"""
    if gemini_ai.initialized:
        return gemini_ai, "Gemini"
    elif openrouter_ai.initialized:
        return openrouter_ai, "OpenRouter"
    else:
        return None, None


# Public API functions
def is_gemini_available() -> bool:
    """Check if Gemini is available and initialized"""
    return gemini_ai.initialized


def is_openrouter_available() -> bool:
    """Check if OpenRouter is available and initialized"""
    return openrouter_ai.initialized


def get_active_ai_name() -> str:
    """Get the name of the currently active AI"""
    ai, name = _get_active_ai()
    return name or "None"


def get_ai_services_status() -> Dict[str, bool]:
    """Get status of all AI services"""
    return {
        "gemini": is_gemini_available(),
        "openrouter": is_openrouter_available(),
        "active": get_active_ai_name()
    }


# Execute initialization and logging
try:
    _log_ai_initialization_status()
except Exception as e:
    logger.error(f"Error logging AI initialization status: {str(e)}")


def enhance_lesson_plan(subject: str, grade: str, topic: str, duration: int, base_content: str) -> Optional[str]:
    """Convenience function to enhance lesson plan"""
    ai, _ = _get_active_ai()
    if not ai:
        logger.error("No AI service available")
        return base_content
    return ai.enhance_lesson_plan(subject, grade, topic, duration, base_content)


def generate_activities(subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
    """Convenience function to generate starter activities"""
    ai, _ = _get_active_ai()
    if not ai:
        return {"success": False, "error": "No AI service available"}
    return ai.generate_starter_activities(subject, grade, topic)


def generate_questions(subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
    """Convenience function to generate assessment questions"""
    ai, _ = _get_active_ai()
    if not ai:
        return {"success": False, "error": "No AI service available"}
    return ai.generate_assessment_questions(subject, grade, topic)


def generate_outcomes(subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
    """Convenience function to generate learning outcomes"""
    ai, _ = _get_active_ai()
    if not ai:
        return {"success": False, "error": "No AI service available"}
    return ai.generate_learning_outcomes(subject, grade, topic)


def chat(message: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Convenience function for chat with automatic fallback between AI providers"""
    # Try Gemini first
    if gemini_ai.initialized:
        result = gemini_ai.chat_with_ai(message, context)
        if result and result.get('success'):
            return result
        logger.warning(f"Gemini chat failed: {result.get('error', 'unknown')}, trying OpenRouter...")
    
    # Fallback to OpenRouter
    if openrouter_ai.initialized:
        result = openrouter_ai.chat_with_ai(message, context)
        if result and result.get('success'):
            return result
        logger.warning(f"OpenRouter chat also failed: {result.get('error', 'unknown')}")
    
    return {"success": False, "error": "All AI services failed or unavailable"}


if __name__ == "__main__":
    # Test Gemini integration
    if is_gemini_available():
        print("✓ Gemini AI is available")
        
        # Test chat
        response = chat("What are some effective teaching strategies for Grade 5 Mathematics?")
        if response["success"]:
            print("\nChat Test:")
            print(response["response"][:500] + "...\n")
        
        # Test activities generation
        activities = generate_activities("Mathematics", "Grade 5", "Fractions")
        print("Activities Generation:")
        print(f"Success: {activities.get('success')}\n")
        
    else:
        print("✗ Gemini AI is not available")
        print("Please install: pip install google-generativeai")
