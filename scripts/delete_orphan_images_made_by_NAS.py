#!/usr/bin/env python3
"""Delete dashboard images with no matching content row.

Supports two modes:
1. HTTP mode (legacy NAS workflow) – requires RENDER_DASHBOARD_URL + SYNC_SECRET/INGEST_TOKEN.
2. Filesystem mode (Render shell) – deletes from EXPORTS_IMAGES_DIR directly.

Run with --delete to actually remove files; otherwise it's a dry run.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Set

import psycopg
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete orphaned files (default: dry-run)",
    )
    return parser.parse_args()


def get_db_url() -> str:
    for key in (
        "DATABASE_URL_POSTGRES_NEW",
        "DATABASE_URL",
        "DATABASE_URL_POSTGRES_INTERNAL",
    ):
        val = os.getenv(key)
        if val:
            return val
    raise SystemExit("Set DATABASE_URL_POSTGRES_NEW (or DATABASE_URL) before running this script.")


def load_used_filenames(db_url: str) -> Set[str]:
    query = """
        SELECT summary_image_url,
               analysis_json->>'summary_image_ai2_url'
        FROM content
        WHERE summary_image_url IS NOT NULL
           OR analysis_json->>'summary_image_ai2_url' IS NOT NULL
    """
    used: Set[str] = set()
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for img1, img2 in cur.fetchall():
                for url in (img1, img2):
                    if not url:
                        continue
                    if "/exports/images/" in url:
                        used.add(url.rsplit("/exports/images/", 1)[-1])
                    else:
                        used.add(url.rsplit("/", 1)[-1])
    return used


def http_mode(used: Set[str], delete: bool) -> None:
    dash = os.getenv("RENDER_DASHBOARD_URL")
    token = os.getenv("SYNC_SECRET") or os.getenv("INGEST_TOKEN")
    if not dash or not token:
        raise SystemExit("HTTP mode requires RENDER_DASHBOARD_URL and SYNC_SECRET/INGEST_TOKEN")
    dash = dash.rstrip('/')

    res = requests.get(
        f"{dash}/api/admin/list-images",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    res.raise_for_status()
    files = res.json().get("files", [])

    orphaned = [name for name in files if name not in used]
    if not delete:
        print(f"Would delete {len(orphaned)} files via HTTP:")
        for name in orphaned:
            print(" -", name)
        return

    deleted = 0
    for name in orphaned:
        resp = requests.delete(
            f"{dash}/api/admin/delete-image/{name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        deleted += 1
    print(f"Deleted {deleted} orphaned images via HTTP")


def fs_mode(used: Set[str], delete: bool) -> None:
    images_dir = Path(os.getenv("EXPORTS_IMAGES_DIR", "/app/exports/images"))
    if not images_dir.exists():
        raise SystemExit(f"Images directory not found: {images_dir}")

    files = [p for p in images_dir.iterdir() if p.is_file()]
    orphaned = [p for p in files if p.name not in used]

    if not delete:
        print(f"Would delete {len(orphaned)} files from {images_dir}:")
        for path in orphaned:
            print(" -", path.name)
        return

    for path in orphaned:
        path.unlink(missing_ok=True)
    print(f"Deleted {len(orphaned)} orphaned files from {images_dir}")


def main() -> None:
    args = parse_args()
    db_url = get_db_url()
    used = load_used_filenames(db_url)

    if os.getenv("RENDER_DASHBOARD_URL") and (
        os.getenv("SYNC_SECRET") or os.getenv("INGEST_TOKEN")
    ):
        http_mode(used, args.delete)
    else:
        fs_mode(used, args.delete)


if __name__ == "__main__":
    main()
