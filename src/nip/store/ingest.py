"""`nip ingest`: validate source files at the door, store them content-addressed, write their rows.

architecture.md › Validation at the door: every file of a call is validated before anything is
written, and a rejected file rejects the call (`INPUT_REJECTED`). Each file is then uploaded to
`nip-media` under its sha256 and registered in `source_file`; a file whose sha256 the episode (or,
for show-level files, the show) already has is skipped, so re-ingesting creates no rows.

Rows per kind (data-model.md › Content and timeline, Knowledge layer, Registries):
- picture: the episode's frame axis (fps, start TC, drop-frame, duration) and `shot` rows with
  keyframes, from a cached `picture.json` or `analyze_picture`.
- script: `scene` (frames estimated by `scene_bounds`, unclipped) + `script_line` (frames NULL
  until alignment, 2.5; `seq` is 1-based within the scene).
- subtitle: `subtitle_track` + `subtitle_cue` (frames by exact ms -> frame, as `build_timeline`).
- bible: `entity` for characters, secrets and fictional brands/orgs/places (`fictional=true`) +
  `entity_alias`; glossary: `entity(kind=term)` + `approved_rendering` aliases; clearance log:
  `clearance_item`. Show-level rows are upserted, so a revised file updates them.

Frames are placed at the picture's frame rate, or 24 fps while the episode has no picture.
Replacing an episode's script, picture or a language's subtitles is refused (incremental re-runs
are 2.9B), and so is a picture whose rate differs from the 24 fps already used for its rows.
"""

import json
import logging
import re
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import Connection, create_engine, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.dialects.postgresql import insert as pg_insert

from nip.ingest import Bible, ClearanceEntry, GlossaryEntry, Script, SubtitleTrack, parse
from nip.ingest.media import MediaInfo, MediaRejected, probe
from nip.ingest.tables import _LANG_RE
from nip.store import objects, schema
from nip.store.db import database_url
from nip.store.runs import ext_id
from nip.timecode import ms_to_frame
from nip.timeline.estimate import NO_PICTURE_FPS, scene_bounds

log = logging.getLogger(__name__)

SCRIPT_FORMATS = {".pdf": "pdf", ".fountain": "fountain", ".fdx": "fdx"}
SUBTITLE_FORMATS = {".srt": "srt", ".vtt": "vtt", ".ttml": "ttml", ".xml": "ttml"}
FORMATS = SCRIPT_FORMATS | SUBTITLE_FORMATS  # file-mode `nip run-files` reads these
VIDEO = {".mp4", ".mov", ".mkv", ".mxf", ".m4v"}
TABLES = ("glossary", "clearance_log")  # csv kinds, given as KIND=PATH
EPISODE_RE = re.compile(r"S(\d+)E(\d+)")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")  # goes into S3 keys and URLs
FICTIONAL_KINDS = {"brands": "brand", "orgs": "org", "places": "location"}


class InputRejected(ValueError):
    """A source file refused at the door (api-contracts.md INPUT_REJECTED)."""


def ingest[T](path: Path, want: type[T], fmt: str | None = None, kind: str | None = None) -> T:
    """Parse + validate one source file as a `want` (format from the extension unless given);
    warnings are logged. A script's scene numbers must be unique (they are its refs, B-106)."""
    fmt = fmt or FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise InputRejected(f"{path.name}: unsupported format {path.suffix!r}")
    p = parse(fmt, path.read_bytes(), kind)
    for w in p.warnings:
        log.warning("%s: %s", path.name, w)
    if not p.ok:
        e = p.errors[0]
        raise InputRejected(f"{path.name}: {e.reason}" + (f" (line {e.line})" if e.line else ""))
    if not isinstance(p.data, want):  # e.g. a script given a subtitle file
        raise InputRejected(f"{path.name}: a {fmt} file is not a {want.__name__}")
    if isinstance(p.data, Script):
        dup = sorted(n for n, k in Counter(s.number for s in p.data.scenes).items() if k > 1)
        if dup:
            raise InputRejected(f"{path.name}: duplicate scene numbers {dup}; renumber them")
    return p.data


@dataclass
class Source:
    path: Path
    kind: str  # script | picture | subtitle | bible | glossary | clearance_log
    format: str
    lang: str | None = None
    role: str | None = None  # subtitles: source | target
    sha: str = ""
    data: Any = None  # parsed content; MediaInfo for a picture

    @property
    def show_level(self) -> bool:
        return self.kind in ("bible", *TABLES)


