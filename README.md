# Book of Mormon Geography — YouTube Comment Knowledge Graph

A data pipeline and analytics system that ingests YouTube comments from Gunther's Book of Mormon / Baja California geography podcast series, analyzes them with LLMs, stores the results in a knowledge graph, and surfaces insights through an interactive dashboard and chatbot.

**Goal:** Give Gunther and collaborators a clear view of the "voice of the audience" — what questions viewers are asking, what claims they're making, and what topics should be addressed in future episodes.

---

## What It Does

- Automatically fetches comments from YouTube videos via the YouTube Data API v3
- Classifies each comment by stance, sentiment, and theological tone using Claude AI
- Extracts questions, geographic mentions, scripture references, and claims
- Stores everything in a Neo4j knowledge graph with a domain-specific ontology
- Provides a Streamlit dashboard with maps, charts, and an "Episode Prep Report"
- Includes a GraphRAG chatbot for natural-language queries over the comment corpus

---

## Architecture

```
YouTube Data API v3
        │
        ▼
┌───────────────────┐
│  Ingestion Layer  │  commentThreads.list → SQLite (raw_comments)
│  (Python script)  │  Idempotent: comment_id primary key
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Staging Layer    │  SQLite: raw → enriched
│  (LLM pipeline)  │  Claude Haiku: classify all comments
│                   │  Claude Sonnet: deep extract substantive ones
└────────┬──────────┘
         │
         ▼
┌────────────────────────────────────┐
│  Knowledge Graph  (Neo4j AuraDB)   │
│  + Vector Store   (ChromaDB)       │
│  Embeddings via Ollama nomic-embed │
└────────┬───────────────────────────┘
         │
         ▼
┌───────────────────┐
│  Interaction      │  Streamlit dashboard
│  Layer            │  GraphRAG chatbot
│                   │  Episode Prep Report generator
│                   │  Folium geographic map
└───────────────────┘
         │
         ▼
  GitHub Actions cron (daily, automated new-video processing)
```

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Comment ingestion | YouTube Data API v3 | Official, free (10K units/day) |
| Staging storage | SQLite | Zero ops, portable, idempotent |
| Bulk classification | Claude Haiku 4.5 | Fast, cheap (~$0.03/video), LDS-aware |
| Deep extraction | Claude Sonnet 4.6 | Nuanced claim/entity extraction |
| Embeddings | Ollama + nomic-embed-text | Free, local, persistent |
| Vector store | ChromaDB | Embedded Python, no server needed |
| Knowledge graph | Neo4j AuraDB Free | Native graph queries, Cypher |
| Dashboard | Streamlit | Rapid UI, Python-native |
| Geographic mapping | Folium + streamlit-folium | Baja California overlays |
| Orchestration | GitHub Actions cron | Free, zero infrastructure |
| Secrets | python-dotenv | Simple solo project |

**Why Claude over local Ollama for analysis:** LDS terminology ("testimony", "Liahona", "narrow neck of land") is highly domain-specific. General-purpose 8B models misclassify devotional language and hallucinate geographic relationships. At this comment volume (~500/video), Claude API costs ~$0.40/video — well worth the accuracy gain.

---

## Knowledge Graph Ontology

### Node Types

```cypher
(:Video {id, title, publishedAt, url, episodeNumber})
(:Comment {id, text, authorChannelId, likeCount, publishedAt,
           isTopLevel, stance, theologicalTone, sentimentScore,
           confidence, processingVersion})
(:Commenter {channelId, commentCount, firstSeenAt})
(:Topic {name, category})
(:Question {text, normalized, priority, isAddressed})
(:Claim {text, claimType, evidenceType})
(:GeographicFeature {name, type, lat, lon, region})
(:ScriptureReference {book, chapter, verse})
(:Stance {value})  // believer | skeptic_academic | hostile | casual | unclear
```

### Relationship Types

