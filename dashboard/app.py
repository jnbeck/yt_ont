"""
Streamlit dashboard for browsing and filtering classified YouTube comments.

Run with:
    streamlit run dashboard/app.py
"""

import json
import os
import sqlite3
from pathlib import Path

import streamlit as st

DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/comments.db")

st.set_page_config(page_title="BoM Geography — Comment Explorer", layout="wide")


@st.cache_data
def load_comments() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT
            r.comment_id,
            r.video_title,
            r.text,
            r.like_count,
            r.published_at,
            r.parent_id,
            e.stance,
            e.theological_tone,
            e.is_substantive,
            e.topics,
            e.confidence
        FROM raw_comments r
        JOIN enriched_comments e ON r.comment_id = e.comment_id
        ORDER BY r.like_count DESC
    """).fetchall()
    conn.close()

    comments = []
    for row in rows:
        c = dict(row)
        c["topics"] = json.loads(c["topics"]) if c["topics"] else ["none"]
        c["is_substantive"] = bool(c["is_substantive"])
        comments.append(c)
    return comments


def stance_color(stance: str) -> str:
    return {
        "believer": "🟢",
        "skeptic_academic": "🔵",
        "hostile": "🔴",
        "casual": "⚪",
        "unclear": "🟡",
    }.get(stance, "⚪")


@st.cache_data
def load_questions() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT q.text, q.is_implied, q.video_id,
               r.like_count, e.stance, e.theological_tone,
               r.video_title
        FROM questions q
        JOIN raw_comments r ON q.comment_id = r.comment_id
        JOIN enriched_comments e ON q.comment_id = e.comment_id
        ORDER BY r.like_count DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@st.cache_data
def load_claims() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT c.text, c.claim_type, c.video_id,
               r.like_count, e.stance,
               r.video_title
        FROM claims c
        JOIN raw_comments r ON c.comment_id = r.comment_id
        JOIN enriched_comments e ON c.comment_id = e.comment_id
        ORDER BY r.like_count DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


comments = load_comments()

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.title("Filters")

all_stances = ["believer", "skeptic_academic", "hostile", "casual", "unclear"]
selected_stances = st.sidebar.multiselect(
    "Stance", all_stances, default=all_stances
)

all_tones = ["devotional", "apologetic", "questioning", "critical", "neutral"]
selected_tones = st.sidebar.multiselect(
    "Theological tone", all_tones, default=all_tones
)

all_topics = [
    "Jaredites", "Chronology", "Language", "People", "Magic Art",
    "Narrow Neck of Land", "Narrow Strip of Wilderness", "Land of Nephi",
    "Cumorah", "Plants and Minerals", "Ecology", "Records",
    "Land of Many Waters", "Destructions", "New Jerusalem",
    "Battles (Movements)", "Moroni's Description (Alma 22)", "Mount Antipas",
    "Temples", "Structures", "Belongings", "Reckoning", "none",
]
selected_topics = st.sidebar.multiselect("Topic", all_topics)

substantive_only = st.sidebar.checkbox("Substantive comments only", value=False)

min_likes = st.sidebar.slider("Minimum likes", 0, 50, 0)

search = st.sidebar.text_input("Search text")

# ── Apply filters ──────────────────────────────────────────────────────────────
filtered = comments

if selected_stances:
    filtered = [c for c in filtered if c["stance"] in selected_stances]

if selected_tones:
    filtered = [c for c in filtered if c["theological_tone"] in selected_tones]

if selected_topics:
    filtered = [c for c in filtered if any(t in c["topics"] for t in selected_topics)]

if substantive_only:
    filtered = [c for c in filtered if c["is_substantive"]]

if min_likes > 0:
    filtered = [c for c in filtered if c["like_count"] >= min_likes]

if search:
    filtered = [c for c in filtered if search.lower() in c["text"].lower()]

# ── Header stats ───────────────────────────────────────────────────────────────
st.title("Book of Mormon Geography — Comment Explorer")

tab1, tab2, tab3 = st.tabs(["Comments", "Questions", "Claims"])

# ── Tab 1: Comments ────────────────────────────────────────────────────────────
with tab1:
    col1, col2, col3, col4, col5 = st.columns(5)
    stance_counts = {s: sum(1 for c in filtered if c["stance"] == s) for s in all_stances}
    col1.metric("🟢 Believer", stance_counts["believer"])
    col2.metric("🔵 Skeptic/Academic", stance_counts["skeptic_academic"])
    col3.metric("🔴 Hostile", stance_counts["hostile"])
    col4.metric("⚪ Casual", stance_counts["casual"])
    col5.metric("Total shown", len(filtered))

    st.divider()
    st.subheader(f"{len(filtered)} comments")

    for c in filtered:
        icon = stance_color(c["stance"])
        topics_str = ", ".join(c["topics"]) if c["topics"] != ["none"] else "—"
        likes_str = f"👍 {c['like_count']}" if c["like_count"] > 0 else ""
        conf_str = f"conf: {c['confidence']:.2f}" if c["confidence"] else ""

        with st.expander(
            f"{icon} {c['stance']} · {c['theological_tone']} · {topics_str}  {likes_str}  —  {c['text'][:100]}..."
        ):
            st.write(c["text"])
            st.caption(
                f"**Stance:** {c['stance']}  |  **Tone:** {c['theological_tone']}  |  "
                f"**Topics:** {topics_str}  |  **Substantive:** {'Yes' if c['is_substantive'] else 'No'}  |  "
                f"**{conf_str}**  |  **Likes:** {c['like_count']}  |  {c['published_at'][:10]}"
            )

# ── Tab 2: Questions ───────────────────────────────────────────────────────────
with tab2:
    questions = load_questions()
    claims = load_claims()

    if not questions:
        st.info("No questions extracted yet. Run `python extract.py` to populate this tab.")
    else:
        st.subheader(f"{len(questions)} questions extracted from substantive comments")

        q_stance = st.multiselect("Filter by stance", all_stances, default=all_stances, key="q_stance")
        q_search = st.text_input("Search questions", key="q_search")
        implied_only = st.checkbox("Implied questions only")

        filtered_q = questions
        if q_stance:
            filtered_q = [q for q in filtered_q if q["stance"] in q_stance]
        if implied_only:
            filtered_q = [q for q in filtered_q if q["is_implied"]]
        if q_search:
            filtered_q = [q for q in filtered_q if q_search.lower() in q["text"].lower()]

        for q in filtered_q:
            likes_str = f"👍 {q['like_count']}" if q["like_count"] > 0 else ""
            implied_str = " *(implied)*" if q["is_implied"] else ""
            st.markdown(f"- {q['text']}{implied_str} {likes_str}  `{q['stance']}`")

# ── Tab 3: Claims ──────────────────────────────────────────────────────────────
with tab3:
    if not claims:
        st.info("No claims extracted yet. Run `python extract.py` to populate this tab.")
    else:
        claim_type_icons = {"supporting": "✅", "challenging": "❌", "neutral": "➖"}

        col_s, col_c, col_n = st.columns(3)
        col_s.metric("✅ Supporting", sum(1 for c in claims if c["claim_type"] == "supporting"))
        col_c.metric("❌ Challenging", sum(1 for c in claims if c["claim_type"] == "challenging"))
        col_n.metric("➖ Neutral", sum(1 for c in claims if c["claim_type"] == "neutral"))

        st.divider()
        st.subheader(f"{len(claims)} claims extracted")

        claim_filter = st.multiselect(
            "Claim type", ["supporting", "challenging", "neutral"],
            default=["supporting", "challenging", "neutral"], key="claim_type"
        )
        claim_search = st.text_input("Search claims", key="claim_search")

        filtered_c = [c for c in claims if c["claim_type"] in claim_filter]
        if claim_search:
            filtered_c = [c for c in filtered_c if claim_search.lower() in c["text"].lower()]

        for c in filtered_c:
            icon = claim_type_icons.get(c["claim_type"], "➖")
            likes_str = f"👍 {c['like_count']}" if c["like_count"] > 0 else ""
            st.markdown(f"- {icon} {c['text']} {likes_str}  `{c['stance']}`")