import os
import stat

import pytest

import runner

FAKE = """#!/bin/sh
printf '%s\\n' "$@" > "$ARGS_FILE"
cat > "$STDIN_FILE"
pwd > "$CWD_FILE"
printf '%s' "$FAKE_OUTPUT"
exit "${FAKE_EXIT:-0}"
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    exe = tmp_path / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    for name in ("ARGS_FILE", "STDIN_FILE", "CWD_FILE"):
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
