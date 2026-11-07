-- plot.knowledge_order (story order): a character references a secret in a scene before any
-- `learns` fact for that character and secret begins. Same story_seq counts as learned already.
-- Parameters: :show (show slug), :episode (episode ref; only claims in it are returned).
-- One row per violating `references` fact; the claim is its first source line in story order.
-- Confidence is the raw event confidence (min of the claim and the later learning); the story-
-- inferred reduction is applied by the loader, once.
-- other_* is the earliest later `learns` fact, when the character does learn it afterwards.
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
)
SELECT r.id AS claim_fact, c.episode, c.scene_no, c.line_seq, c.quote AS claim_quote,
       later.id AS other_fact, o.episode AS other_episode, o.scene_no AS other_scene_no,
       subj.canonical_name AS subject, obj.canonical_name AS object, NULL AS other_object,
       NULL AS detail,
       (c.story_inferred OR COALESCE(o.story_inferred, false)) AS inferred,
       LEAST(c.event_conf, COALESCE(o.event_conf, 1)) AS confidence
FROM fact r
JOIN ev c ON c.fact_id = r.id
JOIN entity subj ON subj.id = r.subject_id
JOIN entity obj ON obj.id = r.object_id
LEFT JOIN LATERAL (
  SELECT l.id FROM fact l
  WHERE l.show_id = r.show_id AND l.predicate = 'learns' AND l.status = 'active'
    AND l.subject_id = r.subject_id AND l.object_id = r.object_id
  ORDER BY lower(l.story), l.id LIMIT 1
) later ON true
LEFT JOIN ev o ON o.fact_id = later.id
WHERE r.show_id = (SELECT id FROM show WHERE slug = :show)
  AND r.predicate = 'references' AND r.status = 'active'
  AND NOT EXISTS (
    SELECT 1 FROM fact l
    WHERE l.show_id = r.show_id AND l.predicate = 'learns' AND l.status = 'active'
      AND l.subject_id = r.subject_id AND l.object_id = r.object_id
      AND lower(l.story) <= lower(r.story))
  AND c.episode = :episode
ORDER BY c.scene_no, c.line_seq, r.id;
