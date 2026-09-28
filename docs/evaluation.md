# Evaluation

## Purpose

Every check is measured against **known, planted errors** in legally usable content. The benchmark answers three questions:

1. **Does each check work?** Precision, recall, and F1 per check ID.
2. **What does each hardware Plan deliver?** The same benchmark runs on every Plan (laptop, workstation, cloud), so quality and cost differences are measured, not assumed.
3. **Did a change make things worse?** The benchmark is the regression gate for prompts, models, and code.

---

## Corpus

All titles are recorded in `eval/corpus/manifest.yaml` with license, attribution, source URL, and checksum. **Media is never committed to the repository.** Public-domain status below is **US-only**; verify for other jurisdictions before use there.

### Open films (Blender Studio)

| Title | License | Runtime | Dialogue | Script | Official subtitles | Primary use |
|-------|---------|---------|----------|--------|--------------------|-------------|
| **Sintel** (2010) | CC BY 3.0 | 14:48 | Some (English) | Free (CC BY) | 40 languages incl. es/fr/de | Localization (all checks), clearance and continuity injection, smoke set |
| **Tears of Steel** (2012) | CC BY 3.0 | 12:14 | Yes (English) | Subscribers only | en, es, fr, de, nl, it, ru, no | Live action: clearance (signs, screens), visual continuity, localization. *The French file's quality is unverified — review before use.* |
| **Cosmos Laundromat** (2015) | CC BY 3.0 | 12:10 | Yes (English) | Subscribers only | None official | Script Critic, continuity; target tracks generated (see below) |
| **Sprite Fright** (2021) | CC BY 4.0 | 10:30 | Yes (English) | — | None official | Dialogue references, localization with generated tracks |
| **Elephants Dream** (2006) | CC BY 2.5 (soundtrack BY-NC-ND 2.5) | 10:53 | Yes (English) | — | Volunteer only | Visual continuity only; **never redistribute derivatives with its soundtrack** |
| Spring, Charge, Singularity | CC BY 4.0 | 4–8 min | None | — | — | Visual-only negatives (no dialogue checks should activate) |

**Excluded:** *Agent 327: Operation Barbershop* — CC BY-ND 4.0 forbids sharing derivatives, and every benchmark item is a derivative.

### Episodic and feature content (public domain, US)

| Title | Why public domain | Use |
|-------|-------------------|-----|
| **The Beverly Hillbillies**, season 1 (36 episodes) | Copyright not renewed | Primary **multi-episode** set: cross-episode Script Critic, story order, continuity text rules. *The theme song is still under copyright — strip it from derived media and never publish clips containing it.* |
| **Dragnet** (1951–59), public-domain episodes | About half the episodes not renewed | Procedural structure (who learns what, when) for `plot.knowledge_order` |
| **His Girl Friday** (1940) | Copyright not renewed | Very fast dialogue — readability and alignment stress test |
| **Night of the Living Dead** (1968) | Published without a valid copyright notice | Script Critic and continuity (a 1968 shooting script exists; its copyright status is separate — internal use only) |

**Avoid:** *The Andy Griffith Show* "public-domain" episodes (a court treated them as derivatives of copyrighted episodes) and *Bonanza* unless each episode is individually verified. *Pioneer One* (CC BY-NC-SA 3.0) is non-commercial only and is excluded from the default sets.

### Derived assets

Titles without a freely available script or subtitles (the episodic and feature titles, plus Tears of Steel, Cosmos Laundromat, and Sprite Fright, whose scripts are subscriber-only or unpublished) get derived assets. The pipeline's own tools create them, **with humans correcting the parts used as ground truth**:

| Asset | How it's made |
|-------|---------------|
| As-broadcast script (Fountain) | Speech-to-text with word timestamps → scene breaks from shot detection → speaker attribution → human cleanup |
| Source subtitles | Generated from the corrected transcript following the en rule pack |
| Target subtitles (es/fr/de) where none exist | Translated locally with an open-weight model, then native-speaker spot-checked. Only cues that pass review are eligible for injection |

### Synthetic multi-episode scripts

