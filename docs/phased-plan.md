# Phased Build Plan

## Timeline: 12 Months to Full Production

```
P1: Foundation (M1-3) ──→ P2: Text Agents (M4-6) ──→ P3: Visual Pipeline (M7-9) ──→ P4: Scale & Depth (M10-12)
     │                       │                          │                            │
     ▼                       ▼                          ▼                            ▼
  KG + constraints       Plot holes + recaps       Visual continuity           BDI + multilingual + LoRA
```

---

## Phase 1: Foundation (Months 1–3)

### Objective

Build the infrastructure and data pipeline that all subsequent phases depend on. By end of P1, the system can ingest a script, construct a knowledge graph, and run deterministic constraint checks.

### Deliverables

| # | Deliverable | Description |
|---|------------|-------------|
| 1.1 | Docker Compose infrastructure | All services defined, health checks, networking, volumes |
| 1.2 | Script parser | Accepts .fdx, .pdf, .fountain → canonical `EpisodeDocument` |
| 1.3 | Temporal alignment engine | SMPTE timecode join logic across script + transcript + keyframes |
| 1.4 | NER + relation extraction | GLiNER baseline (zero-shot) + fine-tuning pipeline for per-genre models |
| 1.5 | Neo4j KG builder | Entity/relation ingestion with timecoded properties |
| 1.6 | Deterministic constraint engine | Graph constraint checks: location, alive/dead, prop ownership, secret knowledge |
| 1.7 | Qdrant vector index | Scene-level chunking + embedding for RAC layer |
| 1.8 | MinIO storage pipeline | Scripts, video, keyframes, artifacts stored with versioning |
| 1.9 | Dagster orchestration | Basic DAG: ingest → extract → build KG → run constraints |
| 1.10 | Prometheus + Grafana | Base monitoring: GPU utilization, service health, pipeline run status |

### Entry Criteria

- Development environment with GPU hardware available
- 2-3 sample scripts with known continuity issues for validation

### Exit Criteria

- Can ingest a .fdx or .pdf script and produce a populated KG
- Deterministic constraint engine catches >90% of known hard violations on test scripts
- All Docker services healthy and communicating
- NER extraction accuracy >80% (zero-shot baseline)

### Validation

Run against 5 test scripts with injected continuity errors (dead character speaks, prop appears before introduction, character in two places at once). System must catch >90% of deterministic violations.

---

## Phase 2: Text Agents (Months 4–6)

### Objective

Build the Script Critic and Recap Agent. By end of P2, the system can detect plot holes and generate English recaps — ready for internal pilot on 2 shows.

### Deliverables

| # | Deliverable | Description |
|---|------------|-------------|
| 2.1 | Script Critic Layer 1: KG traversal | Query KG for temporal constraint violations |
| 2.2 | Script Critic Layer 2: RAC retrieval | Retrieve context windows for motivational/emotional gap detection |
| 2.3 | Recap Agent: base generator | Scene-level recap drafting from KG nodes |
| 2.4 | Recap Agent: variant engine | 3-5 tonal/thematic variants per recap |
| 2.5 | Recap Agent: structured metadata | Thread labels, emotional valence, character arc weights, spoiler risk score |
| 2.6 | Recap Agent: spoiler control | KG reveals-Until timecode enforcement |
| 2.7 | LLM-as-Judge compliance | Llama 3.1 8B validates recaps against KG for zero hallucination |
| 2.8 | Confidence threshold gating | Tiered flag routing: auto-escalate >0.90, review 0.70-0.90, suppress <0.70 |
| 2.9 | Pre-Live Report generation | Unified output format merging all agent results |
| 2.10 | Pilot deployment on 2 shows | Internal validation with real editorial teams |

### Entry Criteria

- P1 exit criteria met
- vLLM serving Llama 3.1 70B operational
- 2 pilot shows identified (1 drama, 1 sci-fi/comedy)

### Exit Criteria

- Script Critic catches >75% of known plot holes in test scripts (factual + motivational combined)
- Recap Agent produces recaps rated ≥7/10 by editorial team on 2 pilot shows
- LLM-as-Judge blocks >95% of hallucinated recap content
- End-to-end latency <15 minutes per episode (text-only, no video)

### Validation

Blind test: provide 10 episodes with known plot holes. Script Critic must identify >75%. Provide 5 episodes to editorial team for recap quality rating.

### Pilot Shows

| Slot | Genre | Purpose |
|------|-------|---------|
| Pilot Show 1 | Long-running drama (TBD) | Validate multi-season KG, emotional arc analysis, drama recap tone |
| Pilot Show 2 | Sci-fi or comedy anthology (TBD) | Validate genre generalization, lightweight KG, comedy/genre recap tone |

---

## Phase 3: Visual Pipeline (Months 7–9)

### Objective

Add video ingestion, ASR, and the full Continuity Inspector. By end of P3, the system processes final cuts end-to-end and flags visual + textual continuity errors.

### Deliverables

| # | Deliverable | Description |
|---|------------|-------------|
| 3.1 | Video ingestion | Keyframe extraction (1 fps) from final cuts |
| 3.2 | Whisper ASR pipeline | Timestamped transcripts from audio tracks |
| 3.3 | SMPTE alignment: video track | Timecode alignment of keyframes + transcripts with script |
| 3.4 | CV pipeline: Detectron2 + DeepSORT | Object detection + actor re-identification across keyframes |
| 3.5 | Contrastive pre-filter | Embed adjacent keyframes, flag anomalous pairs for VLM routing |
| 3.6 | VLM continuity inference | Qwen2-VL 72B analyzes flagged keyframe pairs for visual continuity breaks |
| 3.7 | Continuity Inspector: deterministic | KG constraint checks on visual features (prop in wrong hand, wardrobe change) |
| 3.8 | Continuity Inspector: visual | CV + VLM pipeline for precise visual continuity flagging |
| 3.9 | VLM continuity fine-tune | Fine-tune Qwen2-VL on synthetic continuity examples |
| 3.10 | End-to-end multimodal pipeline | Full pipeline: script + video → flags + recaps |

