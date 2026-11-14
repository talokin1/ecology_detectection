r"""24/7 supervisor for the field-team data pipeline (see scripts/PIPELINE.md).

Runs forever. On start, and whenever a watched branch gets a new commit (polled every
``SPACEAPPS_POLL_SECONDS``, default 300) or the team touches the trigger file, it:

  1. channel  - checks the Cloudflare tunnel (best effort: logged, never blocks the data steps);
  2. ukraine  - ``scripts/pipeline_load.py --stage ukraine`` from the deploy checkout;
  3. world    - ``scripts/pipeline_load.py --stage world``;
  4. ukraine_slow - ``scripts/pipeline_load.py --stage ukraine_slow`` (slow Earthdata series).

The loader always runs from a dedicated *deploy checkout* (never the team's working copy), which
is only ever fast-forwarded (``git merge --ff-only``) and never touched if it has uncommitted
changes. A new commit that arrives during a run is picked up between stages (the run restarts).
One daemon at a time (exclusive lock on ``<state>/daemon.lock``, see file_lock.py); loader runs
hold ``<state>/run.lock``.
Status for humans and scripts: ``<state>/status.json``. Logs: ``<logs>/``.

Configuration (environment variables; defaults in brackets):
    SPACEAPPS_HOME          [/srv/spaceapps]  root of data/, logs/, state/, deploy/
    SPACEAPPS_DATA_DIR      [$HOME/data]      loader output (ukraine/, world/)
    SPACEAPPS_LOG_DIR       [$HOME/logs]
    SPACEAPPS_STATE_DIR     [$HOME/state]     status.json, locks, trigger file "rerun"
    SPACEAPPS_DEPLOY_DIR    [$HOME/deploy]    deploy checkout (cloned on first start)
    SPACEAPPS_SOURCES       ["github=https://github.com/talokin1/ecology_detectection.git#experimental"]
                            space-separated name=url#branch; the newest commit that is a fast-forward
                            of the deploy checkout wins (e.g. add "team=/srv/spaceapps/repo#experimental")
    SPACEAPPS_POLL_SECONDS  [300]
    SPACEAPPS_RETRY_SECONDS [1800]           re-run after a failed stage
    SPACEAPPS_PYTHON        [this interpreter]
    SPACEAPPS_TUNNEL_READY_URL [http://127.0.0.1:20241/ready]  cloudflared --metrics readiness URL
    SPACEAPPS_TUNNEL_HOOK   [unset]          optional command that starts/checks the tunnel (exit 0 = up)

Secrets (EARTHDATA_TOKEN) are inherited from the environment and passed to the loader; they are
never logged or written to the status file.

SI-assisted (GOD / Grok Bot, data-entry agent, 2026-11-14); pending team review (docs/08-si-usage-log.md).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from file_lock import lock  # fcntl on Linux/macOS, msvcrt on Windows

DEFAULT_SOURCES = "github=https://github.com/talokin1/ecology_detectection.git#experimental"
STAGES = ("ukraine", "world", "ukraine_slow")
_CRED_RE = re.compile(r"(https?://)[^/@\s]+@")

log = logging.getLogger("pipeline_daemon")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(text: str) -> str:
    """Remove credentials embedded in URLs from text before logging it."""
    return _CRED_RE.sub(r"\1***@", text or "")


class Config:
    def __init__(self, env=os.environ):
        self.home = Path(env.get("SPACEAPPS_HOME", "/srv/spaceapps"))
        self.data = Path(env.get("SPACEAPPS_DATA_DIR", self.home / "data"))
        self.logs = Path(env.get("SPACEAPPS_LOG_DIR", self.home / "logs"))
        self.state = Path(env.get("SPACEAPPS_STATE_DIR", self.home / "state"))
        self.deploy = Path(env.get("SPACEAPPS_DEPLOY_DIR", self.home / "deploy"))
        self.sources = parse_sources(env.get("SPACEAPPS_SOURCES", DEFAULT_SOURCES))
        self.poll = int(env.get("SPACEAPPS_POLL_SECONDS", "300"))
        self.retry = int(env.get("SPACEAPPS_RETRY_SECONDS", "1800"))
        self.python = env.get("SPACEAPPS_PYTHON", sys.executable)
        self.tunnel_url = env.get("SPACEAPPS_TUNNEL_READY_URL", "http://127.0.0.1:20241/ready")
        self.tunnel_hook = env.get("SPACEAPPS_TUNNEL_HOOK", "")

    @property
    def trigger(self) -> Path:
        return self.state / "rerun"


def parse_sources(spec: str) -> list[tuple[str, str, str]]:
    """``name=url#branch ...`` -> [(name, url, branch)]."""
    out = []
    for item in spec.split():
        name, _, rest = item.partition("=")
        url, _, branch = rest.rpartition("#")
        if not name or not url or not branch:
            raise ValueError(f"bad SPACEAPPS_SOURCES entry {scrub(item)!r}; want name=url#branch")
        out.append((name, url, branch))
    return out


