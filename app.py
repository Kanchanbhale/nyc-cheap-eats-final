import os
import re
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from litellm import completion
from pydantic import BaseModel

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

MODEL = "vertex_ai/gemini-2.0-flash-lite"

SYSTEM_PROMPT = """\
<role>
You are Slice, a fast-talking, opinionated NYC cheap eats guide who knows the best low-cost food across all five boroughs.
You sound confident, practical, and specific.
</role>

<task>
Help users find cheap food in New York City.
When you answer, recommend exactly one specific place unless the user explicitly asks for a crawl.
For each recommendation, name the place, say what to order, and keep the meal under $15.
</task>

<positive_scope>
You can help with:
- cheap restaurant, cart, bodega, and stall recommendations in NYC
- what dish to order at a recommended spot
- neighborhood-specific cheap eats
- quick budget comparisons between cheap NYC food options
- short food crawls in NYC neighborhoods
- light NYC food culture context (halal carts, dollar slices, dumplings, chopped cheese, etc.)
</positive_scope>

<output_constraints>
- Name one concrete place.
- Mention what to order.
- Mention an approximate price under $15.
- Keep answers to 2-4 sentences unless the user asks for a crawl.
- If you are unsure whether a place is still open or prices changed, say:
  "Heads up — I'm not 100% sure this is still current. Always worth a quick Google before you go."
</output_constraints>

<out_of_scope>
When a request falls outside your scope, do not answer the full request.
Instead, briefly explain your scope and redirect.
Use these scope boundaries:
- Recipes and cooking steps
- Locations outside NYC's five boroughs
- Expensive dining above $15 per person
- Non-food topics
</out_of_scope>
"""

FEW_SHOT_EXAMPLES = [
    {
        "user": "Where should I eat in Flushing for under $15?",
        "assistant": (
            "Xi'an Famous Foods in Flushing. Get the spicy cumin lamb hand-ripped noodles for about $12 — "
            "big flavor, fast service, and still under budget."
        ),
    },
    {
        "user": "Give me a cheap food crawl in Astoria.",
        "assistant": (
            "Start at King of Falafel for a falafel sandwich around $8. "
            "Then grab a cheese börek from a local bakery for a few bucks. "
            "Finish with a small dessert from Al Sham Sweets — easy to stay under $15 total if you keep it light."
        ),
    },
    {
        "user": "What's cheap to eat in Chicago?",
        "assistant": (
            "I only cover cheap eats in NYC's five boroughs. "
            "If you want Queens, Brooklyn, Manhattan, the Bronx, or Staten Island, I can point you somewhere great."
        ),
    },
    {
        "user": "How do I make dollar pizza at home?",
        "assistant": (
            "I'm a diner, not a chef — I focus on where to eat cheap food in NYC. "
            "If you want a real cheap slice, try 2 Bros or Joe's depending on the neighborhood."
        ),
    },
    {
        "user": "Is Vanessa's Dumpling House still that cheap?",
        "assistant": (
            "Vanessa's in the Lower East Side is still one of the classic cheap dumpling moves. "
            "Get the fried pork chive dumplings for just a few dollars. "
            "Heads up — I'm not 100% sure this is still current. Always worth a quick Google before you go."
        ),
    },
    {
        "user": "Best halal cart in Midtown?",
        "assistant": (
            "Go to the Halal Guys at 53rd and 6th. Get the chicken and rice with white sauce — usually around $8 to $10, "
            "and it still hits every time."
        ),
    },
]

DISTRESS_KEYWORDS = [
    "kill myself",
    "end my life",
    "want to die",
    "suicidal",
    "self-harm",
    "hurt myself",
    "no reason to live",
]

NON_NYC_HINTS = [
    "chicago",
    "los angeles",
    "la ",
    "boston",
    "seattle",
    "miami",
    "austin",
    "san francisco",
    "philadelphia",
]

RECIPE_HINTS = [
    "recipe",
    "cook",
    "make at home",
    "ingredients",
    "how do i make",
    "how to make",
]

EXPENSIVE_HINTS = [
    "$100",
    "michelin",
    "fine dining",
    "tasting menu",
    "omakase",
    "luxury dinner",
]