`eval/synthetic/` generates Fountain scripts for a small fictional show (6 episodes × ~25 scenes) from a seed `bible.yaml`, using the local text model. Every planted hole is recorded at generation time. Synthetic scripts give Script Critic volume and precise control that real content can't; results are always reported **separately** from real-content results.

### Sets

| Set | Contents | Used by |
|-----|----------|---------|
| `smoke` | 2-minute Sintel excerpt with script, en + es subtitles, bible, clearance log; ~30 injected errors covering every check ID | CI nightly, `nip eval run --set smoke` |
| `mvp` | Sintel, Tears of Steel, Cosmos Laundromat, Sprite Fright, 6 Beverly Hillbillies episodes, His Girl Friday, synthetic show; injected errors per check | Weekly benchmark, phase exit criteria |
| `full` | `mvp` + all 36 Beverly Hillbillies season-1 episodes, Dragnet set, remaining films | Cloud-Plan capacity runs |

### Manifest entry

```yaml
- id: sintel
  title: Sintel
  license: CC-BY-3.0
  attribution: "© copyright Blender Foundation | durian.blender.org"
  source:
    picture: https://download.blender.org/durian/movies/  # exact file recorded with checksum
    script: https://durian.blender.org/  # script.zip (CC BY)
    subtitles:
      en: https://durian.blender.org/wp-content/content/subtitles/sintel_en.srt
      es: https://durian.blender.org/wp-content/content/subtitles/sintel_es.srt
      fr: https://durian.blender.org/wp-content/content/subtitles/sintel_fr.srt
      de: https://durian.blender.org/wp-content/content/subtitles/sintel_de.srt
  sha256: {picture: "…", script: "…", en: "…", es: "…", fr: "…", de: "…"}
  restrictions: []
```

---

## Injectors

Injectors take an original title and a seed and produce (a) a modified copy and (b) ground-truth labels. They are deterministic for a given seed. Items marked *(reviewed)* are LLM-assisted rewrites and 10% are spot-checked by a native speaker before a set is frozen.

### Localization

| Check | Injection |
|-------|-----------|
| `loc.term` | Replace the approved rendering of a glossary term or name in *k* cues with a plausible variant (translated, transliterated, misspelled) |
| `loc.gender` | Flip gender agreement for one referent: pronouns, articles, adjective/participle endings, French feminine job titles *(reviewed)* |
| `loc.formality` | Switch address form in one cue or a run of cues: tú↔usted (and vosotros↔ustedes for es-ES), tu↔vous, du↔Sie, with conjugation *(reviewed)* |
| `loc.spoiler` | Before a secret's reveal, replace a neutral referent with an identity- or gender-revealing one ("the informant" → "Ada"; "the killer" → "la asesina") *(reviewed)* |
| `loc.readability` | Push cues past the rule pack: characters per line, lines per cue, reading speed, min/max duration, 2-frame minimum gap |
| `loc.shot_change` | Move cue in/out points to 1–11 frames from a shot change |
| `loc.drift` | Rescale all target cue times by 25025/24000 (25 fps timing on 23.976 picture: 4.27%, ≈1 min 51 s early after 45 min) or by 1001/1000 (SMPTE-24 vs 23.976 media-time confusion: 0.1%, ≈2.7 s over 45 min) |
| `loc.offset` | Shift all target cues by a constant (e.g. +12 frames, −1 s) |

### Clearance

| Check | Injection |
|-------|-----------|
| `clr.phone` | Render numbers onto planar surfaces (signs, paper, screens) in low-motion shots. **Positives** use NANP area codes reserved for future expansion, so the numbers are real-format but can never reach a real subscriber, plus 555 numbers *outside* 0100–0199 (returned to general use in 2016). **Negatives** use 555-0100–0199, which must not be flagged |
| `clr.url`, `clr.email` | Render made-up domains; RFC 2606 reserved domains (`example.com`, `.test`, `.invalid`) are negatives |
| `clr.address`, `clr.plate` | Render street addresses and license plates in regional formats |
| `clr.brand_text`, `clr.logo` | Composite brand names and logos onto surfaces: generated fictional marks (some declared in the bible as fictional = negatives, some not = positives) and a small **private** set of real marks that is never published |
| `clr.artwork` | Composite public-domain artworks as posters or paintings |
| `clr.dialogue_ref` | Insert real organization and person names from a curated list into dialogue and subtitle text |