# --- status file ---------------------------------------------------------------------------------


class Status:
    def __init__(self, path: Path):
        self.path = path
        self.data = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                self.data = {}
        self.data.update({"daemon": {"pid": os.getpid(), "host": socket.gethostname(), "started": _now()}})
        self.data.setdefault("steps", {})
        self.save()

    def set(self, **kw) -> None:
        self.data.update(kw)
        self.data["updated"] = _now()
        self.save()

    def step(self, name: str, state: str, **kw) -> None:
        s = self.data["steps"].setdefault(name, {})
        s["state"] = state
        if state == "running":
            s["started"] = _now()
            s.pop("finished", None)
        elif state not in ("pending",):
            s["finished"] = _now()
        s.update(kw)
        self.data["current_step"] = name if state == "running" else self.data.get("current_step")
        self.set()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o644)
        tmp.replace(self.path)


# --- git -----------------------------------------------------------------------------------------


def git(repo: Path, *args: str, check: bool = True, timeout: int = 300) -> str:
    cmd = ["git", "-c", "safe.directory=*", "-C", str(repo), *args]
    env = os.environ | {"GIT_TERMINAL_PROMPT": "0"}
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed ({r.returncode}): {scrub(r.stderr.strip())[-500:]}")
    return r.stdout.strip()


