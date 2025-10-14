"""Compare quiz-generation prompts across multiple LLM providers.

This script hits:
  1. OpenAI GPT-5-Nano (current production choice)
  2. OpenRouter Google Gemini 2.5 Flash Lite
  3. OpenRouter DeepSeek Terminus v3.1

Set environment variables before running:
  OPENAI_API_KEY           -> OpenAI key for GPT-5-Nano
  OPENROUTER_API_KEY       -> OpenRouter key for Gemini/DeepSeek

Example:
  OPENAI_API_KEY=sk-... OPENROUTER_API_KEY=or-... python compare_quiz_models.py
"""

from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass
from typing import Dict, Optional, List

import argparse

import requests

RAW_PROMPTS = {
    "italy_wwii": textwrap.dedent(
        """
        Create a 10-question quiz about "Italy in World War II" for an intermediate learner.
        Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values.
        Distribute them as evenly as possible across the 10 questions.
        Ensure the JSON matches exactly this schema:
        {
          "meta": {
            "topic": "Italy in World War II",
            "difficulty": "intermediate",
            "count": 10
          },
          "items": [
            {
              "question": "Question text",
              "answer": "Expected answer",
              "type": "multiplechoice|truefalse",
              "choices": ["A", "B", "C", "D"],
              "solution": "Canonical answer",
              "explanation": "Optional explanation"
            }
          ]
        }

        Rules:
        - Produce exactly 10 items.
        - Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values. Distribute them as evenly as possible across the 10 questions.
        - For multiplechoice items: include a "choices" array with exactly 4 options and a "solution" field matching one of them.
        - For truefalse items: set "solution" to either "true" or "false" (lowercase).
        - Do not include any question type outside of multiplechoice, truefalse.
        - Answers must be accurate and concise.
        - Include an "explanation" field for each question with helpful teaching context.
        - Respond with valid JSON only.
        """
    ).strip(),
    "mcu_phases_1_4": textwrap.dedent(
        """
        Create a 10-question quiz about "The Marvel Cinematic Universe (Phases 1 through 4)" for an intermediate pop culture fan.
        Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values.
        Distribute them as evenly as possible across the 10 questions.
        Ensure the JSON matches exactly this schema:
        {
          "meta": {
            "topic": "MCU Phases 1-4",
            "difficulty": "intermediate",
            "count": 10
          },
          "items": [
            {
              "question": "Question text",
              "answer": "Expected answer",
              "type": "multiplechoice|truefalse",
              "choices": ["A", "B", "C", "D"],
              "solution": "Canonical answer",
              "explanation": "Optional explanation"
            }
          ]
        }

        Rules:
        - Produce exactly 10 items.
        - Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values. Distribute them as evenly as possible across the 10 questions.
        - For multiplechoice items: include a "choices" array with exactly 4 options and a "solution" field matching one of them.
        - For truefalse items: set "solution" to either "true" or "false" (lowercase).
        - Do not include any question type outside of multiplechoice, truefalse.
        - Answers must be accurate and concise.
        - Include an "explanation" field that references movie events, characters, or plot implications.
        - Respond with valid JSON only.
        """
    ).strip(),
    "harlem_literature": textwrap.dedent(
        """
        Create a 10-question quiz about "The Harlem Renaissance in American Literature" for an advanced learner.
        Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values.
        Distribute them as evenly as possible across the 10 questions.
        Ensure the JSON matches exactly this schema:
        {
          "meta": {
            "topic": "Harlem Renaissance Literature",
            "difficulty": "advanced",
            "count": 10
          },
          "items": [
            {
              "question": "Question text",
              "answer": "Expected answer",
              "type": "multiplechoice|truefalse",
              "choices": ["A", "B", "C", "D"],
              "solution": "Canonical answer",
              "explanation": "Optional explanation"
            }
          ]
        }

        Rules:
        - Produce exactly 10 items.
        - Use only the following question types: multiplechoice, truefalse. Each item must set "type" to one of these values. Distribute them as evenly as possible across the 10 questions.
        - For multiplechoice items: include a "choices" array with exactly 4 options and a "solution" field matching one of them.
        - For truefalse items: set "solution" to either "true" or "false" (lowercase).
        - Do not include any question type outside of multiplechoice, truefalse.
        - Answers must reference authors, publications, or literary influence relevant to the Harlem Renaissance.
        - Include an "explanation" field that cites historical context or literary significance.
        - Respond with valid JSON only.
        """
    ).strip(),
}

