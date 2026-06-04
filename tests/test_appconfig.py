"""appconfig: data-directory resolution + XDG global fallback.

`resolve_data_dir` is pure (every input injected) so the precedence rules are
tested without touching the real ~/.config. The global-fallback branch of
`build_context_from_env` is exercised against an isolated XDG_CONFIG_HOME.
"""
import appconfig
import coinbasis


# ── resolve_data_dir precedence (pure) ─────────────────────────────────────────

def test_resolve_data_dir_explicit_wins(tmp_path):
    d, used_global = appconfig.resolve_data_dir(
        data_dir="/explicit/dir", env_dir="/env/dir",
        cwd=str(tmp_path), xdg_config_home=str(tmp_path / "xdg"),
    )
    assert d == "/explicit/dir"
    assert used_global is False


def test_resolve_data_dir_env_beats_cwd_and_global(tmp_path):
    (tmp_path / "ledger.json").write_text("[]")  # cwd has a ledger, but env still wins
    d, used_global = appconfig.resolve_data_dir(
        data_dir=None, env_dir="/env/dir",
        cwd=str(tmp_path), xdg_config_home=str(tmp_path / "xdg"),
    )
    assert d == "/env/dir"
    assert used_global is False


def test_resolve_data_dir_uses_cwd_when_ledger_present(tmp_path):
    (tmp_path / "ledger.json").write_text("[]")
    d, used_global = appconfig.resolve_data_dir(
        data_dir=None, env_dir=None,
        cwd=str(tmp_path), xdg_config_home=str(tmp_path / "xdg"),
    )
    assert d == str(tmp_path)
    assert used_global is False


def test_resolve_data_dir_global_fallback_when_cwd_empty(tmp_path):
    xdg = tmp_path / "xdg"
    d, used_global = appconfig.resolve_data_dir(
        data_dir=None, env_dir=None,
        cwd=str(tmp_path), xdg_config_home=str(xdg),
    )
    assert d == str(xdg / "crypto-price-tracker")
    assert used_global is True


# ── build_context_from_env global-fallback side effects ────────────────────────

def test_build_context_global_fallback_creates_dir_and_notifies(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # empty cwd: no ledger.json
    monkeypatch.delenv("CPT_DATA_DIR", raising=False)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

    ctx = appconfig.build_context_from_env(
        data_dir=None, method="fifo", select_file=None, offline=False,
    )
    global_dir = xdg / "crypto-price-tracker"
    assert ctx.paths["ledger"] == str(global_dir / "ledger.json")
    assert global_dir.is_dir()  # created on first run
    assert "global data directory" in capsys.readouterr().err.lower()


def test_build_context_global_fallback_quiet_suppresses_notice(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CPT_DATA_DIR", raising=False)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    appconfig.build_context_from_env(
        data_dir=None, method="fifo", select_file=None, offline=False, quiet=True,
    )
    assert "global data directory" not in capsys.readouterr().err.lower()


def test_build_context_cwd_ledger_skips_global(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ledger.json").write_text("[]")
    monkeypatch.delenv("CPT_DATA_DIR", raising=False)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    ctx = appconfig.build_context_from_env(
        data_dir=None, method="fifo", select_file=None, offline=False,
    )
    assert ctx.paths["ledger"] == str(tmp_path / "ledger.json")
    assert not (tmp_path / "xdg").exists()  # global dir never created
    assert "global data directory" not in capsys.readouterr().err.lower()
    assert ctx.method == coinbasis.CostBasisMethod.FIFO
