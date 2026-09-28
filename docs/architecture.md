# Architecture

## Overview

The Narrative Intelligence Pipeline (NIP) is a self-hosted system that audits a show before release. It ingests scripts, picture, audio, subtitle tracks, the show bible, and legal's clearance log; places everything on one frame-accurate timeline; builds a shared knowledge layer; and runs four independent agents whose findings are verified and then reviewed by people.

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. INGEST                                                            │
│    Script (.fountain/.fdx/.pdf) · Picture + audio (.mp4/.mov/.mkv)   │
│    Subtitles per language (.srt/.vtt/.ttml) · Show bible (YAML)      │
│    Glossary (CSV) · Clearance log (CSV)                              │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. TIMELINE  (single source of truth, integer frames + SMPTE)        │
│    Shots · keyframes · transcript · script scenes & lines ·          │
│    subtitle cues (all languages) — aligned on one frame axis         │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. KNOWLEDGE                                                         │
│    Timed facts (who/where/holds/knows/state, valid-from → valid-to)  │
│    Scene vector index · Character & term registry · Clearance registry│
└───────┬──────────────────┬──────────────────┬──────────────────┬─────┘
        ▼                  ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ LOCALIZATION  │  │  CLEARANCE    │  │ SCRIPT CRITIC │  │ CONTINUITY    │
│ AUDITOR       │  │  SCANNER      │  │               │  │ INSPECTOR     │
│ names/terms,  │  │ OCR, logos,   │  │ rules on      │  │ story-day     │
│ gender, T–V,  │  │ dialogue refs,│  │ timed facts + │  │ rules + same- │
│ spoilers,     │  │ clearance-log │  │ retrieval +   │  │ setup visual  │
│ timing        │  │ matching      │  │ LLM           │  │ comparison    │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        └──────────────────┴────────┬─────────┴──────────────────┘
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. VERIFICATION  (can only drop or downgrade — never add)            │
│    Evidence resolver → rule re-check → LLM judge → routing & dedup   │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 6. REVIEW                                                            │
│    Ranked report · evidence player · Accept / Fix & Re-run /         │
│    Override (note required) / Correct fact · full audit trail        │
└──────────────────────────────────────────────────────────────────────┘
```

How the pipeline is scheduled onto hardware (laptop GPU or cloud cluster) is described in [Hardware Adaptation](hardware-adaptation.md). Storage and schemas are in [Data Model](data-model.md).

---

## Design Rules

These hold in every stage and every agent.

| Rule | Meaning |
|------|---------|
| **No output without evidence** | Every fact quotes the line it came from; every flag cites timeline objects (`S01E03 @ 00:14:22:05, subtitle #212 (es-419)`). Unresolvable evidence → the fact or flag is dropped. |
| **Inputs activate agents** | An agent runs when its inputs exist. Script only → Script Critic and text continuity. Add picture → Clearance and visual continuity. Add subtitle tracks → Localization. |
| **Deterministic first, models second** | Anything checkable by rules (timing, overlaps, knowledge order, phone formats) is checked by rules. Models are used for what needs interpretation, and their outputs are constrained to JSON schemas. |
| **Verification only subtracts** | Verification can drop, downgrade, or merge flags. It never creates flags or edits facts. |
| **No silent gaps** | Work that fails after retries is reported as a coverage gap in the report, never omitted. |
| **Agents are independent** | Agents read the shared knowledge layer, never each other's output. Any agent can be disabled without affecting the others. |
| **Self-hosted** | Open-weight models only, running on hardware you control (laptop, on-prem, or your own cloud account). No third-party AI APIs; pre-release material never leaves your infrastructure. |

---

## Stage 1: Ingest

### Inputs

| Input | MVP formats | Used by | Required? |
|-------|-------------|---------|-----------|
| Script | Fountain, Final Draft FDX, text-based PDF | Fact extraction, Script Critic, text continuity | Yes (minimum input) |
| Picture + audio | MP4 / MOV / MKV (H.264, H.265, ProRes). IMF packages post-MVP | Timeline, Clearance, visual continuity | Optional |
| Subtitle tracks | SRT, WebVTT, TTML / IMSC 1.1 — one source track + N target tracks | Localization, Clearance (dialogue channel) | Optional |
| Show bible | `bible.yaml`: characters (name, aliases, gender, pronouns), relationships, secrets with intended reveal, fictional brands/orgs/places, story-order overrides | All agents | Recommended |
| Glossary | CSV: `term, lang, approved_rendering, notes` | Localization | Optional |
| Clearance log | CSV: `item, kind, status (cleared/pending/denied), scope, notes` | Clearance | Optional (without it every detection is "unknown") |

