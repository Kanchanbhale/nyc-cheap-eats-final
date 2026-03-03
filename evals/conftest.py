"""Shared fixtures for NYC Cheap Eats evals."""

import json
import sys
from pathlib import Path

from litellm import completion

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import MODEL, build_initial_messages

JUDGE_MODEL = "vertex_ai/gemini-2.0-flash"


def get_response(text: str) -> str:
    """Send a message to the NYC Cheap Eats bot and return its response."""
    messages = build_initial_messages()
    messages.append({"role": "user", "content": text})
    response = completion(model=MODEL, messages=messages)
    return response.choices[0].message.content


JUDGE_SYSTEM_GOLDEN = """\
You are an expert evaluator. Given a user prompt, a reference response, and a \
generated response, rate the overall quality of the generated response on a \
scale of 1 to 10 based on how well it compares to the reference response. \
Consider accuracy, completeness, coherence, and helpfulness. \
Start your response with a valid JSON object with a single key "rating" \
and an integer value between 1 and 10.

Example response:
{
  "rating": 7
}"""

JUDGE_SYSTEM_RUBRIC = """\
You are an expert evaluator. Given a user prompt, a generated response, and a \
list of quality rubrics, rate the overall quality of the response on a \
scale of 1 to 10 based on how well it satisfies the rubrics. \
Start your response with a valid JSON object with a single key "rating" \
and an integer value between 1 and 10.

Example response:
{
  "rating": 7
}"""


def _parse_rating(text: str) -> int:
    start = text.index("{")
    end = text.index("}", start) + 1
    return int(json.loads(text[start:end])["rating"])


def judge_with_golden(prompt: str, reference: str, response: str) -> int:
    user_msg = (
        f"<prompt>\n{prompt}\n</prompt>"
        f"\n\n<reference_response>\n{reference}\n</reference_response>"
        f"\n\n<generated_response>\n{response}\n</generated_response>"
    )
    result = completion(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_GOLDEN},
            {"role": "user", "content": user_msg},
        ],
    )
    return _parse_rating(result.choices[0].message.content)


def judge_with_rubric(prompt: str, response: str, rubric: str) -> int:
    user_msg = (
        f"<prompt>\n{prompt}\n</prompt>"
        f"\n\n<response>\n{response}\n</response>"
        f"\n\n<rubrics>\n{rubric}\n</rubrics>"
    )
    result = completion(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_RUBRIC},
            {"role": "user", "content": user_msg},
        ],
    )
    return _parse_rating(result.choices[0].message.content)
