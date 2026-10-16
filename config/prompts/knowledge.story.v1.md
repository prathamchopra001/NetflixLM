You order the scenes of a screenplay in story time. Two consecutive scenes of the main storyline are
given. The rules could not tell from the headings how the second scene relates to the first: its
time of day is earlier than the first scene's, and nothing in its heading or transitions says why.

Decide how the SECOND scene relates to the FIRST in story time. Answer with exactly one relation:

- `next_day`: it takes place on the following day (the usual reason a time of day "goes backwards").
- `same_day`: it takes place on the same day as the first scene (the heading's time of day is loose).
- `later_days`: it takes place several days later; put the number of days in `days` (at least 2).
- `earlier`: it takes place before the first scene (an unmarked flashback); put how many days
  earlier in `days` (at least 1; use 365 per year if only years are clear).
- `simultaneous`: it takes place at the same time as the first scene (an unmarked intercut).

Use only what the two scenes show: continuing action, characters mid-conversation, props, remarks
like "yesterday", "tonight", "this morning". When nothing contradicts it, prefer `next_day`.
Keep `reason` to one short sentence.

$transition

FIRST scene (story day $prev_day, time of day $prev_tod):
$prev_scene

SECOND scene:
$next_scene

The scene after the second one begins: $following
