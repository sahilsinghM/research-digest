import os
import stat

import pytest

import runner

AUTH_OK = '{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max"}'
OK_OUT = '{"is_error": false, "subtype": "success", "result": "hello"}'


class Fake:
    """A stand-in `claude` executable. Behaviour and observations live in files (not env vars), because the
    runner hands the child a filtered environment."""

    SCRIPT = """#!/bin/sh
D={d}
if [ "$1" = "auth" ]; then cat "$D/auth_out"; exit "$(cat "$D/auth_exit")"; fi
printf '%s\\n' "$@" > "$D/args"
env > "$D/env"
cat > "$D/stdin"
pwd > "$D/cwd"
ls -A > "$D/cwdlist"
prev=""
for a in "$@"; do
  if [ "$prev" = "--system-prompt-file" ]; then cat "$a" > "$D/sysfile"; stat -c %a "$a" > "$D/sysmode"; fi
  prev="$a"
done
[ -s "$D/sleep" ] && exec sleep "$(cat "$D/sleep")"
cat "$D/out"
exit "$(cat "$D/exit")"
"""

    def __init__(self, tmp):
        self.d = tmp / "fake"
        self.d.mkdir()
        exe = tmp / "claude"
        exe.write_text(self.SCRIPT.format(d=self.d))
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        self.set(out=OK_OUT, exit="0", auth_out=AUTH_OK, auth_exit="0", sleep="")

    def set(self, **kw):
        for name, value in kw.items():
            (self.d / name).write_text(value)

    def read(self, name):
        return (self.d / name).read_text()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = Fake(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return f


def test_returns_result_text_and_passes_prompt_on_stdin(fake):
    assert runner.claude("haiku", "SYS", "USER TEXT") == "hello"
    assert fake.read("stdin") == "USER TEXT"


def test_isolation_flags_and_model(fake):
    runner.claude("haiku", "SYS PROMPT", "u")
    args = fake.read("args").split("\n")
    assert args[0] == "-p"
    assert args[args.index("--model") + 1] == "haiku"
    assert args[args.index("--tools") + 1] == ""  # no tools at all
    assert args[args.index("--setting-sources") + 1] == "project,local"
    assert args[args.index("--output-format") + 1] == "json"
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in args
    assert args[args.index("--max-turns") + 1] == "1"  # a plain answer is one turn; never let it loop
    assert "--bare" not in args


def test_system_prompt_goes_through_a_private_file_never_the_command_line(fake):
    secret = "MY PRIVATE PROFILE: weight, debts, health"
    runner.claude("haiku", secret, "u")
    args = fake.read("args")
    assert secret not in args and "--system-prompt\n" not in args  # argv is readable by every local user
    assert "--system-prompt-file" in args
    assert fake.read("sysfile") == secret
    assert fake.read("sysmode").strip() == "600"


def test_runs_in_an_empty_throwaway_directory(fake):
    runner.claude("haiku", "s", "u")
    cwd = fake.read("cwd").strip()
    assert cwd != os.getcwd() and not os.path.exists(cwd)
    assert fake.read("cwdlist").strip() == ""  # the prompt file must not sit in the working directory


def test_nonzero_exit_raises_runner_error(fake):
    fake.set(exit="1")
    with pytest.raises(runner.RunnerError):
        runner.claude("haiku", "s", "u")


def test_error_result_raises_runner_error(fake):
    fake.set(out='{"is_error": true, "subtype": "error_during_execution", "result": "boom"}')
    with pytest.raises(runner.RunnerError, match="boom"):
        runner.claude("haiku", "s", "u")


def test_child_gets_an_allow_listed_environment_so_no_credential_or_endpoint_override_leaks(fake, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_CUSTOM_HEADERS",
                "CLAUDE_CODE_USE_BEDROCK", "AWS_BEARER_TOKEN_BEDROCK", "SOME_UNRELATED_SECRET"):
        monkeypatch.setenv(var, "leak-value")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "subscription-token")
    monkeypatch.setenv("LC_ALL", "C")
    runner.claude("haiku", "s", "u")
    env = fake.read("env")
    assert "leak-value" not in env
    assert "CLAUDE_CODE_OAUTH_TOKEN=subscription-token" in env  # the subscription token is kept
    assert "PATH=" in env and "HOME=" in env and "LC_ALL=C" in env  # what claude needs to run is kept


def test_hang_is_cut_off_by_timeout(fake):
    fake.set(sleep="30")
    with pytest.raises(runner.RunnerError, match="timed out"):
        runner.claude("haiku", "s", "u", timeout=1)


