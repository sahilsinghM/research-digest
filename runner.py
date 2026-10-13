"""Run one headless Claude Code call on the owner's subscription: text in, text out, nothing else."""
import json
import subprocess
import tempfile


class RunnerError(Exception):
    pass


# Measured on a machine with many plugins: unisolated, one trivial call loaded ~243k tokens; isolated, ~575.
ISOLATION = ["--tools", "", "--setting-sources", "project,local", "--strict-mcp-config",
             "--disable-slash-commands", "--no-session-persistence", "--output-format", "json"]


def claude(model, system, user, timeout=300):
    with tempfile.TemporaryDirectory() as empty_cwd:
        p = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", system, *ISOLATION],
                           input=user, capture_output=True, text=True, timeout=timeout, cwd=empty_cwd)
    if p.returncode != 0:
        raise RunnerError(f"claude exited {p.returncode}: {(p.stderr or p.stdout)[:300]}")
    out = json.loads(p.stdout)
    if out.get("is_error"):
        raise RunnerError(str(out.get("result"))[:300])
    return out["result"]
