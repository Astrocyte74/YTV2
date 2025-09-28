# Quiz Backend API Documentation

## API Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/generate-quiz` | Generate quiz using OpenAI GPT-5-nano |
| **POST** | `/api/save-quiz` | Save generated quiz to persistent storage |
| **POST** | `/api/fetch-article` | Retrieve and sanitize article text for quiz generation |
| **GET** | `/api/list-quizzes` | List all saved quizzes with metadata |
| **GET** | `/api/quiz/:filename` | Load specific quiz by filename |
| **POST** | `/api/categorize-quiz` | AI-powered topic categorization |
| **DELETE** | `/api/quiz/:filename` | Delete specific quiz from storage |

## Overview

The YTV2-Dashboard includes a complete AI-powered quiz generation and storage system with advanced categorization. This minimal integration approach adds quiz functionality without affecting the core video dashboard features.

## Architecture

### **Minimal Integration Design**
- **AI-powered generation** using OpenAI GPT-5-nano (ultra cost-effective)
- **AI-powered categorization** with semantic understanding (not keyword-based)
- **File-based storage** in `/app/data/quiz/` directory
- **CORS enabled** for cross-origin requests from Quizzernator
- **Zero hosting costs** - reuses existing YTV2 infrastructure
- **Clean separation** - no changes to YTV2 UI or database

### **Technology Stack**
- **AI Generation**: OpenRouter models (Gemini 2.5 Flash Lite primary, DeepSeek Terminus fallback)
- **AI Categorization**: OpenAI GPT-5-nano with JSON mode (~$0.00005 per categorization)
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
    "model": "gpt-5-nano",
    "max_tokens": 3000,
    "temperature": 0.7
  }'
```

**Request Parameters:**
- `prompt` (required): Quiz generation instructions
- `model` (optional): OpenAI model (default: `gpt-5-nano`)
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

### 2a. Fetch Article Content

**POST /api/fetch-article**

Fetch external article content, sanitize HTML, and return trimmed plain text for downstream quiz generation. The endpoint enforces content-length limits and a safety user agent.

```bash
curl -X POST https://ytv2-dashboard-postgres.onrender.com/api/fetch-article \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/generative-ai-trends"
  }'
```

**Request Parameters:**
- `url` (required): Absolute HTTP or HTTPS URL to fetch.

**Response:**
```json
{
  "success": true,
  "text": "Generative AI adoption continues to accelerate...",
  "truncated": false
}
```

If the downloaded payload exceeds 500 KB or the extracted text exceeds 100,000 characters, `truncated` is returned as `true` to signal that the text was clipped. The backend trims on paragraph or sentence boundaries whenever possible to avoid mid-sentence endings and stops before the page's **References** section when present.

**Implementation Notes:**
- Uses `requests` with a custom Quizzernator user agent and 10-second timeout, streaming the body while honoring the 500 KB cap.
- Wikipedia domains short-circuit to the MediaWiki REST plain-text endpoint before falling back to HTML scraping.
- HTML is parsed with BeautifulSoup; `script`, `style`, and `noscript` blocks are removed before text extraction.
- Paragraph structure is preserved by grouping consecutive lines; clipping prefers double newlines, then sentence boundaries, then whitespace.
- Response payloads are always UTF-8 JSON and include the `truncated` flag so the client can decide whether to fetch or generate additional chunks locally.
- Frontend should still segment long articles into model-friendly windows before sending data to LLMs.

**Error Responses:**
- All failures return HTTP JSON in the shape `{ "success": false, "error": "…", "reason": "…" }`.
- `reason` values you may see:
  - `missing_body`, `invalid_json`, `missing_url`, `invalid_url`
  - `http_error` (non-200 upstream status), `unsupported_content_type`
  - `network_error` (connection/timeout issues)
  - `empty_content` (HTML parsed but no readable text)
  - `internal_error` (unexpected server failure)

**Errors:**
- `400` when the URL is missing or invalid.
- `415` when the resource is not text/HTML.
- `422` when no readable text is extracted.
- `502` when the upstream site cannot be reached.

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

### 5. AI-Powered Topic Categorization

**POST /api/categorize-quiz**

Automatically categorize quiz topics using OpenAI GPT-5-nano with semantic understanding. This AI-based system provides much more accurate categorization than keyword matching, especially for complex or multi-domain topics.

```bash
curl -X POST https://ytv2-dashboard-postgres.onrender.com/api/categorize-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "JavaScript ES6 Features",
    "quiz_content": "Optional: first few questions for context"
  }'
