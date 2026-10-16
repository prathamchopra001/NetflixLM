-- plot.dead_acts (story order): a character is present or speaks in a scene whose story_seq is
-- after their death (`state` fact with value.state = 'dead'), unless that scene is a flashback,
-- dream or vision. Parameters: :show (show slug), :episode (only claims in it are returned).
-- Acts = scenes of the character's `present_at` facts, and lines they speak (script_line speaker).
-- Confidence: raw event confidences, the story-inferred reduction is the loader's.
-- One row per acting line. The claim is that line; other_* is the (earliest) death fact.
WITH ev AS (
  SELECT DISTINCT ON (f.id)
         f.id AS fact_id, e.quote, e.confidence AS event_conf, l.seq AS line_seq,
         s.script_scene_no AS scene_no, s.story_inferred, ep.ref AS episode
  FROM fact f
  JOIN fact_event e ON e.id = ANY(f.source_event_ids)
  JOIN script_line l ON l.id = e.line_id
  JOIN scene s ON s.id = e.scene_id
  JOIN episode ep ON ep.id = s.episode_id
  WHERE f.show_id = (SELECT id FROM show WHERE slug = :show) AND f.status = 'active'
  ORDER BY f.id, s.story_seq, ep.episode_seq, s.id, l.seq
),
dead AS (
  SELECT DISTINCT ON (d.subject_id) d.subject_id, d.id AS fact_id, lower(d.story) AS story_seq
  FROM fact d
  WHERE d.show_id = (SELECT id FROM show WHERE slug = :show) AND d.status = 'active'
    AND d.predicate = 'state' AND d.value ->> 'state' = 'dead'
  ORDER BY d.subject_id, lower(d.story), d.id
),
acts AS (
  SELECT f.subject_id, f.id AS fact_id, e.confidence, e.quote, e.line_id, l.seq AS line_seq,
         s.script_scene_no AS scene_no, s.story_seq, s.story_inferred, s.markers, ep.ref AS episode
  FROM fact f
  JOIN fact_event e ON e.id = ANY(f.source_event_ids)
  JOIN script_line l ON l.id = e.line_id
  JOIN scene s ON s.id = e.scene_id
  JOIN episode ep ON ep.id = s.episode_id
  WHERE f.show_id = (SELECT id FROM show WHERE slug = :show) AND f.status = 'active'
    AND f.predicate = 'present_at'
  UNION ALL
  SELECT l.speaker_entity_id, NULL, 1.0, l.text, l.id, l.seq,
         s.script_scene_no, s.story_seq, s.story_inferred, s.markers, ep.ref
  FROM script_line l
  JOIN scene s ON s.id = l.scene_id
  JOIN episode ep ON ep.id = s.episode_id
  JOIN show sh ON sh.id = ep.show_id
  WHERE sh.slug = :show AND l.speaker_entity_id IS NOT NULL
),
one AS (  -- a spoken line that also has a present_at fact is reported once, with the fact
  SELECT DISTINCT ON (line_id, subject_id) * FROM acts
  ORDER BY line_id, subject_id, fact_id NULLS LAST
)
SELECT a.fact_id AS claim_fact, a.episode, a.scene_no, a.line_seq, a.quote AS claim_quote,
       d.fact_id AS other_fact, od.episode AS other_episode, od.scene_no AS other_scene_no,
       subj.canonical_name AS subject, NULL AS object, NULL AS other_object, NULL AS detail,
       (a.story_inferred OR COALESCE(od.story_inferred, false)) AS inferred,
       LEAST(COALESCE(a.confidence, 1), COALESCE(od.event_conf, 1)) AS confidence
FROM one a
JOIN dead d ON d.subject_id = a.subject_id
JOIN entity subj ON subj.id = a.subject_id
LEFT JOIN ev od ON od.fact_id = d.fact_id
WHERE a.story_seq > d.story_seq
  AND NOT (a.markers && ARRAY['flashback', 'dream', 'vision'])
  AND a.episode = :episode
ORDER BY a.scene_no, a.line_seq, a.subject_id;
