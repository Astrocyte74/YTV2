#!/usr/bin/env python3
"""Delete dashboard images on Render that no longer have a matching Postgres card."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Set

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg (v3) is required to run this script") from exc

DEFAULT_IMAGES_DIR = "/app/exports/images"

SQL_ALLOWED_IMAGES = """
WITH urls AS (
    SELECT summary_image_url AS url
    FROM content
    WHERE summary_image_url IS NOT NULL
      AND summary_image_url <> ''
    UNION ALL
    SELECT analysis->>'summary_image_ai2_url'
    FROM content
    WHERE analysis->>'summary_image_ai2_url' IS NOT NULL
)
SELECT DISTINCT regexp_replace(url, '^/exports/images/', '')
FROM urls
WHERE url IS NOT NULL
  AND url <> '';
"""

def load_allowed_filenames(db_url: str) -> Set[str]:
    """Return the set of filenames currently referenced by cards."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_ALLOWED_IMAGES)
            rows = cur.fetchall()
    return {row[0] for row in rows if row and row[0]}


def purge_orphans(images_dir: Path, allowed: Set[str], do_delete: bool) -> tuple[int, int]:
    deleted = 0
    kept = 0
    for path in images_dir.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name in allowed:
            kept += 1
            continue
        if do_delete:
            path.unlink(missing_ok=True)
        deleted += 1
    return kept, deleted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images-dir",
        default=os.getenv("EXPORTS_IMAGES_DIR", DEFAULT_IMAGES_DIR),
        help="Directory containing uploaded summary images (default: %(default)s)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete orphaned files (otherwise dry-run)",
    )
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL_POSTGRES_NEW") or os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL_POSTGRES_NEW (or DATABASE_URL) must be set")

    images_dir = Path(args.images_dir)
    if not images_dir.exists():
        raise SystemExit(f"Images directory not found: {images_dir}")

    allowed = load_allowed_filenames(db_url)
    print(f"Loaded {len(allowed)} referenced filenames from Postgres")

    kept, deleted = purge_orphans(images_dir, allowed, args.delete)
    action = "Deleted" if args.delete else "Would delete"
    print(f"{action} {deleted} orphaned files; kept {kept} referenced files in {images_dir}")


if __name__ == "__main__":
    main()
