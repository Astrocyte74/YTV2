"""
Jeop3 Prompt Builder for YTV2-Dashboard
Port of Jeop3's prompt building logic from JavaScript to Python
"""

import os
from typing import Dict, Any, Optional

# Allowed prompt types from Jeop3
ALLOWED_PROMPT_TYPES = {
    'game-title',
    'categories-generate',
    'categories-generate-from-content',
    'category-rename',
    'category-title-generate',
    'category-generate-clues',
    'category-replace-all',
    'questions-generate-five',
    'question-generate-single',
    'editor-generate-clue',
    'editor-rewrite-clue',
    'editor-generate-answer',
    'editor-validate',
    'team-name-random',
    'team-name-enhance',
}

# Value guidance for difficulty calibration
VALUE_GUIDANCE = {
    200: "Obvious / very well-known facts",
    400: "Common knowledge within topic",
    600: "Requires familiarity with the topic",
    800: "Niche or specific details",
    1000: "Deep cuts / less obvious information"
}

# System instruction for all prompts
SYSTEM_INSTRUCTION = "You are a Jeopardy game content generator. Always respond with valid JSON only, no prose. No markdown, no explanations, just raw JSON."


def build_jeop3_prompt(prompt_type: str, context: Dict[str, Any], difficulty: str) -> Dict[str, str]:
    """
    Build a Jeop3 prompt from template.

    Args:
        prompt_type: Type of prompt (game-title, categories-generate, etc.)
        context: Context object with theme, difficulty, etc.
        difficulty: Difficulty level (easy, normal, hard)

    Returns:
        Dict with 'system' and 'user' prompt strings
    """
    if prompt_type not in ALLOWED_PROMPT_TYPES:
        raise ValueError(f"Invalid prompt type: {prompt_type}. Allowed: {ALLOWED_PROMPT_TYPES}")

    # Difficulty text
    difficulty_text = {
        'easy': 'Make questions accessible and straightforward.',
        'hard': 'Make questions challenging and specific.',
        'normal': 'Balanced difficulty level.'
    }.get(difficulty, 'Balanced difficulty level.')

    # Build prompts based on type
    if prompt_type == 'game-title':
        return _build_game_title_prompt(context, difficulty_text)

    elif prompt_type == 'categories-generate':
        return _build_categories_generate_prompt(context, difficulty_text)

    elif prompt_type == 'categories-generate-from-content':
        return _build_categories_generate_from_content_prompt(context, difficulty_text)

    elif prompt_type == 'category-rename':
        return _build_category_rename_prompt(context)

    elif prompt_type == 'category-title-generate':
        return _build_category_title_generate_prompt(context, difficulty_text)

    elif prompt_type == 'category-generate-clues':
        return _build_category_generate_clues_prompt(context, difficulty_text)

    elif prompt_type == 'category-replace-all':
        return _build_category_replace_all_prompt(context, difficulty_text)

    elif prompt_type == 'questions-generate-five':
        return _build_questions_generate_five_prompt(context, difficulty_text)

    elif prompt_type == 'question-generate-single':
        return _build_question_generate_single_prompt(context, difficulty_text)

    elif prompt_type == 'editor-generate-clue':
        return _build_editor_generate_clue_prompt(context, difficulty_text)

    elif prompt_type == 'editor-rewrite-clue':
        return _build_editor_rewrite_clue_prompt(context)

    elif prompt_type == 'editor-generate-answer':
        return _build_editor_generate_answer_prompt(context)

    elif prompt_type == 'editor-validate':
        return _build_editor_validate_prompt(context)

    elif prompt_type == 'team-name-random':
        return _build_team_name_random_prompt(context)

    elif prompt_type == 'team-name-enhance':
        return _build_team_name_enhance_prompt(context)

    else:
        # Fallback
        return {
            'system': SYSTEM_INSTRUCTION,
            'user': 'Generate Jeopardy content.'
        }


