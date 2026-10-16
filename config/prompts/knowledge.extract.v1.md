You extract story facts from one scene of a screenplay. Read the scene and list every event it
states. Use only what the scene text says: do not guess, do not use outside knowledge, do not
repeat facts from other scenes.

Each event has:
- `line`: the number in brackets of the line that states it.
- `quote`: the exact words from that line that state it, copied character for character (a short
  span is best, never words from another line).
- `predicate`: one of
  - `present_at`: a character is at a place in this scene. Subject = character, object = place.
  - `holds`: a character picks up, carries, uses or checks an object. Subject = character,
    object = the object, value = `obtain`, `use`, `give` or `lose`.
  - `owns`: a character owns an object. Value as for `holds`.
  - `state`: a character or object changes condition. Subject = it, value = the new state:
    `dead`, `destroyed`, `lost`, `injured: <detail>`, `healed`, or another short word.
  - `wearing`: a character wears a garment the text names. Subject = character, object = garment.
  - `learns`: a character learns a secret (hears or discovers it). Subject = character,
    object = the secret.
  - `references`: a character speaks about a secret they already know. Subject = character,
    object = the secret.
  - `relationship`: how two characters relate. Subject and object = characters, value = the
    relationship (`strangers`, `colleagues`, `partners`, `family`, `enemies`, ...).
  - `setup`: an object is shown so that it can matter later. Subject = the object,
    value = importance 1-3.
  - `payoff`: an object that was set up earlier is used decisively. Subject = the object,
    object = the character who uses it.
  - `decision`: a character decides to do something. Subject = character, value = what.
  - `mentions`: a line names an organization, brand or product. Subject = the speaker (or the
    character the line is about), object = the organization, brand or product.
- `confidence`: 0 to 1, how clearly the line states the event.

$ids_rule

Dialogue lines show the speaker before the colon: the speaker is the one who says the line.

Registry:
$registry

Characters in this scene:
$bible

Scene:
$scene
