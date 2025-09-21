# Quiz Backend API Documentation

## Overview

The YTV2-Dashboard now includes a complete AI-powered quiz generation and storage system. This minimal integration approach adds quiz functionality without affecting the core video dashboard features.

## Architecture

### **Minimal Integration Design**
- **Single API endpoint** for AI quiz generation
- **File-based storage** in `/app/data/quiz/` directory
- **CORS enabled** for cross-origin requests from Quizzernator
- **Zero hosting costs** - reuses existing YTV2 infrastructure
- **Clean separation** - no changes to YTV2 UI or database

### **Technology Stack**
- **AI Generation**: OpenAI GPT-3.5-turbo (configurable)
- **Storage**: JSON files in persistent `/app/data/` mount
- **CORS**: Full cross-origin support for web frontends
- **Security**: Filename sanitization, input validation

## API Endpoints

### 1. Generate Quiz (AI-Powered)

**POST /api/generate-quiz**

Generate quiz questions using OpenAI's language models.

```bash
curl -X POST https://ytv2-dashboard-postgres.onrender.com/api/generate-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate 5 multiple choice questions about JavaScript basics",
    "model": "gpt-3.5-turbo",
    "max_tokens": 3000,
    "temperature": 0.7
  }'
```

**Request Parameters:**
- `prompt` (required): Quiz generation instructions
- `model` (optional): OpenAI model (default: `gpt-3.5-turbo`)
- `max_tokens` (optional): Response length limit (default: `3000`)
- `temperature` (optional): AI creativity level (default: `0.7`)

**Response:**
```json
{
  "success": true,
  "content": "{\\"count\\": 5, \\"items\\": [...]}",
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 892,
    "total_tokens": 937
  }
}
```

### 2. Save Generated Quiz

**POST /api/save-quiz**

Save a quiz to persistent storage for later use.

```bash
curl -X POST https://ytv2-dashboard-postgres.onrender.com/api/save-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "javascript_basics_quiz.json",
    "quiz": {
      "count": 5,
      "meta": {
        "topic": "JavaScript Basics",
        "difficulty": "intermediate",
        "category": "Technology",
        "subcategory": "Programming & Software Development"
      },
      "items": [...]
    }
  }'
```

**Request Parameters:**
- `quiz` (required): Complete quiz data object
- `filename` (optional): Custom filename (auto-generated if not provided)

**Auto-generated Filename Format:**
```
{topic}_{timestamp}.json
Example: javascript_basics_20250921_143052.json
```

**Response:**
```json
{
  "success": true,
  "filename": "javascript_basics_quiz.json",
  "path": "/app/data/quiz/javascript_basics_quiz.json"
}
```

### 3. List All Saved Quizzes

**GET /api/list-quizzes**

Retrieve metadata for all saved quizzes.

```bash
curl https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes
```

**Response:**
```json
{
  "success": true,
  "quizzes": [
    {
      "filename": "javascript_basics_quiz.json",
      "topic": "JavaScript Basics",
      "count": 5,
      "difficulty": "intermediate",
      "created": "2025-09-21T14:30:52Z"
    },
    {
      "filename": "python_advanced_quiz.json",
      "topic": "Python Advanced Concepts",
      "count": 10,
      "difficulty": "advanced",
      "created": "2025-09-20T16:45:12Z"
    }
  ]
}
```

### 4. Load Specific Quiz

**GET /api/quiz/:filename**

Load complete quiz data by filename.

```bash
curl https://ytv2-dashboard-postgres.onrender.com/api/quiz/javascript_basics_quiz.json
```

**Response:**
```json
{
  "success": true,
  "quiz": {
    "count": 5,
    "meta": {
      "topic": "JavaScript Basics",
      "difficulty": "intermediate",
      "category": "Technology",
      "subcategory": "Programming & Software Development"
    },
    "items": [
      {
        "question": "What is the correct way to declare a variable in JavaScript?",
        "type": "multiplechoice",
        "options": ["var x = 5;", "variable x = 5;", "v x = 5;", "declare x = 5;"],
        "correct": 0,
        "explanation": "The 'var' keyword is used to declare variables in JavaScript."
      }
    ],
    "metadata": {
      "created": "2025-09-21T14:30:52Z",
      "filename": "javascript_basics_quiz.json",
      "origin": "https://quizzernator.onrender.com"
    }
  }
}
```

### 5. Delete Quiz

**DELETE /api/quiz/:filename**

Remove a quiz from storage.

```bash
curl -X DELETE https://ytv2-dashboard-postgres.onrender.com/api/quiz/javascript_basics_quiz.json
```

**Response:**
```json
{
  "success": true,
  "message": "Quiz deleted successfully"
}
```

## Quiz JSON Schema

### Standard Quiz Format

