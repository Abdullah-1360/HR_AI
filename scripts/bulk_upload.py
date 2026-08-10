#!/usr/bin/env python3
"""
scripts/bulk_upload.py
----------------------
Bulk upload 100+ resume PDFs to the HR AI Platform.

Usage:
    python scripts/bulk_upload.py --folder ./resumes
    python scripts/bulk_upload.py --folder ./resumes --workers 5
    python scripts/bulk_upload.py --folder ./resumes --workers 3 --api http://localhost:3006

Arguments:
    --folder    Path to folder containing PDF files (required)
    --workers   Number of parallel uploads (default: 5, max: 10)
    --api       API base URL (default: http://localhost:3006)
    --output    Path to save results JSON (default: upload_results.json)
    --retry     Number of retries per file on failure (default: 2)
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import aiohttp

# ── Terminal colours ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def print_banner():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗
║          HR AI Platform — Bulk Resume Uploader           ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")


def print_progress(done: int, total: int, success: int, failed: int, current: str = ""):
    bar_len = 40
    filled = int(bar_len * done / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = int(100 * done / total) if total > 0 else 0
    status = f"{GREEN}✓ {success}{RESET}  {RED}✗ {failed}{RESET}"
    short_name = current[:40] + "..." if len(current) > 40 else current
    print(
        f"\r  [{bar}] {BOLD}{pct}%{RESET}  ({done}/{total})  {status}  {YELLOW}{short_name:<43}{RESET}",
        end="",
        flush=True,
    )


async def upload_one(
    session: aiohttp.ClientSession,
    pdf_path: Path,
    api_url: str,
    semaphore: asyncio.Semaphore,
    max_retries: int,
) -> Dict:
    """Upload a single PDF and return a result dict."""
    result = {
        "file": pdf_path.name,
        "path": str(pdf_path),
        "status": "pending",
        "candidate_id": None,
        "candidate_name": None,
        "skills_found": 0,
        "error": None,
        "attempt": 0,
        "duration_s": 0,
    }

    async with semaphore:
        for attempt in range(1, max_retries + 2):
            result["attempt"] = attempt
            start = time.monotonic()
            try:
                with open(pdf_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        "file",
                        f,
                        filename=pdf_path.name,
                        content_type="application/pdf",
                    )
                    async with session.post(
                        f"{api_url}/api/v1/candidates/",
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=120),  # 2 min per file
                    ) as resp:
                        duration = time.monotonic() - start
                        result["duration_s"] = round(duration, 1)

                        if resp.status == 201:
                            body = await resp.json()
                            result["status"] = "success"
                            result["candidate_id"] = body.get("id")
                            result["candidate_name"] = body.get("name") or "Unknown"
                            result["skills_found"] = len(body.get("skills") or [])
                            return result

                        elif resp.status == 413:
                            result["status"] = "failed"
                            result["error"] = "File too large (>10MB)"
                            return result  # no point retrying

                        elif resp.status == 400:
                            body = await resp.text()
                            result["status"] = "failed"
                            result["error"] = f"Bad file: {body[:100]}"
                            return result  # no point retrying

                        else:
                            body = await resp.text()
                            result["error"] = f"HTTP {resp.status}: {body[:120]}"
                            # Will retry

            except aiohttp.ClientConnectorError:
                result["error"] = "Cannot connect to API — is the backend running?"
                break  # no point retrying connection errors
            except asyncio.TimeoutError:
                result["error"] = f"Timeout on attempt {attempt}"
            except FileNotFoundError:
                result["error"] = "File not found"
                break
            except Exception as exc:
                result["error"] = str(exc)[:120]

            # Exponential backoff before retry
            if attempt <= max_retries:
                await asyncio.sleep(2 ** attempt)

        result["status"] = "failed"
        return result


async def bulk_upload(
    folder: Path,
    api_url: str,
    workers: int,
    output_path: Path,
    max_retries: int,
):
    # ── Find all PDFs ─────────────────────────────────────────────────────────
    pdf_files = sorted(folder.glob("**/*.pdf"))
    if not pdf_files:
        print(f"{RED}No PDF files found in: {folder}{RESET}")
        sys.exit(1)

    total = len(pdf_files)
    print(f"  {BOLD}Found {total} PDF files{RESET} in {folder}")
    print(f"  {BOLD}Workers:{RESET} {workers} parallel uploads")
    print(f"  {BOLD}API:{RESET}     {api_url}")
    print(f"  {BOLD}Retries:{RESET} {max_retries} per file\n")

    # ── Run uploads ───────────────────────────────────────────────────────────
    semaphore = asyncio.Semaphore(workers)
    results: List[Dict] = []
    done = 0
    success_count = 0
    failed_count = 0
    start_all = time.monotonic()

    connector = aiohttp.TCPConnector(limit=workers + 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            upload_one(session, pdf, api_url, semaphore, max_retries)
            for pdf in pdf_files
        ]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            done += 1

            if result["status"] == "success":
                success_count += 1
            else:
                failed_count += 1

            print_progress(done, total, success_count, failed_count, result["file"])

    total_time = time.monotonic() - start_all
    print()  # newline after progress bar

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"""
{BOLD}{'─' * 60}{RESET}
  {BOLD}Upload Complete!{RESET}
{'─' * 60}
  Total files    : {total}
  {GREEN}Successful     : {success_count}{RESET}
  {RED}Failed         : {failed_count}{RESET}
  Total time     : {total_time:.1f}s
  Avg per resume : {total_time/total:.1f}s
{'─' * 60}
""")

    # ── Print failures ────────────────────────────────────────────────────────
    failed_results = [r for r in results if r["status"] == "failed"]
    if failed_results:
        print(f"{RED}{BOLD}Failed files:{RESET}")
        for r in failed_results:
            print(f"  {RED}✗{RESET} {r['file']:<40}  {r['error']}")
        print()

    # ── Print successes ───────────────────────────────────────────────────────
    success_results = [r for r in results if r["status"] == "success"]
    if success_results:
        print(f"{GREEN}{BOLD}Successfully uploaded:{RESET}")
        for r in sorted(success_results, key=lambda x: x["candidate_name"] or ""):
            name = r["candidate_name"] or "Unknown"
            skills = r["skills_found"]
            cid = (r["candidate_id"] or "")[:8]
            print(f"  {GREEN}✓{RESET} {name:<35} skills: {skills:<3}  id: {cid}...")
        print()

    # ── Save results JSON ─────────────────────────────────────────────────────
    output_data = {
        "summary": {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "total_time_s": round(total_time, 1),
            "avg_time_per_resume_s": round(total_time / total, 1),
            "api_url": api_url,
            "folder": str(folder),
        },
        "results": sorted(results, key=lambda x: x["status"]),
    }
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"  {CYAN}Full results saved → {output_path}{RESET}\n")

    return 0 if failed_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Bulk upload resume PDFs to HR AI Platform"
    )
    parser.add_argument(
        "--folder", required=True,
        help="Folder containing PDF resume files (searched recursively)"
    )
    parser.add_argument(
        "--workers", type=int, default=5,
        help="Number of parallel uploads (default: 5)"
    )
    parser.add_argument(
        "--api", default="http://localhost:3006",
        help="API base URL (default: http://localhost:3006)"
    )
    parser.add_argument(
        "--output", default="upload_results.json",
        help="Path to save results JSON (default: upload_results.json)"
    )
    parser.add_argument(
        "--retry", type=int, default=2,
        help="Number of retries per file on failure (default: 2)"
    )
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.exists():
        print(f"{RED}Error: Folder not found: {folder}{RESET}")
        sys.exit(1)
    if not folder.is_dir():
        print(f"{RED}Error: Not a directory: {folder}{RESET}")
        sys.exit(1)

    print_banner()
    exit_code = asyncio.run(
        bulk_upload(
            folder=folder,
            api_url=args.api.rstrip("/"),
            workers=min(args.workers, 10),  # cap at 10
            output_path=Path(args.output),
            max_retries=args.retry,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
