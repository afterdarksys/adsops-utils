import pytest
from adsops.sysscript.runner import SysscriptRunner
from adsops.sysscript.mock import MockSys


def test_run_simple_expression(tmp_path):
    """Test 1: runner.run() on a simple .star that sets result = 1 + 2 returns globals with result == 3."""
    sysscripts = tmp_path / "sysscripts"
    sysscripts.mkdir()
    script = sysscripts / "simple.star"
    script.write_text("result = 1 + 2\n")

    runner = SysscriptRunner(sys_global=MockSys({}))
    globs = runner.run(str(script))
    assert globs["result"] == 3


def test_run_injects_sys_global(tmp_path):
    """Test 2: runner.run() injects sys global — script accessing sys.net.http_get with fixture returns fixture value."""
    sysscripts = tmp_path / "sysscripts"
    sysscripts.mkdir()
    script = sysscripts / "net_check.star"
    script.write_text('response = sys.net.http_get("https://example.com")\n')

    runner = SysscriptRunner(sys_global=MockSys({"net.http_get": {"status_code": 200, "body": "ok"}}))
    globs = runner.run(str(script))
    assert globs["response"] == {"status_code": 200, "body": "ok"}


def test_run_resolves_load_statement(tmp_path):
    """Test 3: runner resolves load() statements — a service script that load()s a lib file gets lib functions in globals."""
    sysscripts = tmp_path / "sysscripts"
    lib_dir = sysscripts / "lib"
    lib_dir.mkdir(parents=True)
    services_dir = sysscripts / "services" / "test"
    services_dir.mkdir(parents=True)

    lib_file = lib_dir / "helper.star"
    lib_file.write_text("def helper_fn():\n    return 42\n")

    main_script = services_dir / "main.star"
    main_script.write_text(
        'load("../../lib/helper.star", "helper_fn")\n'
        "result = helper_fn()\n"
    )

    runner = SysscriptRunner(sys_global=MockSys({}))
    globs = runner.run(str(main_script))
    assert globs["result"] == 42


def test_run_rejects_path_traversal(tmp_path):
    """Test 4: runner rejects load() path that escapes sysscripts/ root raises ValueError with 'path traversal'."""
    sysscripts = tmp_path / "sysscripts" / "services"
    sysscripts.mkdir(parents=True)
    evil = sysscripts / "evil.star"
    evil.write_text('load("../../../etc/passwd", "x")\n')

    runner = SysscriptRunner(sys_global=MockSys({}))
    with pytest.raises(ValueError, match="path traversal"):
        runner.run(str(evil))


def test_find_sysscripts_root_raises_when_not_under_sysscripts(tmp_path):
    """Test 5: runner._find_sysscripts_root raises ValueError when script is not under a sysscripts/ directory."""
    # Script is under a directory NOT named sysscripts
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "notasysscript.star"
    script.write_text("x = 1\n")

    runner = SysscriptRunner(sys_global=MockSys({}))
    with pytest.raises(ValueError, match="No 'sysscripts/' ancestor found"):
        runner.run(str(script))


def test_run_empty_mocksys_raises_on_sys_call(tmp_path):
    """Test 6: runner with empty MockSys (no fixtures) raises NotImplementedError when script calls sys.net.http_get."""
    sysscripts = tmp_path / "sysscripts"
    sysscripts.mkdir()
    script = sysscripts / "call_net.star"
    script.write_text('result = sys.net.http_get("https://example.com")\n')

    runner = SysscriptRunner(sys_global=MockSys({}))
    with pytest.raises(NotImplementedError, match="no fixture for 'net.http_get'"):
        runner.run(str(script))
