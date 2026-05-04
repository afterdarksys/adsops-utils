import typer

app = typer.Typer(help="adsops - After Dark Systems ops CLI", no_args_is_help=True)


def _register():
    """Register sub-apps. Uses try/except so modules built in later waves
    are picked up automatically once they exist."""
    try:
        from adsops.hostctl.cli import app as hostctl_app
        app.add_typer(hostctl_app, name="hostctl")
    except ImportError:
        pass

    try:
        from adsops.infractl.cli import app as infractl_app
        app.add_typer(infractl_app, name="infractl")
    except ImportError:
        pass

    try:
        from adsops.stats.cli import app as stats_app
        app.add_typer(stats_app, name="stats")
    except ImportError:
        pass

    try:
        from adsops.sysscript.cli import app as sysscript_app
        app.add_typer(sysscript_app, name="sysscript")
    except ImportError:
        pass


_register()

if __name__ == "__main__":
    app()