NON_FOOD_HINTS = [
    "bitcoin",
    "crypto",
    "401k",
    "stocks",
    "resume",
    "relationship advice",
]

HARMFUL_PATTERNS = [
    r"\bexplosive(s)?\b",
    r"\bbomb\b",
    r"\bdetonator\b",
    r"\bbuy drugs\b",
    r"\bcocaine\b",
    r"\billegal\b",
]


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


app = FastAPI(title="SLICE — NYC Cheap Eats")
sessions: dict[str, list[dict]] = {}


def build_initial_messages() -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    return messages


def classify_user_request(text: str) -> str | None:
    lower = text.lower()

    if any(kw in lower for kw in DISTRESS_KEYWORDS):
        return (
            "Hey, it sounds like things might be really heavy right now. "
            "If you're in immediate danger or thinking about hurting yourself, call or text 988 right now "
            "to reach the Suicide & Crisis Lifeline. I'm just a food bot, but you deserve real support."
        )

    if any(hint in lower for hint in RECIPE_HINTS):
        return (
            "I'm a diner, not a chef — I focus on where to eat cheap food in NYC, not recipes. "
            "Tell me a neighborhood and I'll give you one great under-$15 place to try."
        )

    if any(hint in lower for hint in NON_NYC_HINTS):
        return (
            "I only cover cheap eats in NYC's five boroughs. "
            "Ask me about Manhattan, Brooklyn, Queens, the Bronx, or Staten Island and I'll point you somewhere good."
        )

    if any(hint in lower for hint in EXPENSIVE_HINTS):
        return (
            "That's above my budget lane — I focus on meals under $15. "
            "Give me a neighborhood and I'll swap in a cheaper NYC option instead."
        )

    if any(hint in lower for hint in NON_FOOD_HINTS):
        return "I just know food — ask me where to eat cheap in NYC."

    if any(re.search(pattern, lower) for pattern in HARMFUL_PATTERNS):
        return (
            "I can't help with that. I only cover cheap food recommendations in NYC. "
            "If you want, give me a neighborhood and budget and I'll help with a meal instead."
        )

    return None


def python_backstop(text: str) -> tuple[bool, str]:
    lower = text.lower()
    if any(kw in lower for kw in DISTRESS_KEYWORDS):
        return True, "distress"
    if re.search(r"\b(tablespoon|teaspoon|preheat|boil|bake at|simmer)\b", lower):
        return True, "recipe"
    if re.search(r"\b(bitcoin|crypto|401k|stock tip)\b", lower):
        return True, "non_food"
    if any(re.search(pattern, lower) for pattern in HARMFUL_PATTERNS):
        return True, "harmful"
    return False, ""


def generate_response(messages: list[dict]) -> str:
    try:
        result = completion(model=MODEL, messages=messages)
        reply = result.choices[0].message.content or ""
        flagged, reason = python_backstop(reply)
        if not flagged:
            return reply

        if reason == "distress":
            return (
                "Hey, it sounds like things might be really heavy right now. "
                "If you're in immediate danger or thinking about hurting yourself, call or text 988 right now "
                "to reach the Suicide & Crisis Lifeline. I'm just a food bot, but you deserve real support."
            )

        return (
            "I drifted out of my lane there. I only help with cheap places to eat in NYC for under $15. "
            "Ask me for a neighborhood and I'll give you one strong recommendation."
        )
    except Exception as exc:
        return (
            "Something went wrong on my end. "
            f"Please try again in a moment. ({exc})"
        )


def respond_once(user_text: str) -> str:
    direct = classify_user_request(user_text)
    if direct:
        return direct

    messages = build_initial_messages()
    messages.append({"role": "user", "content": user_text})
    return generate_response(messages)


@app.get("/")
def read_index():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = build_initial_messages()

    user_text = request.message.strip()
    sessions[session_id].append({"role": "user", "content": user_text})

    direct = classify_user_request(user_text)
    if direct:
        response_text = direct
    else:
        response_text = generate_response(sessions[session_id])

    sessions[session_id].append({"role": "assistant", "content": response_text})
    return ChatResponse(response=response_text, session_id=session_id)


@app.post("/clear")
def clear(session_id: str | None = None) -> dict[str, str]:
    if session_id and session_id in sessions:
        del sessions[session_id]
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
