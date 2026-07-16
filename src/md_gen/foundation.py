from __future__ import annotations

import json

from common.gateway import GatewayError
from common.config import AppConfig, ConfigValidationError

from .discovery import build_work_items
from .page_processor import process_file


def _emit_stage(stage: str, *, status: str, detail: str = "") -> None:
    detail_token = f" detail={detail}" if detail else ""
    print(f"STAGE name={stage} status={status}{detail_token}")


def _emit_error(error_code: str, message: str) -> None:
    print(f"ERROR code={error_code} message={message}")


def run_foundation_bootstrap(config: AppConfig) -> int:
    try:
        config.paths.output_dir.mkdir(parents=True, exist_ok=True)

        work_items = build_work_items(config)
        _emit_stage("discover_work_items", status="ok", detail=f"count={len(work_items)}")

        metadata_records: list[dict] = []
        for file_item in work_items:
            print(f"> processing source {file_item.source_path.name}")
            metadata = process_file(config, file_item)
            metadata_records.append(metadata)

        batch_path = config.paths.output_dir / "batch.json"
        batch_path.write_text(
            json.dumps({"documents": metadata_records}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _emit_stage("persist_batch", status="ok", detail=f"path={batch_path}")

        return 0

    except ConfigValidationError as exc:
        _emit_error(exc.error_code, str(exc))
        return 2
    except GatewayError as exc:
        _emit_error(exc.error_code, str(exc))
        return 4
    except Exception as exc:
        _emit_error("foundation_runtime_error", f"{type(exc).__name__}: {exc}")
        return 1