```cypher
(Comment)-[:BELONGS_TO]->(Video)
(Comment)-[:POSTED_BY]->(Commenter)
(Comment)-[:REPLIES_TO]->(Comment)
(Comment)-[:EXPRESSES_STANCE]->(Stance)
(Comment)-[:ASKS]->(Question)
(Comment)-[:MAKES_CLAIM]->(Claim)
(Comment)-[:MENTIONS_LOCATION]->(GeographicFeature)
(Comment)-[:REFERENCES]->(ScriptureReference)
(Claim)-[:SUPPORTS]->(Claim)
(Claim)-[:CONTRADICTS]->(Claim)
(Claim)-[:LOCATES_EVENT_AT]->(GeographicFeature)
```

### Stance Taxonomy

| Value | Description |
|---|---|
| `believer` | Expresses faith in Gunther's theory or LDS doctrine |
| `skeptic_academic` | Questions evidence without hostility — most valuable for engagement |
| `hostile` | Adversarial, dismissive, or anti-Mormon |
| `casual` | "Great video!", emoji-only, no substantive content |
| `unclear` | Cannot be confidently classified |

### Theological Tone Taxonomy

| Value | Description |
|---|---|
| `devotional` | Testimony, gratitude, expressions of faith |
| `apologetic` | Defending LDS doctrine or the Baja theory |
| `questioning` | Genuine inquiry, open-minded skepticism |
| `critical` | Challenges the theory or doctrine |
| `neutral` | Academic, informational, no strong tone |

---

## Project Structure

```
yt_ont/
├── .github/
│   └── workflows/
│       └── ingest.yml          # Daily cron: fetch + process new comments
├── ingestion/
│   ├── youtube_client.py       # YouTube Data API wrapper
│   └── sqlite_store.py         # Raw comment storage, idempotency
├── processing/
│   ├── classify.py             # Claude Haiku: stance, sentiment, flags
│   ├── extract.py              # Claude Sonnet: questions, claims, entities
│   ├── embeddings.py           # Ollama nomic-embed-text → ChromaDB
│   └── prompts/
│       ├── classify.txt        # Classification prompt template
│       └── extract.txt         # Deep extraction prompt template
├── graph/
│   ├── neo4j_client.py         # Neo4j connection + Cypher helpers
│   ├── schema.cypher           # Ontology: constraints + indexes
│   └── sync.py                 # SQLite enriched → Neo4j upsert
├── dashboard/
│   ├── app.py                  # Streamlit main app
│   ├── pages/
│   │   ├── overview.py         # Stance distribution, sentiment trends
│   │   ├── questions.py        # Top unanswered questions
│   │   ├── map.py              # Folium geographic mention map
│   │   ├── episode_prep.py     # Episode Prep Report generator
│   │   └── chatbot.py          # GraphRAG chatbot
│   └── components/
│       └── filters.py          # Video selector, date range, stance filter
├── gis/
│   └── baja_layers.py          # GeoJSON layers for Baja California
├── data/
│   ├── comments.db             # SQLite: raw + enriched comments
│   └── vectors/                # ChromaDB persistent storage
├── tests/
│   ├── test_classify.py
│   └── test_extract.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) installed locally with `nomic-embed-text` pulled
- Neo4j AuraDB Free account
- Anthropic API key
- YouTube Data API v3 key (Google Cloud Console)

### Installation

```bash
git clone https://gitlab.com/jnbeck87/yt_ont.git
cd yt_ont
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Pull the embedding model:
```bash
ollama pull nomic-embed-text
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
# YouTube
YOUTUBE_API_KEY=your_key_here

# Anthropic (Claude)
ANTHROPIC_API_KEY=your_key_here

# Neo4j AuraDB
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434

# Target YouTube channel
YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxx
```

### Initialize the Knowledge Graph Schema

```bash
python graph/schema.cypher   # Creates constraints + indexes in Neo4j
```

---

## Usage

### Manual Run (single video)

```bash
# Fetch comments for a specific video
python ingestion/youtube_client.py --video-id dQw4w9WgXcQ

# Process staged comments through LLM pipeline
python processing/classify.py
python processing/extract.py
python processing/embeddings.py

# Sync enriched comments to Neo4j
python graph/sync.py

# Launch dashboard
streamlit run dashboard/app.py
```

### Automated (via GitHub Actions)

The daily cron job in `.github/workflows/ingest.yml` handles new videos and comments automatically. Set the secrets in your GitLab/GitHub repository settings matching the `.env` variables above.

