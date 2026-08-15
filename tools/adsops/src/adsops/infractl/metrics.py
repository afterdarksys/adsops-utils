"""Prometheus node_exporter metrics commands for infractl.

Read commands (show, top, query) fetch /metrics over HTTP directly — no SSH
needed. Write commands (install, service) run scripts over SSH.

Threat model:
- T-02-09: Hosts are validated to contain no shell metacharacters before being
  embedded in HTTP URLs or SSH command strings.
"""
import base64
import fnmatch
import math
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from adsops.infractl.ssh import run_sync

_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9._\-]+$")

DEFAULT_PORT = 9100
DEFAULT_VERSION = "1.8.2"


def _validate_host(host: str) -> None:
    """Raise ValueError if host contains shell metacharacters (T-02-09)."""
    if not _SAFE_HOST_RE.match(host):
        raise ValueError(f"Invalid hostname {host!r}: must match [a-zA-Z0-9._-]")


# ---------------------------------------------------------------------------
# Prometheus text format parser
# ---------------------------------------------------------------------------


@dataclass
class Sample:
    name: str
    labels: dict[str, str] = field(default_factory=dict)
    value: float = 0.0


def _parse_labels(s: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    while s:
        s = s.strip()
        eq = s.find('="')
        if eq < 0:
            break
        key = s[:eq].strip()
        s = s[eq + 2:]
        chars: list[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == '\\' and i + 1 < len(s):
                i += 1
                chars.append({'n': '\n', '\\': '\\', '"': '"'}.get(s[i], s[i]))
            elif c == '"':
                s = s[i + 1:]
                break
            else:
                chars.append(c)
            i += 1
        labels[key] = ''.join(chars)
        s = s.lstrip(',')
    return labels


def _parse_sample(line: str) -> Optional[Sample]:
    name_end = next((i for i, c in enumerate(line) if c in ('{', ' ')), -1)
    if name_end < 0:
        return None
    name = line[:name_end]
    rest = line[name_end:]
    labels: dict[str, str] = {}
    if rest.startswith('{'):
        end = rest.find('}')
        if end < 0:
            return None
        labels = _parse_labels(rest[1:end])
        rest = rest[end + 1:].strip()
    else:
        rest = rest.strip()
    parts = rest.split()
    if not parts:
        return None
    try:
        val = float(parts[0])
    except ValueError:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return Sample(name=name, labels=labels, value=val)


def _parse_metrics(text: str) -> list[Sample]:
    samples = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        s = _parse_sample(line)
        if s is not None:
            samples.append(s)
    return samples


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _find_first(samples: list[Sample], name: str) -> Optional[Sample]:
    return next((s for s in samples if s.name == name), None)


def _find_all(samples: list[Sample], name: str) -> list[Sample]:
    return [s for s in samples if s.name == name]


def _label_value(samples: list[Sample], name: str, label: str) -> str:
    for s in samples:
        if s.name == name:
            return s.labels.get(label, '')
    return ''


def _filter(samples: list[Sample], pattern: str) -> list[Sample]:
    if not pattern:
        return samples
    if '*' in pattern:
        return [s for s in samples if fnmatch.fnmatch(s.name, pattern)]
    return [s for s in samples if pattern in s.name]


def _fetch(host: str, port: int, timeout: float = 10.0) -> list[Sample]:
    _validate_host(host)
    url = f'http://{host}:{port}/metrics'
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return _parse_metrics(resp.read().decode('utf-8', errors='replace'))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_BYTE_UNITS = [('PiB', 1024**5), ('TiB', 1024**4), ('GiB', 1024**3),
               ('MiB', 1024**2), ('KiB', 1024)]


def _fmt_bytes(b: float) -> str:
    for name, div in _BYTE_UNITS:
        if b >= div:
            return f'{b / div:.1f} {name}'
    return f'{b:.0f} B'


def _fmt_uptime(boot_ts: float) -> str:
    d = int(time.time() - boot_ts)
    days, rem = divmod(d, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return f'{days}d {hours}h {mins}m'
    if hours:
        return f'{hours}h {mins}m'
    return f'{mins}m'


def _fmt_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ''
    return '{' + ','.join(f'{k}="{v}"' for k, v in sorted(labels.items())) + '}'


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------


def _compute_cpu(samples: list[Sample]) -> tuple[float, int]:
    total = idle = 0.0
    cores: set[str] = set()
    for s in _find_all(samples, 'node_cpu_seconds_total'):
        total += s.value
        if s.labels.get('mode') == 'idle':
            idle += s.value
        if 'cpu' in s.labels:
            cores.add(s.labels['cpu'])
    pct = (total - idle) / total * 100 if total > 0 else 0.0
    return pct, len(cores)


def _compute_mem(samples: list[Sample]) -> tuple[float, float, float]:
    tot = _find_first(samples, 'node_memory_MemTotal_bytes')
    avail = _find_first(samples, 'node_memory_MemAvailable_bytes')
    if not tot or not avail:
        return 0.0, 0.0, 0.0
    used = tot.value - avail.value
    pct = used / tot.value * 100 if tot.value > 0 else 0.0
    return used, tot.value, pct


def _compute_root_disk(samples: list[Sample]) -> tuple[float, float, float]:
    size_s = next((s for s in _find_all(samples, 'node_filesystem_size_bytes')
                   if s.labels.get('mountpoint') == '/'), None)
    avail_s = next((s for s in _find_all(samples, 'node_filesystem_avail_bytes')
                    if s.labels.get('mountpoint') == '/'), None)
    if not size_s:
        return 0.0, 0.0, 0.0
    avail = avail_s.value if avail_s else 0.0
    used = size_s.value - avail
    pct = used / size_s.value * 100 if size_s.value > 0 else 0.0
    return used, size_s.value, pct


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_SKIP_FS = {
    'tmpfs', 'devtmpfs', 'sysfs', 'proc', 'cgroup', 'cgroup2', 'pstore',
    'securityfs', 'debugfs', 'tracefs', 'configfs', 'fusectl', 'mqueue',
    'hugetlbfs', 'rpc_pipefs', 'nfsd', 'overlay', 'squashfs', 'nsfs', 'efivarfs',
}
_VIRTUAL_IFACE = ('docker', 'veth', 'br-', 'flannel', 'cni', 'tunl', 'wg')


def _pct_color(pct: float, text: str, warn: float = 75, crit: float = 90) -> str:
    if pct > crit:
        return f'\033[31m{text}\033[0m'
    if pct > warn:
        return f'\033[33m{text}\033[0m'
    return f'\033[32m{text}\033[0m'


def _print_filesystems(samples: list[Sample]) -> None:
    size_map: dict[str, dict[str, float]] = {}
    for s in _find_all(samples, 'node_filesystem_size_bytes'):
        mp = s.labels.get('mountpoint', '')
        if mp and s.labels.get('fstype', '') not in _SKIP_FS:
            size_map.setdefault(mp, {})['size'] = s.value
    for s in _find_all(samples, 'node_filesystem_avail_bytes'):
        mp = s.labels.get('mountpoint', '')
        if mp in size_map:
            size_map[mp]['avail'] = s.value

    for mp in sorted(size_map, key=lambda m: (m != '/', m)):
        size = size_map[mp].get('size', 0)
        avail = size_map[mp].get('avail', 0)
        if not size:
            continue
        used = size - avail
        pct = used / size * 100
        print(f'  {mp:<24} {_fmt_bytes(used)} / {_fmt_bytes(size)}  ({_pct_color(pct, f"{pct:.1f}%")})')


def _print_network(samples: list[Sample]) -> None:
    rx: dict[str, float] = {}
    tx: dict[str, float] = {}
    for s in _find_all(samples, 'node_network_receive_bytes_total'):
        dev = s.labels.get('device', '')
        if dev and dev != 'lo' and not any(dev.startswith(p) for p in _VIRTUAL_IFACE):
            rx[dev] = s.value
    for s in _find_all(samples, 'node_network_transmit_bytes_total'):
        dev = s.labels.get('device', '')
        if dev and dev != 'lo' and not any(dev.startswith(p) for p in _VIRTUAL_IFACE):
            tx[dev] = s.value
    for dev in sorted(rx):
        print(f'  {dev:<24} RX {_fmt_bytes(rx[dev]):<12} TX {_fmt_bytes(tx.get(dev, 0))}')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def metrics_show(host: str, port: int = DEFAULT_PORT) -> None:
    """Fetch and print a metrics summary for a single host."""
    samples = _fetch(host, port)
    print(f'\n\033[1;36m── node_exporter: {host} \033[0m')

    ver = _label_value(samples, 'node_exporter_build_info', 'version')
    go_ver = _label_value(samples, 'node_exporter_build_info', 'goversion')
    if ver:
        print(f'  \033[1m{"version:":<20}\033[0m v{ver} ({go_ver})' if go_ver
              else f'  \033[1m{"version:":<20}\033[0m v{ver}')

    release = _label_value(samples, 'node_uname_info', 'release')
    machine = _label_value(samples, 'node_uname_info', 'machine')
    if release:
        print(f'  \033[1m{"kernel:":<20}\033[0m Linux {release} ({machine})')

    boot = _find_first(samples, 'node_boot_time_seconds')
    if boot:
        print(f'  \033[1m{"uptime:":<20}\033[0m {_fmt_uptime(boot.value)}')

    print()
    l1 = _find_first(samples, 'node_load1')
    l5 = _find_first(samples, 'node_load5')
    l15 = _find_first(samples, 'node_load15')
    print(f'  \033[1m{"LOAD:":<20}\033[0m '
          f'{(l1.value if l1 else 0):.2f} / '
          f'{(l5.value if l5 else 0):.2f} / '
          f'{(l15.value if l15 else 0):.2f}  (1m/5m/15m)')

    cpu_pct, cores = _compute_cpu(samples)
    cpu_str = f'{cpu_pct:.1f}% used  ({cores} cores)'
    print(f'  \033[1m{"CPU:":<20}\033[0m {_pct_color(cpu_pct, cpu_str, 80, 90)}')

    mem_used, mem_total, mem_pct = _compute_mem(samples)
    mem_str = f'{_fmt_bytes(mem_used)} / {_fmt_bytes(mem_total)}  ({mem_pct:.1f}%)'
    print(f'  \033[1m{"MEMORY:":<20}\033[0m {_pct_color(mem_pct, mem_str, 80, 90)}')

    swap_tot = _find_first(samples, 'node_memory_SwapTotal_bytes')
    swap_free = _find_first(samples, 'node_memory_SwapFree_bytes')
    if swap_tot and swap_tot.value > 0:
        swap_used = swap_tot.value - (swap_free.value if swap_free else 0.0)
        swap_pct = swap_used / swap_tot.value * 100
        swap_str = f'{_fmt_bytes(swap_used)} / {_fmt_bytes(swap_tot.value)}  ({swap_pct:.1f}%)'
        print(f'  \033[1m{"SWAP:":<20}\033[0m {_pct_color(swap_pct, swap_str, 50, 80)}')

    print(f'\n  \033[1m{"FILESYSTEM":<20}\033[0m')
    _print_filesystems(samples)

    print(f'\n  \033[1m{"NETWORK":<20}\033[0m (cumulative bytes since boot)')
    _print_network(samples)
    print()


def metrics_top(
    hosts: list[str],
    port: int = DEFAULT_PORT,
    sort_by: Optional[str] = None,
    warn_cpu: float = 0,
    warn_mem: float = 0,
    warn_disk: float = 0,
) -> None:
    """Print a compact vitals table for multiple hosts in parallel."""

    def _fetch_top(host: str) -> dict:
        try:
            samples = _fetch(host, port)
            l1 = _find_first(samples, 'node_load1')
            cpu_pct, _ = _compute_cpu(samples)
            _, _, mem_pct = _compute_mem(samples)
            _, _, disk_pct = _compute_root_disk(samples)
            ver = _label_value(samples, 'node_exporter_build_info', 'version')
            return {'load1': l1.value if l1 else 0.0, 'cpu_pct': cpu_pct,
                    'mem_pct': mem_pct, 'disk_pct': disk_pct, 'version': ver}
        except Exception as exc:
            return {'error': str(exc)}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_top, h): h for h in hosts}
        raw = {futs[f]: f.result() for f in as_completed(futs)}

    rows = [(h, raw[h]) for h in hosts]

    if sort_by:
        key_map = {'load': 'load1', 'cpu': 'cpu_pct', 'mem': 'mem_pct', 'disk': 'disk_pct'}
        col = key_map.get(sort_by)
        if col:
            rows.sort(key=lambda x: x[1].get(col, -1) if 'error' not in x[1] else -1,
                      reverse=True)

    if warn_cpu > 0 or warn_mem > 0 or warn_disk > 0:
        rows = [
            (h, r) for h, r in rows
            if 'error' not in r and (
                (warn_cpu > 0 and r['cpu_pct'] >= warn_cpu) or
                (warn_mem > 0 and r['mem_pct'] >= warn_mem) or
                (warn_disk > 0 and r['disk_pct'] >= warn_disk)
            )
        ]

    print(f'\n{"HOST":<24} {"LOAD1":<8} {"CPU%":<7} {"MEM%":<7} {"DISK(/)":<9} VERSION')
    print('─' * 70)
    for host, r in rows:
        if 'error' in r:
            print(f'{host:<24} \033[31mFAIL  {r["error"]}\033[0m')
            continue
        cpu_str = f'{r["cpu_pct"]:.1f}%'.ljust(6)
        mem_str = f'{r["mem_pct"]:.1f}%'.ljust(6)
        disk_str = f'{r["disk_pct"]:.1f}%'.ljust(8)
        print(f'{host:<24} {r["load1"]:<8.2f} '
              f'{_pct_color(r["cpu_pct"], cpu_str, 80, 90)} '
              f'{_pct_color(r["mem_pct"], mem_str, 80, 90)} '
              f'{_pct_color(r["disk_pct"], disk_str)} v{r["version"]}')
    print()


def metrics_query(pattern: str, hosts: list[str], port: int = DEFAULT_PORT) -> None:
    """Query metrics matching a pattern across one or more hosts."""
    for host in hosts:
        try:
            samples = _fetch(host, port)
        except Exception as exc:
            print(f'{host}: \033[31m{exc}\033[0m')
            continue
        matched = _filter(samples, pattern)
        if not matched:
            print(f'{host}: no metrics match {pattern!r}')
            continue
        if len(hosts) > 1:
            print(f'\n\033[1;36m── {host} \033[0m')
        print(f'\n{"METRIC":<50} {"LABELS":<40} VALUE')
        print('─' * 100)
        for s in matched:
            val_str = str(int(s.value)) if (s.value == int(s.value) and abs(s.value) < 1e15) else f'{s.value:g}'
            print(f'{s.name:<50} {_fmt_labels(s.labels):<40} {val_str}')
        print(f'\n{len(matched)} metric(s) matched\n')


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

_NODE_EXPORTER_UNIT = """\
[Unit]
Description=Prometheus Node Exporter
Documentation=https://prometheus.io/docs/guides/node-exporter/
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter
SyslogIdentifier=node_exporter
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""


def _build_install_script(version: str) -> str:
    unit_b64 = base64.b64encode(_NODE_EXPORTER_UNIT.encode()).decode()
    return f"""\
set -e
VERSION={version}
TARBALL=node_exporter-${{VERSION}}.linux-amd64.tar.gz
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

if [ -x /usr/local/bin/node_exporter ]; then
    INSTALLED=$(/usr/local/bin/node_exporter --version 2>&1 | grep -oE '[0-9]+\\.[0-9]+\\.[0-9]+' | head -1 || true)
    if [ "$INSTALLED" = "$VERSION" ]; then
        echo "STATUS=already_installed"
        echo "VERSION=$VERSION"
        exit 0
    fi
    echo "UPGRADE_FROM=$INSTALLED"
fi

URL="https://github.com/prometheus/node_exporter/releases/download/v${{VERSION}}/${{TARBALL}}"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$TMPDIR/$TARBALL" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TMPDIR/$TARBALL" "$URL"
else
    echo "STATUS=error:no_downloader"; exit 1
fi

tar xzf "$TMPDIR/$TARBALL" -C "$TMPDIR"
cp "$TMPDIR/node_exporter-${{VERSION}}.linux-amd64/node_exporter" /usr/local/bin/node_exporter
chmod 755 /usr/local/bin/node_exporter

id node_exporter >/dev/null 2>&1 || \\
    useradd -r -s /sbin/nologin -d /nonexistent -c "Prometheus Node Exporter" node_exporter

echo '{unit_b64}' | base64 -d > /etc/systemd/system/node_exporter.service
systemctl daemon-reload
systemctl enable node_exporter
systemctl restart node_exporter
STATUS=$(systemctl is-active node_exporter 2>/dev/null || echo "failed")
echo "STATUS=$STATUS"
echo "VERSION=$VERSION"
"""


def metrics_install(hosts: list[str], version: str = DEFAULT_VERSION) -> None:
    """Install node_exporter on one or more remote hosts via SSH (parallel)."""

    def _do_install(host: str) -> dict:
        try:
            stdout, _ = run_sync(host, _build_install_script(version))
            info: dict[str, str] = {}
            for line in stdout.splitlines():
                kv = line.strip().split('=', 1)
                if len(kv) == 2:
                    info[kv[0]] = kv[1]
            return {'info': info}
        except Exception as exc:
            return {'error': str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(_do_install, h): h for h in hosts}
        raw = {futs[f]: f.result() for f in as_completed(futs)}

    for host in hosts:
        r = raw[host]
        print(f'\033[1m{host}\033[0m:')
        if 'error' in r:
            print(f'  \033[31m{r["error"]}\033[0m\n')
            continue

        info = r['info']
        status = info.get('STATUS', '')
        installed_ver = info.get('VERSION', '')
        upgrade_from = info.get('UPGRADE_FROM', '')

        if status == 'already_installed':
            print(f'  already at v{installed_ver} — nothing to do')
        elif status == 'active':
            if upgrade_from:
                print(f'  upgraded v{upgrade_from} → v{installed_ver}')
            else:
                print(f'  installed v{installed_ver}')
            print(f'  service: \033[32mactive (running)\033[0m')
        else:
            print(f'  \033[33mWARNING\033[0m  status={status}')
        print()


def metrics_service(action: str, hosts: list[str]) -> None:
    """Run a systemctl action against node_exporter on remote hosts."""
    for host in hosts:
        try:
            stdout, stderr = run_sync(host, f'systemctl {action} node_exporter 2>&1')
            out = (stdout or stderr or '').strip()
            if action == 'status':
                print(f'\033[1m{host}\033[0m:')
                for line in out.splitlines():
                    print(f'  {line}')
            else:
                print(f'{host}: \033[32m{action} OK\033[0m')
        except Exception as exc:
            print(f'{host}: \033[31mFAIL  {exc}\033[0m')