def classify(tag: str | None, path: Path, source_lang: str) -> Source:
    """What a `[TAG=]PATH` argument is: subtitles need LANG=, csv glossary= or clearance_log=."""
    ext = path.suffix.lower()
    if ext in SUBTITLE_FORMATS:
        if not tag or not _LANG_RE.match(tag):
            raise InputRejected(f"{path.name}: give subtitles as LANG=PATH (e.g. es-419={path})")
        role = "source" if tag == source_lang else "target"
        return Source(path, "subtitle", SUBTITLE_FORMATS[ext], tag, role)
    if tag and not (ext == ".csv" and tag in TABLES):
        raise InputRejected(f"{tag}={path.name}: only subtitles and csv tables take a TAG=")
    if ext in SCRIPT_FORMATS:
        return Source(path, "script", SCRIPT_FORMATS[ext])
    if ext in VIDEO:
        return Source(path, "picture", ext[1:])
    if ext in (".yaml", ".yml"):
        return Source(path, "bible", "yaml")
    if ext == ".csv" and tag:
        return Source(path, tag, "csv")
    if ext == ".csv":
        raise InputRejected(f"{path.name}: give csv files as glossary=PATH or clearance_log=PATH")
    raise InputRejected(f"{path.name}: unsupported format {ext!r}")


def _validate(src: Source) -> None:
    if src.kind == "picture":
        try:
            src.data = probe(src.path)
        except MediaRejected as e:
            raise InputRejected(str(e)) from e
        return
    want: type = {"script": Script, "subtitle": SubtitleTrack, "bible": Bible}.get(src.kind, list)
    src.data = ingest(src.path, want, src.format, src.kind if src.format == "csv" else None)


def _picture(media: MediaInfo, video: Path, picture: Path | None, work: Path) -> dict[str, Any]:
    """Shots + keyframes: the cached `picture.json` (checked against the probe) or a fresh run;
    keyframe images are read from `<dir>/keyframes/` next to it when present."""
    if picture is None:
        from nip.timeline.picture import analyze_picture  # torch: only when a picture is analysed

        return analyze_picture(video, work) | {"dir": work}
    pic: dict[str, Any] = json.loads(picture.read_text(encoding="utf-8"))
    if Fraction(*pic["fps"]) != media.fps or pic["duration_frames"] != media.duration_frames:
        raise InputRejected(
            f"{picture.name}: fps {pic['fps']} / {pic['duration_frames']} frames are not "
            f"{video.name}'s ({media.fps} / {media.duration_frames})"
        )
    if any(b > media.duration_frames for _, b in pic["shots"]):  # 1.8A M3: decoder past the probe
        raise InputRejected(f"{picture.name}: shots end past the probed duration")
    pic["dir"] = picture.parent
    return pic


def _id(conn: Connection, stmt: Any) -> int | None:
    return conn.execute(stmt).scalar_one_or_none()


def _episode_state(conn: Connection, episode_id: int | None) -> tuple[set[tuple[str, str]], bool]:
    """((kind, lang or '') of the episode's source files, whether it has rows placed in frames)."""
    if episode_id is None:
        return set(), False
    sf = schema.source_file
    have = {
        (k, lang or "")
        for k, lang in conn.execute(
            select(sf.c.kind, sf.c.lang).where(sf.c.episode_id == episode_id)
        )
    }
    return have, any(k in ("script", "subtitle") for k, _ in have)