```json
{
  "count": 5,
  "meta": {
    "topic": "JavaScript Basics",
    "difficulty": "beginner|intermediate|advanced",
    "category": "Technology",
    "subcategory": "Programming & Software Development",
    "description": "Basic concepts of JavaScript programming",
    "estimatedTime": "10 minutes",
    "tags": ["javascript", "programming", "web-development"]
  },
  "items": [
    {
      "question": "Question text here?",
      "type": "multiplechoice|truefalse|shortanswer|yesno",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0,
      "explanation": "Detailed explanation of the correct answer"
    }
  ],
  "metadata": {
    "created": "2025-09-21T14:30:52Z",
    "filename": "javascript_basics_quiz.json",
    "origin": "https://quizzernator.onrender.com"
  }
}
```

### Question Types

1. **Multiple Choice** (`multiplechoice`)
   ```json
   {
     "question": "What is 2 + 2?",
     "type": "multiplechoice",
     "options": ["3", "4", "5", "6"],
     "correct": 1,
     "explanation": "2 + 2 equals 4"
   }
   ```

2. **True/False** (`truefalse`)
   ```json
   {
     "question": "JavaScript is a compiled language.",
     "type": "truefalse",
     "options": ["True", "False"],
     "correct": 1,
     "explanation": "JavaScript is an interpreted language, not compiled"
   }
   ```

3. **Short Answer** (`shortanswer`)
   ```json
   {
     "question": "What does HTML stand for?",
     "type": "shortanswer",
     "correct": "HyperText Markup Language",
     "explanation": "HTML stands for HyperText Markup Language"
   }
   ```

4. **Yes/No** (`yesno`)
   ```json
   {
     "question": "Can CSS be used to style HTML elements?",
     "type": "yesno",
     "options": ["Yes", "No"],
     "correct": 0,
     "explanation": "Yes, CSS is specifically designed to style HTML elements"
   }
   ```

## Implementation Details

### Storage Structure

```
/app/data/quiz/
├── javascript_basics_20250921_143052.json
├── python_advanced_20250920_164512.json
├── react_components_quiz.json
└── database_fundamentals_quiz.json
```

### Security Features

1. **Filename Sanitization**
   - Removes dangerous characters: `<>:"/\\|?*`
   - Prevents path traversal attacks (`../`)
   - Auto-adds `.json` extension

2. **Input Validation**
   - JSON schema validation
   - Required field checking
   - File existence verification

3. **CORS Configuration**
   - Allows specific origins: `quizzernator.onrender.com`
   - Supports development: `localhost:3000`, `localhost:8080`
   - Proper preflight handling

### Environment Variables

Required for AI generation:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### Error Handling

All endpoints return consistent error format:
```json
{
  "error": "Detailed error message"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found (quiz doesn't exist)
- `500` - Server Error (file I/O, OpenAI API issues)

## Integration Examples

### Quizzernator Integration

The Quizzernator frontend can call these endpoints directly:

```javascript
// Generate quiz
const response = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/generate-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt: "Create 5 questions about React hooks",
    model: "gpt-3.5-turbo"
  })
});

// Save generated quiz
await fetch('https://ytv2-dashboard-postgres.onrender.com/api/save-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: "react_hooks_quiz.json",
    quiz: generatedQuizData
  })
});
```

### Cost Optimization

**GPT-3.5-turbo pricing** (recommended):
- ~$0.0015 per 1K tokens
- Typical quiz generation: ~900 tokens = $0.00135 per quiz

**GPT-4 pricing** (higher quality):
- ~$0.03 per 1K tokens
- Typical quiz generation: ~900 tokens = $0.027 per quiz

## Future Enhancements

### Planned Features
- **Bulk import/export** of quiz libraries
- **Category filtering** for quiz listings
- **Quiz templates** with predefined formats
- **Analytics** tracking (quiz completion rates)
- **Integration with YTV2 video content** (generate quizzes from video summaries)

### Potential Integrations
- **Quiz widgets** embedded in YTV2 summary pages
- **Learning paths** connecting related videos and quizzes
- **Progress tracking** across quiz sessions
- **Quiz recommendations** based on video viewing history

## Troubleshooting

### Common Issues

1. **CORS Errors**
   ```
   Access to fetch at 'https://...' from origin 'https://quizzernator.onrender.com' has been blocked by CORS policy
   ```
   **Solution**: Verify origin is in allowed list, check OPTIONS preflight

2. **OpenAI API Errors**
   ```
   {"error": "OpenAI API key not configured"}
   ```
   **Solution**: Set `OPENAI_API_KEY` environment variable in Render

3. **File Storage Issues**
   ```
   {"error": "Failed to save quiz"}
   ```
   **Solution**: Check `/app/data/` directory permissions and disk space

### Debug Commands

```bash
# Check quiz storage directory
ls -la /app/data/quiz/

# View quiz file content
cat /app/data/quiz/javascript_basics_quiz.json

# Check API endpoint
curl https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes

# Monitor logs for CORS issues
# Look for: "🌐 CORS preflight request from origin:"
# Look for: "🤖 Quiz generation request from origin:"
```

---

**Created**: September 21, 2025
**Last Updated**: September 21, 2025
**API Version**: 1.0
**Integration**: YTV2-Dashboard + Quizzernator