from argparse import Namespace
from pathlib import Path

from md_gen.config import build_config_from_args


def test_build_config_normalizes_and_sorts_sources(tmp_path: Path) -> None:
    src_a = tmp_path / "b.pdf"
    src_b = tmp_path / "a.png"
    args = Namespace(
        source=[str(src_a), str(src_b), str(src_a)],
        source_list_file=[],
        output_dir="output",
        im_temp_dir="im-temp",
        md_temp_dir="md-temp",
        log_file="logs/md-gen.log",
        model_endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        request_timeout_seconds=120.0,
        request_max_retries=2,
        max_longest_edge_px=1540,
        token_threshold=16000,
        dry_run=True,
        overwrite=False,
    )

    config = build_config_from_args(args)

    assert config.paths.source_paths == tuple(sorted({src_a.resolve(), src_b.resolve()}))
    assert config.paths.source_list_files == tuple()
    assert config.model.request_max_retries == 2
    assert config.image.max_longest_edge_px == 1540
    assert config.image.token_threshold == 16000
    assert config.runtime.dry_run is True
    assert config.runtime.overwrite is False
