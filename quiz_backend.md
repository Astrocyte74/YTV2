# Quiz Backend API Documentation

## API Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/generate-quiz` | Generate quiz using OpenRouter LLMs (Gemini 2.5 Flash Lite default) |
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
- **AI-powered generation** using OpenRouter (Gemini 2.5 Flash Lite primary, DeepSeek Terminus fallback)
- **AI-powered categorization** with semantic understanding (OpenAI GPT-5-nano)
- **File-based storage** in `data/quiz/` (persisted to `/app/data/quiz/` in production)
- **CORS enabled** for cross-origin requests from Quizzernator
- **Zero hosting costs** - reuses existing YTV2 infrastructure
- **Clean separation** - no changes to YTV2 UI or database

### **Technology Stack**
- **AI Generation**: OpenRouter chat completions (`google/gemini-2.5-flash-lite`, fallback `deepseek/deepseek-v3.1-terminus`)
- **AI Categorization**: OpenAI GPT-5-nano with JSON mode (requires `OPENAI_API_KEY`)
- **Storage**: JSON files in persistent `/app/data/` mount
- **CORS**: Full cross-origin support for web frontends
- **Security**: Filename sanitization, input validation

## Frontend Integration

The Quizzernator web client (`quizzernator` repo) consumes these endpoints directly. Important coordination points:
- The browser client hardcodes the same OpenRouter defaults documented here (`google/gemini-2.5-flash-lite` with `deepseek/deepseek-v3.1-terminus` fallback, `max_tokens=1800`, `temperature=0.7`). Updating defaults in one place should be mirrored in the other.
- `/api/list-quizzes` returns filename/topic/difficulty/count/created only. The frontend now hydrates each entry by calling `/api/quiz/:filename`, caching the payload locally (`quizDetailCache`) so taxonomy metadata (category/subcategory, confidence) is available without re-fetching on every view.
- Saves from the UI include enriched `meta` fields (topic, difficulty, category, subcategory, `auto_categorized`, `categorization_confidence`) so that a subsequent list + detail fetch round-trips the same data.
- Deletes and edits in the UI evict or refresh the local cache to stay aligned with the backend.

### Quizzernator Deep Linking

Quizzernator can auto-load a saved quiz via URL parameters. This enables one-tap playback from the Telegram bot or other tools once a quiz is saved here.

- Load by filename stored on this backend:
  - `https://quizzernator.onrender.com/?quiz=api:<filename>`
- Autoplay immediately after loading:
  - `https://quizzernator.onrender.com/?quiz=api:<filename>&autoplay=1`
- Full API URL also supported (mapped internally):
  - `https://quizzernator.onrender.com/?quiz=https://ytv2-dashboard-postgres.onrender.com/api/quiz/<filename>`

If the quiz cannot be loaded (missing/deleted), Quizzernator falls back to the default selection with a friendly notice.

Storage shape is preserved as `options[] + correct` for compatibility; Quizzernator normalizes to `choices[] + solution` at load time.

Filename convention used by the Telegram bot: `slug(title)[videoId][timestamp].json`.

Minimum `meta` fields to include on save: `topic`, `difficulty`, `language`, `category`, `subcategory`, `count` (equals `items.length`), and when applicable `auto_categorized`, `categorization_confidence`.

Defaults used by the bot for generation: 10 items, `multiplechoice` + `truefalse`, `temperature=0.7`, `max_tokens=1800`, `model=google/gemini-2.5-flash-lite`, `fallback_model=deepseek/deepseek-v3.1-terminus`. Language matches the summary language.

Rate limiting guidance: cap concurrent generations per user/chat; queue overflow to manage cost.

## API Endpoints

### 1. Generate Quiz (AI-Powered)

**POST /api/generate-quiz**

Generate quiz questions using OpenRouter-hosted language models.

```bash
curl -X POST https://ytv2-dashboard-postgres.onrender.com/api/generate-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate 5 multiple choice questions about JavaScript basics",
    "model": "google/gemini-2.5-flash-lite",
    "fallback_model": "deepseek/deepseek-v3.1-terminus",
    "max_tokens": 1800,
    "temperature": 0.7
  }'
```