### Validation at the door

Every file is validated before any GPU work is scheduled. Rejected inputs return a precise error (`INPUT_REJECTED`) and the run does not start.

- Media: probe container, codec, frame rate, duration, start timecode, drop-frame flag. Unknown or variable frame rate → reject.
- Subtitles: parse fully; report malformed cues with line numbers; record the declared frame rate (TTML) or `none` (SRT/VTT).
- Script: parse to scenes; a script with zero scene headings → reject.
- Bible / glossary / clearance log: schema-validated; unknown columns are warnings, missing required columns are errors.

Each file is stored content-addressed (SHA-256) with a version label (`draft_07`, `picture_lock_02`), so every run is reproducible.

---

## Stage 2: Timeline

The timeline is a single frame axis per episode. Every object — scene, script line, shot, keyframe, transcript segment, subtitle cue — is an integer frame range on it. SMPTE timecode (`HH:MM:SS:FF`, drop-frame where applicable) is only a display format. See [Data Model › Time](data-model.md#time) for the exact representation.

| Step | What happens | Output |
|------|--------------|--------|
| Media probe | Frame rate (e.g. 24000/1001), start timecode, drop-frame | Episode frame axis |
| Shot detection | Hard cuts and gradual transitions | `shot` ranges |
| Keyframes | Middle frame of each shot, plus one every 2 s for shots longer than 4 s (configurable) | Keyframe images in object storage |
| Transcription | Speech-to-text on the original-language audio, word-level timestamps | `transcript_segment` ranges |
| Script ↔ transcript | Monotonic sequence alignment of normalized dialogue tokens to transcript words; scene boundaries snapped to shot cuts | Each script line and scene gets a frame range |
| Subtitles → frames | Cue times converted to frames at the picture's frame rate (exact rational math) | `subtitle_cue` ranges |
| Target ↔ source cues | Temporal-overlap alignment, tolerant of 1:n and n:1 splits/merges | Each target cue linked to its source cue(s) |

**Script-estimate mode.** When no picture exists (e.g., a draft before shooting), scenes get *estimated* frame ranges from script order and page length (industry rule of thumb: one page ≈ one minute, at 24 fps). All downstream logic works unchanged; evidence is displayed as `S01E03 · Sc 12 (script estimate)` instead of a timecode. When picture arrives, alignment replaces estimates with real ranges.

**Edit order vs script order.** Editors move and cut scenes. Once picture exists, *screen order* follows the cut, not the script; scenes absent from the cut are marked `not_in_cut` and excluded from screen-order checks.

---

## Stage 3: Knowledge

### Timed facts

The LLM reads one scene at a time (plus the bible entries for characters present) and returns facts in a fixed JSON schema. MVP predicates:

| Predicate | Example | Primary consumers |
|-----------|---------|-------------------|
| `present_at` | Maya present at *Harbor Warehouse* (Sc 12) | Script Critic, Continuity |
| `holds` / `owns` | Maya holds *brass key* | Script Critic, Continuity |
| `state` | Leo `injured: left hand cut`; Ada `dead` | Script Critic, Continuity |
| `wearing` | Maya wearing *red scarf* (only when the script or bible states it) | Continuity |
| `learns` | Leo learns *secret: Ada is the informant* | Script Critic, Localization |
| `references` | Leo references *secret: Ada is the informant* | Script Critic |
| `relationship` | Maya ↔ Leo: `strangers` → `colleagues` → `partners` | Localization (formality) |
| `setup` / `payoff` | Setup: *gun in the drawer* (importance 3); payoff links back to its setup | Script Critic |
| `decision` | Leo decides to leave the city | Script Critic |
| `mentions` | Line mentions *Brightwave Energy* (org) | Clearance, Localization |

**Grounding validator.** Every extracted fact carries a quote and a line id. A deterministic validator checks the quote exists in that line (normalized, fuzzy threshold). Facts that fail are dropped and counted in extraction metrics — the LLM cannot invent a fact that isn't in the text.

**Entity resolution.** Names and aliases are resolved against the bible's character list first, then against previously seen entities. Unresolved names become *candidate entities* shown in the review UI's fact queue.

**Fact correction loop.** Low-confidence facts (below `NIP_FACT_REVIEW_THRESHOLD`) and candidate entities appear in the correction queue. A reviewer can confirm, edit, or retract. Corrections are stored as new fact versions (never destructive updates), and every flag whose evidence included the corrected fact is automatically re-evaluated.

### Story order and story days

Screen order is not story order (flashbacks, intercuts). Each scene gets:

- **`story_day`** — derived from scene headings and transitions: `DAY`/`NIGHT`, `CONTINUOUS`, `LATER`, `NEXT MORNING`, `THAT NIGHT`.
- **`story_seq`** — chronological rank. Flashbacks (`FLASHBACK`, `YEARS EARLIER`, `PRESENT DAY`) are moved; `INTERCUT` / `SAME TIME` scenes share a `story_seq`.

Derivation is rule-based; ambiguous transitions go to the LLM with neighboring scenes; the bible's `story_overrides` always win. Flags that depend on an *inferred* (not explicit) story position get their confidence reduced by a configurable factor.

**Which order each check uses:**

| Check type | Order |
|------------|-------|
| Plot logic (knowledge before learning, dead characters acting) | Story order |
| Spoilers (including translation-induced) | Screen order (what the viewer has seen) |
| Continuity (wardrobe, injuries, props) | Story day, then screen order within a scene |

### Registries

- **Character & term registry** — canonical names, aliases, gender/pronouns, `identity_hidden_until` for secret identities, invented terms, and approved per-language renderings from the glossary. When the glossary has no entry, the season's most frequent rendering becomes the observed standard.
- **Clearance registry** — the clearance log plus the bible's fictional brands, organizations, and places (fictional items never need clearance).

### Scene vector index

Scene text (headings, action, dialogue) is embedded per scene and stored in Postgres (pgvector). Retrieval combines vector similarity with structured filters from the timed facts (shared characters, props, secrets), so agents retrieve *related* scenes, not just textually similar ones. Embedding text only — not fact summaries — keeps the index buildable before extraction, which avoids an extra model load in staged mode.

---

## Stage 4: Agents

### Common contract

Every agent is a set of **checks**. Each check declares its required inputs, runs over small work units (scene, shot pair, subtitle cue window), and emits flags in one schema:

```json
{
  "agent": "localization_auditor",
  "check": "translation_spoiler",
  "severity": 5,
  "confidence": 0.93,
  "title": "Spanish subtitle reveals the killer's gender before the reveal",
  "explanation": "Source 'the killer' is gender-neutral; target 'la asesina' marks the referent as female. The killer's identity is hidden until S01E08 @ 00:41:10:00.",
  "suggested_fix": "Use a gender-neutral construction, e.g. 'quien lo mató'.",
  "evidence": [
    {"kind": "subtitle_cue", "ref": "S01E03/es-419/212", "tc": "00:14:22:05", "role": "claim", "quote": "La asesina sigue aquí."},
    {"kind": "subtitle_cue", "ref": "S01E03/en/209", "tc": "00:14:22:05", "role": "context", "quote": "The killer is still here."},
    {"kind": "fact", "ref": "fact/8812", "role": "context", "quote": "identity_hidden_until S01E08 @ 00:41:10:00"}
  ],
  "produced_by": {"model_variant": "qwen3.5-4b-awq", "prompt_version": "loc.spoiler.v3", "plan_id": "plan_42"}
}
```

Full schema: [Data Model › Flag](data-model.md#flag-and-evidence).

### Activation matrix

| Agent / check group | Script | Picture | Source subs | Target subs | Bible | Glossary | Clearance log |
|---------------------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Script Critic | ● | | | | ◐ | | |
| Continuity — text rules | ● | | | | ◐ | | |
| Continuity — visual | ● | ● | | | | | |
| Clearance — on-screen text & logos | | ● | | | ◐ | | ◐ |
| Clearance — dialogue references | ● | | ◐ | | ◐ | | ◐ |
| Localization — names/terms, gender, T–V, spoilers | ● | | ● | ● | ● | ◐ | |
| Localization — timing & readability | | ◐ | ● | ● | | | |

● required · ◐ improves results · blank: not used. (Timing checks without picture skip shot-change rules.)

---

### Agent 1: Localization Auditor

Audits every target-language subtitle track against the source track and the knowledge layer. MVP languages: **Spanish, French, German**. All language behavior lives in rule packs (`config/languages/<lang>.yaml`: gendered grammar, T–V forms, readability limits), so adding a language is configuration.

| Check | Method | Example |
|-------|--------|---------|
| **Names & terms** | Deterministic: find registry entities in the source cue; expect the approved (or observed-standard) rendering in the aligned target cue; fuzzy match for inflection; LLM only adjudicates ambiguous cases | "Wren" rendered "Reyezuelo" in E3, "Wren" elsewhere |
| **Gender & pronouns** | LLM extracts, per target cue, which referents receive grammatical gender (candidates = characters present + speaker/addressee). Deterministic comparison with registry gender | Character is "elle" in E1, "il" in E4 (French) |
| **Formality (T–V)** | LLM labels address form per cue (`T`, `V`, `none`) toward the addressee. Deterministic check of each speaker→addressee sequence against the `relationship` timeline; a switch without a relationship change, or mixing within a scene, is flagged | Returns to "usted" mid-season with no change in the relationship |
| **Translation-induced spoilers** | For cues *before* a secret's on-screen reveal (screen order), LLM compares what source and target disclose about the relevant secrets (retrieved by entity overlap, not all secrets). Includes gender-forcing of hidden identities | English "the killer" (neutral) vs Spanish "la asesina" five episodes early |
| **Timing & readability** | Deterministic per rule pack: reading speed (CPS), characters per line, lines per cue, min/max duration, min gap, overlaps, cue boundaries near shot changes | 26 CPS cue; cue ends 3 frames after a cut |
| **Sync drift** | Deterministic: regress (target start − source start) against episode time. A slope near 4.27% means 25 fps timing on 23.976 fps picture; near 0.1% means SMPTE-24 timecode confused with 23.976 media time; a constant offset means a sync offset | Spanish track timed at 25 fps runs ≈2.5 s early per minute, ≈1 min 51 s early by the end of a 45-minute episode |

**Rule pack defaults** (from the Netflix Timed Text Style Guide; stored in `config/languages/*.yaml`):

| Rule | en | es (es-419, es-ES) | fr-FR | de-DE |
|------|:-:|:-:|:-:|:-:|
| Max characters per line | 42 | 42 | 42 | 42 |
| Reading speed, adult / children (characters per second) | 20 / 17 | 17 / 13 | 17 / 13 | 17 / 13 |
| Max lines per cue | 2 | 2 | 2 | 2 |
| Min / max cue duration | 5/6 s (20 frames at 24 fps) / 7 s | same | same | same |
| Min gap between cues | 2 frames; at 24 fps, gaps of 3–11 frames are closed to 2 | same | same | same |
| Shot changes | Cues starting within ½ s after a cut start on the cut; cues ending within ½ s before a cut extend to it (keeping the 2-frame gap) | same | same | same |

Spaces and punctuation count toward reading speed. Packs resolve by language-tag fallback (`es-ES` → `es` → `_base`), so a track tagged `es` or `es-419` uses the `es` pack. The Spanish guide covers both Latin American and Castilian Spanish; `es-ES` overrides `es` only for address forms (`vosotros` is the informal plural in Spain). The guides require subtitles to match the original's register and formality rather than prescribing forms, which is why `loc.formality` checks *consistency against the relationship timeline* rather than correctness. Netflix's own delivery format is TTML; SRT and WebVTT are accepted for corpus material and older assets.

**Out of MVP:** dubbed-audio checks (transcribe dub tracks, run the same checks), non-Latin scripts, SDH/closed-caption rules, forced narratives.

---

### Agent 2: Clearance Scanner

Finds items that need legal clearance and reports them in a form an errors-and-omissions (E&O) reviewer can act on.

| Channel | Method | Finds |
|---------|--------|-------|
| **On-screen text** | OCR on keyframes → deterministic parsers | Phone numbers that look real. Only fiction-reserved ranges pass (per-country config; NANP: 555-0100–0199 — other 555 numbers returned to general use in 2016). URLs and emails (RFC 2606 reserved domains such as `example.com` pass), street addresses, license plates, brand names |
| **Logos & artwork** | Open-vocabulary detector proposes regions (`logo`, `sign`, `poster`, `screen`, `packaging`, `artwork`); only frames with candidates go to the vision model, which names the item and returns its box | Brand logos, product packaging, posters, artworks, screens showing real content |
| **Dialogue & subtitles** | Zero-shot NER + LLM on source dialogue and subtitles; entities not in the bible's fictional registry are candidates | Real people, companies, products, places referenced by name |

**Matching.** Each detection is normalized (case, punctuation, known variants) and matched against the clearance registry:

| Registry status | Report treatment |
|-----------------|------------------|
| Fictional (bible) | Dropped (not a clearance item) |
| Cleared | Hidden from the report; kept in the audit trail |
| Pending / denied | Flag, high severity — **always shown regardless of confidence** |
| Unknown (not in log) | Flag, severity by prominence |

**Occurrences.** Detections of the same item in consecutive shots of a scene (gap ≤ 2 s, configurable) are merged into one occurrence with a frame range, total screen time, and a prominence score (box area, centrality, sharpness, duration). *Featured* vs *background* prominence drives severity.

**Output:** a clearance report — one row per occurrence with thumbnail crop, SMPTE in/out, screen time, prominence, status — plus CSV export.

**Deliberately excluded:** face recognition of real people (privacy and legal risk) and music clearance (needs an audio-fingerprint reference database).

---

### Agent 3: Script Critic

Finds plot holes. Works from the script alone.

**Layer 1 — rules on timed facts (deterministic SQL):**

| Rule | Order used |
|------|-----------|
| Character references or acts on a secret before any `learns` fact for it | Story |
| Dead character acts or speaks (unless the scene is marked flashback, dream, or vision) | Story |
| Same character present in two different locations at the same `story_seq` | Story |
| Character uses a prop never obtained, or after it was destroyed/lost | Story |

**Layer 2 — retrieval + LLM:**

| Check | Method |
|-------|--------|
| **Motivation** | For each extracted `decision`, retrieve the character's prior goals, traits, relationships, and related scenes. The LLM classifies the decision as `supported`, `unsupported`, or `contradicted`, citing evidence. `contradicted` → flag; `unsupported` → low-confidence flag. |
| **Unresolved setups** | Setups (object, threat, promise, open question) are tracked as facts; each scene's processing receives the open setups related to its entities and may record payoffs. Setups still open at the season finale → flag. If the finale isn't in the provided material, flags say "open at end of provided episodes" at reduced severity. |

Every Layer 2 flag must cite at least two pieces of evidence (the setup and the contradiction, or the setup and the missing payoff).

**Out of MVP:** belief–desire–intention (BDI) simulation of each character.

---

### Agent 4: Continuity Inspector

**Text rules (deterministic, by story day):**

- Wardrobe stated in the script/bible persists within a story day; a change between days is normal.
- An injury persists through the story day it occurs in, unless treated or covered on-page.
- Prop state carries across `CONTINUOUS` scenes.

**Visual (picture required):**

1. **Group shots by camera setup.** Within each scene, cluster keyframes by image embedding similarity. Shots from the same setup (the return to the wide, each side of a shot/reverse-shot) look alike by design.
2. **Compare within a setup, not across cuts.** Adjacent shots are *supposed* to differ (wide → close-up), so comparing them flags every cut. Comparing shots of the *same* setup isolates real anomalies: glass level, prop position, hair, collar, blood.
3. **Pre-filter.** For each same-setup pair, compute an anomaly score (pair distance relative to that setup's typical variation, plus region-level differences on detected people/objects). Only pairs above threshold go to the vision model.
4. **Vision-model verification.** The model sees both keyframes and returns a structured list of discrepancies (`subject`, `attribute`, `before`, `after`, box) and is instructed to ignore framing, lens, and lighting changes.

A per-episode cap on vision-model calls (derived from the Plan's throughput) keeps cost bounded; pairs beyond the cap are reported as coverage gaps, not skipped silently.

**Out of MVP:** character-level visual tracking *across* scenes (needs reliable character identification).

---

## Stage 5: Verification

Applied in order to every flag. Each step can only drop, downgrade, or merge.

| Step | Applies to | What it does |
|------|-----------|--------------|
| 1. **Evidence resolver** | All flags | Every cited object must exist; quotes must match the stored text; timecodes must fall inside the episode. Failure → drop (logged with reason). |
| 2. **Rule re-check** | Rule-originated flags | Re-runs the originating query against the *current* facts, so stale cached results can't pass. |
| 3. **LLM judge** | Flags from LLM or vision-model checks | Sees only the claim and the resolved evidence (text, crops) — never the agent's reasoning. Returns `supported` / `not_supported` / `uncertain` with a confidence. `not_supported` → drop; `uncertain` → downgrade. |
| 4. **Routing & dedup** | All surviving flags | Assigns a review tier; merges duplicate findings from different agents into one flag with all sources. |

**Judge independence.** When the Plan has room, the judge is a model from a *different family* than the agents' model, reducing correlated errors. On small hardware it is the same model with a fresh context and a judge-specific prompt; the report states which configuration was used.

**Review tiers:**

| Confidence | Tier | Shown by default |
|-----------|------|------------------|
| ≥ 0.90 | `must_review` | Yes |
| 0.70 – 0.90 | `review_recommended` | Yes |
| < 0.70 | `suppressed` | No (visible with a filter) |
| Clearance item with status pending/denied | `must_review` | Always |

---

## Stage 6: Review

### Report order

Ordered by consequence, then severity, then confidence:

1. **Clearance** — legal exposure; can block release.
2. **Continuity** — hard violations first.
3. **Localization** — wrong names, spoilers, then readability.
4. **Plot holes** — high to low confidence.

### Actions

| Action | Effect |
|--------|--------|
| **Accept** | The issue is real and will be fixed outside NIP. Logged. |
| **Fix & Re-run** | Upload a new version (script draft, subtitle track, cut). Only affected work re-runs (see below). The flag is marked resolved if it no longer reproduces. |
| **Override** | "Intentional — dream sequence." A note is required; the override is stored and annotates the relevant facts so the same finding isn't raised again. |
| **Correct fact** | Fix an extraction error in the knowledge layer. Flags that cited the fact are re-evaluated. |

Clearance flags can only be dispositioned by users with the `legal` role. Every action, AI output, and system decision is written to the audit trail. Roles and endpoints: [API Contracts](api-contracts.md).

---

## Incremental Re-runs

Every work unit's output is cached under a key derived from **what the unit actually read**:

```
cache_key = sha256(stage, stage_version, model_variant, prompt_version, params,
                   hashes of the exact inputs consumed)
```

For retrieval-based checks, the unit first runs its (cheap, deterministic) retrieval, hashes the retrieved facts and scenes, and only then looks up the cache for the expensive model call. Consequences:

- Edit scene 5 → scene 5 re-extracts; only checks that *read* scene 5's facts re-run.
- Replace the Spanish track → only Spanish localization units re-run.
- Swap a model in the catalog → only units that used that slot re-run.

Each run produces a diff against the previous run of the same episode: new flags, resolved flags, unchanged flags.

---

## Failure Handling

| Failure | Handling |
|---------|----------|
| Work unit throws | Retry up to 3 times with backoff; then mark failed and record a **coverage gap** (shown in the report: "shots 112–118 not analyzed: GPU out of memory"). |
| GPU out of memory | Retry with smaller batch/context; if it persists, the planner downgrades that slot to the next smaller variant for the rest of the run and records a Plan amendment. |
| Model server crash | Ray restarts the replica; in-flight units are retried. |
| Invalid structured output | Constrained decoding against the JSON schema; on validation failure, one repair attempt; then unit failure. |
| Bad input | Rejected at ingest with a precise error before any GPU time is spent. |

Each agent reports coverage (`units_total`, `units_done`, `units_failed`), and the report header shows coverage per agent. A run with gaps is marked `completed_with_gaps`, never `completed`.

---

## MVP Scope Summary

| Area | In MVP | Post-MVP |
|------|--------|----------|
| Localization | Subtitles in es/fr/de; names/terms, gender, T–V, translation spoilers, timing, drift | Dubbed audio, non-Latin scripts, SDH rules |
| Clearance | OCR text, logos/artwork, dialogue references, clearance-log matching, occurrences, CSV report | Face recognition (excluded by design), music clearance |
| Script Critic | Layer 1 rules, Layer 2 motivation + unresolved setups | BDI simulation |
| Continuity | Story-day text rules, same-setup visual comparison | Cross-scene character tracking |
| Platform | Hardware-adaptive runtime, incremental re-runs, verification, review UI, benchmark | IMF ingest, fine-tuned models |
