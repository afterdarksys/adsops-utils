import os
import re
import pathlib
from adsops.sysscript.mock import MockSys

_LOAD_PATTERN = re.compile(
    r"""load\(\s*["']([^"']+)["'](?:\s*,\s*["']\w+["'])*\s*\)\n?"""
)


class SysscriptRunner:
    """Execute .star (Starlark) files via Python exec() with load() resolution and sandbox enforcement.

    Per D-01/research: starlark-py does not exist on PyPI. Python exec() is used instead —
    pure Python, no binary deps, equivalent for the Starlark subset used by service scripts.
    Per D-02: sys injected as predefined global.
    Per D-03: empty MockSys() is default — any sys.* call raises NotImplementedError.
    Per D-05: load() paths resolved relative to script file location.
    Per D-06: sandbox root is sysscripts/ — paths outside rejected with ValueError.
    Per D-07: root auto-discovered by walking ancestors for directory named 'sysscripts'.
    """

    def __init__(self, sys_global=None):
        self._sys = sys_global if sys_global is not None else MockSys()

    def _find_sysscripts_root(self, script_path: pathlib.Path) -> pathlib.Path:
        """Walk ancestors to find nearest directory named 'sysscripts' (D-07)."""
        for parent in script_path.parents:
            if parent.name == "sysscripts":
                return parent
        raise ValueError(f"No 'sysscripts/' ancestor found for: {script_path}")

    def _resolve_load(
        self,
        load_path: str,
        script_dir: pathlib.Path,
        sysscripts_root: pathlib.Path,
    ) -> pathlib.Path:
        """Resolve a load() path and enforce sandbox (D-05, D-06, T-04-01, T-04-02).

        Resolves load_path relative to script_dir, then verifies the resolved absolute
        path is within sysscripts_root. pathlib.resolve() follows symlinks before
        comparison (T-04-02: symlink pointing outside sandbox is caught).
        """
        resolved = (script_dir / load_path).resolve()
        root = sysscripts_root.resolve()
        # Check both startswith(root + sep) and == root (Pitfall 6 guard)
        if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
            raise ValueError(f"load({load_path!r}): path traversal not allowed")
        return resolved

    def run(self, script_path: str) -> dict:
        """Execute a .star file and return its final globals dict.

        Resolves and pre-executes all load() targets in order, sharing a single
        globals dict so lib functions are available in the main script.
        """
        path = pathlib.Path(script_path).resolve()
        root = self._find_sysscripts_root(path)
        content = path.read_text()

        globs = {"sys": self._sys}

        # Pre-execute load() targets (in order found) into shared globals
        for m in _LOAD_PATTERN.finditer(content):
            lib_path = self._resolve_load(m.group(1), path.parent, root)
            lib_src = lib_path.read_text()
            # Strip nested load() from lib (recursive resolution not needed for MVP)
            lib_src_clean = _LOAD_PATTERN.sub("", lib_src)
            exec(compile(lib_src_clean, str(lib_path), "exec"), globs)

        # Strip load() statements from main script then execute
        main_src = _LOAD_PATTERN.sub("", content)
        exec(compile(main_src, str(path), "exec"), globs)
        return globs
