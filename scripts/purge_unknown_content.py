#!/usr/bin/env python3
"""List or delete placeholder content rows (Content unknown-…)."""
from __future__ import annotations

import argparse
import os
from typing import Optional

import psycopg


def get_db_url() -> str:
    for key in (
        "DATABASE_URL_POSTGRES_NEW",
        "DATABASE_URL",
        "DATABASE_URL_POSTGRES_INTERNAL",
    ):
        value = os.getenv(key)
        if value:
            # allow using Render's internal host by stripping the trailing domain
            # when only the short hostname is provided in env
            if "@" in value and value.count("/") >= 3:
                url_head, url_tail = value.rsplit("/", 1)
                if ".render.com" in url_head and not url_head.endswith(".render.com"):
                    pass
            return value
    raise SystemExit("Set DATABASE_URL_POSTGRES_NEW (or DATABASE_URL) before running this script.")


def list_rows(conn: psycopg.Connection, limit: Optional[int]) -> list[tuple[str, str]]:
    sql = (
        "SELECT id, indexed_at FROM content "
        "WHERE title ILIKE %s "
        "ORDER BY indexed_at"
    )
    values = ["Content unknown-%"]
    if limit:
        sql += " LIMIT %s"
        values.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, tuple(values))
        return [(row[0], row[1].isoformat()) for row in cur.fetchall()]


def delete_rows(conn: psycopg.Connection) -> int:
    sql = "DELETE FROM content WHERE title ILIKE 'Content unknown-%'"
    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount
    conn.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50, help="Preview up to this many rows.")
    parser.add_argument("--apply", action="store_true", help="Delete matching rows.")
    args = parser.parse_args()

    db_url = get_db_url()
    with psycopg.connect(db_url) as conn:
        rows = list_rows(conn, args.limit)

    if not rows:
        print("No placeholder rows found.")
        return

    print(f"Found {len(rows)} placeholder rows (showing up to {args.limit}):")
    for ident, indexed in rows:
        print(f" - {indexed} | {ident}")

    if not args.apply:
        print("\nRe-run with --apply to delete all rows matching 'Content unknown-%'.")
        return

    with psycopg.connect(db_url) as conn:
        deleted = delete_rows(conn)
    print(f"Deleted {deleted} placeholder rows.")


if __name__ == "__main__":
    main()
