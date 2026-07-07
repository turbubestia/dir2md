from md_gen.cli import main


def test_cli_bootstrap_creates_default_directories(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    source_file = tmp_path / "sample.png"
    source_file.touch()
    monkeypatch.setattr("sys.argv", ["md-gen", "--source", str(source_file)])

    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "im-temp").is_dir()
    assert (tmp_path / "md-temp").is_dir()
    assert (tmp_path / "logs").is_dir()
