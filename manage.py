#!/usr/bin/env python3
"""Unified developer CLI for TerraNepal / TerraRaksha.

Commands:
  test      Run all Python and Node.js test suites across the project
  build     Build allowlisted public assets for deployment
  serve     Run the local private research lab web service
  verify    Run tests and build verification in sequence
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run_tests() -> int:
    """Run all test suites across deploy, disaster_lab, disaster_archive, and public_site."""
    print("=" * 60)
    print("TerraNepal — Running All Test Suites")
    print("=" * 60)
    suites = [
        ("Deploy Suite", [sys.executable, "-m", "unittest", "discover", "-s", "deploy", "-p", "test_*.py", "-v"]),
        ("Archive Suite", [sys.executable, "-m", "unittest", "discover", "-s", "disaster_archive", "-p", "test_*.py", "-v"]),
        ("Lab Production Suite", [sys.executable, "-m", "unittest", "discover", "-s", "disaster_lab", "-p", "test_production.py", "-v"]),
        ("Lab Analytics Suite", [sys.executable, "-m", "unittest", "discover", "-s", "disaster_lab", "-p", "test_analytics.py", "-v"]),
        ("Public Site Python Suite", [sys.executable, "-m", "unittest", "discover", "-s", "public_site", "-p", "test_*.py", "-v"]),
    ]
    failed = []
    for label, cmd in suites:
        print(f"\n--- {label} ---")
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            failed.append(label)

    # Node.js logic tests
    print("\n--- Public Site Logic (Node.js) ---")
    node_proc = subprocess.run(["node", "public_site/test_logic.cjs"], cwd=ROOT)
    if node_proc.returncode != 0:
        failed.append("Public Site Logic (Node.js)")

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED: {len(failed)} suite(s) had errors: {', '.join(failed)}")
        return 1
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return 0


def run_build(output: str | None = None) -> int:
    """Build Vercel public distribution bundle."""
    sys.path.insert(0, str(ROOT))
    from deploy.build_vercel import build
    try:
        build(output=output)
        return 0
    except Exception as exc:
        print(f"Build error: {exc}", file=sys.stderr)
        return 1


def run_serve(port: int = 8765, local: bool = True) -> int:
    """Run the local research lab."""
    sys.path.insert(0, str(ROOT / "disaster_lab"))
    from production import create_app
    from waitress import serve
    app = create_app(root=ROOT, local=local)
    print(f"TerraRaksha private lab listening on http://127.0.0.1:{port} (local={local})")
    try:
        serve(app, host="127.0.0.1", port=port, threads=6, clear_untrusted_proxy_headers=True)
    except KeyboardInterrupt:
        print("\nService stopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("test", help="Run all Python and Node.js test suites")

    build_p = subparsers.add_parser("build", help="Build allowlisted public assets")
    build_p.add_argument("--output", "-o", help="Target output directory (default: ./public)")

    serve_p = subparsers.add_parser("serve", help="Run local private lab server")
    serve_p.add_argument("--port", "-p", type=int, default=8765, help="Port to bind (default: 8765)")
    serve_p.add_argument("--no-local", action="store_true", help="Run in strict remote mode with owner auth")

    subparsers.add_parser("verify", help="Run full test suite and verify build")

    args = parser.parse_args(argv)

    if args.command == "test":
        return run_tests()
    elif args.command == "build":
        return run_build(output=args.output)
    elif args.command == "serve":
        return run_serve(port=args.port, local=not args.no_local)
    elif args.command == "verify":
        test_rc = run_tests()
        if test_rc != 0:
            return test_rc
        print("\nVerifying build output...")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            build_rc = run_build(output=tmp)
            if build_rc != 0:
                return build_rc
        print("Verification completed successfully!")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
