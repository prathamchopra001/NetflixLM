# Labelling shot cuts in Label Studio

A **cut** is the instant one camera shot is replaced by another. To measure how well the shot
detectors work (EXP-002) we need a list of the true cuts, made by a person. This page shows how to
make that list for *Sintel* even if you have never labelled anything before. Plan for about
45-60 minutes: Sintel has 15 clips of 60 seconds each and a few dozen cuts per clip.

All commands below are typed in a terminal in the project folder. `lbl` is shorthand for
`uv run python -m eval.labeling.labeling` (type the long form; once the integration step wires the
sub-app, the same commands are `nip eval labels ...`).

## What you will mark

For every cut, mark **the first frame of the new shot** (the first picture that no longer belongs
to the previous shot). That is all. For a dissolve/fade mark the first frame where the new shot is
clearly the main picture. Do not mark camera moves inside one shot.

In Label Studio frames are numbered **from 1**. Every clip after the first starts with the *last
frame of the previous clip* (a one-frame overlap so that a cut on a clip boundary is still
visible). **Never mark frame 1 of a clip**: it is ignored (frame 1 can never be a cut of that clip).

## One-time setup

1. **Make the clips** (cuts `data/corpus/sintel/Sintel.2010.1080p.mkv` into 15 small preview clips
   plus one check clip, all in `data/labeling/sintel/`; ~120 MB, about 1 minute):

   ```
   lbl prepare --title sintel
   ```

2. **Start Label Studio** with the `data/` folder mounted so it can serve the clips (in `cmd`;
   in PowerShell use a backtick instead of `^`; on Linux/macOS use `\` and a normal path):

   ```
   docker run -d --name ls -p 8081:8080 ^
     -e LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true ^
     -e LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files ^
     -v "D:\Projects\In Process\Netflix LM\data:/label-studio/files" ^
     -v ls-data:/label-studio/data heartexlabs/label-studio:1.23.2
   ```

   Do not run this in Git Bash: it rewrites `/label-studio/files` into a Windows path and Label
   Studio then refuses the storage. The first start takes 2-3 minutes (it builds its database).
   Open <http://localhost:8081>, click **Sign up**, make a local account (any e-mail/password; it
   only exists on your machine).

3. **Get an API token**: click your avatar (top right) -> **Account & Settings** -> **Personal
   Access Token** -> **Create**. **Copy it immediately: it is shown only once.** Put it in the
   terminal you run commands from (`cmd`: `set LABEL_STUDIO_TOKEN=...`; PowerShell:
   `$env:LABEL_STUDIO_TOKEN="..."`).

4. **Create the project**:

   ```
   lbl push --project cuts-sintel --title sintel
   ```

   `push` measures the exact frame rate of every clip (24/1 for Sintel), refuses a mix of rates,
   writes it into the project config, and prints e.g. `project 1: verify task + 15 clip tasks, fps
   24/1`. To see the exact config it sends: `lbl config --title sintel` (for Sintel the line
   `<Video ... framerate="24" ...>`; for 23.976 media it must read `23.976023976`, never
   `24000/1001`, which Label Studio silently reads as 24).

5. **Check the frame numbers line up** (2 minutes; do it once per project). Label Studio can
   misread frame rates, which would shift every label. Task 1 of the project is a clip with the
   true frame number burned into the top-left of every picture:
   1. In Label Studio click **Projects** -> **cuts-sintel**. You see a table of 16 tasks.
   2. Click the row whose `clip` column says `_verify.mp4` (ID 1). The video opens.
   3. Scroll down inside the page to the control bar under the video. The box at its left reads
      `1 of 240`.
   4. Click that box, type `100`, press **Enter**, then **Tab**.
   5. Compare: the box now reads `100 of 240` and the number burned into the picture must be
      **100** too. Repeat with `240` and `1`. If any pair differs, stop and tell the developer.
   You do not need to Submit this task; if you do, it is ignored when the labels are pulled.

## Labelling (the human part)

1. In the project table click **Label All Tasks** (top, above the table), or click a row
   `sintel_000.mp4` ... `sintel_014.mp4`. Skip `_verify.mp4`.
2. Scroll down to the controls under the video. Under the timeline you see a red button **Cut**
   (hotkey `1`). Click it once to select it; a grey lane named **Cut** appears in the timeline.
3. Play the clip with the play button (or the space bar). When the picture jumps to a new shot,
   pause and step with the **left/right arrow buttons** next to the play button (one press = one
   frame) until the box reads the **first frame of the new shot**. Check the frame before it still
   shows the old shot. (You can also type a frame number into that box, press Enter, then Tab.)
4. **Double-click the grey Cut lane on the highlighted thin vertical strip** (that strip marks the
   current frame). A red tick appears and the right-hand panel shows `Start frame` and `End frame`.
   Both must equal the number in the frame box (a single-frame mark; only the start is used); if
   not, type the right number into both boxes. To remove a mark, click it and press Delete, or
   click the bin icon in the right panel.
5. Continue to the end of the clip, press **Submit** (bottom right), go to the next clip.

Tips: set the playback speed low while looking for cuts; when unsure whether something is a cut,
step back and forth across it three times: a cut replaces the whole picture in one frame.

## Getting the labels out

```
lbl pull <project id> --title sintel --labeller human
```

It prints how many clips are labelled (`15/15 clips labelled`) and **fails if any clip has no
finished annotation** (an unlabelled clip would silently count as "no cuts" and make every
detector look worse); finish the missing clips, or add `--allow-partial` to write the file anyway
(missing clips are then listed in `unlabelled_clips`). Cancelled/skipped tasks count as unlabelled.

### Cuts label file format

Output: `eval/labeling/labels/<title>_cuts.json` (human labeller) or
`eval/labeling/labels/<title>_cuts.provisional.json` (any other labeller, e.g. `agent`). Shot cuts
are **not** Flags and are not scored by `eval/metrics.py`; the EXP-002 cut-F1 (±2 frames) reads
this file. One JSON object:

```json
{
 "title": "sintel",
 "check": "shot.cut",
 "fps": "24/1",
 "labeller": "human",
 "frame_convention": "0-based index in the whole film of the first frame of the new shot",
 "unlabelled_clips": [],
 "cuts": [34, 1440, 1538]
}
```

| Field | Meaning |
|-------|---------|
| `title` | Corpus title id (`eval/corpus/manifest.yaml`) |
| `check` | Always `shot.cut` |
| `fps` | Exact frame rate of the labelled media as `numerator/denominator` (`24/1`, `24000/1001`); the indexes below are frames at this rate |
| `labeller` | `human`, or e.g. `agent` for provisional labels made by frame inspection |
| `frame_convention` | A cut at `N` means frames `N-1` and `N` are in different shots, i.e. `N` is the first frame of the new shot, counted from 0 at the first frame of the whole film (the same convention as `nip.timeline.shots`). Clip numbering, the one-frame overlap and Label Studio's 1-based numbering are already removed |
| `unlabelled_clips` | Clip names with no finished annotation (non-empty only with `--allow-partial`) |
| `cuts` | Sorted, de-duplicated list of cut frame indexes (frame 0 is never a cut) |

## What each piece is

| File | Purpose |
|------|---------|
| `cuts.xml` | The Label Studio project config (video + one `Cut` label; the framerate is filled in from the probed clips) |
| `labeling.py` | `prepare` (make clips + the burned-in verify clip), `config`, `push`, `pull`, `verify-clip` (stand-alone check clip at any rate, e.g. `--fps 24000/1001`) |
