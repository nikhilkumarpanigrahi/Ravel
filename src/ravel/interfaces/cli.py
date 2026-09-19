"""RAVEL CLI entrypoints (ingest, benchmark)."""

from __future__ import annotations

import argparse
import json
import sys

from ravel.config import settings


def cmd_ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ravel.infrastructure.ingestion.pipeline import run_pipeline

    out = args.out_dir or str(settings.data_dir.parent / "data" / "level0")
    metrics = run_pipeline(settings.data_dir, Path(out), chunksize=args.chunksize)
    print(json.dumps(metrics.to_dict(), indent=2))
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from ravel.application.benchmark_service import BenchmarkService

    service = BenchmarkService(settings)
    report = service.run_all(
        limit=args.limit,
        output_dir=args.out_dir or str(settings.output_dir),
        replay=args.replay,
    )
    print(json.dumps(report, indent=2, default=str)[:4000])
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("ravel.interfaces.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from pathlib import Path

    p = Path(settings.output_dir) / f"{args.case_id}.json"
    if not p.exists():
        print(f"Error: case file {p} not found.")
        return 1
    print(p.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="ravel", description="RAVEL — agentic fraud investigation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="run the normalized ingestion pipeline")
    p.add_argument("--chunksize", type=int, default=200_000)
    p.add_argument("--out-dir", default="")
    p.set_defaults(func=cmd_ingest)

    b = sub.add_parser("benchmark", help="run the 20-case benchmark")
    b.add_argument("--limit", type=int, default=0)
    b.add_argument("--out-dir", default="")
    b.add_argument("--replay", action="store_true", help="reuse persisted investigations when present")
    b.set_defaults(func=cmd_benchmark)

    s = sub.add_parser("serve", help="launch the FastAPI backend and Forensic Workstation UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=cmd_serve)

    sh = sub.add_parser("show", help="inspect an answer file by case ID")
    sh.add_argument("case_id", help="e.g. HHG-001")
    sh.set_defaults(func=cmd_show)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