**Request Parameters:**
- `prompt` (required): Quiz generation instructions
- `model` (optional): Primary OpenRouter model (default: `google/gemini-2.5-flash-lite`)
- `fallback_model` (optional): Alternate model used if the primary fails (default: `deepseek/deepseek-v3.1-terminus`)
- `max_tokens` (optional): Response length limit (default: `1800`)
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
  },
  "model": "google/gemini-2.5-flash-lite"
}
```

**Notes:**
- Requires `OPENROUTER_API_KEY` in the environment.
- Set `fallback_model` to `null` to skip the automatic retry.
- The Quizzernator frontend posts both `model` and `fallback_model` with these defaults; changing them here requires updating the frontend constants too.
- Prompt structure differs slightly by use case:
  - **Topic-only requests** (no reference text) instruct the model to “Create a `<count>`-question quiz about `<topic>` for a `<difficulty>` learner” and enforce a JSON schema with the selected question types.
  - **Reference/URL-backed requests** (initiated after `/api/fetch-article`) stream the article in chunks; each chunk prompt says “This is chunk X of Y… Aim to produce `<chunkGoal>` questions drawn strictly from this chunk,” and reiterates the JSON schema rules. The frontend merges chunk results client-side before saving.

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
  "path": "data/quiz/javascript_basics_quiz.json"
}
```

The handler stores quizzes under `data/quiz/` relative to the app working directory (mounted to `/app/data/quiz/` in production).

**Frontend expectations:** saved payloads should include `meta.topic`, `meta.difficulty`, `meta.language`, `meta.category`, `meta.subcategory`, `meta.count` (equals `items.length` when unspecified), and (when auto-categorised) `meta.auto_categorized`/`meta.categorization_confidence`. The Quizzernator UI injects or consumes these fields so the same metadata is available when the quiz is reloaded.

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
      "created": "2025-09-21T14:30:52.813245"
    },
    {
      "filename": "python_advanced_quiz.json",
      "topic": "Python Advanced Concepts",
      "count": 10,
      "difficulty": "advanced",
      "created": "2025-09-20T16:45:12.104572"
    }
  ]
}
```

`created` is populated from quiz metadata when available; otherwise it falls back to the file's modification timestamp (float seconds since epoch).

> ⚠️ The listing does not include category/subcategory metadata. Fetch an individual quiz via `/api/quiz/:filename` to inspect taxonomy fields.
> The Quizzernator frontend does this automatically and memoizes each detail response client-side so repeated visits avoid extra backend reads.

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

Automatically categorize quiz topics using OpenAI GPT-5-nano with semantic understanding. This AI-based system provides much more accurate categorization than keyword matching, especially for complex or multi-domain topics. Configure `OPENAI_API_KEY`; without it the handler falls back to a generic "General → Mixed Content" classification.

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
      "category": "Technology",
      "subcategory": "Software Tutorials",
      "confidence": 0.2
    },
    {
      "category": "AI Software Development",
      "subcategory": "Agents & MCP/Orchestration",
      "confidence": 0.2
    }
  ],
  "available_categories": [
    "Technology",
    "AI Software Development",
    "History",
    "Education",
    "Business",
    "World War II (WWII)",
    "Hobbies & Special Interests",
    "Science & Nature",
    "News & Politics",
    "Entertainment",
    "Reviews & Products",
    "General",
    "Computer Hardware",
    "Astronomy",
    "Sports",
    "News",
    "World War I (WWI)"
  ],
  "available_subcategories": {
    "Technology": [
      "Software Tutorials",
      "Tech Reviews & Comparisons",
      "Tech News & Trends",
      "Programming & Software Development",
      "Mobile Development",
      "Web Development",
      "DevOps & Infrastructure",
      "Cybersecurity",
      "Databases & Data Science"
    ],
    "AI Software Development": [
      "Agents & MCP/Orchestration",
      "APIs & SDKs",
      "Model Selection & Evaluation",
      "Deployment & Serving",
      "Cost Optimisation",
      "Security & Safety",
      "Prompt Engineering & RAG",
      "Data Engineering & ETL",
      "Training & Fine-Tuning"
    ],
    "History": [
      "Modern History",
      "Historical Analysis",
      "Cultural Heritage",
      "Ancient Civilizations"
    ],
    "Education": [
      "Tutorials & Courses",
      "Teaching Methods",
      "Academic Subjects"
    ],
    "Business": [
      "Industry Analysis",
      "Finance & Investing",
      "Career Development",
      "Marketing & Sales",
      "Leadership & Management"
    ],
    "World War II (WWII)": [
      "European Theatre",
      "Aftermath & Reconstruction",
      "Technology & Weapons",
      "Causes & Prelude",
      "Biographies & Commanders",
      "Home Front & Society",
      "Pacific Theatre",
      "Holocaust & War Crimes",
      "Intelligence & Codebreaking"
    ],
    "Hobbies & Special Interests": [
      "Automotive"
    ],
    "Science & Nature": [
      "Physics & Chemistry"
    ],
    "News & Politics": [
      "Political Analysis",
      "Government & Policy",
      "Current Events",
      "International Affairs"
    ],
    "Entertainment": [
      "Comedy & Humor",
      "Music & Performance",
      "Reaction Content",
      "Movies & TV"
    ],
    "Reviews & Products": [
      "Comparisons & Tests",
      "Product Reviews",
      "Buying Guides"
    ],
    "General": [
      "Mixed Content"
    ],
    "Computer Hardware": [
      "Networking & NAS",
      "Cooling & Thermals"
    ],
    "Astronomy": [
      "Space Missions & Exploration",
      "Solar System & Planets",
      "Space News & Discoveries"
    ],
    "Sports": [
      "Equipment & Gear"
    ],
    "News": [
      "General News"
    ],
    "World War I (WWI)": [
      "Aftermath & Interwar"
    ]
  }
}
```

