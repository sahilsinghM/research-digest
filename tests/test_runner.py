import os
import stat

import pytest

import runner

FAKE = """#!/bin/sh
if [ "$1" = "auth" ]; then printf '%s' "$FAKE_AUTH_OUTPUT"; exit "${FAKE_AUTH_EXIT:-0}"; fi
printf '%s\\n' "$@" > "$ARGS_FILE"
env > "$ENV_FILE"
cat > "$STDIN_FILE"
pwd > "$CWD_FILE"
[ -n "$FAKE_SLEEP" ] && exec sleep "$FAKE_SLEEP"
printf '%s' "$FAKE_OUTPUT"
exit "${FAKE_EXIT:-0}"
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    exe = tmp_path / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    for name in ("ARGS_FILE", "STDIN_FILE", "CWD_FILE", "ENV_FILE"):
        monkeypatch.setenv(name, str(tmp_path / name))
    monkeypatch.setenv("FAKE_OUTPUT", '{"is_error": false, "subtype": "success", "result": "hello"}')
    return tmp_path


def seen(tmp, name):
    return (tmp / name).read_text()


def test_returns_result_text_and_passes_prompt_on_stdin(fake_claude):
    assert runner.claude("haiku", "SYS", "USER TEXT") == "hello"
    assert seen(fake_claude, "STDIN_FILE") == "USER TEXT"


def test_isolation_flags_and_model_and_system_prompt(fake_claude):
    runner.claude("haiku", "SYS PROMPT", "u")
    args = seen(fake_claude, "ARGS_FILE").split("\n")
    assert args[0] == "-p"
    assert args[args.index("--model") + 1] == "haiku"
    assert args[args.index("--system-prompt") + 1] == "SYS PROMPT"
    assert args[args.index("--tools") + 1] == ""  # no tools at all
    assert args[args.index("--setting-sources") + 1] == "project,local"
    assert args[args.index("--output-format") + 1] == "json"
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in args
    assert "--bare" not in args


def test_runs_in_an_empty_throwaway_directory(fake_claude):
    runner.claude("haiku", "s", "u")
    cwd = seen(fake_claude, "CWD_FILE").strip()
    assert cwd != os.getcwd() and not os.path.exists(cwd)


def test_nonzero_exit_raises_runner_error(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "1")
    with pytest.raises(runner.RunnerError):
        runner.claude("haiku", "s", "u")


def test_error_result_raises_runner_error(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_OUTPUT", '{"is_error": true, "subtype": "error_during_execution", "result": "boom"}')
    with pytest.raises(runner.RunnerError, match="boom"):
        runner.claude("haiku", "s", "u")


def test_api_key_and_alternative_auth_variables_never_reach_claude(fake_claude, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
        monkeypatch.setenv(var, "secret-value")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "subscription-token")
    runner.claude("haiku", "s", "u")
    env = seen(fake_claude, "ENV_FILE")
    assert "secret-value" not in env and "ANTHROPIC_API_KEY" not in env
    assert "CLAUDE_CODE_OAUTH_TOKEN=subscription-token" in env  # the subscription token is kept


def test_hang_is_cut_off_by_timeout(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "30")
    with pytest.raises(runner.RunnerError, match="timed out"):
        runner.claude("haiku", "s", "u", timeout=1)


@pytest.mark.parametrize("exit_code,output", [
    ("1", "You've hit your session limit · resets 3:45pm"),
    ("1", '{"is_error": true, "result": "You\'ve hit your weekly limit · resets Mon 12:00am"}'),
    ("0", '{"is_error": false, "result": "You\'ve hit your session limit · resets 3:45pm"}'),
])
def test_usage_limit_is_detected_distinctly(fake_claude, monkeypatch, exit_code, output):
    monkeypatch.setenv("FAKE_EXIT", exit_code)
    monkeypatch.setenv("FAKE_OUTPUT", output)
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")


def test_usage_limit_error_is_a_runner_error(fake_claude):
    assert issubclass(runner.UsageLimitReached, runner.RunnerError)


def test_normal_text_mentioning_limits_is_not_a_usage_limit(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_OUTPUT", '{"is_error": false, "result": "Authors hit their funding limit in year two."}')
    assert "funding limit" in runner.claude("haiku", "s", "u")


def test_bad_json_from_claude_is_a_runner_error(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_OUTPUT", "not json at all")
    with pytest.raises(runner.RunnerError):
        runner.claude("haiku", "s", "u")


AUTH_OK = '{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max"}'


def test_check_login_passes_for_subscription_login(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_AUTH_OUTPUT", AUTH_OK)
    assert runner.check_login() == "max"


@pytest.mark.parametrize("output", [
    '{"loggedIn": false}',
    '{"loggedIn": true, "authMethod": "api_key"}',
    "garbage",
])
def test_check_login_rejects_logged_out_api_key_or_garbage(fake_claude, monkeypatch, output):
    monkeypatch.setenv("FAKE_AUTH_OUTPUT", output)
    with pytest.raises(runner.RunnerError):
        runner.check_login()


def test_check_login_fails_on_nonzero_exit(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_AUTH_OUTPUT", AUTH_OK)
    monkeypatch.setenv("FAKE_AUTH_EXIT", "1")
    with pytest.raises(runner.RunnerError):
        runner.check_login()


def test_check_login_ignores_api_key_in_environment(fake_claude, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    monkeypatch.setenv("FAKE_AUTH_OUTPUT", AUTH_OK)
    runner.check_login()  # must not raise; the key is stripped before claude runs


def test_model_text_that_imitates_a_limit_message_is_not_a_usage_limit(fake_claude, monkeypatch):
    # A prompt-injected abstract could make the model *say* this; a real limit means no tokens were generated.
    monkeypatch.setenv("FAKE_OUTPUT", '{"is_error": false, "result": "You\'ve hit your session limit", '
                                      '"usage": {"output_tokens": 9}}')
    assert runner.claude("haiku", "s", "u").startswith("You've hit your")


def test_real_limit_with_zero_generated_tokens_is_still_detected(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_OUTPUT", '{"is_error": false, "result": "You\'ve hit your session limit", '
                                      '"usage": {"output_tokens": 0}}')
    with pytest.raises(runner.UsageLimitReached):
        runner.claude("haiku", "s", "u")
