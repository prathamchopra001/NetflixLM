You order the scenes of a screenplay in story time. Two consecutive scenes of the main storyline are
given. The second scene's heading has an EARLIER time of day than the first scene's (for example
NIGHT, then MORNING), and nothing in its heading or transitions says why.

A time of day that goes backwards is NORMAL: it almost always means the story moved on to the next
day. It does NOT mean the second scene happens earlier in the story.

Answer with exactly one relation. Check them in this order and stop at the first that fits:

1. `earlier`: ONLY when the text of the second scene itself says it takes place in the past, for
   example "eight years ago", "back then", "when we were young", "a decade before". A heading with an
   earlier time of day is not enough. Put how many days earlier in `days` (365 per year).
2. `simultaneous`: ONLY when the text of the second scene itself says it happens at the same moment
   as the first scene, somewhere else ("at the same moment", "meanwhile", "across town, right now").
3. `later_days`: ONLY when the second scene says several days have passed ("three days later",
   "a week after"); put the number of days in `days` (at least 2).
4. `same_day`: the second scene clearly continues the first scene's day (the same conversation, "a
   moment later", "that evening").
5. `next_day`: everything else. This is the default and by far the most common answer.

Keep `reason` to one short sentence.

$transition

FIRST scene (story day $prev_day, time of day $prev_tod):
$prev_scene

SECOND scene:
$next_scene

The scene after the second one begins: $following