def ensure_deploy(cfg: Config) -> None:
    """Clone the deploy checkout on first start; keep its remotes in line with SPACEAPPS_SOURCES."""
    if not (cfg.deploy / ".git").exists():
        name, url, branch = cfg.sources[0]
        log.info("cloning deploy checkout from %s (%s) into %s", name, branch, cfg.deploy)
        cfg.deploy.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["git", "clone", "-o", name, "-b", branch, url, str(cfg.deploy)],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(f"clone failed: {scrub(r.stderr.strip())[-500:]}")
    remotes = set(git(cfg.deploy, "remote").split())
    for name, url, _ in cfg.sources:
        if name in remotes:
            git(cfg.deploy, "remote", "set-url", name, url)
        else:
            git(cfg.deploy, "remote", "add", name, url)


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return (
        subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def poll_and_update(cfg: Config) -> dict:
    """Fetch every source; fast-forward the deploy checkout to the newest reachable commit.

    Returns {"head", "changed", "source", "note"}. Never resets, rebases or discards local work.
    """
    head = git(cfg.deploy, "rev-parse", "HEAD")
    candidates: list[tuple[str, str]] = []
    notes = []
    for name, _, branch in cfg.sources:
        try:
            git(cfg.deploy, "fetch", "--quiet", name, f"+refs/heads/{branch}:refs/remotes/{name}/{branch}")
            candidates.append((name, git(cfg.deploy, "rev-parse", f"refs/remotes/{name}/{branch}")))
        except Exception as exc:  # noqa: BLE001 - one unreachable source must not stop the others
            notes.append(f"{name}: fetch failed: {exc}")
    ahead = [(n, c) for n, c in candidates if c != head and is_ancestor(cfg.deploy, head, c)]
    for n, c in candidates:
        if c != head and not is_ancestor(cfg.deploy, head, c) and not is_ancestor(cfg.deploy, c, head):
            notes.append(f"{n} has diverged from the deploy checkout ({c[:10]}); not a fast-forward, ignored")
    if not ahead:
        return {"head": head, "changed": False, "source": None, "note": "; ".join(notes)}
    # newest = a candidate that contains all the others
    best = ahead[0]
    for n, c in ahead[1:]:
        if is_ancestor(cfg.deploy, best[1], c):
            best = (n, c)
    dirty = git(cfg.deploy, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        notes.append(f"deploy checkout has uncommitted changes; NOT updating to {best[0]} {best[1][:10]}")
        return {"head": head, "changed": False, "source": None, "note": "; ".join(notes)}
    git(cfg.deploy, "merge", "--ff-only", "--quiet", best[1])
    return {"head": best[1], "changed": True, "source": best[0], "note": "; ".join(notes)}


def commit_info(cfg: Config, sha: str) -> dict:
    line = git(cfg.deploy, "log", "-1", "--format=%H%x1f%h%x1f%s%x1f%cI", sha)
    full, short, subject, date = line.split("\x1f")
    return {"sha": full, "short": short, "subject": subject, "committed": date}


# --- steps ---------------------------------------------------------------------------------------


def channel_step(cfg: Config) -> tuple[str, str]:
    """Best-effort tunnel check. Returns (state, message); never raises."""
    if cfg.tunnel_hook:
        try:
            r = subprocess.run(
                shlex.split(cfg.tunnel_hook), capture_output=True, text=True, timeout=120, check=False
            )
            msg = scrub((r.stdout + r.stderr).strip())[-300:]
            return ("up" if r.returncode == 0 else "down"), msg or f"hook exit {r.returncode}"
        except Exception as exc:  # noqa: BLE001
            return "down", f"tunnel hook failed: {type(exc).__name__}: {exc}"
    try:
        with urllib.request.urlopen(cfg.tunnel_url, timeout=5) as resp:
            body = resp.read(500).decode("utf-8", "replace")
            return "up", f"cloudflared ready: {body.strip()[:200]}"
    except urllib.error.HTTPError as exc:  # 503 = running but no connection to Cloudflare's edge
        return "down", f"cloudflared running but not connected (HTTP {exc.code} from {cfg.tunnel_url})"
    except Exception as exc:  # noqa: BLE001
        return (
            "not_running",
            f"no cloudflared metrics at {cfg.tunnel_url} ({type(exc).__name__}); "
            "tunnel not configured or not started",
        )


def _rotate(path: Path, max_bytes: int = 20_000_000) -> None:
    if path.exists() and path.stat().st_size > max_bytes:
        path.replace(path.with_name(path.name + ".1"))


def run_stage(cfg: Config, stage: str) -> int:
    log_path = cfg.logs / f"{stage}.log"
    _rotate(log_path)
    cmd = [
        cfg.python,
        str(cfg.deploy / "scripts" / "pipeline_load.py"),
        "--stage",
        stage,
        "--data-dir",
        str(cfg.data),
        "--lock",
        str(cfg.state / "run.lock"),
    ]
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n===== {_now()} {stage} (deploy {git(cfg.deploy, 'rev-parse', '--short', 'HEAD')}) =====\n"
        )
        fh.flush()
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=cfg.deploy, check=False)
    return r.returncode


def stage_summary(cfg: Config, stage: str) -> dict:
    p = cfg.data / ("world" if stage == "world" else "ukraine") / "STAGE_STATUS.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"counts": d.get("counts"), "loader_state": d.get("state")}
    except (OSError, ValueError):
        return {}


# --- main loop -----------------------------------------------------------------------------------

_stop = False


def _on_signal(signum, _frame):
    global _stop
    _stop = True
    log.info("signal %d: stopping after the current step", signum)


def setup_logging(cfg: Config) -> None:
    cfg.logs.mkdir(parents=True, exist_ok=True)
    logging.Formatter.converter = time.gmtime
    fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S")
    fh = logging.handlers.RotatingFileHandler(cfg.logs / "pipeline.log", maxBytes=10_000_000, backupCount=3)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[fh, sh])