def ingest_files(
    conn: Connection,
    s3: Any,
    *,
    show: str,
    episode: str | None,
    files: Sequence[tuple[str | None, Path]],
    source_lang: str = "en",
    picture: Path | None = None,
) -> dict[str, Any]:
    """Validate every file, then store the new ones and write their rows (in `conn`'s transaction).

    `files` are (tag, path): tag = subtitle language, or `glossary` / `clearance_log` for csv.
    Raises InputRejected before anything is written. Returns what was stored and skipped.
    """
    if not SLUG_RE.fullmatch(show):
        raise InputRejected(f"show slug {show!r}: lowercase letters, digits, '-', '_' only")
    srcs = [classify(tag, p, source_lang) for tag, p in files]
    if picture is not None and not any(s.kind == "picture" for s in srcs):
        raise InputRejected("a picture.json needs the video it was made from")
    m = EPISODE_RE.fullmatch(episode or "")
    if any(not s.show_level for s in srcs) and m is None:
        raise InputRejected(f"episode files need --episode SxxEyy (got {episode!r})")
    twice = [k for k, n in Counter((s.kind, s.lang) for s in srcs).items() if n > 1]
    if twice:
        raise InputRejected(f"more than one file for {twice}")

    sf = schema.source_file
    show_id = _id(conn, select(schema.show.c.id).where(schema.show.c.slug == show))
    ep_id = (
        _id(
            conn,
            select(schema.episode.c.id).where(
                schema.episode.c.show_id == show_id, schema.episode.c.ref == episode
            ),
        )
        if show_id is not None and m
        else None
    )
    known: set[str] = set()
    if show_id is not None:
        known = set(
            conn.execute(
                select(sf.c.sha256).where(
                    sf.c.show_id == show_id,
                    (sf.c.episode_id == ep_id) | sf.c.episode_id.is_(None),
                )
            ).scalars()
        )
    for s in srcs:
        s.sha = objects.sha256_file(s.path)
    new = [s for s in srcs if s.sha not in known]
    if picture is not None and not any(s.kind == "picture" for s in new):
        log.warning("%s ignored: its video is already ingested", picture.name)
    for s in new:
        _validate(s)

    have, placed = _episode_state(conn, ep_id)
    ep_fps = (
        conn.execute(
            select(schema.episode.c.fps_num, schema.episode.c.fps_den).where(
                schema.episode.c.id == ep_id
            )
        ).one()
        if ep_id is not None
        else (None, None)
    )
    fps = Fraction(*ep_fps) if ep_fps[0] else NO_PICTURE_FPS
    for s in new:
        if s.kind == "picture":
            if ("picture", "") in have:
                raise InputRejected(
                    f"{episode} already has a picture; replacing it is not supported"
                )
            if placed and s.data.fps != NO_PICTURE_FPS:
                raise InputRejected(
                    f"{episode}'s script/subtitle rows were placed at {NO_PICTURE_FPS} fps but "
                    f"{s.path.name} is {s.data.fps} fps; ingest the picture first"
                )
            fps = s.data.fps
        elif not s.show_level and (s.kind, s.lang or "") in have:
            what = f"{s.lang} subtitles" if s.lang else f"a {s.kind}"
            raise InputRejected(f"{episode} already has {what}; replacing it is not supported")

    stored: list[dict[str, Any]] = []
    if new:
        with tempfile.TemporaryDirectory() as work:
            pics = {
                id(s): _picture(s.data, s.path, picture, Path(work))
                for s in new
                if s.kind == "picture"
            }
            if show_id is None:
                show_id = conn.execute(
                    insert(schema.show).values(slug=show, title=show).returning(schema.show.c.id)
                ).scalar_one()
            if ep_id is None and m:
                season, number = int(m[1]), int(m[2])
                ep_id = conn.execute(
                    insert(schema.episode)
                    .values(
                        show_id=show_id,
                        season=season,
                        number=number,
                        episode_seq=season * 1000 + number,  # release order = SxxEyy order
                        ref=episode,
                    )
                    .returning(schema.episode.c.id)
                ).scalar_one()
            order = ("picture", "script", "subtitle", "bible", "glossary", "clearance_log")
            for s in sorted(new, key=lambda s: order.index(s.kind)):
                key = objects.source_key(
                    show, None if s.show_level else episode, s.sha, s.path.suffix
                )
                objects.put_file(s3, objects.media_bucket(), key, s.path)
                declared = s.data.frame_rate if s.kind == "subtitle" else None
                sid = conn.execute(
                    insert(sf)
                    .values(
                        episode_id=None if s.show_level else ep_id,
                        show_id=show_id,
                        kind=s.kind,
                        lang=s.lang,
                        role=s.role,
                        format=s.format,
                        object_key=key,
                        sha256=s.sha,
                        declared_fps=(str(declared) if declared else "none")
                        if s.kind == "subtitle"
                        else None,
                    )
                    .returning(sf.c.id)
                ).scalar_one()
                if s.kind == "bible":
                    _write_bible(conn, show_id, s.data)
                elif s.kind == "glossary":
                    _write_glossary(conn, show_id, s.data)
                elif s.kind == "clearance_log":
                    _write_clearance(conn, show_id, sid, s.data)
                else:
                    assert ep_id is not None and episode is not None
                    if s.kind == "picture":
                        _write_picture(conn, s3, show, episode, ep_id, s.data, pics[id(s)])
                    elif s.kind == "script":
                        _write_script(conn, ep_id, s.data, fps)
                    else:
                        _write_subtitles(conn, ep_id, sid, s, fps)
                stored.append(
                    {"file": s.path.name, "kind": s.kind, "source_id": ext_id("src", sid)}
                )
    return {
        "show": show,
        "episode": episode,
        "stored": stored,
        "unchanged": [s.path.name for s in srcs if s.sha in known],
    }


