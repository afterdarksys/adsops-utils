"""Typer sub-app for sysscript: run .star scripts locally.

This module is auto-registered by adsops/cli.py via conditional import:
    from adsops.sysscript.cli import app as sysscript_app
"""
import typer

app = typer.Typer(help="Run and manage sysscripts", no_args_is_help=True)


@app.command("run")
def run_cmd(script: str = typer.Argument(..., help="Path to .star script")) -> None:
    """Execute a .star script locally with empty MockSys (D-04)."""
    from adsops.sysscript.runner import SysscriptRunner
    runner = SysscriptRunner()
    try:
        runner.run(script)
        typer.echo("Script completed successfully.")
    except NotImplementedError as e:
        typer.echo(f"Script needs fixture: {e}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    except (FileNotFoundError, PermissionError) as e:
        typer.echo(f"ERROR: Cannot read script: {e}", err=True)
        raise typer.Exit(1)
    except SyntaxError as e:
        typer.echo(f"ERROR: Script syntax error: {e}", err=True)
        raise typer.Exit(1)
