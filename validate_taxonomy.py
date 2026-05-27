"""
Validate stance/tone taxonomy against a sample of comments.
Picks 20 comments spread across the dataset and classifies each with Claude Haiku.
Prints a readable table so you can spot misclassifications and tune the taxonomy.

Usage:
    python validate_taxonomy.py --input data/comments_aIeBFtP7XZA.json
"""

import argparse
import json
import os
import random
import textwrap
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TOPICS = [
    "Jaredites",
    "Chronology",
    "Language",
    "People",
    "Magic Art",
    "Narrow Neck of Land",
    "Narrow Strip of Wilderness",
    "Land of Nephi",
    "Cumorah",
    "Plants and Minerals",
    "Ecology",
    "Records",
    "Land of Many Waters",
    "Destructions",
    "New Jerusalem",
    "Battles (Movements)",
    "Moroni's Description (Alma 22)",
    "Mount Antipas",
    "Temples",
    "Structures",
    "Belongings",
    "Reckoning",
    "none",
]

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
{"stance": "...", "theological_tone": "...", "is_substantive": true/false, "topics": ["...", "..."], "confidence": 0.0-1.0, "one_line_reason": "..."}"""


def classify(comment_text: str) -> dict:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=384,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Comment: {comment_text}"}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def pick_sample(comments: list[dict], n: int = 20) -> list[dict]:
    # Spread picks evenly across the dataset so we get early, mid, and late comments
    top_level = [c for c in comments if c["parent_id"] is None]
    step = max(1, len(top_level) // n)
    evenly_spaced = top_level[::step][:n]
    # Pad with random picks if we got fewer than n
    if len(evenly_spaced) < n:
        remaining = [c for c in top_level if c not in evenly_spaced]
        evenly_spaced += random.sample(remaining, min(n - len(evenly_spaced), len(remaining)))
    return evenly_spaced[:n]


def print_results(results: list[dict]) -> None:
    divider = "-" * 110
    print(divider)
    print(f"{'#':<3}  {'STANCE':<18} {'TONE':<14} {'SUB':<5} {'CONF':<6}  {'TOPICS':<35}  TEXT")
    print(divider)
    for i, r in enumerate(results, 1):
        text_preview = textwrap.shorten(r["text"], width=45, placeholder="...")
        topics_str = ", ".join(r.get("topics", ["none"]))
        label = f"{r['stance']:<18} {r['theological_tone']:<14} {'Y' if r['is_substantive'] else 'N':<5} {r['confidence']:.2f}"
        print(f"{i:<3}  {label}  {topics_str:<35}  {text_preview}")
        print(f"     reason: {r['one_line_reason']}")
        print()
    print(divider)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to comments JSON file")
    parser.add_argument("--n", type=int, default=20, help="Number of comments to sample")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(f"Loaded {data['comment_count']} comments from: {data['title']}\n")

    sample = pick_sample(data["comments"], n=args.n)
    print(f"Classifying {len(sample)} comments with Claude Haiku...\n")

    results = []
    for i, comment in enumerate(sample, 1):
        print(f"  [{i}/{len(sample)}] classifying...", end="\r")
        classification = classify(comment["text"])
        results.append({**comment, **classification})

    print(" " * 40)  # clear the progress line
    print_results(results)

    out_path = Path(args.input).parent / f"taxonomy_validation_{Path(args.input).stem}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull results saved to: {out_path}")


if __name__ == "__main__":
    main()