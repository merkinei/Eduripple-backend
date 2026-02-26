# Global AI Service Initialization - OpenRouter Fallback Support

## Overview

The EduRipple backend now supports **global initialization of AI services** with **OpenRouter as an automatic fallback** when Gemini is unavailable. This provides robust AI-powered features with graceful degradation.

## Architecture

### Initialization Flow

```
Application Start
    ↓
Load Environment Variables (.env)
    ↓
Initialize Gemini AI (if GEMINI_API_KEY configured)
    ↓
Initialize OpenRouter AI (if OPENROUTER_API_KEY configured)
    ↓
Log Initialization Status
    ↓
Ready to Serve Requests
```

### Fallback Chain

```
User Request
    ↓
Is Gemini Available?
    ├─ YES → Use Gemini
    └─ NO → Is OpenRouter Available?
         ├─ YES → Use OpenRouter
         └─ NO → Return Error (503 Service Unavailable)
```

## Configuration

### Environment Variables (.env)

```env
# Gemini configuration (Primary AI service)
GEMINI_API_KEY=your-gemini-api-key-here

# OpenRouter configuration (Fallback AI service)
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

### Optional: Use Only OpenRouter

If you prefer to use OpenRouter without Gemini, simply omit or leave empty:
```env
# GEMINI_API_KEY=        # Leave empty or omit
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

## Global Initialization Details

### Module: `gemini_integration.py`

**Global Instances:**
- `gemini_ai`: GeminiAI instance
- `openrouter_ai`: OpenRouterAI instance
- `_ai_services`: Dictionary tracking all services

**Initialization Functions:**
```python
def _log_ai_initialization_status()
    # Logs comprehensive status of all AI services on startup
    
def _get_active_ai()
    # Returns (ai_instance, service_name) based on availability
    
def is_gemini_available() -> bool
    # Check Gemini availability
    
def is_openrouter_available() -> bool
    # Check OpenRouter availability
    
def get_active_ai_name() -> str
    # Get name of currently active service
    
def get_ai_services_status() -> Dict[str, bool]
    # Get comprehensive status of all services
```

### Startup Logging

On application startup, the following is logged:
```
==================================================
EduRipple AI Services Initialization Status
==================================================
GEMINI           : ✓ READY
OPENROUTER       : ✓ READY

ACTIVE SERVICE   : GEMINI
Fallback chain   : Gemini → OpenRouter
==================================================
```

Or with fallback:
```
==================================================
EduRipple AI Services Initialization Status
==================================================
GEMINI           : ✗ UNAVAILABLE
OPENROUTER       : ✓ READY

ACTIVE SERVICE   : OPENROUTER
Fallback chain   : Gemini → OpenRouter
==================================================
```

## API Endpoints

### Status Check Endpoint

**Endpoint:** `GET /api/gemini/status`

**Response (Both services available):**
```json
{
    "available": true,
    "active_service": "Gemini",
    "services": {
        "gemini": {
            "available": true,
            "status": "Ready"
        },
        "openrouter": {
            "available": true,
            "status": "Ready (Fallback)"
        }
    },
    "fallback_chain": "Gemini → OpenRouter",
    "message": "AI services ready. Using: Gemini"
}
```

**Response (Only OpenRouter available):**
```json
{
    "available": true,
    "active_service": "OpenRouter",
    "services": {
        "gemini": {
            "available": false,
            "status": "Not initialized"
        },
        "openrouter": {
            "available": true,
            "status": "Ready (Fallback)"
        }
    },
    "fallback_chain": "Gemini → OpenRouter",
    "message": "AI services ready. Using: OpenRouter"
}
```

**Response (No services available):**
```json
{
    "available": false,
    "active_service": "None",
    "services": {
        "gemini": {
            "available": false,
            "status": "Not initialized"
        },
        "openrouter": {
            "available": false,
            "status": "Not initialized"
        }
    },
    "fallback_chain": "Gemini → OpenRouter",
    "message": "No AI services available. Some features will be limited."
}
```

### AI-Powered Endpoints

All AI endpoints now support fallback:

