import json
from pathlib import Path

import pytest
from PIL import Image

from common.gateway import GatewayError
from md_mrg import apply as apply_mod
from md_mrg import io as io_mod
from md_mrg import planner as planner_mod
from md_mrg import scorers as scorers_mod
from md_mrg.models import CandidateEdge, EdgeScore, FragmentRecord


def _fragment(fragment_id: str, image_file: str, markdown_file: str) -> FragmentRecord:
    return FragmentRecord(
        source_document_id="doc",
        source_name="scan.jpg",
        fragment_id=fragment_id,
        sequence_number=1,
        image_file=image_file,
        markdown_file=markdown_file,
        first_line="start",
        last_line="end",
        snippet="snippet",
    )


def test_io_validate_rejects_non_dicts() -> None:
    with pytest.raises(ValueError, match="merge batch must be an object"):
        io_mod.validate_merge_batch_payload(["bad"])

    with pytest.raises(ValueError, match="fragment must be an object"):
        io_mod.validate_fragment_payload(["bad"])


def test_io_load_metadata_documents_supports_batch_payload(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    payload = {
        "batch_id": "b1",
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "documents": [
            {
                "document_id": "d1",
                "source_name": "a.jpg",
                "total_pages": 1,
                "is_verified_sequence": False,
                "fragments": [{"sequence_number": 1, "image_file": "a.jpg", "markdown_file": "a.md"}],
            }
        ],
    }
    (metadata_dir / "a.json").write_text(json.dumps(payload), encoding="utf-8")

    docs = io_mod.load_metadata_documents(metadata_dir)
    assert len(docs) == 1
    assert docs[0]["document_id"] == "d1"


def test_io_load_metadata_documents_rejects_unknown_shape(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "bad.json").write_text(json.dumps({"unknown": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported metadata payload"):
        io_mod.load_metadata_documents(metadata_dir)


def test_io_path_derivers() -> None:
    source = Path("/tmp/source")
    assert io_mod.derive_temp_root(source) == source / "temp"
    assert io_mod.derive_metadata_dir(source) == source / "temp" / "metadata"
    assert io_mod.derive_markdown_dir(source) == source / "temp" / "markdown"
    assert io_mod.derive_image_dir(source) == source / "temp" / "images"
    assert io_mod.derive_plan_file(source).name == io_mod.DETERMINISTIC_PLAN_FILE_NAME


def test_write_plan_file_obeys_overwrite_flag(tmp_path: Path) -> None:
    output = tmp_path / "merge-plan.json"
    payload = {
        "batch_id": "b1",
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "documents": [
            {
                "document_id": "d1",
                "source_name": "a.jpg",
                "total_pages": 1,
                "is_verified_sequence": False,
                "fragments": [{"sequence_number": 1, "image_file": "a.jpg", "markdown_file": "a.md"}],
            }
        ],
    }

    io_mod.write_plan_file(output, payload, overwrite=True)
    first = output.read_text(encoding="utf-8")
    output.write_text("changed", encoding="utf-8")
    io_mod.write_plan_file(output, payload, overwrite=False)
    assert output.read_text(encoding="utf-8") == "changed"
    io_mod.write_plan_file(output, payload, overwrite=True)
    assert output.read_text(encoding="utf-8") == first


def test_planner_build_candidate_edges_windowing() -> None:
    fragments = (
        _fragment("a", "a.jpg", "a.md"),
        _fragment("b", "b.jpg", "b.md"),
        _fragment("c", "c.jpg", "c.md"),
    )
    edges = planner_mod._build_candidate_edges(fragments, rolling_window=1)
    edge_pairs = {(e.from_fragment_id, e.to_fragment_id) for e in edges}
    assert edge_pairs == {("a", "b"), ("b", "a"), ("b", "c"), ("c", "b")}


def test_planner_creates_cycle_detection() -> None:
    next_map = {"a": "b", "b": "c"}
    assert planner_mod._creates_cycle(next_map, start_id="c", target_id="a") is True
    assert planner_mod._creates_cycle(next_map, start_id="d", target_id="a") is False


def test_planner_resolve_edges_rejects_conflicts_and_cycles() -> None:
    scores = (
        EdgeScore("a", "b", 9.0, "r", "llm", 1.0, "auto_merge"),
        EdgeScore("a", "c", 8.5, "r", "llm", 1.0, "auto_merge"),
        EdgeScore("b", "a", 8.0, "r", "llm", 1.0, "auto_merge"),
        EdgeScore("c", "d", 7.0, "r", "llm", 1.0, "auto_merge"),
    )
    accepted = planner_mod._resolve_edges(scores)
    accepted_pairs = {(s.from_fragment_id, s.to_fragment_id) for s in accepted}
    assert ("a", "b") in accepted_pairs
    assert ("a", "c") not in accepted_pairs
    assert ("b", "a") not in accepted_pairs


def test_planner_build_documents_from_edges_with_standalone() -> None:
    fragments = (
        _fragment("a", "a.jpg", "a.md"),
        _fragment("b", "b.jpg", "b.md"),
        _fragment("c", "c.jpg", "c.md"),
    )
    accepted = (EdgeScore("a", "b", 7.0, "ok", "llm", 1.0, "review_required"),)
    docs = planner_mod._build_documents_from_edges(fragments, accepted)
    assert len(docs) == 2
    multi = [d for d in docs if d["total_pages"] == 2][0]
    solo = [d for d in docs if d["total_pages"] == 1][0]
    assert multi["review_required"] is True
    assert solo["review_required"] is False


def test_planner_load_prompt_file_none_on_missing_or_empty(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    assert planner_mod._load_prompt_file(missing) is None
    empty = tmp_path / "empty.txt"
    empty.write_text("   ", encoding="utf-8")
    assert planner_mod._load_prompt_file(empty) is None


def test_scorer_decision_thresholds() -> None:
    assert scorers_mod._decision_from_score(7.0) == "auto_merge"
    assert scorers_mod._decision_from_score(5.0) == "review_required"
    assert scorers_mod._decision_from_score(4.9) == "reject"


def test_llm_scorer_maps_gateway_error(monkeypatch) -> None:
    class FakeGateway:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def send_bridge_score_request(self, request):
            raise GatewayError("connection_error", "boom")

    monkeypatch.setattr(scorers_mod, "LlamaBridgeScoreGateway", FakeGateway)
    scorer = scorers_mod.LlmEdgeScorer(
        endpoint_url="http://x",
        model_name="m",
        timeout_seconds=1,
        max_retries=0,
        system_prompt="prompt",
    )
    candidate = CandidateEdge(
        from_fragment_id="a",
        to_fragment_id="b",
        from_fragment=_fragment("a", "a.jpg", "a.md"),
        to_fragment=_fragment("b", "b.jpg", "b.md"),
    )
    out = scorer.score_edges((candidate,))
    assert out[0].reason.startswith("llm_error:")
    assert out[0].decision_status == "reject"


def test_apply_helpers_basic_behavior(tmp_path: Path) -> None:
    assert apply_mod._sanitize_component("Invoice 2026/07") == "invoice-2026-07"
    assert apply_mod._extract_llm_filename_stem("name: 2026-bill-main") == "2026-bill-main"
    assert apply_mod._choose_canvas_size((850, 1100)) == apply_mod._LETTER_SIZE
    assert apply_mod._choose_canvas_size((850, 1400)) == apply_mod._LEGAL_SIZE

    img = Image.new("RGB", (1200, 400), color=(255, 255, 255))
    canvas = apply_mod._fit_image_to_canvas(img, apply_mod._LETTER_SIZE)
    assert canvas.size == apply_mod._LETTER_SIZE
    canvas.close()
    img.close()

    doc = {"fragments": [{"content_fingerprint": {"snippet": "a"}}, {"content_fingerprint": {"snippet": "b"}}]}
    assert apply_mod._merge_fragment_snippets(doc) == "a b"


def test_apply_build_pdf_from_images_noop_empty(tmp_path: Path) -> None:
    output = tmp_path / "out.pdf"
    apply_mod._build_pdf_from_images(tuple(), output)
    assert output.exists() is False


def test_apply_build_pdf_from_images_writes_file(tmp_path: Path) -> None:
    img1 = tmp_path / "a.jpg"
    img2 = tmp_path / "b.jpg"
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(img1)
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(img2)

    output = tmp_path / "out.pdf"
    apply_mod._build_pdf_from_images((img1, img2), output)
    assert output.exists() and output.stat().st_size > 0


def test_apply_propose_document_stem_fallback_without_endpoint() -> None:
    doc = {"source_name": "scan.jpg", "fragments": []}
    stem = apply_mod._propose_document_stem(doc, None, None, 1.0, 0)
    assert stem.startswith("scan-jpg")


def test_apply_propose_document_stem_uses_gateway_response(monkeypatch) -> None:
    class FakeResponse:
        text = "2026-utility-invoice"

    class FakeGateway:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def send_text_request(self, request):
            return FakeResponse()

    monkeypatch.setattr(apply_mod, "LlamaLanguageGateway", FakeGateway)
    doc = {"source_name": "scan.jpg", "fragments": []}
    stem = apply_mod._propose_document_stem(doc, "http://x", "m", 1.0, 0)
    assert stem == "2026-utility-invoice"


def test_apply_propose_document_stem_falls_back_on_gateway_exception(monkeypatch) -> None:
    class BadGateway:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def send_text_request(self, request):
            raise RuntimeError("nope")

    monkeypatch.setattr(apply_mod, "LlamaLanguageGateway", BadGateway)
    doc = {"source_name": "scan.jpg", "fragments": []}
    stem = apply_mod._propose_document_stem(doc, "http://x", "m", 1.0, 0)
    assert stem.startswith("scan-jpg")