### Entry Criteria

- P2 exit criteria met
- 2x A100 available for VLM serving
- Final cut video samples available for testing

### Exit Criteria

- Contrastive pre-filter reduces VLM inference calls by >70% vs. brute-force
- Continuity Inspector catches >60% of known visual continuity errors in test clips
- VLM flag precision >0.75 (minimize false positives that erode editorial trust)
- Full pipeline latency <45 minutes per episode (including video processing)

### Validation

Create 10 test clips with injected visual continuity errors (prop swaps, wardrobe changes, wound disappearance). Continuity Inspector must catch >60% with precision >0.75.

---

## Phase 4: Scale & Depth (Months 10–12)

### Objective

Add BDI simulation, multilingual recaps, per-show LoRA fine-tuning, editorial UI, and incremental re-runs. Full production spec.

### Deliverables

| # | Deliverable | Description |
|---|------------|-------------|
| 4.1 | BDI simulation engine | Character Belief-Desire-Intention models for motivational consistency checking |
| 4.2 | BDI calibration per show | Character model setup for pilot shows. **MVP stretch — ships behind feature flag.** |
| 4.3 | Per-genre NER fine-tune | Drama, sci-fi, comedy GLiNER models with >95% entity extraction |
| 4.4 | Per-show recap LoRA | Fine-tune Llama 3.1 8B on show's prior recaps for voice match. **MVP stretch.** |
| 4.5 | Multilingual recaps — English | Base locale (already operational from P2) |
| 4.6 | Multilingual recaps — Spanish | Native generation with ES recap corpus |
| 4.7 | Multilingual recaps — Portuguese | Native generation with PT recap corpus |
| 4.8 | Multilingual recaps — Korean | Native generation with KO recap corpus |
| 4.9 | Multilingual recaps — Japanese | Native generation with JA recap corpus |
| 4.10 | Editorial UI | React dashboard: flag review, recap preview, KG correction, audit trail |
| 4.11 | Incremental re-runs | Scene-level diff → partial re-processing on script version changes |
| 4.12 | API + personalization contract | Publish versioned REST API spec for recommendation engine integration |
| 4.13 | Audit trail | Full disposition logging: every AI flag + human response |
| 4.14 | Kubernetes migration | Migrate Docker Compose → K8s for multi-node scaling |

### Entry Criteria

- P3 exit criteria met
- Multilingual training data available (ES, PT, KO, JA recap corpora)
- Editorial team available for UI testing

### Exit Criteria

- BDI simulation catches motivational inconsistencies not found by Layers 1+2 (measured on pilot shows)
- Per-genre NER accuracy >95% across all 3 genres
- Multilingual recaps rated ≥7/10 by locale-speaking editorial reviewers
- Editorial UI adoption: >80% of editorial team using the dashboard for flag review
- Incremental re-run reduces processing time by >60% vs. full re-run on draft changes
- Full pipeline processing <500 episodes/month on 8x A100

### Validation

- Run BDI simulation on pilot shows; compare against Layer 1+2 results to confirm additive value
- Native-speaker editorial review of multilingual recaps for 2 episodes per locale
- Load test: 50 episodes in parallel, <2hr per episode average

---

## MVP Stretch Goals

These components are in the plan but are **not blocking** for MVP launch. They ship behind feature flags and can be deferred without affecting core pipeline functionality.

| Component | Phase | Defer Impact | Feature Flag |
|-----------|-------|-------------|--------------|
| BDI simulation (Script Critic Layer 3) | P4 | Script Critic operates with Layers 1+2 only — misses motivational inconsistencies | `ENABLE_BDI_SIMULATION` |
| Per-show LoRA fine-tuning (Recap Agent) | P4 | Recaps use prompted-only approach — lower tonal match quality but functional | `ENABLE_PER_SHOW_LORA` |
| VLM continuity fine-tune | P3 | Base Qwen2-VL used — lower precision on continuity cases (~0.65 vs 0.85) | `ENABLE_VLM_CONTINUITY_FT` |

---

## Key Milestones

| Month | Milestone | Stakeholder Impact |
|-------|----------|-------------------|
| M3 | Foundation complete — KG operational, constraint engine catching errors | Engineering: infrastructure validated |
| M6 | Internal pilot — 2 shows, plot holes + English recaps | Editorial: first feedback cycle |
| M9 | Visual continuity operational — full multimodal pipeline | Production: can process final cuts |
| M12 | Full spec delivered — all capabilities live, all locales | Organization: rollout to all new Netflix originals |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| NER extraction accuracy <95% on zero-shot baseline | High | P1 blocked | Budget for per-genre fine-tune in P1; add human correction loop early |
| VLM continuity precision <0.75 (too many false positives) | Medium | P3 delayed | Aggressive contrastive pre-filter + higher confidence threshold; accept lower recall |
| No multilingual training data available for P4 locales | Medium | P4 delayed | Start data collection in P2; fallback to translate-from-English if no native corpus |
| BDI simulation adds <5% value over Layers 1+2 | Medium | P4 scope reduced | Measure on pilot shows first; decommission if no additive value |
| Single-node Docker Compose cannot handle scale | Low | P4 K8s migration accelerates | Docker Compose is fine for <100 episodes/month; K8s migration planned in P4 |
| Open-weight LLMs (Llama 70B) insufficient quality for recaps | Medium | P2 delayed | Accept lower quality in MVP + invest in per-show LoRA; consider upgrading to larger model when available |