def _write_picture(
    conn: Connection, s3: Any, show: str, ep: str, ep_id: int, media: MediaInfo, pic: dict[str, Any]
) -> None:
    conn.execute(
        update(schema.episode)
        .where(schema.episode.c.id == ep_id)
        .values(
            fps_num=media.fps.numerator,
            fps_den=media.fps.denominator,
            drop_frame=media.drop_frame,
            start_tc_frames=media.start_tc_frames,
            duration_frames=media.duration_frames,
        )
    )
    kfs: dict[int, list[dict[str, Any]]] = {}
    for k in pic["keyframes"]:
        rec = {"n": k["n"], "frame": k["frame"]}
        img = Path(pic["dir"]) / "keyframes" / k.get("file", f"{k['shot']}_{k['n']}.jpg")
        if img.is_file():
            rec["object_key"] = objects.keyframe_key(show, ep, k["shot"], k["n"])
            objects.put_file(s3, objects.media_bucket(), rec["object_key"], img)
        kfs.setdefault(k["shot"], []).append(rec)
    if pic["shots"]:
        conn.execute(
            insert(schema.shot),
            [
                {"episode_id": ep_id, "frames": Range(a, b), "keyframes": kfs.get(i, [])}
                for i, (a, b) in enumerate(pic["shots"])
            ],
        )


def _write_script(conn: Connection, ep_id: int, script: Script, fps: Fraction) -> None:
    bounds = scene_bounds(script, fps)
    for s, a, b in zip(script.scenes, bounds, bounds[1:], strict=False):
        sc_id = conn.execute(
            insert(schema.scene)
            .values(
                episode_id=ep_id,
                script_scene_no=s.number,
                heading=s.heading,
                time_of_day=s.time_of_day,
                frames=Range(a, b) if b > a else None,  # an empty scene has no frames
                text_hash=s.text_hash,
            )
            .returning(schema.scene.c.id)
        ).scalar_one()
        if s.elements:
            conn.execute(
                insert(schema.script_line),
                [
                    {"scene_id": sc_id, "seq": i, "kind": e.kind, "text": e.text}
                    for i, e in enumerate(s.elements, 1)
                ],
            )


def cue_frames(start_ms: int, end_ms: int, fps: Fraction) -> tuple[int, int]:
    """As `build_timeline`: exact ms -> frame; a sub-frame cue keeps one frame (B-062)."""
    a = ms_to_frame(start_ms, fps)
    return a, max(ms_to_frame(end_ms, fps), a + 1)


def _write_subtitles(conn: Connection, ep_id: int, sid: int, src: Source, fps: Fraction) -> None:
    track_id = conn.execute(
        insert(schema.subtitle_track)
        .values(episode_id=ep_id, source_file_id=sid, lang=src.lang, role=src.role)
        .returning(schema.subtitle_track.c.id)
    ).scalar_one()
    if src.data.cues:
        conn.execute(
            insert(schema.subtitle_cue),
            [
                {
                    "track_id": track_id,
                    "idx": c.idx,
                    "frames": Range(*cue_frames(c.start_ms, c.end_ms, fps)),
                    "text": c.text,
                }
                for c in src.data.cues
            ],
        )


def _entity(
    conn: Connection,
    show_id: int,
    kind: str,
    name: str,
    origin: str,
    aliases: Sequence[tuple[str, str, str]] = (),
    attributes: dict[str, Any] | None = None,
    fictional: bool | None = None,
) -> int:
    """Upsert the entity (show, kind, canonical name) and add its (lang, alias, kind) aliases."""
    e = schema.entity
    values = {"attributes": attributes or {}, "fictional": fictional, "origin": origin}
    eid = _id(
        conn,
        select(e.c.id).where(e.c.show_id == show_id, e.c.kind == kind, e.c.canonical_name == name),
    )
    if eid is None:
        eid = conn.execute(
            insert(e)
            .values(show_id=show_id, kind=kind, canonical_name=name, **values)
            .returning(e.c.id)
        ).scalar_one()
    else:
        conn.execute(update(e).where(e.c.id == eid).values(**values))
    if aliases:
        conn.execute(
            pg_insert(schema.entity_alias).on_conflict_do_nothing(),
            [{"entity_id": eid, "lang": lg, "alias": a, "kind": k} for lg, a, k in aliases],
        )
    return eid


