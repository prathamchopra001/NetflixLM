-- plot.two_places (story order): the same character is `present_at` two different locations at
-- the same story moment (overlapping story ranges), except in flashback, dream or vision scenes.
-- Parameters: :show (show slug), :episode (only claims in it are returned).
-- Pair orientation: b is the later scene in screen order (episode, scene); the claim is b's first
-- line, other_* is a (the earlier presence), so each pair is reported once, in b's episode.
WITH ev AS (
  SELECT DISTINCT ON (f.id)
         f.id AS fact_id, e.quote, e.confidence AS event_conf, l.seq AS line_seq,
         s.script_scene_no AS scene_no, s.id AS scene_id, s.story_inferred, s.markers,
         ep.ref AS episode, ep.episode_seq
  FROM fact f
  JOIN fact_event e ON e.id = ANY(f.source_event_ids)
  JOIN script_line l ON l.id = e.line_id
  JOIN scene s ON s.id = e.scene_id
  JOIN episode ep ON ep.id = s.episode_id
  WHERE f.show_id = (SELECT id FROM show WHERE slug = :show) AND f.status = 'active'
    AND f.predicate = 'present_at'
  ORDER BY f.id, s.story_seq, ep.episode_seq, s.id, l.seq
)
SELECT b.id AS claim_fact, eb.episode, eb.scene_no, eb.line_seq, eb.quote AS claim_quote,
       a.id AS other_fact, ea.episode AS other_episode, ea.scene_no AS other_scene_no,
       subj.canonical_name AS subject, lb.canonical_name AS object,
       la.canonical_name AS other_object, NULL AS detail,
       (ea.story_inferred OR eb.story_inferred) AS inferred,
       LEAST(ea.event_conf, eb.event_conf) AS confidence
FROM fact a
JOIN fact b ON b.show_id = a.show_id AND b.subject_id = a.subject_id
           AND b.predicate = 'present_at' AND b.status = 'active'
           AND b.object_id <> a.object_id AND b.story && a.story
JOIN ev ea ON ea.fact_id = a.id
JOIN ev eb ON eb.fact_id = b.id
JOIN entity subj ON subj.id = a.subject_id
JOIN entity la ON la.id = a.object_id
JOIN entity lb ON lb.id = b.object_id
WHERE a.show_id = (SELECT id FROM show WHERE slug = :show)
  AND a.predicate = 'present_at' AND a.status = 'active'
  AND (ea.episode_seq, ea.scene_id) < (eb.episode_seq, eb.scene_id)
  AND NOT (ea.markers && ARRAY['flashback', 'dream', 'vision'])
  AND NOT (eb.markers && ARRAY['flashback', 'dream', 'vision'])
  AND eb.episode = :episode
ORDER BY eb.scene_no, eb.line_seq, a.id, b.id;
