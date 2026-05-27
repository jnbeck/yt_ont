"""
Classify all comments in a JSON file using Claude Haiku and save results to SQLite.

Usage:
    python classify.py --input data/comments_aIeBFtP7XZA.json

On re-run, already-classified comments are skipped automatically.
"""

import argparse
import json
import os
import time
from pathlib import Path

import re

import anthropic
from dotenv import load_dotenv

import sqlite_store

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/comments.db")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are an expert at analyzing YouTube comments on a podcast about
Book of Mormon geography. The host proposes that Book of Mormon events took place in
the Baja California region of North America (not Mesoamerica or the Heartland/Great Lakes).

LDS terminology glossary:
- Nephites / Lamanites: peoples described in the Book of Mormon
- Hill Cumorah: final battle site; LDS tradition places it in upstate New York
- Lehi: prophet who led a family from Jerusalem to the Americas (~600 BC)
- Liahona: compass-like instrument used by Lehi's family
- Narrow neck of land: key geographic feature in the Book of Mormon
- Iron rod / tree of life: symbols from Lehi's vision
- Testimony: personal spiritual witness of LDS doctrine
- Joseph Smith: founder of the LDS church
- Hagoth: Book of Mormon shipbuilder
- Jaredites: earlier people group who came to the Americas before Lehi
- Zarahemla: major Nephite city in the Book of Mormon

Classify the comment using ONLY these values:

stance (pick one):
  believer          - expresses faith in the host's theory or LDS doctrine
  skeptic_academic  - questions evidence without hostility; intellectual engagement
  hostile           - adversarial, dismissive, or anti-Mormon
  casual            - "great video!", emoji-only, no substantive content
  unclear           - cannot be confidently classified

theological_tone (pick one):
  devotional   - testimony, gratitude, expressions of faith
  apologetic   - defending LDS doctrine or the geography theory
  questioning  - genuine inquiry, open-minded skepticism
  critical     - challenges the theory or doctrine
  neutral      - academic, informational, no strong tone

is_substantive (true/false):
  true if the comment contains a question, claim, geographic reference,
  scripture citation, or meaningful argument. false for pleasantries only.

topics (list of 1-2 from this exact list, or ["none"] if no topic applies):
  Jaredites, Chronology, Language, People, Magic Art, Narrow Neck of Land,
  Narrow Strip of Wilderness, Land of Nephi, Cumorah, Plants and Minerals,
  Ecology, Records, Land of Many Waters, Destructions, New Jerusalem,
  Battles (Movements), Moroni's Description (Alma 22), Mount Antipas,
  Temples, Structures, Belongings, Reckoning, none

  Note on "Records": use this only when the comment discusses the scriptural
  records kept by Book of Mormon prophets — e.g. the Plates of Nephi, Brass Plates,
  Gold Plates, or the abridgment process. Do NOT use it for generic mentions of
  historical records or documentation.

Return JSON only, no explanation:
{"stance": "...", "theological_tone": "...", "is_substantive": true/false, "topics": ["..."], "confidence": 0.0-1.0, "one_line_reason": "..."}"""


URL_ONLY = re.compile(r"^\s*(https?://\S+)\s*$")

def is_url_only(text: str) -> bool:
    return bool(URL_ONLY.match(text))


def classify(comment_text: str, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=384,
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
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s
            print(f"\n  [retry {attempt + 1}/{retries - 1}] {e} — waiting {wait}s...")
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="Classify YouTube comments with Claude Haiku.")
    parser.add_argument("--input", required=True, help="Path to comments JSON file")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    video_title = data.get("title", "")
    comments = data["comments"]

    print(f"Video: {video_title}")
    print(f"Total comments in file: {len(comments)}")

    sqlite_store.init_db(DB_PATH)
    new_raw = sqlite_store.insert_raw_comments(DB_PATH, comments, video_title)
    print(f"Loaded into SQLite: {new_raw} new, {len(comments) - new_raw} already existed")

    todo = sqlite_store.get_unprocessed_comments(DB_PATH)
    print(f"Comments to classify: {len(todo)}\n")

    if not todo:
        print("Nothing to do — all comments already classified.")
        return

    errors = 0
    for i, comment in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] classifying...", end="\r")
        try:
            if is_url_only(comment["text"]):
                result = {
                    "stance": "casual", "theological_tone": "neutral",
                    "is_substantive": False, "topics": ["none"],
                    "confidence": 1.0, "one_line_reason": "URL-only comment",
                }
            else:
                result = classify(comment["text"])
            sqlite_store.insert_enriched_comment(DB_PATH, comment["comment_id"], result, MODEL)
        except Exception as e:
            errors += 1
            print(f"\n  [!] Error on comment {comment['comment_id']}: {e}")
        # Small delay to stay well under API rate limits
        time.sleep(0.1)

    print(" " * 50)
    print(f"\nDone. Classified {len(todo) - errors}/{len(todo)} comments.")
    if errors:
        print(f"  {errors} errors — re-run to retry failed comments.")
    print(f"Results saved to: {DB_PATH}")


if __name__ == "__main__":
    main()