import unittest

from modules.postgres_content_index import PostgreSQLContentIndex


class _FakeCursor:
    def __init__(self, rowcounts):
        self.rowcounts = list(rowcounts)
        self.rowcount = 0
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        self.rowcount = self.rowcounts.pop(0)

    def close(self):
        return None


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _DeleteIndex(PostgreSQLContentIndex):
    def __init__(self, conn, *, has_follow_up_runs=True, has_follow_up_suggestions=True):
        self._conn = conn
        self._has_runs = has_follow_up_runs
        self._has_suggestions = has_follow_up_suggestions

    def _get_connection(self):
        return self._conn

    def _has_follow_up_research_table(self, conn=None):
        return self._has_runs

    def _has_follow_up_suggestions_table(self, conn=None):
        return self._has_suggestions


class DeleteContentTests(unittest.TestCase):
    def test_delete_content_also_purges_follow_up_rows(self):
        cursor = _FakeCursor([3, 2, 5, 1])
        conn = _FakeConnection(cursor)
        index = _DeleteIndex(conn)

        result = index.delete_content("abc123video")

        self.assertTrue(result["success"])
        self.assertEqual(result["follow_up_runs_deleted"], 3)
        self.assertEqual(result["follow_up_suggestions_deleted"], 2)
        self.assertEqual(result["summaries_deleted"], 5)
        self.assertEqual(result["content_deleted"], 1)
        self.assertTrue(conn.committed)
        self.assertTrue(conn.closed)
        self.assertFalse(conn.rolled_back)

        statements = [sql for sql, _ in cursor.executed]
        self.assertIn("DELETE FROM follow_up_research_runs WHERE video_id = %s", statements[0])
        self.assertIn("DELETE FROM follow_up_suggestions WHERE video_id = %s", statements[1])
        self.assertIn("DELETE FROM content_summaries WHERE video_id = %s", statements[2])
        self.assertIn("DELETE FROM content WHERE video_id = %s", statements[3])


if __name__ == "__main__":
    unittest.main()