`alternatives` is a static helper list intended for dropdown population.

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
    "language": "en|fr|es|...",
    "category": "Technology",
    "subcategory": "Programming & Software Development",
    "count": 5,
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

Notes:
- Persisted storage uses `options[] + correct` for multiple-choice, `correct: "yes"|"no"` for yes/no when applicable, and `correct: true|false` for true/false. Short answers should include a string in `correct`.
- Quizzernator normalizes these items on load to a runtime shape with `choices[] + solution` where needed; no backend change is required.

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
   - Request body presence and JSON parsing safeguards
   - Required field checking (prompt, quiz payload, topic, etc.)
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

`/api/list-quizzes` does not return taxonomy data, so fetch each quiz to enrich the listing before grouping.

```javascript
const listResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes');
const { quizzes } = await listResponse.json();

// Fetch full quiz details to access meta.category / meta.subcategory
const quizzesWithTaxonomy = await Promise.all(
  quizzes.map(async (quiz) => {
    const detailResponse = await fetch(`https://ytv2-dashboard-postgres.onrender.com/api/quiz/${quiz.filename}`);
    const detail = await detailResponse.json();
    const meta = detail?.quiz?.meta || {};

    return {
      ...quiz,
      category: meta.category || 'Uncategorized',
      subcategory: meta.subcategory || 'General'
    };
  })
);

const quizzesByCategory = quizzesWithTaxonomy.reduce((acc, quiz) => {
  acc[quiz.category] = acc[quiz.category] || {};
  acc[quiz.category][quiz.subcategory] = acc[quiz.category][quiz.subcategory] || [];
  acc[quiz.category][quiz.subcategory].push(quiz);
  return acc;
}, {});

Object.entries(quizzesByCategory).forEach(([category, subcategories]) => {
  console.log(`📁 ${category}`);
  Object.entries(subcategories).forEach(([subcategory, grouped]) => {
    console.log(`  └── ${subcategory} (${grouped.length} quizzes)`);
    grouped.forEach(quiz => {
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
async function findRelatedQuizzes(videoCategories, videoSubcategories) {
  const listResponse = await fetch('https://ytv2-dashboard-postgres.onrender.com/api/list-quizzes');
  const { quizzes } = await listResponse.json();

  const detailedQuizzes = await Promise.all(
    quizzes.map(async (quiz) => {
      const detailResponse = await fetch(`https://ytv2-dashboard-postgres.onrender.com/api/quiz/${quiz.filename}`);
      const detail = await detailResponse.json();
      const meta = detail?.quiz?.meta || {};

      return {
        ...quiz,
        category: meta.category,
        subcategory: meta.subcategory
      };
    })
  );

  return detailedQuizzes.filter((quiz) => {
    if (quiz.category && videoCategories.includes(quiz.category)) return true;
    if (quiz.subcategory && videoSubcategories.includes(quiz.subcategory)) return true;
    return false;
  });
}

const relatedQuizzes = await findRelatedQuizzes(
  ['Technology', 'AI Software Development'],
  ['Programming & Software Development', 'AI Tools & Platforms']
);

console.log(`Found ${relatedQuizzes.length} related quizzes:`, relatedQuizzes);
```

### Cost Optimization

**OpenRouter Generation Costs**:
- Pricing is determined by OpenRouter's current rates for `google/gemini-2.5-flash-lite` (primary) and `deepseek/deepseek-v3.1-terminus` (fallback).
- Review https://openrouter.ai/pricing for the latest per-token charges before high-volume use.
- Monitor the `/api/generate-quiz` JSON `usage` object to capture actual prompt/completion token counts per request.

**Categorization Costs**:
- `gpt-5-nano` runs through OpenAI's API and typically remains inexpensive for the short prompts used here.
- Leave categorization disabled (or provide manual overrides) if you need to avoid OpenAI charges.

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

2. **OpenRouter API Errors**
   ```
   {"error": "OpenRouter API key not configured"}
   ```
   **Solution**: Set `OPENROUTER_API_KEY` environment variable in Render

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
