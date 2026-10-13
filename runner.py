"""Run one headless Claude Code call on the owner's subscription: text in, text out, nothing else."""
import json
import os
import re
import subprocess
import tempfile


class RunnerError(Exception):
    pass


class UsageLimitReached(RunnerError):
    """The subscription's session or weekly allowance is used up."""


# Measured on a machine with many plugins: unisolated, one trivial call loaded ~243k tokens; isolated, ~575.
ISOLATION = ["--tools", "", "--setting-sources", "project,local", "--strict-mcp-config",
             "--disable-slash-commands", "--no-session-persistence", "--output-format", "json"]

# Anything here would override the subscription login (or route billing elsewhere), so the child never sees it.
STRIPPED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")

# ponytail: the exit code / JSON for a limit hit is undocumented; this matches the documented message text
# ("You've hit your session limit", "...weekly limit"). Tighten after observing a real one (issue 07).
LIMIT = re.compile(r"hit your .{0,20}limit", re.I)


def _env():
    return {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}


def _run(args, user=None, timeout=300):
    with tempfile.TemporaryDirectory() as empty_cwd:
        try:
            return subprocess.run(["claude", *args], input=user, capture_output=True, text=True,
                                  timeout=timeout, cwd=empty_cwd, env=_env())
        except subprocess.TimeoutExpired:
            raise RunnerError(f"claude timed out after {timeout}s") from None


def claude(model, system, user, timeout=300):
    p = _run(["-p", "--model", model, "--system-prompt", system, *ISOLATION], user, timeout)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    text = str(out.get("result", "")) if isinstance(out, dict) else p.stdout
    failed = p.returncode != 0 or not isinstance(out, dict) or out.get("is_error")
    # A limit message can arrive as a failed call, or as the result text of an "ok" one. In the "ok" case the
    # model must have generated nothing: text that merely imitates the message (e.g. via a prompt-injected
    # abstract) always comes with output tokens and must not stop the run.
    generated = isinstance(out, dict) and (out.get("usage") or {}).get("output_tokens", 0) > 0
    if LIMIT.search(text) and (failed or (LIMIT.search(text.lstrip()[:60]) and not generated)):
        raise UsageLimitReached(text[:200])
    if failed:
        raise RunnerError(f"claude exited {p.returncode}: {(text or p.stderr)[:300]}")
    return out["result"]


def check_login():
    """Fail fast unless Claude Code is logged in with a subscription. Returns the plan name."""
    p = _run(["auth", "status"], timeout=30)
    try:
        status = json.loads(p.stdout)
    except ValueError:
        status = None
    if p.returncode != 0 or not isinstance(status, dict) or not status.get("loggedIn"):
        raise RunnerError("Claude Code is not logged in: run `claude setup-token` and set CLAUDE_CODE_OAUTH_TOKEN")
    if status.get("authMethod") == "api_key":
        raise RunnerError("Claude Code is using an API key; this tool must use the subscription")
    return status.get("subscriptionType", "unknown")
