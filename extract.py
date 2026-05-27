"""
Deep extraction pipeline — runs Claude Sonnet on substantive comments to pull out
specific questions and claims. Saves results to SQLite questions and claims tables.

Usage:
    python extract.py

Skips comments already in extraction_log — safe to re-run.
"""

import json
import os
import time

import anthropic
from dotenv import load_dotenv

import sqlite_store

load_dotenv()

MODEL = "claude-sonnet-4-6"
DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/comments.db")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are an expert at analyzing YouTube comments on a podcast about
Book of Mormon geography. The host proposes that Book of Mormon events took place in
Baja California (not Mesoamerica or the Heartland/Great Lakes region).

Your job is to extract two things from the comment:

1. QUESTIONS — anything the viewer is asking, either explicitly or implicitly.
   - Explicit: ends with "?" or uses "what", "how", "why", "where", "when"
   - Implied: "I wonder about...", "It's unclear to me...", "I'd like to know..."
   - Write each question as a clear, complete sentence
   - Only include genuine questions, not rhetorical ones used as arguments

2. CLAIMS — factual assertions the viewer is making about the theory or the Book of Mormon.
   - supporting: supports the host's Baja California theory or LDS doctrine
   - challenging: challenges or contradicts the theory or LDS doctrine
   - neutral: factual statement without a clear position
   - Write each claim as a clear, complete sentence
   - Skip pure opinions ("I liked this video") — only extract factual assertions

If the comment contains no questions, return an empty questions array.
If the comment contains no claims, return an empty claims array.

Return JSON only, no explanation:
{
  "questions": [
    {"text": "...", "is_implied": false}
  ],
  "claims": [
    {"text": "...", "claim_type": "supporting|challenging|neutral"}
  ]
}"""


def extract(comment_text: str, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Comment: {comment_text}"}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except (anthropic.APIStatusError, json.JSONDecodeError) as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"\n  [retry {attempt + 1}/{retries - 1}] {e} — waiting {wait}s...")
            time.sleep(wait)


def main():
    sqlite_store.init_db(DB_PATH)

    todo = sqlite_store.get_unextracted_comments(DB_PATH)
    print(f"Substantive comments to extract: {len(todo)}\n")

    if not todo:
        print("Nothing to do — all substantive comments already extracted.")
        return

    total_questions = 0
    total_claims = 0
    errors = 0

    for i, comment in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] extracting...", end="\r")
        try:
            result = extract(comment["text"])
            questions = result.get("questions", [])
            claims = result.get("claims", [])
            sqlite_store.insert_extraction(
                DB_PATH, comment["comment_id"], comment["video_id"],
                questions, claims, MODEL
            )
            total_questions += len(questions)
            total_claims += len(claims)
        except Exception as e:
            errors += 1
            print(f"\n  [!] Error on {comment['comment_id']}: {e}")
        time.sleep(0.15)

    print(" " * 50)
    print(f"\nDone.")
    print(f"  Comments processed: {len(todo) - errors}/{len(todo)}")
    print(f"  Questions extracted: {total_questions}")
    print(f"  Claims extracted:    {total_claims}")
    if errors:
        print(f"  Errors: {errors} — re-run to retry")
    print(f"\nResults saved to: {DB_PATH}")


if __name__ == "__main__":
    main()