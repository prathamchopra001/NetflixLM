import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Netflix LM pre-release QA pipeline."""