The clearance log for each injected title marks a mix of injected items as `cleared`, `pending`, and `denied`, so matching and routing are tested too (cleared items must be hidden; pending/denied must always be shown).

### Script Critic

| Check | Injection |
|-------|-----------|
| `plot.knowledge_order` | Move a reference to a secret before the scene where the character learns it (or move the learning scene later) |
| `plot.dead_acts` | Give a character a line or action after their death scene (outside flashback/dream scenes) |
| `plot.two_places` | Add a character to two simultaneous (`INTERCUT` / same story moment) scenes at different locations |
| `plot.prop_provenance` | Have a character use a prop before obtaining it, or after it was destroyed |
| `plot.motivation` | Insert a decision that contradicts established goals or traits *(reviewed)* |
| `plot.unresolved_setup` | Delete the payoff of an established setup |

### Continuity

| Check | Injection |
|-------|-----------|
| `cont.visual` | In one shot of a same-setup pair: recolor a garment region (SAM 2 mask + hue shift), remove a small prop (inpainting), or add one (compositing) |
| `cont.wardrobe_text`, `cont.injury_text`, `cont.prop_text` | Edit the script so wardrobe, injury, or prop state contradicts itself within a story day |

### Label format

One JSON object per planted error in `eval/labels/<set>/<title>.jsonl`:

```json
{"label_id": "sintel-es-0042", "title": "sintel", "episode": "S01E01",
 "check": "loc.gender", "lang": "es",
 "target": {"kind": "subtitle_cue", "refs": ["S01E01/es/88"], "frames": [15840, 15912]},
 "description": "Referent 'Sintel' changed to masculine agreement ('cansado')",
 "injector": "loc.gender.v2", "seed": 7, "reviewed": true}
```

Script-level labels use scene/line refs instead of frames.

---

## Scoring

### Matching flags to labels

A flag matches a label when **all** hold:

- Same `check` ID (a small equivalence map allows e.g. `cont.prop_text` to match a `plot.prop_provenance` label when both describe the same line);
- Same `lang` where applicable;
- Evidence overlaps the label target: temporal IoU ≥ 0.3 for timed targets, or a shared scene/line ref for script targets.

Matching is one-to-one (highest confidence first). Then:

- **True positive:** matched flag.
- **False negative:** unmatched label.
- **False positive:** unmatched flag, *unless* it matches a **native label** — a genuine error already present in the original content, found during clean-run triage. Native labels count as true positives.

### Metrics

| Metric | Granularity |
|--------|-------------|
| Precision, recall, F1 | Per check ID, per language, per Plan; computed on *shown* flags (`must_review` + `review_recommended`) and separately on all flags |
| Verification effect | Share of false positives dropped by verification vs share of true positives wrongly dropped |
| Noise | Shown false positives per hour of content, per agent (clean runs) |
| Cost | GPU-seconds and wall time per content-hour, per agent and per slot; vision-model calls per episode; cache hit rate on re-runs |
| Coverage | Share of work units completed; every gap listed |

### Clean-run triage

Every benchmark title is also run **un-injected**. Each shown flag is triaged by a person as either a false positive or a genuine native error (added to `eval/labels/<set>/<title>.native.jsonl`). The false positives give the realistic noise rate; the native errors keep real mistakes in the originals from being scored as false positives later.

---

## MVP Targets

Targets apply to the **reference cloud Plan** (8× 80 GB, `quality` objective) on the `mvp` set. The laptop Plan is always reported alongside; it is expected to score lower and is not held to these numbers.

