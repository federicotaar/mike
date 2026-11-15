from agent.guardrails import PROTECTED_FILES


def test_guardrails_are_protected():
    assert "agent/guardrails.py" in PROTECTED_FILES


def test_run_tests_always_refuses(monkeypatch):
    """Fail closed: self-edit execution refuses even with any env marker set."""
    import pytest
    from agent import selfedit

    monkeypatch.setenv("MIKE_SELFEDIT_ISOLATED_CONTAINER", "yes")
    with pytest.raises(selfedit.SelfEditDisabled):
        selfedit.run_tests()


def test_changed_files_unknown_branch_is_a_clean_error():
    import pytest
    from agent import selfedit
    with pytest.raises(selfedit.UnknownBranch):
        selfedit.changed_files("no-such-branch-here")


def _make_repo(tmp_path):
    """A tiny git repo: main with two files, two branches - one touches a
    protected file, one only a normal file."""
    import subprocess

    def git(*args, cwd):
        subprocess.run(["git", *args], cwd=cwd, check=True,
                       capture_output=True, text=True)

    repo = tmp_path / "repo"
    (repo / "agent").mkdir(parents=True)
    (repo / "agent" / "guardrails.py").write_text("# protected\n")
    (repo / "agent" / "foo.py").write_text("# normal\n")
    git("init", "-b", "main", cwd=repo)
    git("config", "user.email", "t@example.com", cwd=repo)
    git("config", "user.name", "T", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-m", "start", cwd=repo)
    git("checkout", "-b", "safe-branch", cwd=repo)
    (repo / "agent" / "foo.py").write_text("# normal, changed\n")
    git("commit", "-am", "safe change", cwd=repo)
    git("checkout", "-b", "bad-branch", "main", cwd=repo)
    (repo / "agent" / "guardrails.py").write_text("# protected, changed\n")
    git("commit", "-am", "bad change", cwd=repo)
    return repo


def test_check_allowed_rejects_protected_changes(tmp_path, monkeypatch):
    import pytest
    from agent import selfedit
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    with pytest.raises(selfedit.ProtectedFileTouched):
        selfedit.check_allowed("bad-branch")


def test_check_allowed_accepts_normal_changes_and_diff_shows_them(tmp_path, monkeypatch):
    from agent import selfedit
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    selfedit.check_allowed("safe-branch")  # must not raise
    diff = selfedit.diff_for_approval("safe-branch")
    assert "agent/foo.py" in diff
    assert "guardrails" not in diff