def _write_bible(conn: Connection, show_id: int, bible: Bible) -> None:
    for c in bible.characters:
        attrs = {
            "bible_id": c.id,
            "gender": c.gender,
            "pronouns": c.pronouns or None,
            "identity_hidden_until": c.identity_hidden_until,
        }
        names = [("any", c.name, "name"), *(("any", a, "nickname") for a in c.aliases)]
        _entity(
            conn, show_id, "character", c.name, "bible", names,
            {k: v for k, v in attrs.items() if v is not None},
        )  # fmt: skip
    for s in bible.secrets:
        attrs = {"description": s.description, "revealed_on_screen": s.revealed_on_screen}
        _entity(conn, show_id, "secret", s.id, "bible", (), {"bible_id": s.id, **attrs})
    for field, kind in FICTIONAL_KINDS.items():
        for name in getattr(bible.fictional, field):
            _entity(conn, show_id, kind, name, "bible", [("any", name, "name")], fictional=True)


def _write_glossary(conn: Connection, show_id: int, rows: list[GlossaryEntry]) -> None:
    alias = schema.entity_alias
    for term in dict.fromkeys(r.term for r in rows):
        mine = [r for r in rows if r.term == term]
        eid = _entity(conn, show_id, "term", term, "glossary", [("any", term, "name")])
        langs = {r.lang for r in mine}
        conn.execute(  # a revised glossary replaces the approved rendering per language
            delete(alias).where(
                alias.c.entity_id == eid,
                alias.c.kind == "approved_rendering",
                alias.c.lang.in_(langs),
            )
        )
        conn.execute(
            pg_insert(alias).on_conflict_do_nothing(),
            [
                {"entity_id": eid, "lang": r.lang, "alias": r.approved_rendering,
                 "kind": "approved_rendering"}
                for r in mine
            ],
        )  # fmt: skip


def _write_clearance(conn: Connection, show_id: int, sid: int, rows: list[ClearanceEntry]) -> None:
    c = schema.clearance_item
    for r in rows:
        scope = r.scope or None
        values = {"status": r.status, "notes": r.notes or None, "source_file_id": sid}
        cid = _id(
            conn,
            select(c.c.id).where(
                c.c.show_id == show_id,
                func.lower(c.c.name) == r.item.lower(),
                c.c.kind == r.kind,
                c.c.scope.is_not_distinct_from(scope),
            ),
        )
        if cid is None:
            conn.execute(
                insert(c).values(show_id=show_id, name=r.item, kind=r.kind, scope=scope, **values)
            )
        else:
            conn.execute(update(c).where(c.c.id == cid).values(**values))


TAG_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def ingest_cmd(
    show: Annotated[str, typer.Option(help="Show slug, e.g. sintel")],
    files: Annotated[
        list[str],
        typer.Argument(
            help="PATH; subtitles as LANG=PATH; csv as glossary=PATH, clearance_log=PATH"
        ),
    ],
    episode: Annotated[str | None, typer.Option(help="SxxEyy; needed for episode files")] = None,
    source_lang: Annotated[str, typer.Option(help="Language of the source subtitles")] = "en",
    picture: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Cached picture.json of the video"),
    ] = None,
) -> None:
    """Register source files: validate, store content-addressed, write their rows."""
    pairs: list[tuple[str | None, Path]] = []
    for f in files:
        tag, sep, path = f.partition("=")
        pairs.append((tag, Path(path)) if sep and TAG_RE.fullmatch(tag) else (None, Path(f)))
    engine = create_engine(database_url())
    try:
        with engine.begin() as conn:
            summary = ingest_files(
                conn,
                objects.client(),
                show=show,
                episode=episode,
                files=pairs,
                source_lang=source_lang,
                picture=picture,
            )
    except (InputRejected, FileNotFoundError) as e:
        typer.echo(f"INPUT_REJECTED: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        engine.dispose()
    typer.echo(json.dumps(summary, indent=2))
