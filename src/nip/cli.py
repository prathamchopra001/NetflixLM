import os

import typer

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")  # mlflow logs a hint on import

from eval.corpus.downloader import app as corpus_app
from eval.inject import inject
from eval.labeling.labeling import app as labeling_app
from eval.report import app as eval_app
from nip import pipeline
from nip.runtime import planner
from nip.store import ingest
from nip.timeline import align, asr, picture

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Netflix LM pre-release QA pipeline."""


eval_app.add_typer(corpus_app, name="corpus")
eval_app.add_typer(labeling_app, name="labels")
eval_app.command("inject")(inject)
app.add_typer(eval_app, name="eval")
picture.app.add_typer(asr.app)  # nip timeline asr
picture.app.add_typer(align.app)  # nip timeline align
app.add_typer(picture.app, name="timeline")
app.add_typer(planner.app, name="plan")
app.command("ingest")(ingest.ingest_cmd)
app.command("run")(pipeline.run)
app.command("run-files")(pipeline.run_files)