```

**Request Parameters:**
- `topic` (required): The quiz topic to categorize
- `quiz_content` (optional): Additional context from quiz questions

**Response:**
```json
{
  "success": true,
  "category": "Technology",
  "subcategory": "Programming & Software Development",
  "confidence": 0.9,
  "alternatives": [
    {
      "category": "AI Software Development",
      "subcategory": "AI Tools & Platforms",
      "confidence": 0.77
    },
    {
      "category": "Education",
      "subcategory": "Educational Content",
      "confidence": 0.65
    }
  ],
  "available_categories": [
    "Technology",
    "AI Software Development",
    "History",
    "Science & Nature",
    "Business",
    "Education",
    "Entertainment"
  ],
  "available_subcategories": {
    "Technology": [
      "Programming & Software Development",
      "Tech Reviews",
      "AI & Machine Learning",
      "Software Tutorials",
      "Tech News & Trends"
    ],
    "AI Software Development": [
      "AI Tools & Platforms",
      "Machine Learning",
      "AI Applications"
    ]
  }
}
```

### 6. Delete Quiz

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

## AI Categorization System

### **GPT-5-nano Powered Classification**

The quiz categorization system uses OpenAI's GPT-5-nano model with structured JSON output to provide semantic understanding of quiz topics. This is a significant upgrade from keyword-based matching.

**Key Advantages**:
- **Semantic Understanding**: Handles complex topics like "machine learning for medical diagnosis"
- **High Accuracy**: Confidence scores typically 0.8-0.9 for clear topics
- **Multi-domain Topics**: Properly categorizes topics spanning multiple categories
- **Cost Effective**: ~$0.00005 per categorization (20,000 categorizations per $1)
- **Consistent Output**: JSON mode ensures reliable response format

**Example Categorizations**:
```
"photosynthesis in plants" → Science & Nature → Physics & Chemistry (confidence: 0.9)
"machine learning for medical diagnosis" → AI Software Development → Data Engineering & ETL (confidence: 0.9)
"Napoleon Bonaparte campaigns" → History → Modern History (confidence: 0.9)
"random gibberish xyz123" → General → Mixed Content (confidence: 0.95)
```

**Fallback Behavior**: Topics that don't clearly fit any category are automatically assigned to "General" → "Mixed Content" with appropriate confidence scoring.

## Quiz JSON Schema

### Enhanced Quiz Format with YTV2 Taxonomy

```json
{
  "count": 5,
  "meta": {
    "topic": "JavaScript ES6 Features",
    "difficulty": "beginner|intermediate|advanced",
    "category": "Technology",
    "subcategory": "Programming & Software Development",
    "auto_categorized": true,
    "categorization_confidence": 0.92,
    "description": "Modern JavaScript ES6+ features and syntax",
    "estimatedTime": "15 minutes",
    "tags": ["javascript", "es6", "programming", "web-development"],
    "generated": "2025-09-21T14:30:52Z"
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
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

Optional (categorization fallback):
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

### Complete Quiz Generation Workflow

The enhanced workflow with auto-categorization:

```javascript
// Step 1: Auto-categorize the topic
const categorizationResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/categorize-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    topic: "JavaScript ES6 Features",
    quiz_content: "Arrow functions, destructuring, async/await"
  })
});

const categorization = await categorizationResponse.json();
console.log('Auto-categorized as:', categorization.category, '→', categorization.subcategory);

// Step 2: Generate quiz with categorization context
const quizResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/generate-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt: `Create 10 ${categorization.category} questions about JavaScript ES6 Features.
             Focus on ${categorization.subcategory} level content.
             Format as JSON with count, meta, and items fields.`,
    model: "google/gemini-2.5-flash-lite"
  })
});

const quizData = await quizResponse.json();
const parsedQuiz = JSON.parse(quizData.content);

// Step 3: Enhance quiz with taxonomy metadata
const enhancedQuiz = {
  ...parsedQuiz,
  meta: {
    ...parsedQuiz.meta,
    category: categorization.category,
    subcategory: categorization.subcategory,
    auto_categorized: true,
    categorization_confidence: categorization.confidence,
    generated: new Date().toISOString()
  }
};

// Step 4: Save categorized quiz
const saveResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/save-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: "javascript_es6_features_quiz.json",
    quiz: enhancedQuiz
  })
});

console.log('Quiz saved with YTV2 taxonomy integration!');
```

### Category-Based Quiz Browsing

```javascript
// Load all quizzes with category organization
const quizzesResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes');
const { quizzes } = await quizzesResponse.json();

// Group by category for hierarchical display
const quizzesByCategory = quizzes.reduce((acc, quiz) => {
  const category = quiz.category || 'Uncategorized';
  if (!acc[category]) acc[category] = {};

  const subcategory = quiz.subcategory || 'General';
  if (!acc[category][subcategory]) acc[category][subcategory] = [];

  acc[category][subcategory].push(quiz);
  return acc;
}, {});

// Render hierarchical quiz browser
Object.entries(quizzesByCategory).forEach(([category, subcategories]) => {
  console.log(`📁 ${category}`);
  Object.entries(subcategories).forEach(([subcategory, quizzes]) => {
    console.log(`  └── ${subcategory} (${quizzes.length} quizzes)`);
    quizzes.forEach(quiz => {
      console.log(`      • ${quiz.topic} (${quiz.difficulty})`);
    });
  });
});
```

### Dynamic Category Selection UI

```javascript
// Get available categories and subcategories
const categorizeResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/categorize-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ topic: "sample topic" })
});

const { available_categories, available_subcategories } = await categorizeResponse.json();

// Populate category dropdown
const categorySelect = document.getElementById('category');
available_categories.forEach(category => {
  const option = new Option(`📱 ${category}`, category);
  categorySelect.add(option);
});

// Dynamic subcategory population
categorySelect.addEventListener('change', (e) => {
  const subcategorySelect = document.getElementById('subcategory');
  subcategorySelect.innerHTML = '<option value="">Select subcategory</option>';

  const selectedCategory = e.target.value;
  if (selectedCategory && available_subcategories[selectedCategory]) {
    available_subcategories[selectedCategory].forEach(subcategory => {
      const option = new Option(subcategory, subcategory);
      subcategorySelect.add(option);
    });
    subcategorySelect.disabled = false;
  } else {
    subcategorySelect.disabled = true;
  }
});
```

### Quiz Discovery by Video Content

```javascript
// Find quizzes related to a specific video's categories
function findRelatedQuizzes(videoCategories, videoSubcategories) {
  return fetch('https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes')
    .then(response => response.json())
    .then(data => {
      return data.quizzes.filter(quiz => {
        // Exact category match
        if (videoCategories.includes(quiz.category)) return true;

        // Subcategory match across categories
        if (videoSubcategories.includes(quiz.subcategory)) return true;

        return false;
      });
    });
}

// Usage example
const relatedQuizzes = await findRelatedQuizzes(
  ['Technology', 'AI Software Development'],
  ['Programming & Software Development', 'AI Tools & Platforms']
);

console.log(`Found ${relatedQuizzes.length} related quizzes:`, relatedQuizzes);
```

### Cost Optimization

**GPT-5-nano pricing** (recommended):
- Ultra cost-effective: ~$0.00005 per categorization
- ~20,000 categorizations per $1
- Typical quiz generation: ~900 tokens = ~$0.000045 per quiz

**Model Comparison**:
- **GPT-5-nano**: ~$0.000045 per quiz (20,000 quizzes/$1)
- **GPT-4o-mini**: ~$0.00012 per quiz (8,333 quizzes/$1)
- **GPT-3.5-turbo**: ~$0.00135 per quiz (740 quizzes/$1)

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
