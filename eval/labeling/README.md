# Labelling shot cuts in Label Studio

A **cut** is the instant one camera shot is replaced by another. To measure how well the shot
detectors work (EXP-002) we need a list of the true cuts, made by a person. This page shows how to
make that list for *Sintel* even if you have never labelled anything before. Plan for about
45-60 minutes: Sintel has roughly 15 clips of 60 seconds each and a few dozen cuts per clip.

## What you will mark

For every cut, mark **the first frame of the new shot** (the first picture that no longer belongs
to the previous shot). That is all. Do not mark dissolves/fades as two points; mark the frame where
the new shot is first clearly visible. Do not mark camera moves inside one shot.

In Label Studio frames are numbered **from 1**. The first frame of every clip after the first is
the *last frame of the previous clip* (a one-frame overlap so that a cut on a clip boundary is
still visible). **Never mark frame 1 of a clip.** If you do, it is ignored.

## One-time setup (the app side)

1. Prepare the clips (cuts `data/corpus/sintel/Sintel.2010.1080p.mkv` into 15 small preview
   clips in `data/labeling/sintel/`, ~120 MB, about 1 minute):

   ```
   uv run python -c "from eval.labeling.labeling import app; app()" prepare --title sintel
   ```

   (Once the integration step has wired the sub-app this is `nip eval labels prepare`.)

2. Start Label Studio with the `data/` folder mounted so it can serve the clips:

   ```
   docker run -d --name ls -p 8081:8080 ^
     -e LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true ^
     -e LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files ^
     -v "D:\Projects\In Process\Netflix LM\data:/label-studio/files" ^
     -v ls-data:/label-studio/data heartexlabs/label-studio:1.23.2
   ```

   (`^` is the Windows `cmd` line-continuation character; in PowerShell use a backtick, on
   Linux/macOS use `\` and a normal path. Do not run this in Git Bash: it rewrites
   `/label-studio/files` into a Windows path and Label Studio then refuses the project storage.)
   The first start takes 2-3 minutes (it builds its database). Open <http://localhost:8081>, click
   **Sign up**, make a local account (any e-mail/password; it only exists on your machine).

3. Get an API token: click your avatar (top right) -> **Account & Settings** -> **Personal Access
   Token** -> **Create**. **Copy it immediately: it is shown only once.** (Legacy tokens are
   disabled in Label Studio 1.23.) Put it in the shell you run commands from:

   ```
   set LABEL_STUDIO_TOKEN=<paste token>
   ```

4. **Check the frame numbers line up** (do this once per frame rate; takes 2 minutes). Label Studio
   silently misreads some frame rates, which would shift every label. The check clip has the real
   frame number burned into every picture:

   ```
   uv run python -c "from eval.labeling.labeling import app; app()" verify-clip --fps 24/1
   ```

   This writes `data/labeling/verify_24.mp4`. Create a throw-away project in Label Studio with the
   same config (see step 5 but any name), add that clip as a task, open it, step forward with the
   arrow keys until the burned-in number reads, say, **100**, and look at the frame counter in the
   Label Studio timeline. **They must be identical.** If they differ, stop and tell the developer.
   Sintel and Tears of Steel are exactly 24 fps (`ffprobe` says `24/1`), so the project uses
   `framerate="24"`. For 23.976 fps material use `--fps 24000/1001`; the project then uses
   `framerate="23.976023976"`. Never type `24000/1001` into the config: Label Studio reads it as 24.

5. Create the project and its tasks (one task per clip):

   ```
   uv run python -c "from eval.labeling.labeling import app; app()" push --project cuts-sintel --title sintel --fps 24/1
   ```

   It prints the project id.

## Labelling (the human part)

1. Open the project **cuts-sintel**, click the first task, then **Label All Tasks** (or open each
   clip).
2. The video appears with a timeline under it and one label, **Cut** (click it to select it).
3. Play the clip. When the picture jumps to a new shot, pause and step with the **left/right arrow
   keys** until you are on the *first frame of the new shot* (one arrow press = one frame).
   Compare the previous frame: it must clearly show the old shot.
4. With **Cut** selected, click the timeline at that frame to add a one-frame mark. Make sure the
   mark starts and ends on the same frame (a single-frame range). If you made a longer range,
   drag its right edge back to the left edge. Only the **start** of the range is used.
5. Continue to the end of the clip, press **Submit**, go to the next clip.
6. Mistakes: select the mark on the timeline and press Delete.

Tips: set playback speed to 0.5x while looking for cuts; when unsure whether something is a cut,
step back and forth across it three times; a cut is a *single-frame* change, so you should see the
whole picture replaced.

## Getting the labels out

```
uv run python -c "from eval.labeling.labeling import app; app()" pull <project id> --title sintel --labelled-by human
```

This writes `eval/labels/cuts/sintel.jsonl`, one line per cut:

```json
{"title": "sintel", "check": "shot.cut", "frame": 1540, "labelled_by": "human"}
```

`frame` is the **0-based index in the whole film** of the first frame of the new shot (clip number,
the one-frame overlap and Label Studio's 1-based numbering are already accounted for), which is the
convention the shot detectors in `nip.timeline` use. `--labelled-by agent` is used for provisional
labels made by frame inspection; human review replaces them.

## What each piece is

| File | Purpose |
|------|---------|
| `cuts.xml` | The Label Studio project config (video + one `Cut` label; `{framerate}` is filled in) |
| `labeling.py` | `prepare` (make clips), `verify-clip` (burned-in frame numbers), `push`, `pull` |