def _build_game_title_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build game title generation prompt."""
    existing_titles = context.get('existingTitles', [])
    existing_titles_text = ""
    if existing_titles and len(existing_titles) > 0:
        existing_titles_text = f"""IMPORTANT: Do NOT repeat these existing titles:
{chr(10).join(f'- "{t["title"]}"' for t in existing_titles)}

Generate something completely different and fresh.
"""

    if context.get('hasContent'):
        sample_content = context.get('sampleContent', '')
        user_prompt = f"""Generate 3 engaging Jeopardy game title options based on this sample content:

{sample_content}

Analyze the content above to identify the main topics, themes, and tone. Then create catchy, engaging titles that capture the essence of this material.

{difficulty_text}

{existing_titles_text}

Return JSON format:
{{
  "titles": [
    { "title": "...", "subtitle": "..." },
    { "title": "...", "subtitle": "..." },
    { "title": "...", "subtitle": "..." }
  ]
}}"""
    else:
        theme = context.get('theme', 'general trivia')
        random_hint = "Choose any interesting trivia theme at random." if theme == 'random' else ""
        user_prompt = f"""Generate 3 engaging Jeopardy game title options for theme: "{theme}"

{random_hint}

{difficulty_text}

{existing_titles_text}

Return JSON format:
{{
  "titles": [
    { "title": "...", "subtitle": "..." },
    { "title": "...", "subtitle": "..." },
    { "title": "...", "subtitle": "..." }
  ]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_categories_generate_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build categories generation prompt."""
    count = context.get('count', 6)
    theme = context.get('theme', 'general')

    value_guidance = ""
    if difficulty_text == 'Balanced difficulty level.':
        value_guidance = f"""
Value guidelines:
- 200: {VALUE_GUIDANCE[200]}
- 400: {VALUE_GUIDANCE[400]}
- 600: {VALUE_GUIDANCE[600]}
- 800: {VALUE_GUIDANCE[800]}
- 1000: {VALUE_GUIDANCE[1000]}
"""

    user_prompt = f"""Generate {count} Jeopardy categories for theme: "{theme}"

Difficulty: {difficulty_text}
{value_guidance}

IMPORTANT: Each category needs TWO names:
1. "title" - A creative, catchy display name for players (e.g., "Geography Genius", "Word Wizards")
2. "contentTopic" - The descriptive topic name for AI context (e.g., "World Capitals", "Literary Terms")

The title should be fun and creative while the contentTopic should be clear and descriptive.

Return JSON format:
{{
  "categories": [
    {{
      "title": "Creative Display Name",
      "contentTopic": "Descriptive Topic Name",
      "clues": [
        {{ "value": 200, "clue": "...", "response": "..." }},
        {{ "value": 400, "clue": "...", "response": "..." }},
        {{ "value": 600, "clue": "...", "response": "..." }},
        {{ "value": 800, "clue": "...", "response": "..." }},
        {{ "value": 1000, "clue": "...", "response": "..." }}
      ]
    }}
  ]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_categories_generate_from_content_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build categories generation prompt based on source material."""
    count = context.get('count', 6)
    reference_material = context.get('referenceMaterial', '')
    theme = context.get('theme', 'general')

    value_guidance = ""
    if difficulty_text == 'Balanced difficulty level.':
        value_guidance = f"""
Value guidelines:
- 200: {VALUE_GUIDANCE[200]}
- 400: {VALUE_GUIDANCE[400]}
- 600: {VALUE_GUIDANCE[600]}
- 800: {VALUE_GUIDANCE[800]}
- 1000: {VALUE_GUIDANCE[1000]}
"""

    # Limit reference material to prevent prompt overflow
    max_reference_chars = 50000
    if len(reference_material) > max_reference_chars:
        reference_snippet = reference_material[:max_reference_chars] + "\n\n[Content truncated for length...]"
    else:
        reference_snippet = reference_material

    user_prompt = f"""Generate {count} Jeopardy categories based on the following source material.

Source material:
\"\"\"{reference_snippet}\"\"\"

Theme: {theme}
Difficulty: {difficulty_text}
{value_guidance}

IMPORTANT INSTRUCTIONS:
1. Create categories that cover the key topics, people, events, places, and concepts from the source material above
2. All clues must be answerable using ONLY the information provided in the source material
3. Do NOT fabricate facts or include outside knowledge
4. Each category needs TWO names:
   - "title" - A creative, catchy display name for players (e.g., "Historical Events", "Famous Figures")
   - "contentTopic" - The descriptive topic name for AI context (e.g., "World War II Battles", "Scientists")

The title should be fun and creative while the contentTopic should be clear and descriptive.

Return JSON format:
{{
  "categories": [
    {{
      "title": "Creative Display Name",
      "contentTopic": "Descriptive Topic Name",
      "clues": [
        {{ "value": 200, "clue": "...", "response": "..." }},
        {{ "value": 400, "clue": "...", "response": "..." }},
        {{ "value": 600, "clue": "...", "response": "..." }},
        {{ "value": 800, "clue": "...", "response": "..." }},
        {{ "value": 1000, "clue": "...", "response": "..." }}
      ]
    }}
  ]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_category_rename_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build category rename prompt."""
    current_title = context.get('currentTitle', '')
    theme = context.get('theme', 'general')

    user_prompt = f"""Suggest 3 alternative names for this Jeopardy category: "{current_title}"

Theme: {theme}

Return JSON format:
{{
  "names": ["Option 1", "Option 2", "Option 3"]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_category_title_generate_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build category title generation prompt."""
    content_topic = context.get('contentTopic', '')
    theme = context.get('theme', '')

    theme_line = f"""- Optionally connect to the overall game theme: "{theme}\"\n""" if theme else ""

    user_prompt = f"""Generate a BRAND NEW, completely original Jeopardy category title for this content topic: "{content_topic}"

IMPORTANT: Create something FRESH and DIFFERENT - not just a variation or rewording of existing titles.

The category title should:
- Be completely original and unique
- Use clever wordplay, puns, or pop culture references related to "{content_topic}"
- Fit the classic Jeopardy style (playful, sometimes cryptic, often using before/after, puns, or rhymes)
- Capture the essence of "{content_topic}" in a creative way
{theme_line}- Be short (typically 1-6 words)

Examples of good Jeopardy category styles:
- "Before & After" (combining two phrases)
- Puns or wordplay on the topic
- Rhymes or alliteration
- Pop culture references
- Play on words or idioms

Difficulty: {difficulty_text}

Return JSON format:
{{
  "title": "Brand New Clever Title"
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_category_generate_clues_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build category clues generation prompt."""
    category_title = context.get('categoryTitle', '')
    theme = context.get('theme', context.get('categoryTitle', ''))
    existing_clues = context.get('existingClues', [])

    value_guidance = ""
    if difficulty_text == 'Balanced difficulty level.':
        value_guidance = f"""
Value guidelines:
- 200: {VALUE_GUIDANCE[200]}
- 400: {VALUE_GUIDANCE[400]}
- 600: {VALUE_GUIDANCE[600]}
- 800: {VALUE_GUIDANCE[800]}
- 1000: {VALUE_GUIDANCE[1000]}
"""

    existing_clues_json = str(existing_clues).replace("'", '"')

    user_prompt = f"""Generate missing clues for category: "{category_title}"

Theme: {theme}
Existing clues: {existing_clues_json}

Fill missing values to complete [200, 400, 600, 800, 1000] set.
{value_guidance}

Return JSON format:
{{
  "clues": [
    {{ "value": 200, "clue": "...", "response": "..." }}
  ]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_category_replace_all_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build category replace all prompt."""
    category_title = context.get('categoryTitle', '')
    theme = context.get('theme', context.get('categoryTitle', ''))
    count = context.get('count', 5)

    value_guidance = ""
    if difficulty_text == 'Balanced difficulty level.':
        value_guidance = f"""
Value guidelines:
- 200: {VALUE_GUIDANCE[200]}
- 400: {VALUE_GUIDANCE[400]}
- 600: {VALUE_GUIDANCE[600]}
- 800: {VALUE_GUIDANCE[800]}
- 1000: {VALUE_GUIDANCE[1000]}
"""

    user_prompt = f"""Replace all clues in category: "{category_title}"

Theme: {theme}
Count: {count}
{value_guidance}

Return JSON format:
{{
  "category": {{
    "title": "{category_title}",
    "clues": [
      {{ "value": 200, "clue": "...", "response": "..." }}
    ]
  }}
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_questions_generate_five_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build five questions generation prompt."""
    category_title = context.get('categoryTitle', '')
    theme = context.get('theme', context.get('categoryTitle', ''))

    value_guidance = ""
    if difficulty_text == 'Balanced difficulty level.':
        value_guidance = f"""
Value guidelines:
- 200: {VALUE_GUIDANCE[200]}
- 400: {VALUE_GUIDANCE[400]}
- 600: {VALUE_GUIDANCE[600]}
- 800: {VALUE_GUIDANCE[800]}
- 1000: {VALUE_GUIDANCE[1000]}
"""

    user_prompt = f"""Generate 5 clues for category: "{category_title}"

Theme: {theme}
{value_guidance}

Return JSON format:
{{
  "clues": [
    {{ "value": 200, "clue": "...", "response": "..." }},
    {{ "value": 400, "clue": "...", "response": "..." }},
    {{ "value": 600, "clue": "...", "response": "..." }},
    {{ "value": 800, "clue": "...", "response": "..." }},
    {{ "value": 1000, "clue": "...", "response": "..." }}
  ]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_question_generate_single_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build single question generation prompt."""
    value = context.get('value', 200)
    category_title = context.get('categoryTitle', '')
    theme = context.get('theme', context.get('categoryTitle', ''))

    value_guidance_text = VALUE_GUIDANCE.get(value, '') if difficulty_text == 'Balanced difficulty level.' else ''

    user_prompt = f"""Generate 1 clue for value $${value}.

Category: "{category_title}"
Theme: {theme}
{f'Value guidance: {value_guidance_text}' if value_guidance_text else ''}

Return JSON format:
{{
  "clue": {{
    "value": {value},
    "clue": "...",
    "response": "..."
  }}
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_editor_generate_clue_prompt(context: Dict[str, Any], difficulty_text: str) -> Dict[str, str]:
    """Build editor clue generation prompt."""
    category_title = context.get('categoryTitle', '')
    value = context.get('value', 200)
    theme = context.get('theme', 'general')

    value_guidance_text = VALUE_GUIDANCE.get(value, '') if difficulty_text == 'Balanced difficulty level.' else ''

    user_prompt = f"""Generate a question and answer for this slot.

Category: "{category_title}"
Value: $${value}
Theme: {theme}
{f'Value guidance: {value_guidance_text}' if value_guidance_text else ''}

Return JSON format:
{{
  "clue": "...",
  "response": "..."
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_editor_rewrite_clue_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build editor rewrite clue prompt."""
    current_clue = context.get('currentClue', '')
    category_title = context.get('categoryTitle', '')
    value = context.get('value', 200)

    user_prompt = f"""Rewrite this question to be more engaging.

Original: "{current_clue}"
Category: "{category_title}"
Value: $${value}

Return JSON format:
{{
  "clue": "..."
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_editor_generate_answer_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build editor generate answer prompt."""
    clue = context.get('clue', '')
    category_title = context.get('categoryTitle', '')
    value = context.get('value', 200)

    user_prompt = f"""Generate the correct answer for this question.

Question: "{clue}"
Category: "{category_title}"
Value: $${value}

Return JSON format:
{{
  "response": "..."
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_editor_validate_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build editor validate prompt."""
    clue = context.get('clue', '')
    response = context.get('response', '')
    category_title = context.get('categoryTitle', '')
    value = context.get('value', 200)

    user_prompt = f"""Validate this Jeopardy clue pair.

Question: "{clue}"
Answer: "{response}"
Category: "{category_title}"
Value: $${value}

Check for:
1. Answer matches question
2. Difficulty appropriate for value
3. Clear and unambiguous

Return JSON format:
{{
  "valid": true/false,
  "issues": ["..."],
  "suggestions": ["..."]
}}"""

    return {
        'system': SYSTEM_INSTRUCTION,
        'user': user_prompt
    }


def _build_team_name_random_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build random team name generation prompt."""
    count = context.get('count', 1)
    game_topic = context.get('gameTopic', '')
    existing_names = context.get('existingNames', [])
    reference_material = context.get('referenceMaterial', '')

    existing_text = ""
    if existing_names and len(existing_names) > 0:
        names_list = ', '.join([f'"{n}"' for n in existing_names])
        existing_text = f"\n\nIMPORTANT: Do NOT use these existing team names: {names_list}"

    # Build context information for themed names
    context_lines = []
    if game_topic:
        context_lines.append(f"Game theme/topic: \"{game_topic}\"")

    if reference_material:
        # Include a snippet of the reference material for inspiration
        snippet = reference_material[:300] + "..." if len(reference_material) > 300 else reference_material
        context_lines.append(f"Game is based on this content:\n\"\"\"\n{snippet}\n\"\"\"")

    topic_section = ""
    if context_lines:
        topic_section = "\n\n" + "\n".join(context_lines)
        topic_section += "\n\nConsider making the team names thematically related to the game content above."

    count_text = f"{count}" if count > 1 else "1"

    user_prompt = f"""Generate {count_text} creative and fun team name(s) for a trivia game.

Make them memorable, clever, and fun. Use wordplay, puns, or creative concepts related to knowledge, trivia, or competition.{topic_section}{existing_text}

Return JSON format:
{{
  "names": ["Team Name 1"{', "Team Name 2", "Team Name 3"' if count > 1 else ''}]
}}"""

    return {
        'system': "You are a creative team name generator. Always respond with valid JSON only, no prose.",
        'user': user_prompt
    }


def _build_team_name_enhance_prompt(context: Dict[str, Any]) -> Dict[str, str]:
    """Build team name enhancement prompt."""
    current_name = context.get('currentName', '')
    game_topic = context.get('gameTopic', '')
    existing_names = context.get('existingNames', [])
    reference_material = context.get('referenceMaterial', '')

    # Build context information for themed enhancement
    context_lines = []
    if game_topic:
        context_lines.append(f"Game theme/topic: \"{game_topic}\"")

    if reference_material:
        # Include a snippet of the reference material for inspiration
        snippet = reference_material[:300] + "..." if len(reference_material) > 300 else reference_material
        context_lines.append(f"Game is based on this content:\n\"\"\"\n{snippet}\n\"\"\"")

    topic_section = ""
    if context_lines:
        topic_section = "\n\n" + "\n".join(context_lines)
        topic_section += "\n\nConsider enhancing the name to be thematically related to the game content above."

    existing_text = ""
    if existing_names and len(existing_names) > 0:
        names_list = ', '.join([f'"{n}"' for n in existing_names])
        existing_text = f"\n\nIMPORTANT: The enhanced name should not conflict with these existing team names: {names_list}"

    user_prompt = f"""Make this team name more creative and fun for a trivia game: "{current_name}"

Transform it into something more memorable, clever, or humorous. Keep the spirit of the original but make it better.{topic_section}{existing_text}

Return JSON format:
{{
  "name": "Enhanced Team Name"
}}"""

    return {
        'system': "You are a creative team name enhancer. Always respond with valid JSON only, no prose.",
        'user': user_prompt
    }
