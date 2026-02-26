# EduRipple Backend API Documentation

## Overview
EduRipple is an educational platform that provides curriculum-based lesson planning, assessment rubrics, and AI-powered learning resources.

## Authentication
All API endpoints (except public pages) require user authentication via session or JWT token.

### Rate Limiting
- Default: 200 requests per day, 50 per hour per IP
- AI endpoints: 10 requests per hour per user

## Endpoints

### Curriculum/CBC Endpoints

#### POST `/api/cbc`
Generate curriculum-based documents (lesson plans, schemes of work, rubrics).

**Authentication:** Required (Teacher login)

**Request Body:**
```json
{
  "prompt": "Generate a Grade 7 Mathematics lesson plan on fractions"
}
```

**Response:**
```json
{
  "success": true,
  "response": "LESSON PLAN (TSC-READY)...",
  "downloads": [
    {
      "name": "lesson_plan_*.docx",
      "url": "/resources/lesson_plan_*.docx"
    }
  ],
  "resources": [
    {
      "name": "resource.docx",
      "url": "/resources/resource.docx"
    }
  ]
}
```

**Query Format:**
- For lesson plans: "Grade 7 Mathematics lesson plan on [topic]"
- For schemes of work: "Grade 7 Mathematics scheme of work Term 1"
- For assessment rubrics: "Grade 7 Mathematics assessment rubric"

**Valid Subjects:**
- Mathematics, English, Kiswahili, Science
- Integrated Science, Social Studies, CRE, IRE
- Creative Arts, Creative Arts and Sports
- Agriculture and Nutrition, Pre-technical Studies

**Valid Grades:** Grade 1-9

---

### AI Enhancement Endpoints

#### POST `/api/gemini/activities`
Generate starter activities for a lesson using AI.

**Authentication:** Required
**Rate Limit:** 10 per hour

**Request Body:**
```json
{
  "subject": "Mathematics",
  "grade": "Grade 7",
  "topic": "Fractions",
  "count": 3
}
```

**Response:**
```json
{
  "success": true,
  "activities": [
    {
      "title": "Activity name",
      "description": "Brief description",
      "duration": "5-10 minutes",
      "resources": "Materials needed"
    }
  ]
}
```

---

#### POST `/api/gemini/questions`
Generate assessment questions for a topic.

**Authentication:** Required
**Rate Limit:** 10 per hour

**Request Body:**
```json
{
  "subject": "Mathematics",
  "grade": "Grade 7",
  "topic": "Fractions",
  "count": 5
}
```

**Response:**
```json
{
  "success": true,
  "questions": [
    {
      "question": "Question text",
      "difficulty": "medium",
      "answer": "Expected answer"
    }
  ]
}
```

---

#### POST `/api/gemini/learning-outcomes`
Generate specific learning outcomes for a topic.

**Authentication:** Required
**Rate Limit:** 10 per hour

**Request Body:**
```json
{
  "subject": "Mathematics",
  "grade": "Grade 7",
  "topic": "Fractions",
  "count": 5
}
```

**Response:**
```json
{
  "success": true,
  "outcomes": [
    "By the end of the lesson, learners should be able to...",
    ...
  ]
}
```

---

#### POST `/api/gemini/chat`
Chat with AI for general educational queries.

**Authentication:** Required
**Rate Limit:** 10 per hour

**Request Body:**
```json
{
  "message": "How do I teach fractions effectively?"
}
```

**Response:**
```json
{
  "success": true,
  "response": "AI response text here..."
}
```

---

#### POST `/api/gemini/enhance-lesson`
Enhance an existing lesson plan with AI suggestions.

**Authentication:** Required
**Rate Limit:** 10 per hour

**Request Body:**
```json
{
  "subject": "Mathematics",
  "grade": "Grade 7",
  "topic": "Fractions",
  "duration": 40,
  "base_lesson": "Existing lesson content..."
}
```

**Response:**
```json
{
  "success": true,
  "enhanced_content": "Enhanced lesson with AI suggestions...",
  "original_content": "Original lesson..."
}
```

---

#### GET `/api/gemini/status`
Check availability of AI services.

**Authentication:** Optional

**Response:**
```json
{
  "gemini_available": true,
  "openrouter_available": true,
  "active_service": "gemini"
}
```

---

### Resource Endpoints

#### GET `/api/resources`
List all available downloadable resources.

**Response:**
```json
[
  {
    "name": "resource_name.docx",
    "url": "/resources/resource_name.docx",
    "date": "2024-01-15T10:30:00",
    "size": 102400
  }
]
```

---

#### GET `/resources/<filename>`
Download a specific resource file.

**Parameters:**
- `filename` (path): The resource file name

**Response:** File download

---

### Teacher Authentication Endpoints

#### POST `/teacher/signup`
Create a new teacher account.

**Request Body:**
```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "school": "ABC School",
  "password": "secure_password",
  "subject_area": "Mathematics",
  "grade_level": "Grade 7-9",
  "years_experience": 5,
  "bio": "Experienced mathematics teacher"
}
```

---

#### POST `/teacher/signin`
Login to teacher account.

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "secure_password"
}
```

---

#### POST `/teacher/signout`
Logout from current session.

---

#### POST `/teacher/change-password`
Change teacher account password.

**Authentication:** Required

**Request Body:**
```json
{
  "current_password": "old_password",
  "new_password": "new_password"
}
```

---

### Public Endpoints

#### GET `/`
Home page

#### GET `/features`
Features page

#### GET `/how-it-works`
How it works page

#### GET `/about`
About page

#### GET `/library`
Resource library page

#### POST `/contact/submit`
Submit contact form

**Request Body:**
```json
{
  "name": "Sender name",
  "email": "sender@example.com",
  "message": "Contact message"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "success": false,
  "error": "Invalid input: [specific error message]"
}
```

### 401 Unauthorized
```json
{
  "success": false,
  "error": "Login required"
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded. Please try again later."
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": "An error occurred while processing your request. Please try again."
}
```

---

## Input Validation Rules

### Prompt Validation
- Maximum length: 2000 characters
- Must not be empty

### Subject Validation
- Must be from the list of valid subjects
- Case-insensitive

### Grade Validation
- Must be Grade 1-9 format
- Examples: "Grade 7", "grade 1", "GRADE 9"

---

## Caching

The following requests are cached:
- CBC content queries (1 hour cache)
- Curriculum data (1 hour cache)

Cache can be cleared by restarting the server.

---

## Environment Variables Required

```
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
YOUTUBE_API_KEY=your_youtube_api_key
ENVIRONMENT=production|development
FLASK_SECRET_KEY=your_secret_key
```

---

## Logging

All API requests and responses are logged in `logs/app.log` with the following structure:
```json
{
  "event": "api_request|api_response|api_error",
  "method": "GET|POST",
  "endpoint": "/api/endpoint",
  "status_code": 200,
  "duration_ms": 150,
  "user_id": "user_id",
  "timestamp": "2024-01-15T10:30:00"
}
```

---

## Version
API Version: 1.0.0
Last Updated: February 2026