SCENARIO_HELP = {
    "italy_wwii": "Italy in World War II (baseline)",
    "mcu_phases_1_4": "Marvel Cinematic Universe Phases 1-4",
    "harlem_literature": "Harlem Renaissance literature",
}

SYSTEM_PROMPT = (
    "You are a quiz question generator. Respond with valid JSON only, no code fences, no commentary."
)

@dataclass
class ModelConfig:
    name: str
    provider: str  # 'openai' or 'openrouter'
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 1800


MODELS = [
    ModelConfig(
        name="OpenAI GPT-5-Nano",
        provider="openai",
        model_id="gpt-5-nano",
    ),
    ModelConfig(
        name="Gemini 2.5 Flash Lite (OpenRouter)",
        provider="openrouter",
        model_id="google/gemini-2.5-flash-lite",
    ),
    ModelConfig(
        name="DeepSeek Terminus v3.1 (OpenRouter)",
        provider="openrouter",
        model_id="deepseek/deepseek-v3.1-terminus",
    ),
]


def call_openai(model: ModelConfig, prompt: str) -> Dict[str, Optional[str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}

    payload = {
        "model": model.model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": model.max_tokens,
        "response_format": {"type": "json_object"},
    }
    # GPT-5-nano treats temperature as fixed; omit to avoid 400s
    if not model.model_id.startswith("gpt-5-nano"):
        payload["temperature"] = model.temperature
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    data = response.json()
    result: Dict[str, Optional[str]] = {
        "status": str(response.status_code),
        "finish_reason": None,
        "content": None,
        "usage": None,
        "error": None,
    }

    if response.status_code != 200:
        result["error"] = json.dumps(data)
        return result

    choice = data.get("choices", [{}])[0]
    result["finish_reason"] = choice.get("finish_reason")
    result["content"] = (choice.get("message") or {}).get("content")
    result["usage"] = json.dumps(data.get("usage"), indent=2)
    return result


def call_openrouter(model: ModelConfig, prompt: str) -> Dict[str, Optional[str]]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY not set"}

    payload = {
        "model": model.model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": model.max_tokens,
        "temperature": model.temperature,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://quizzernator.onrender.com",
            "X-Title": "Quiz Model Comparator",
        },
        json=payload,
        timeout=60,
    )
    data = response.json()
    result: Dict[str, Optional[str]] = {
        "status": str(response.status_code),
        "finish_reason": None,
        "content": None,
        "usage": None,
        "error": None,
    }

    if response.status_code != 200:
        result["error"] = json.dumps(data)
        return result

    choice = data.get("choices", [{}])[0]
    result["finish_reason"] = choice.get("finish_reason")
    result["content"] = (choice.get("message") or {}).get("content")
    result["usage"] = json.dumps(data.get("usage"), indent=2)
    return result


def run_models(prompt_name: str, prompt_text: str) -> None:
    title = SCENARIO_HELP.get(prompt_name, prompt_name)
    print("=" * 80)
    print(f"Scenario: {title}")
    print("Prompt preview:\n" + "-" * 80)
    print(prompt_text[:500] + ("..." if len(prompt_text) > 500 else ""))
    print("\nRunning model comparisons...\n")

    for cfg in MODELS:
        print(f"=== {cfg.name} ===")
        if cfg.provider == "openai":
            result = call_openai(cfg, prompt_text)
        else:
            result = call_openrouter(cfg, prompt_text)

        error = result.get("error")
        if error:
            print(f"Error: {error}\n")
            continue

        print(f"HTTP status: {result['status']}")
        print(f"finish_reason: {result['finish_reason']}")
        usage = result.get("usage")
        if usage:
            print(f"usage tokens: {usage}")

        content = result.get("content") or ""
        if content:
            preview = content[:400] + ("..." if len(content) > 400 else "")
            print(f"Content preview: {preview}")
        else:
            print("Content preview: <empty>")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare quiz generation models across scenarios")
    parser.add_argument(
        "--scenario",
        choices=["all", *RAW_PROMPTS.keys()],
        default="all",
        help="Which scenario to run (default: all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scenario == "all":
        scenarios: List[str] = list(RAW_PROMPTS.keys())
    else:
        scenarios = [args.scenario]

    for name in scenarios:
        run_models(name, RAW_PROMPTS[name])
        print()


if __name__ == "__main__":
    main()