---

## Dashboard Features

| Page | Description |
|---|---|
| **Overview** | Stance distribution, sentiment trend per video, comment volume timeline |
| **Questions** | Top unanswered questions ranked by frequency + engagement, filterable by topic |
| **Geographic Map** | Folium map of Baja California with comment location mentions, color-coded by stance |
| **Episode Prep** | Auto-generated briefing: top questions to address, strongest objections, suggested response angles |
| **Chatbot** | GraphRAG chatbot — ask natural-language questions over the full comment corpus |

### Example Chatbot Queries

- *"What are the most common questions about the narrow neck of land?"*
- *"Summarize the strongest geographic objections from skeptical commenters."*
- *"Which scripture references do hostile commenters cite most?"*
- *"Generate an episode outline addressing viewer questions about Lehi's journey."*

---

## Estimated Costs

At typical volume (~500 comments per video, weekly episodes):

| Service | Monthly cost |
|---|---|
| YouTube Data API | Free (well under quota) |
| Claude Haiku 4.5 (bulk classification) | ~$0.15 |
| Claude Sonnet 4.6 (deep extraction) | ~$1.20 |
| Neo4j AuraDB Free | Free |
| ChromaDB (local) | Free |
| GitHub Actions | Free |
| **Total** | **~$1.35/month** |

---

## Roadmap

**Phase 1 — Core Pipeline (Weeks 1–2)**
- [x] Project scaffolding
- [ ] YouTube API ingestion + SQLite storage
- [ ] Claude Haiku classification on sample comments
- [ ] Taxonomy validation with Gunther
- [ ] Basic Streamlit comment table + stance distribution

**Phase 2 — Knowledge Graph (Month 1)**
- [ ] Neo4j schema + constraints
- [ ] Claude Sonnet deep extraction (questions, claims, entities)
- [ ] ChromaDB embeddings
- [ ] Episode Prep Report generator

**Phase 3 — Intelligence Layer (Month 2)**
- [ ] GraphRAG chatbot
- [ ] Geographic mention extraction + Folium map
- [ ] GitHub Actions cron automation

**Phase 4 — Future**
- [ ] BERTopic topic modeling (once 2,000+ comments in aggregate)
- [ ] QGIS export of geographic claim data
- [ ] Fine-tuned stance classifier on accumulated labeled data
- [ ] Neo4j Bloom / NeoDash graph explorer

---

## Handling Religious Content

This system analyzes commentary on a religiously sensitive topic. A few design decisions reflect that:

- **Commenter privacy:** Only `authorChannelId` (YouTube's pseudonymous ID) is stored — never display names or profile photos.
- **Stance vs. tone are separate:** A comment can be `believer` stance with `questioning` tone, or `skeptic_academic` with `neutral` tone. Don't conflate them.
- **Devotional ≠ evidence claim:** Testimony statements ("I know this is true") are tagged `devotional` and excluded from question/claim extraction.
- **`skeptic_academic` is not hostile:** These comments often contain the most valuable intellectual engagement and should never be filtered or suppressed.
- **LLM prompts include LDS glossary:** Every prompt includes terminology context so the model correctly interprets "nephites", "Liahona", "iron rod", etc.

---

## GIS Integration

Gunther's dad is a professional geographer. The system is designed to feed his expertise:

- All geographic mentions are geocoded and stored with lat/lon in `GeographicFeature` nodes
- Claims link scripture events to specific Baja California locations
- Folium map in the dashboard supports overlay of Gunther's proposed route as GeoJSON
- Data can be exported to GeoJSON for analysis in QGIS

See [gis/baja_layers.py](gis/baja_layers.py) for the geographic data layer structure.

---

## Contributing

This is a personal project for Gunther's podcast community. If you're collaborating:

1. Open a merge request with a clear description of the change
2. Tag any changes to the ontology with `[ontology]` in the MR title — these need review since they affect the entire downstream pipeline
3. Run `pytest tests/` before submitting

---

## Acknowledgments

Built for Gunther's Book of Mormon geography podcast series. The Baja California hypothesis is Gunther's original research — this system exists to help him understand and engage with his audience, not to advocate for or against any theological position.
