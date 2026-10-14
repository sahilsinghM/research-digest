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
             "--disable-slash-commands", "--no-session-persistence", "--max-turns", "1", "--output-format", "json"]

# The child gets an allow-list, not a filtered copy: any credential or endpoint override (ANTHROPIC_API_KEY,
# ANTHROPIC_BASE_URL, cloud-provider switches, ...) could bill something other than the subscription or send
# the prompts elsewhere. Only what claude needs to run, plus the subscription token, passes through.
SAFE_ENV = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "TMPDIR", "TZ", "SHELL", "TERM",
            "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy", "all_proxy"}
SUBSCRIPTION_LOGINS = {"claude.ai", "oauth_token"}

# Wording taken from the strings inside the Claude Code program itself (v2.1.296): "You've hit your session /
# weekly / Opus / Sonnet / Fable / fast limit", "monthly spend limit", "team's shared budget", "You've reached your
# ... limit", "You're out of (extra) usage (credits)", "Usage limit reached", "Credit balance is too low".
# The exit code / JSON for a limit hit is still undocumented, so the text decides; real hits are logged (issue 07).
LIMIT = re.compile(r"hit your .{0,40}?(limit|budget)|reached your .{0,20}limit|out of (extra )?usage"
                   r"|usage limit reached|credit balance (is )?too low", re.I)


def _env():
    return {k: v for k, v in os.environ.items() if k in SAFE_ENV or k.startswith(("LC_", "XDG_"))}


def _run(args, user=None, timeout=300):
    with tempfile.TemporaryDirectory() as empty_cwd:
        try:
            return subprocess.run(["claude", *args], input=user, capture_output=True, text=True,
                                  timeout=timeout, cwd=empty_cwd, env=_env())
        except subprocess.TimeoutExpired:
            raise RunnerError(f"claude timed out after {timeout}s") from None


def claude(model, system, user, timeout=300):
    # The system prompt embeds the owner's private profile; argv is readable by every local user, so it goes
    # through a 0600 file in a private directory (separate from the empty working directory).
    with tempfile.TemporaryDirectory() as private:
        prompt_file = os.path.join(private, "system.txt")
        fd = os.open(prompt_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(system)
        p = _run(["-p", "--model", model, "--system-prompt-file", prompt_file, *ISOLATION], user, timeout)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    text = str(out.get("result", "")) if isinstance(out, dict) else p.stdout
    failed = p.returncode != 0 or not isinstance(out, dict) or out.get("is_error") or "result" not in out
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
    if status.get("authMethod") not in SUBSCRIPTION_LOGINS:
        raise RunnerError(f"Claude Code login is {status.get('authMethod')!r}; this tool must use the subscription")
    return status.get("subscriptionType", "unknown")
