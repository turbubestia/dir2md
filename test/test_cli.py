from md_gen.cli import main
from PIL import Image


def test_cli_bootstrap_creates_default_directories(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    source_file = tmp_path / "sample.png"
    image = Image.new("RGB", (50, 50), color=(255, 255, 255))
    image.save(source_file)
    image.close()
    monkeypatch.setattr("sys.argv", ["md-gen", "--source", str(source_file)])

    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "im-temp").is_dir()
    assert (tmp_path / "md-temp").is_dir()
    assert (tmp_path / "logs").is_dir()
