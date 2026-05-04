from typer.testing import CliRunner
from adsops.cli import app

runner = CliRunner()


def test_help_shows_hostctl():
    """PY-05: adsops --help output contains hostctl subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "hostctl" in result.output


def test_help_shows_infractl():
    """PY-05: adsops --help output contains infractl subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "infractl" in result.output


def test_help_shows_stats():
    """PY-05: adsops --help output contains stats subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "stats" in result.output


def test_hostctl_subcommand_help():
    """PY-05: adsops hostctl --help shows list/add/update/import-ssh-config/probe."""
    result = runner.invoke(app, ["hostctl", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "probe" in result.output


def test_infractl_subcommand_help():
    """PY-05: adsops infractl --help shows docker and k3s."""
    result = runner.invoke(app, ["infractl", "--help"])
    assert result.exit_code == 0
    assert "docker" in result.output
    assert "k3s" in result.output


def test_stats_subcommand_help():
    """PY-05: adsops stats --help shows once and fetch."""
    result = runner.invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    assert "once" in result.output
    assert "fetch" in result.output
