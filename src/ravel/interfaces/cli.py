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


def cmd_mcp(args: argparse.Namespace) -> int:
    from ravel.infrastructure.graph.mcp_server import run_mcp_stdio

    print("Starting RAVEL TigerGraph Model Context Protocol (MCP) server on stdio...", file=sys.stderr)
    run_mcp_stdio()
    return 0


def cmd_tg_setup(args: argparse.Namespace) -> int:
    host = args.host or settings.tg_host
    username = args.username or settings.tg_username or "tigergraph"
    password = args.password or settings.tg_password
    graphname = args.graphname or getattr(settings, "tg_graphname", "ravel")

    if not host or not password:
        print("TigerGraph Savanna / CE Configuration Guide:")
        print("---------------------------------------------")
        print("To connect RAVEL to a live TigerGraph instance:")
        print("1. Create a free blank graph on TigerGraph Savanna (https://savanna.tgcloud.io).")
        print("2. Set the following in your .env file:")
        print("   RAVEL_GRAPH_ADAPTER=tigergraph")
        print("   RAVEL_TG_HOST=https://your-domain.i.tgcloud.io")
        print("   RAVEL_TG_USERNAME=tigergraph")
        print("   RAVEL_TG_PASSWORD=your_password")
        print("   RAVEL_TG_GRAPHNAME=ravel")
        print("\nOr run directly:")
        print("   ravel tg-setup --host https://... --password ...")
        return 1

    print(f"Connecting to TigerGraph at {host} (graph: {graphname})...")
    from pyTigerGraph import TigerGraphConnection

    from ravel.infrastructure.graph import gsql_scripts as gsql

    try:
        conn = TigerGraphConnection(
            host=host,
            graphname=graphname,
            username=username,
            password=password,
        )
        print("Authenticating and creating secret...")
        secret = conn.createSecret()
        conn.getToken(secret)
        print("Connection successful! Token acquired.")

        print("Checking/installing GSQL schema and loading jobs...")
        schema_code = gsql.SCHEMA_GSQL.replace("@@graphname@@", graphname)
        res_schema = conn.gsql(schema_code)
        print("Schema output:", res_schema[:200])

        load_code = gsql.LOAD_JOBS_GSQL.replace("@@graphname@@", graphname)
        res_load = conn.gsql(load_code)
        print("Loading job output:", res_load[:200])

        print("Installing bounded investigation GSQL queries (this takes 2-3 minutes)...")
        queries_code = gsql.QUERIES_GSQL.replace("@@graphname@@", graphname)
        res_queries = conn.gsql(queries_code)
        print("Queries output:", res_queries[:200])

        print("TigerGraph deployment complete and verified!")
        return 0
    except Exception as exc:
        print(f"TigerGraph setup failed: {exc}", file=sys.stderr)
        return 1


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

    m = sub.add_parser("mcp", help="run the TigerGraph Model Context Protocol (MCP) server")
    m.set_defaults(func=cmd_mcp)

    tg = sub.add_parser("tg-setup", help="deploy schema, loading jobs, and queries to live TigerGraph")
    tg.add_argument("--host", default="")
    tg.add_argument("--username", default="")
    tg.add_argument("--password", default="")
    tg.add_argument("--graphname", default="ravel")
    tg.set_defaults(func=cmd_tg_setup)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