def sleep_until(cfg: Config, seconds: float) -> None:
    end = time.monotonic() + seconds
    while not _stop and time.monotonic() < end and not cfg.trigger.exists():
        time.sleep(min(5, max(0, end - time.monotonic())))


def run_pipeline(cfg: Config, status: Status) -> str:
    """One full run. Returns "done", "failed" or "restart" (a newer commit arrived)."""
    status.set(last_run_started=_now(), run_state="running")
    for s in ("channel", *STAGES):
        status.step(s, "pending")
    status.step("channel", "running")
    state, msg = channel_step(cfg)
    log.info("channel: %s (%s)", state, msg)
    status.step("channel", state, message=msg)  # best effort: continue whatever the result
    failed = False
    for stage in STAGES:
        if _stop:
            return "failed"
        status.step(stage, "running")
        log.info("%s: start", stage)
        code = run_stage(cfg, stage)
        result = "done" if code == 0 else "failed"
        failed |= code != 0
        log.info("%s: %s (exit %d)", stage, result, code)
        status.step(stage, result, exit_code=code, **stage_summary(cfg, stage))
        try:
            upd = poll_and_update(cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("poll between stages failed: %s", exc)
            upd = {"changed": False}
        if upd.get("changed"):
            log.info("new commit %s from %s during the run; restarting", upd["head"][:10], upd["source"])
            status.set(commit=commit_info(cfg, upd["head"]) | {"source": upd["source"]})
            return "restart"
    status.set(last_run_finished=_now(), run_state="failed" if failed else "done", current_step=None)
    return "failed" if failed else "done"


def main() -> int:
    cfg = Config()
    setup_logging(cfg)
    cfg.state.mkdir(parents=True, exist_ok=True)
    lock_fh = (cfg.state / "daemon.lock").open("w")
    try:
        lock(lock_fh, blocking=False)
    except BlockingIOError:
        log.error("another pipeline daemon holds %s; exiting", cfg.state / "daemon.lock")
        return 1
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    status = Status(cfg.state / "status.json")
    log.info(
        "daemon start: home=%s data=%s deploy=%s sources=%s poll=%ss",
        cfg.home,
        cfg.data,
        cfg.deploy,
        [scrub(f"{n}={u}#{b}") for n, u, b in cfg.sources],
        cfg.poll,
    )
    log.info("Earthdata token in environment: %s", "yes" if os.environ.get("EARTHDATA_TOKEN") else "no")

    need_run, reason, last_fail = True, "daemon start", None
    while not _stop:
        try:
            ensure_deploy(cfg)
            upd = poll_and_update(cfg)
            status.set(last_poll=_now(), poll_note=upd["note"] or None)
            if upd["note"]:
                log.warning("poll: %s", upd["note"])
            if upd["changed"]:
                need_run, reason = True, f"new commit {upd['head'][:10]} from {upd['source']}"
            if "commit" not in status.data or upd["changed"]:
                status.set(commit=commit_info(cfg, upd["head"]) | {"source": upd["source"]})
        except Exception as exc:  # noqa: BLE001 - offline / GitHub down: keep serving, retry later
            log.warning("poll failed: %s", scrub(str(exc)))
            status.set(last_poll=_now(), poll_note=scrub(str(exc))[:500])
        if cfg.trigger.exists():
            try:
                cfg.trigger.unlink()
            except OSError:
                pass
            need_run, reason = True, "trigger file"
        if not need_run and last_fail and time.monotonic() - last_fail > cfg.retry:
            need_run, reason = True, "retry after failure"
        if need_run and (cfg.deploy / "scripts" / "pipeline_load.py").exists():
            log.info("run: %s", reason)
            status.set(run_reason=reason)
            result = run_pipeline(cfg, status)
            need_run = result == "restart"
            reason = "newer commit during run" if need_run else reason
            last_fail = time.monotonic() if result == "failed" else None
            if need_run:
                continue
        elif need_run:
            log.error("deploy checkout has no scripts/pipeline_load.py; waiting for a commit that adds it")
            need_run = False
        status.set(next_poll_in_s=cfg.poll)
        sleep_until(cfg, cfg.poll)
    status.set(run_state="stopped", daemon={**status.data["daemon"], "stopped": _now()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