| Check(s) | Recall ≥ | Precision ≥ | Bound by |
|----------|:-:|:-:|---------|
| `loc.readability`, `loc.shot_change`, `loc.drift`, `loc.offset` | 0.98 | 0.98 | Pure rules |
| `loc.term` | 0.90 | 0.85 | Alignment quality |
| `loc.gender`, `loc.formality` | 0.70 | 0.80 | LLM labeling |
| `loc.spoiler` | 0.60 | 0.80 | LLM comparison |
| `clr.phone`, `clr.url`, `clr.email`, `clr.address`, `clr.plate`, `clr.brand_text` | 0.85 | 0.85 | OCR recall |
| `clr.logo`, `clr.artwork` | 0.60 | 0.75 | Detector + vision model |
| `clr.dialogue_ref` | 0.80 | 0.75 | NER + LLM |
| `plot.knowledge_order`, `plot.dead_acts`, `plot.two_places`, `plot.prop_provenance` | 0.80 | 0.85 | Fact extraction |
| `plot.motivation`, `plot.unresolved_setup` | 0.50 | 0.70 | LLM reasoning |
| `cont.wardrobe_text`, `cont.injury_text`, `cont.prop_text` | 0.75 | 0.80 | Fact extraction + story days |
| `cont.visual` | 0.50 | 0.70 | Pre-filter + vision model |

**System-level targets**

| Target | Value |
|--------|-------|
| Clearance items with status `pending`/`denied` that were detected but not shown | 0 (routing must never hide them) |
| Shown false positives on clean runs | ≤ 10 per content-hour across all agents |
| Verification | Drops ≥ 50% of false positives while dropping ≤ 5% of true positives |
| Throughput (reference cloud node, `throughput` objective) | A 45-minute episode with 3 target languages completes in ≤ 30 minutes wall time |
| Throughput (`quality` objective, laptop) | Reported, no target — the `quality` objective favors the largest models over speed, and the laptop is for development and small runs |

---

## Per-Plan Report

`nip eval run` writes `eval/<benchmark_run_id>/report.md` and `report.json`:

```
Benchmark mvp · commit 3f9c2e1 · 2026-11-20
                                  laptop (1× 8 GB)       cloud (8× 80 GB)        cloud (8× 80 GB)
Objective                         quality                quality                 throughput
Mode                              staged, 5 groups       staged, 2 groups        resident, 9 replicas
text_llm + vlm                    qwen3.5-4b-awq         qwen3.5-397b-a17b-fp8   qwen3.5-122b-a10b-int4
Judge                             ministral-3-3b-fp8     gemma-4-31b-qat         gemma-4-31b-qat
loc.gender      P / R / F1        0.74 / 0.58 / 0.65     0.86 / 0.77 / 0.81      0.84 / 0.75 / 0.79
cont.visual     P / R / F1        0.61 / 0.34 / 0.44     0.78 / 0.57 / 0.66      0.76 / 0.55 / 0.64
…
GPU-s per content-hour            41,200                 30,500                  18,900
Wall time per 45-min episode      5 h 10 min             41 min                  24 min
```

*(Numbers above illustrate the format only.)*

---

## Regression Gate

| Trigger | Gate |
|---------|------|
| Every pull request | Unit, contract, and CPU-profile integration tests must pass |
| Nightly (GPU runner) | `smoke` benchmark on the runner's Plan; alert if any check's F1 drops more than 0.03 below the stored baseline for that Plan |
| Change to a prompt, a catalog variant, or a rule pack | `mvp` benchmark for the affected check IDs; merge blocked if F1 drops more than 0.03, or if any check falls below its MVP precision target |
| Weekly | Full `mvp` benchmark on the laptop Plan; from week 7 also on the cloud Plan |

Baselines are stored per Plan fingerprint (catalog hash + chosen variants), because a laptop baseline says nothing about a cloud run.

---

## Test Strategy

| Layer | What | Where it runs |
|-------|------|---------------|
| Unit | Timecode math (property-based: frame↔SMPTE round-trips, drop-frame, ms↔frame), parsers, planner (simulated inventories → expected Plans), SQL rules on fixture fact sets, cache keys, evidence resolver, matching logic | CI, no GPU |
| Contract | Each model client against recorded request/response pairs, including malformed outputs and timeouts | CI, no GPU |
| Integration | The fixture episode through the whole pipeline with `NIP_PROFILE=cpu` (stub models return recorded outputs) | CI |
| Integration (GPU) | Same fixture with real models on the runner's Plan | Nightly |
| Benchmark | `smoke` nightly, `mvp` weekly and on gated changes | GPU runner / cloud |
