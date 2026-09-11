# Architecture

## Overview

The Netflix Narrative Intelligence Pipeline (NIP) is a 6-stage, local-first system that ingests scripts and video, builds a dual knowledge representation, runs three specialized agents, and gates output through deterministic + LLM verification before human review.

```
┌──────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                           │
│   Scripts (.fdx/.pdf/.fountain) + Video (final cuts)            │
│   + Subtitles + Show Bibles + Prior Episode Data                │
└───────────────┬──────────────────────────────┬───────────────────┘
                │                              │
                ▼                              ▼
┌───────────────────────────┐  ┌───────────────────────────────────┐
│  TEXT PIPELINE             │  │  VISUAL PIPELINE                  │
│  Script Parser             │  │  Keyframe Extraction              │
│  ASR (Whisper)             │  │  Object Detection + Re-ID          │
│  Temporal Alignment        │  │  Feature Embedding (Contrastive)  │
└───────────┬───────────────┘  └───────────┬───────────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              SMPTE-ALIGNED UNIFIED TIMELINE                     │
│   [Scene]──[Timecode]──[Script Chunk]──[Transcript]──[Keyframe] │
└─────────────────────────────┬───────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                                    ▼
┌──────────────────────┐        ┌────────────────────────────────┐
│  DETERMINISTIC KG     │        │  DENSE VECTOR INDEX (RAC)     │
│  (Neo4j)              │        │  (Qdrant)                     │
│                       │        │                                │
│  Hard facts only:     │        │  Raw scripts, transcripts,    │
│  - Character location │        │  scene descriptions, prior    │
│  - Alive/dead state   │        │  episode summaries indexed    │
│  - Prop ownership     │        │  as dense embeddings           │
│  - Known secrets      │        │                                │
│  - Timecoded events   │        │  Used for: motivational      │
│                       │        │  consistency, tonal coherence, │
│  Source: fine-tuned   │        │  emotional arc gaps,          │
│  NER + human          │        │  absence detection            │
│  correction loop      │        │                                │
│                       │        │  Source: raw ingested text,   │
│  Verified by:         │        │  no extraction needed          │
│  graph constraint      │        │                                │
│  engine (no LLM)      │        │                                │
└──────────┬───────────┘        └────────────┬───────────────────┘
           │                                  │
           └──────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MULTI-AGENT INFERENCE LAYER                   │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  SCRIPT CRITIC   │  │ CONTINUITY      │  │  RECAP AGENT    │ │
│  │                  │  │ INSPECTOR       │  │                 │ │
│  │ KG + RAC hybrid  │  │ KG (hard facts) │  │ KG (scene nodes)│ │
│  │                  │  │ + VLM + CV      │  │ + RAC (tone)    │ │
│  │ Layer 1: KG      │  │ + Contrastive   │  │                 │ │
│  │ graph traversal   │  │ Embeddings      │  │ Base recap +    │ │
│  │ (factual holes)  │  │ (pre-filter)    │  │ 3-5 tonal       │ │
│  │                  │  │                  │  │ variants with    │ │
│  │ Layer 2: RAC     │  │ Visual: object  │  │ structured       │ │
│  │ retrieval for    │  │ tracking across │  │ metadata output  │ │
│  │ motivational &   │  │ keyframes via   │  │ (thread labels,  │ │
│  │ emotional gaps   │  │ CV + actor re-ID │  │ valence scores) │ │
│  │                  │  │                  │  │                 │ │
│  │ Layer 3: BDI      │  │ Textual: KG     │  │ Per-show LoRA   │ │
│  │ simulation        │  │ constraint check │  │ fine-tuning on  │ │
│  │ (MVP STRETCH)    │  │ (deterministic) │  │ prior recaps    │ │
│  │                  │  │                  │  │ (MVP STRETCH)   │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
└───────────┼────────────────────┼────────────────────┼───────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VERIFICATION & COMPLIANCE                     │
│                                                                 │
│  ┌──────────────────────────┐  ┌─────────────────────────────┐ │
│  │  DETERMINISTIC CONSTRAINT │  │  LLM-AS-A-JUDGE             │ │
│  │  ENGINE                   │  │  COMPLIANCE LAYER            │ │
│  │                           │  │                             │ │
│  │  - Character cannot be   │  │  - Cross-checks recaps      │ │
│  │    at 2 locations at     │  │    against KG for zero       │ │
│  │    same timecode          │  │    hallucination             │ │
│  │  - Dead character cannot  │  │  - Validates continuity     │ │
│  │    perform actions after  │  │    flags cross confidence    │ │
│  │    death timecode         │  │    threshold                 │ │
│  │  - Prop cannot be held by │  │  - Flags low-confidence     │ │
│  │    2 characters at once   │  │    outputs for human review  │ │
│  │  - Secret cannot be known │  │                             │ │
│  │    before revelation event│  │  Never validates against     │ │
│  │                           │  │  its own claims — only       │ │
│  │  Runs on KG only, no LLM │  │  against KG truth            │ │
│  │  involved. Pure graph     │  │                             │ │
│  │  queries.                 │  │                             │ │
│  └──────────────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRE-LIVE REPORT                              │
│                                                                 │
│  Priority Queue:                                               │
│  1. Continuity errors (deterministic violations)               │
│  2. Plot holes (high-confidence factual contradictions)        │
│  3. Plot holes (low-confidence motivational/emotional gaps)     │
│  4. Recap drafts (blocked until 1-3 resolved or acknowledged)  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              HUMAN-IN-THE-LOOP EDITORIAL UI                     │
│                                                                 │
│  - Accept / Fix & Re-run / Override with Note                  │
│  - Incremental re-run: only changed scenes re-processed         │
│  - Audit trail: every AI flag + human disposition logged       │
│  - KG correction loop: human edits feed back into KG           │
│    to improve extraction accuracy over time                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Multimodal Ingestion & Alignment

### Text Pipeline

| Input | Processing | Output |
|-------|-----------|--------|
| Shooting script (.fdx, .pdf, .fountain) | Scene parser → structured scene blocks | `SceneBlock{scene_id, characters[], location, time_of_day, dialogue[], stage_directions[]}` |
| Show bible / character sheets / season outlines | Schema-mapped ingestion | `ShowMetadata{characters, relationships, rules, tone_guide}` |
| Prior episode recaps | Ingest for tone-matching | `RecapCorpus{episode_id, text, tone_tags}` |

### Visual Pipeline

| Input | Processing | Output |
|-------|-----------|--------|
| Final video cut | Keyframe extraction (1 fps) | `Keyframe{image, timecode, scene_id}` |
| Final video cut (audio) | ASR via Whisper Large-v3 | `TranscriptSegment{text, start_tc, end_tc, confidence}` |
| Subtitles (.srt, .vtt) | Timecode-aligned import | `SubtitleSegment{text, start_tc, end_tc}` |

### SMPTE Alignment

All data streams join on SMPTE timecodes. Script scene boundaries map to timecode ranges. Transcript segments align to script dialogue via fuzzy string matching. Keyframes inherit scene context from their timecode's assigned scene block.

**Result**: A single `EpisodeDocument` with a unified timeline — every moment has script context + transcript + visual frame(s).

---

## Stage 2: Dual Knowledge Representation

### Path A — Deterministic Knowledge Graph (Neo4j)

Only hard, verifiable facts are extracted into the graph. This is intentional — the KG's value is that it can be verified without LLM reasoning.

| Entity Type | Relations | Example |
|------------|-----------|---------|
| Character | AT_LOCATION, HOLDS_PROP, KNOWS_SECRET, ALIVE_AT, RELATES_TO | `(Walter)-[HOLDS_PROP]->(Revolver) @ [S3E5, 00:14:22]` |
| Location | CONTAINS, ADJACENT_TO | `(Jesse's House)-[CONTAINS]->(Basement) @ [S1E1]` |
| Prop | OWNED_BY, APPEARS_IN, STATE_OF | `(Revolver)-[STATE_OF]->(Loaded) @ [S3E5, 00:14:22]` |
| Event | CAUSES, PRECEDES, CONTRADICTS | `(Hank shot)-[CAUSES]->(Walter panic) @ [S3E13]` |
| Secret/Fact | KNOWN_BY, REVEALED_IN, CONCEALED_FROM | `(Hank is DEA)-[KNOWN_BY]->(Walter) since [S2E8]` |

**Extraction pipeline**: Fine-tuned GLiNER + custom relation model per genre. Extraction confidence threshold at 0.95 — anything below routes to human correction queue.

**Graph Constraint Engine** (deterministic, no LLM):
- Character cannot be at two locations at the same timecode
- Dead characters cannot perform actions after their death timecode
- Props cannot be held by two characters at the same timecode
- Secrets cannot be known before their revelation event timecode
- Relationship cardinality constraints (e.g., biological parent is immutable)

### Path B — Dense Vector Index (RAC Layer)

All raw text (scripts, transcripts, show bibles, prior episode summaries) is chunked at scene granularity and embedded into Qdrant. No extraction step — raw text goes in directly. This eliminates the KG extraction accuracy problem for softer assessments.

**Used for**:
- Retrieving context windows when the Script Critic assesses motivational consistency
- Tonal coherence checks in recaps
- Absence detection — retrieving what should be there (e.g., unresolved subplots)

**Why both**: KG handles what can be verified deterministically. RAC handles what requires interpretation. Neither alone covers the full problem space.

---

## Stage 3: Multi-Agent Inference

All three agents run in parallel via Dagster orchestration. They share the same KG and vector index but are decoupled — no agent depends on another's output.

### Agent 1: Script Critic (Plot Hole Predictor)

Three-layer detection, each catching a different class of plot hole:

| Layer | Method | Catches | Misses |
|-------|--------|---------|--------|
| **Layer 1: Graph traversal** | Query KG for temporal constraint violations | Factual contradictions (character acts on info they don't have yet, dead character acts, impossible location) | Motivational inconsistencies |
| **Layer 2: RAC retrieval** | Retrieve relevant prior scenes, present to LLM side-by-side with current script | Motivational gaps, unresolved subplots, emotional discontinuities | Multi-hop logical gaps |
| **Layer 3: BDI simulation** (MVP STRETCH) | Model each character as a Belief-Desire-Intention agent. Replay the script. Flag actions that contradict belief state. | Psychological inconsistency, unearned decisions, out-of-character actions | Setup cost per show; requires character model calibration |

**Output per flag**:
```json
{
  "issue": "Walter references Gale's assignment in E6 but doesn't learn about it until E8",
  "severity": 4,
  "layer": "graph_traversal",
  "evidence": [
    {"ref": "S3E6@00:22:15", "type": "dialogue"},
    {"ref": "S3E8@00:08:30", "type": "revelation_event"}
  ],
  "confidence": 0.97,
  "suggested_fix": "Move revelation event to before S3E6, or remove reference in S3E6 dialogue",
  "script_version": "draft_07"
}
```

### Agent 2: Continuity Inspector (Visual + Textual)

Three-signal architecture:

| Signal | Method | Example Detection |
|--------|--------|------------------|
| **Deterministic graph check** | KG constraint engine queries for prop/state/location violations across timecodes | "Character holds wine glass in left hand at Scene 1A, right hand at Scene 1B with no intervening action" |
| **Visual: CV + VLM** | Object detection + tracking across keyframes. Actor re-identification segments each character per frame. Prop state extracted per frame. VLM interprets ambiguous cases. | "Character's jacket changes from blue to black between shots" |
| **Contrastive pre-filter** | Embed adjacent keyframes as multimodal vectors. Flag pairs with anomalous cosine distance in should-be-continuous scenes. Route flagged pairs to CV+VLM for precise analysis. | "Lighting/mood shift between Shot A and Shot B" — cheap anomaly detection before expensive VLM inference |

**Why contrastive pre-filter**: Running VLM on every keyframe pair is cost-prohibitive. The contrastive layer acts as cheap triage — only keyframe pairs with high visual distance in continuous scenes go to the VLM pipeline. This cuts VLM compute by ~80%.

### Agent 3: Editorial Recap Generator

| Component | Detail |
|-----------|--------|
| **Input** | Scene-level KG nodes + RAC retrieval for tonal context from prior recaps |
| **Base recap** | LLM identifies 3 primary narrative threads from scene nodes, drafts structured recap |
| **Tonal variants** | 3-5 variants: action-focused, romance-focused, suspense-focused, comedy-focused, character-study |
| **Per-show LoRA** (MVP STRETCH) | Fine-tune on show's prior recaps for voice match. MVP uses prompted-only approach. |
| **Structured metadata** | Each variant outputs structured fields for downstream personalization systems |
| **Spoiler control** | Toggle: "episodic mode" (avoid end-of-season spoilers) vs. "full mode". KG reveals-Until timecodes enforce what can be mentioned. |

**Output per recap**:
```json
{
  "base_recap": "Walter scrambles to cover his tracks after...",
  "variants": [
    {
      "text": "Tension explodes as Walter's double life...",
      "tone": "suspense",
      "thread_focus": "walter_coverup",
      "emotional_valence": {"tension": 0.9, "relief": 0.1}
    }
  ],
  "thread_labels": ["walter_coverup", "skyler_agency", "hank_investigation"],
  "emotional_valence_map": {"tension": 0.85, "dread": 0.7, "relief": 0.1},
  "character_arc_weights": {"walter": 0.4, "skyler": 0.3, "hank": 0.2, "jesse": 0.1},
  "spoiler_risk_score": 0.15
}
```

---

## Stage 4: Verification & Compliance

Two independent verification paths — avoids circular trust problem (LLM validating LLM against LLM-extracted KG).

| Path | Method | Scope | When It Runs |
|------|--------|-------|-------------|
| **Deterministic Constraint Engine** | Pure graph queries on KG. No LLM. | Hard factual violations only. | Before agents run (pre-screen) and after agents produce output (post-check). |
| **LLM-as-a-Judge** | Llama 3.1 8B cross-checks agent outputs against KG. | Hallucination in recaps, low-confidence continuity flags, plot hole validity. | After agents produce output. |

**Key design rule**: The LLM Judge never validates against its own claims — it only validates against the KG. It also never modifies the KG — it can only flag disagreements between agent output and KG state.

**Confidence thresholds**:

| Threshold Range | Action |
|----------------|--------|
| > 0.90 | Auto-escalate to human review |
| 0.70 – 0.90 | Surface in dashboard with "review recommended" tag |
| < 0.70 | Log but suppress from editorial view (reduce noise) |
| Recap spoiler_risk_score > 0.40 | Block from publish, require editorial sign-off |

---

## Stage 5: Pre-Live Report

Agents output into a unified report with priority ordering:

1. **Continuity errors** (deterministic violations) — must be addressed
2. **Plot holes** (high-confidence, >0.90) — should be addressed
3. **Plot holes** (low-confidence, 0.70–0.90) — review recommended
4. **Recap drafts** — blocked from publish until 1-3 resolved or acknowledged

**Report output schema per flag**:
```json
{
  "id": "flag_uuid",
  "issue": "...",
  "severity": 1-5,
  "source_agent": "script_critic|continuity_inspector",
  "evidence_refs": [],
  "confidence": 0.0-1.0,
  "suggested_fix": "...",
  "script_version": "draft_07",
  "human_disposition": null
}
```

---

## Stage 6: Human-in-the-Loop Editorial UI

| Action | Effect |
|--------|--------|
| **Accept** | Publish recap / acknowledge flag. Logged to audit trail. |
| **Fix & Re-run** | Edit script or metadata → triggers incremental re-processing of only changed scenes. KG diffs. Affected downstream outputs regenerated. Full pipeline NOT re-run. |
| **Override with note** | "Intentional inconsistency — dream sequence" → logged, flag dismissed, KG annotated with override context. |
| **KG correction** | Human corrects extraction errors → feeds back into fine-tuning data for NER model. Improves extraction accuracy over time. |

---

## Incremental Re-runs

Every pipeline run is tagged with a script version. When a new draft arrives:

1. Diff the new script against the prior version at scene level
2. Identify changed scenes + any scenes with cross-references to changed scenes (via KG traversal)
3. Re-run only the affected subgraph:
   - Re-extract entities for changed scenes → merge into KG
   - Re-run affected agent queries only
4. Produce incremental diff report: "New flags introduced by draft_08. Resolved flags from draft_07."