@pytest.mark.parametrize("exit_code,output", [
    ("1", "You've hit your session limit · resets 3:45pm"),
    ("1", "Claude AI usage limit reached|1760000000"),
    ("1", '{"is_error": true, "result": "You\'ve hit your weekly limit · resets Mon 12:00am"}'),
    ("0", '{"is_error": false, "result": "You\'ve hit your session limit · resets 3:45pm"}'),
])
def test_usage_limit_is_detected_distinctly(fake, exit_code, output):
    fake.set(exit=exit_code, out=output)
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")


def test_usage_limit_error_is_a_runner_error(fake):
    assert issubclass(runner.UsageLimitReached, runner.RunnerError)


def test_normal_text_mentioning_limits_is_not_a_usage_limit(fake):
    fake.set(out='{"is_error": false, "result": "Authors hit their funding limit in year two."}')
    assert "funding limit" in runner.claude("haiku", "s", "u")


def test_bad_json_from_claude_is_a_runner_error(fake):
    fake.set(out="not json at all")
    with pytest.raises(runner.RunnerError):
        runner.claude("haiku", "s", "u")


def test_model_text_that_imitates_a_limit_message_is_not_a_usage_limit(fake):
    # A prompt-injected abstract could make the model *say* this; a real limit means no tokens were generated.
    fake.set(out='{"is_error": false, "result": "You\'ve hit your session limit", "usage": {"output_tokens": 9}}')
    assert runner.claude("haiku", "s", "u").startswith("You've hit your")


def test_real_limit_with_zero_generated_tokens_is_still_detected(fake):
    fake.set(out='{"is_error": false, "result": "You\'ve hit your session limit", "usage": {"output_tokens": 0}}')
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")


@pytest.mark.parametrize("method", ["claude.ai", "oauth_token"])
def test_check_login_passes_for_subscription_logins(fake, method):
    fake.set(auth_out=f'{{"loggedIn": true, "authMethod": "{method}", "subscriptionType": "max"}}')
    assert runner.check_login() == "max"


@pytest.mark.parametrize("output", [
    '{"loggedIn": false}',
    '{"loggedIn": true, "authMethod": "api_key"}',
    '{"loggedIn": true, "authMethod": "api_key_helper"}',
    '{"loggedIn": true, "authMethod": "third_party"}',
    '{"loggedIn": true, "authMethod": "none"}',
    '{"loggedIn": true}',
    "garbage",
])
def test_check_login_rejects_anything_that_is_not_a_subscription_login(fake, output):
    fake.set(auth_out=output)
    with pytest.raises(runner.RunnerError):
        runner.check_login()


def test_check_login_fails_on_nonzero_exit(fake):
    fake.set(auth_exit="1")
    with pytest.raises(runner.RunnerError):
        runner.check_login()


def test_check_login_ignores_api_key_in_environment(fake, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leak-value")
    runner.check_login()  # must not raise; the key never reaches claude


def test_missing_result_on_a_clean_exit_is_a_runner_error_not_a_keyerror(fake):
    fake.set(out='{"is_error": false, "subtype": "success"}')
    with pytest.raises(runner.RunnerError):
        runner.claude("haiku", "s", "u")


# Wording taken from the strings inside the Claude Code program itself (v2.1.296).
REAL_LIMIT_MESSAGES = [
    "You've hit your session limit \u00b7 resets 3:45pm",
    "You've hit your weekly limit \u00b7 resets Mon 12:00am",
    "You've hit your Opus limit",
    "You've hit your Sonnet limit",
    "You've hit your Fable limit",
    "You've hit your fast limit \u00b7 resets in 2h",
    "You've hit your monthly spend limit.",
    "You've hit your team's shared budget. /model to switch models.",
    "You've reached your Fable limit",
    "You're out of extra usage",
    "You're out of usage credits. Run /usage-credits",
    "Usage limit reached",
    "Credit balance is too low",
]


@pytest.mark.parametrize("message", REAL_LIMIT_MESSAGES)
def test_every_limit_wording_found_in_the_program_is_recognised_when_the_call_fails(fake, message):
    fake.set(exit="1", out=message)
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")


@pytest.mark.parametrize("message", REAL_LIMIT_MESSAGES)
def test_every_limit_wording_is_recognised_in_a_json_error_result_with_no_tokens_generated(fake, message):
    import json
    fake.set(out=json.dumps({"is_error": True, "result": message, "usage": {"output_tokens": 0}}))
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")


def test_ordinary_paper_text_about_usage_and_budgets_is_never_mistaken_for_a_limit(fake):
    import json
    for text in ("Firms hit their budget constraint in year two.", "The usage of credits rose; balance was too low.",
                 "Households were out of savings."):
        fake.set(out=json.dumps({"is_error": False, "result": text, "usage": {"output_tokens": 12}}))
        assert runner.claude("haiku", "s", "u") == text
