"""ShellScan CLI — scan AI agent skills for security issues.

Usage:
    shellscan SKILL.md [SKILL2.py ...]
    shellscan --depth deep SKILL.md
    shellscan --json SKILL.md

Environment:
    SHELLSCAN_API_KEY   Your API key (required)
    SHELLSCAN_API_URL   API base URL (default: https://api.shellscan.dev)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

POLL_INTERVAL = 5  # seconds
POLL_TIMEOUT = 600  # 10 minutes max
TERMINAL_STATES = {"completed", "complete", "failed"}

VERDICT_COLORS = {
    "PASS": "\033[32m",  # green
    "REVIEW": "\033[33m",  # yellow
    "FAIL": "\033[31m",  # red
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def get_config() -> tuple[str, str]:
    """Return (api_key, api_url) from env."""
    api_key = os.environ.get("SHELLSCAN_API_KEY", "")
    if not api_key:
        print("Error: SHELLSCAN_API_KEY not set", file=sys.stderr)
        print("  Get a key at https://shellscan.dev", file=sys.stderr)
        sys.exit(1)

    api_url = os.environ.get(
        "SHELLSCAN_API_URL", "https://api.shellscan.dev"
    ).rstrip("/")
    return api_key, api_url


def api_request(
    method: str, url: str, api_key: str, data: bytes | None = None, headers: dict | None = None,
) -> dict:
    """Make an authenticated API request, return parsed JSON."""
    hdrs = {"Authorization": f"Bearer {api_key}"}
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body).get("detail", body)
        except (json.JSONDecodeError, AttributeError):
            detail = body
        print(f"Error: HTTP {e.code} — {detail}", file=sys.stderr)
        sys.exit(1)


def submit_scan(api_key: str, api_url: str, files: list[Path], depth: str) -> str:
    """Submit files for scanning, return run_id."""
    import mimetypes

    boundary = f"----ShellScan{int(time.time() * 1000)}"
    body_parts: list[bytes] = []

    for filepath in files:
        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        if filepath.stat().st_size > 10 * 1024 * 1024:
            print(f"Error: file too large (max 10MB): {filepath}", file=sys.stderr)
            sys.exit(1)

        mime = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="files"; filename="{filepath.name}"\r\n'.encode()
        )
        body_parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
        body_parts.append(filepath.read_bytes())
        body_parts.append(b"\r\n")

    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    url = f"{api_url}/v1/scan?depth={depth}&source=cli"
    result = api_request(
        "POST", url, api_key, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return result["run_id"]


def poll_scan(api_key: str, api_url: str, run_id: str) -> dict:
    """Poll until scan reaches a terminal state."""
    url = f"{api_url}/v1/scan/{run_id}"
    start = time.monotonic()
    last_status = ""

    while time.monotonic() - start < POLL_TIMEOUT:
        result = api_request("GET", url, api_key)
        status = result.get("status", "unknown")

        if status != last_status:
            if sys.stderr.isatty():
                print(f"  {DIM}status: {status}{RESET}", file=sys.stderr)
            last_status = status

        if status in TERMINAL_STATES:
            return result

        time.sleep(POLL_INTERVAL)

    print(f"Error: scan timed out after {POLL_TIMEOUT}s (run_id: {run_id})", file=sys.stderr)
    sys.exit(1)


def format_findings(findings: list[dict]) -> str:
    """Format findings for terminal output."""
    if not findings:
        return ""

    lines = []
    for f in sorted(findings, key=lambda x: SEVERITY_ORDER.index(x.get("severity", "INFO")) if x.get("severity") in SEVERITY_ORDER else 99):
        sev = f.get("severity", "?")
        cat = f.get("category", "unknown")
        desc = f.get("description", "")
        line_ref = f.get("line_reference")

        if sev in ("CRITICAL", "HIGH"):
            color = VERDICT_COLORS["FAIL"]
        elif sev == "MEDIUM":
            color = VERDICT_COLORS["REVIEW"]
        else:
            color = DIM

        loc = f" (line {line_ref})" if line_ref else ""
        lines.append(f"  {color}{sev:<8}{RESET} {cat}{loc}")
        if desc:
            lines.append(f"           {DIM}{desc}{RESET}")

    return "\n".join(lines)


def print_result(result: dict, json_output: bool) -> int:
    """Print scan result. Returns exit code (0=PASS, 1=FAIL, 2=REVIEW)."""
    if json_output:
        print(json.dumps(result, indent=2))
        report = result.get("report", result)
        verdict = report.get("verdict", "UNKNOWN")
        return {"PASS": 0, "REVIEW": 2, "FAIL": 1}.get(verdict, 1)

    report = result.get("report", {})
    status = result.get("status", "unknown")

    if status == "failed":
        error = result.get("error", "unknown error")
        print(f"\n{VERDICT_COLORS['FAIL']}{BOLD}SCAN FAILED{RESET}: {error}")
        return 1

    verdict = report.get("verdict", "UNKNOWN")
    risk_score = report.get("risk_score", "?")
    finding_count = report.get("finding_count", 0)
    color = VERDICT_COLORS.get(verdict, "")

    print(f"\n{color}{BOLD}ShellScan: {verdict}{RESET}  (risk score: {risk_score}/100, {finding_count} findings)")

    findings = report.get("findings", [])
    if findings:
        print(format_findings(findings))

    run_id = report.get("run_id", result.get("run_id", "?"))
    print(f"\n  {DIM}run_id: {run_id}{RESET}")
    return {"PASS": 0, "REVIEW": 2, "FAIL": 1}.get(verdict, 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="shellscan",
        description="Scan AI agent skills for security issues",
    )
    parser.add_argument("files", nargs="+", type=Path, help="Skill files to scan")
    parser.add_argument(
        "--depth", default="scan", choices=["scan", "deep", "assess", "full"],
        help="Scan depth (default: scan)",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    parser.add_argument("--run-id", help="Check status of an existing scan instead of submitting")
    args = parser.parse_args()

    api_key, api_url = get_config()

    if args.run_id:
        result = poll_scan(api_key, api_url, args.run_id)
    else:
        filenames = ", ".join(f.name for f in args.files)
        if sys.stderr.isatty():
            print(f"{BOLD}Scanning:{RESET} {filenames} (depth={args.depth})", file=sys.stderr)

        run_id = submit_scan(api_key, api_url, args.files, args.depth)
        if sys.stderr.isatty():
            print(f"  {DIM}run_id: {run_id}{RESET}", file=sys.stderr)

        result = poll_scan(api_key, api_url, run_id)

    exit_code = print_result(result, args.json_output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
