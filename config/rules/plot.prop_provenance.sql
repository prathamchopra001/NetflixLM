-- plot.prop_provenance (story order): a character uses a prop before anyone holds or owns it, or
-- after it was destroyed or lost. Parameters: :show (show slug), :episode (claims in it only).
-- Works on the source events of active facts, because consolidation merges a character's `holds`
-- events of one prop into a single interval and the use would be lost in it:
--   use        = a `holds` event whose value.event is 'use'
--   possession = any other `holds` or `owns` event of that prop (no event kind means obtained)
--   gone       = a `state` event of the prop itself, value.state destroyed or lost
-- Positions are the scenes' story_seq; confidence is the raw event confidence (the story-inferred
-- reduction is the loader's). A pickup after the loss and not after the use ends the loss.
-- One row per use event (a use that is both gets before_obtained first; the loader keeps one row
-- per claim line). detail = 'before_obtained' (other_* = first later possession, if any) or
-- 'after_gone' (other_* = the destroying/losing event). The claim is the use line.
WITH evs AS (
  SELECT f.id AS fact_id, e.confidence, e.predicate, e.subject_id, e.object_id, e.value,
         e.quote, l.seq AS line_seq, s.script_scene_no AS scene_no, s.story_seq,
         s.story_inferred, ep.ref AS episode
  FROM fact f
  JOIN fact_event e ON e.id = ANY(f.source_event_ids)
  JOIN script_line l ON l.id = e.line_id
  JOIN scene s ON s.id = e.scene_id
  JOIN episode ep ON ep.id = s.episode_id
  WHERE f.show_id = (SELECT id FROM show WHERE slug = :show) AND f.status = 'active'
    AND s.story_seq IS NOT NULL
),
uses AS (
  SELECT * FROM evs
  WHERE predicate = 'holds' AND value ->> 'event' = 'use' AND object_id IS NOT NULL
),
possessions AS (
  SELECT * FROM evs
  WHERE predicate IN ('holds', 'owns') AND COALESCE(value ->> 'event', 'obtain') <> 'use'
    AND object_id IS NOT NULL
),
gone AS (
  SELECT * FROM evs WHERE predicate = 'state' AND value ->> 'state' IN ('destroyed', 'lost')
),
found AS (
  SELECT u.*, 'before_obtained' AS detail, nxt.fact_id AS other_fact,
         nxt.episode AS other_episode, nxt.scene_no AS other_scene_no,
         nxt.story_inferred AS other_inferred, nxt.confidence AS other_confidence,
         nxt.quote AS other_quote
  FROM uses u
  LEFT JOIN LATERAL (
    SELECT * FROM possessions g WHERE g.object_id = u.object_id
    ORDER BY g.story_seq, g.fact_id LIMIT 1
  ) nxt ON true
  WHERE NOT EXISTS (
    SELECT 1 FROM possessions g WHERE g.object_id = u.object_id AND g.story_seq <= u.story_seq)
  UNION ALL
  SELECT u.*, 'after_gone', d.fact_id, d.episode, d.scene_no, d.story_inferred, d.confidence,
         d.quote
  FROM uses u
  JOIN LATERAL (
    SELECT * FROM gone d WHERE d.subject_id = u.object_id AND d.story_seq < u.story_seq
    ORDER BY d.story_seq, d.fact_id LIMIT 1
  ) d ON true
  WHERE NOT EXISTS (  -- picked up again after the loss, by the time of this use
    SELECT 1 FROM possessions g
    WHERE g.object_id = u.object_id AND g.story_seq > d.story_seq AND g.story_seq <= u.story_seq)
)
SELECT u.fact_id AS claim_fact, u.episode, u.scene_no, u.line_seq, u.quote AS claim_quote,
       u.other_fact, u.other_episode, u.other_scene_no,
       subj.canonical_name AS subject, prop.canonical_name AS object, NULL AS other_object,
       u.detail, u.other_quote,
       (u.story_inferred OR COALESCE(u.other_inferred, false)) AS inferred,
       LEAST(u.confidence, COALESCE(u.other_confidence, 1)) AS confidence
FROM found u
JOIN entity subj ON subj.id = u.subject_id
JOIN entity prop ON prop.id = u.object_id
WHERE u.episode = :episode
ORDER BY u.scene_no, u.line_seq, u.fact_id, u.detail DESC;