- `POST /api/gemini/activities` - Generate starter activities
- `POST /api/gemini/questions` - Generate assessment questions
- `POST /api/gemini/learning-outcomes` - Generate learning outcomes
- `POST /api/gemini/chat` - Chat with AI
- `POST /api/gemini/enhance-lesson` - Enhance lesson plans

**Error Response (No service available):**
```json
{
    "success": false,
    "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
}
```
HTTP Status: 503 Service Unavailable

## Feature Parity

Both Gemini and OpenRouter support the same features:
- ✓ Starter Activity Generation
- ✓ Assessment Question Generation
- ✓ Learning Outcomes Generation
- ✓ Educational Chat
- ✓ Lesson Plan Enhancement

## Testing

### Run the Initialization Test

```bash
python test_ai_initialization.py
```

This will:
1. Display API key configuration status
2. Show individual service availability
3. Display active service
4. Show comprehensive status report
5. Provide warnings and setup instructions if needed

### Expected Output

```
🔍 Running AI Initialization Tests...

============================================================
EduRipple AI Services Initialization Test
============================================================

API Key Configuration:
  GEMINI_API_KEY:      ✓ Configured
  OPENROUTER_API_KEY:  ✓ Configured

Service Availability:
  Gemini:              ✓ Available
  OpenRouter:          ✓ Available

Active Service: Gemini

Full Status Report:
  {'gemini': True, 'openrouter': True, 'active': 'Gemini'}

✓ Overall Status: AI services ready
  Fallback chain: Gemini → OpenRouter
  Currently using: Gemini

============================================================

Testing Flask Integration...
------------------------------------------------------------
✓ API Status Endpoint would return:
  Gemini available: True
  OpenRouter available: True
  Active service: Gemini
```

## Troubleshooting

### Issue: "No AI services available"

**Causes:**
1. Missing or invalid `GEMINI_API_KEY`
2. Missing or invalid `OPENROUTER_API_KEY`
3. `google-generativeai` package not installed (for Gemini)
4. Network connectivity issues

**Solutions:**
1. Verify API keys in `.env` file
2. Install Gemini package: `pip install google-generativeai`
3. Test network connectivity
4. Check logs for detailed error messages

### Issue: Gemini not initializing but OpenRouter is

**This is expected behavior!** The system will:
1. Detect Gemini is unavailable
2. Fall back to OpenRouter automatically
3. All AI features will continue to work

Check logs to see why Gemini failed and address the issue, but your application remains operational.

## Code Examples

### Check Service Status in Code

```python
from gemini_integration import (
    is_gemini_available,
    is_openrouter_available,
    get_active_ai_name,
    get_ai_services_status
)

# Check individual services
if is_gemini_available():
    print("Using Gemini")
elif is_openrouter_available():
    print("Using OpenRouter fallback")
else:
    print("No AI service available")

# Get active service name
active = get_active_ai_name()
print(f"Current service: {active}")

# Get full status
status = get_ai_services_status()
print(f"Gemini ready: {status['gemini']}")
print(f"OpenRouter ready: {status['openrouter']}")
```

### Use AI Functions with Fallback

```python
from gemini_integration import (
    generate_activities,
    generate_questions,
    generate_outcomes,
    chat
)

# All these automatically use Gemini if available, else OpenRouter
activities = generate_activities("Math", "Grade 5", "Fractions")
questions = generate_questions("Science", "Grade 6", "Photosynthesis")
outcomes = generate_outcomes("English", "Grade 4", "Literature Analysis")
chat_result = chat("What's a good teaching strategy?")

# All will work with either service - no changes needed
```

## Production Recommendations

1. **Always configure both services** for maximum reliability
2. **Monitor logs** for service initialization status
3. **Test both services** during deployment
4. **Set up alerts** if both services become unavailable
5. **Use `/api/gemini/status` endpoint** for health checks

## Migration Notes

If you were previously using Gemini only:
1. No code changes required - everything is backward compatible
2. Optionally add `OPENROUTER_API_KEY` for fallback support
3. Test with both services to ensure feature parity
4. Monitor logs for any service-specific issues

If you were manually implementing fallback:
1. Remove custom fallback logic - use the built-in system
2. Update error handling to use consolidated endpoints
3. Use `get_ai_services_status()` for monitoring instead of custom checks
