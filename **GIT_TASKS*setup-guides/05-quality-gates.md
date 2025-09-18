# Quality Gates Setup

## Overview

This guide implements **Step 4: Quality Gates** - turning your CI into merge-blocking quality enforcement. After setup, all code changes (mobile AI, Claude Code, manual development) must pass quality checks before merging to main.

## What Quality Gates Provide

✅ **Merge Protection** - No direct pushes to main branch allowed
✅ **CI Pipeline** - PostgreSQL + pgvector testing with home inspection
✅ **Automated Scoring** - Quality scores with 90% threshold enforcement
✅ **PR Comments** - Automatic inspection results posted to pull requests
✅ **Code Review** - Required reviewer approval via CODEOWNERS
✅ **Universal Enforcement** - Same rules apply to all development methods

## Step 1: Create CI Pipeline

Create `.github/workflows/ci.yml`:

```yaml
name: CI Pipeline (T-000f)

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

permissions:
  contents: read

jobs:
  ci:
    name: Tests + Home Inspection
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_USER: testuser
          POSTGRES_DB: testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r ci/requirements.txt

      - name: Run tests
        run: |
          python -m pytest tests/ -v

      - name: Run home inspection
        id: inspection
        run: |
          python ci/run_home_inspection.py
        env:
          DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: |
            test-results.xml
            coverage.xml

      - name: Upload inspection report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: home-inspection-report
          path: ci/inspection_report.json
```

## Step 2: Create Home Inspection Script

Create `ci/run_home_inspection.py`:

```python
#!/usr/bin/env python3
"""
Home inspection script for unified platform CI.
Runs integrity checks and reports pass/fail with 90% threshold.
"""
import json
import os
import sys
import psycopg2
from typing import Dict, Any

def get_db_connection():
    """Get database connection from environment."""
    database_url = os.environ.get('DATABASE_URL', 'postgresql://testuser:testpass@localhost:5432/testdb')
    return psycopg2.connect(database_url)

def setup_schema(conn):
    """Create test schema and sample data."""
    with conn.cursor() as cur:
        # Enable pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Create tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_artifacts (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                embedding vector(1536),
                workspace_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_heads (
                workspace_id INTEGER PRIMARY KEY,
                current_head_id INTEGER REFERENCES research_artifacts(id),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Insert sample data
        cur.execute("""
            INSERT INTO research_artifacts (title, content, embedding, workspace_id)
            VALUES
                ('Sample Research 1', 'Content for research 1', '[0.1,0.2,0.3]'::vector, 1),
                ('Sample Research 2', 'Content for research 2', '[0.4,0.5,0.6]'::vector, 1),
                ('Sample Research 3', 'Content for research 3', '[0.7,0.8,0.9]'::vector, 2)
            ON CONFLICT DO NOTHING;
        """)

        cur.execute("""
            INSERT INTO workspace_heads (workspace_id, current_head_id)
            VALUES (1, 1), (2, 3)
            ON CONFLICT (workspace_id) DO UPDATE SET current_head_id = EXCLUDED.current_head_id;
        """)

        conn.commit()

def run_integrity_checks(conn, thresholds=None):
    """Run integrity checks and return results."""
    if thresholds is None:
        thresholds = {
            'min_artifacts': 3,
            'max_orphan_artifacts': 0,
            'min_embedding_coverage': 0.9,
            'max_avg_latency_ms': 100
        }

    results = {}

    with conn.cursor() as cur:
        # Check 1: Minimum artifacts exist
        cur.execute("SELECT COUNT(*) FROM research_artifacts;")
        artifact_count = cur.fetchone()[0]
        results['artifact_count'] = {
            'value': artifact_count,
            'threshold': thresholds['min_artifacts'],
            'pass': artifact_count >= thresholds['min_artifacts']
        }

        # Check 2: No orphan artifacts (artifacts without valid workspace heads)
        cur.execute("""
            SELECT COUNT(*) FROM research_artifacts ra
            LEFT JOIN workspace_heads wh ON ra.workspace_id = wh.workspace_id
            WHERE wh.workspace_id IS NULL;
        """)
        orphan_count = cur.fetchone()[0]
        results['orphan_artifacts'] = {
            'value': orphan_count,
            'threshold': thresholds['max_orphan_artifacts'],
            'pass': orphan_count <= thresholds['max_orphan_artifacts']
        }

        # Check 3: Embedding coverage
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(embedding) as with_embeddings
            FROM research_artifacts;
        """)
        total, with_embeddings = cur.fetchone()
        embedding_coverage = with_embeddings / total if total > 0 else 0
        results['embedding_coverage'] = {
            'value': embedding_coverage,
            'threshold': thresholds['min_embedding_coverage'],
            'pass': embedding_coverage >= thresholds['min_embedding_coverage']
        }

        # Check 4: Query latency (simple performance check)
        import time
        start_time = time.time()
        cur.execute("SELECT * FROM research_artifacts LIMIT 10;")
        cur.fetchall()
        latency_ms = (time.time() - start_time) * 1000
        results['query_latency'] = {
            'value': latency_ms,
            'threshold': thresholds['max_avg_latency_ms'],
            'pass': latency_ms <= thresholds['max_avg_latency_ms']
        }

    return results

def calculate_overall_health(results):
    """Calculate overall health percentage."""
    passed_checks = sum(1 for check in results.values() if check['pass'])
    total_checks = len(results)
    return (passed_checks / total_checks) * 100

def main():
    """Main inspection function."""
    try:
        print("🏠 Starting home inspection...")

        # Connect to database
        conn = get_db_connection()
        print("✅ Database connection established")

        # Setup schema and sample data
        setup_schema(conn)
        print("✅ Schema and sample data ready")

        # Run integrity checks
        results = run_integrity_checks(conn)
        print("✅ Integrity checks completed")

        # Calculate overall health
        overall_health = calculate_overall_health(results)
        print(f"📊 Overall health: {overall_health:.1f}%")

        # Determine pass/fail (90% threshold)
        passed = overall_health >= 90.0

        # Create inspection report
        report = {
            'ok': passed,
            'overallHealth': {
                'percentage': overall_health,
                'threshold': 90.0
            },
            'checks': results,
            'summary': {
                'total_checks': len(results),
                'passed_checks': sum(1 for check in results.values() if check['pass']),
                'failed_checks': sum(1 for check in results.values() if not check['pass'])
            }
        }

        # Write report file
        os.makedirs('ci', exist_ok=True)
        with open('ci/inspection_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        # Print results
        print("\n🔍 INSPECTION RESULTS:")
        for check_name, check_result in results.items():
            status = "✅ PASS" if check_result['pass'] else "❌ FAIL"
            print(f"  {check_name}: {status} ({check_result['value']} vs {check_result['threshold']})")

        print(f"\n🏠 HOME INSPECTION: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"📊 Score: {overall_health:.1f}% (threshold: 90%)")

        # Exit with appropriate code
        sys.exit(0 if passed else 1)

    except Exception as e:
        print(f"❌ Home inspection failed: {e}")
        # Create failure report
        report = {
            'ok': False,
            'error': str(e),
            'overallHealth': {'percentage': 0, 'threshold': 90.0}
        }
        os.makedirs('ci', exist_ok=True)
        with open('ci/inspection_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    main()
```

## Step 3: Create CI Requirements

Create `ci/requirements.txt`:

```
psycopg2-binary>=2.9
pytest>=7.0
```

## Step 4: Create PR Quality Summary Workflow

Create `.github/workflows/pr-quality-summary.yml`:

```yaml
name: PR Quality Summary

on:
  workflow_run:
    workflows: ["CI Pipeline (T-000f)"]   # Must match the name in ci.yml
    types: [completed]

permissions:
  actions: read          # Required to read artifacts from CI runs
  contents: read
  issues: write
  pull-requests: write

jobs:
  summarize:
    runs-on: ubuntu-latest
    # Only summarize PR-triggered CI runs
    if: ${{ github.event.workflow_run.event == 'pull_request' }}

    steps:
      - name: Install jq & unzip
        run: |
          sudo apt-get update
          sudo apt-get install -y jq unzip

      - name: Download inspection artifact
        uses: actions/github-script@v7
        with:
          script: |
            const run_id = context.payload.workflow_run.id;
            const { data: arts } = await github.rest.actions.listWorkflowRunArtifacts({
              owner: context.repo.owner, repo: context.repo.repo, run_id
            });

            // Artifact name from CI workflow
            const artifact = arts.artifacts.find(a => a.name === 'home-inspection-report');
            if (!artifact) {
              core.setFailed('No artifact named "home-inspection-report" found.');
              return;
            }

            const zip = await github.rest.actions.downloadArtifact({
              owner: context.repo.owner, repo: context.repo.repo,
              artifact_id: artifact.id, archive_format: 'zip'
            });

            const fs = require('fs');
            fs.writeFileSync('report.zip', Buffer.from(zip.data));

      - name: Unzip & parse score
        id: parse
        run: |
          unzip -o report.zip -d report >/dev/null 2>&1 || true

          # The CI writes to ci/inspection_report.json
          if [ -f report/ci/inspection_report.json ]; then
            # Extract boolean 'ok' status and any percentage if available
            STATUS=$(jq -r '.ok // false' report/ci/inspection_report.json)
            # Try to get a percentage score if available, otherwise show pass/fail
            SCORE=$(jq -r '.overallHealth.percentage // (.ok | if . then "✅ PASS" else "❌ FAIL" end)' report/ci/inspection_report.json)
          elif [ -f report/inspection_report.json ]; then
            # Alternative path if uploaded differently
            STATUS=$(jq -r '.ok // false' report/inspection_report.json)
            SCORE=$(jq -r '.overallHealth.percentage // (.ok | if . then "✅ PASS" else "❌ FAIL" end)' report/inspection_report.json)
          else
            STATUS="unknown"
            SCORE="❓ No report found"
          fi

          echo "status=$STATUS" >> $GITHUB_OUTPUT
          echo "score=$SCORE" >> $GITHUB_OUTPUT

      - name: Comment/Update PR with score
        uses: actions/github-script@v7
        with:
          script: |
            const pr = context.payload.workflow_run.pull_requests?.[0];
            if (!pr) { return; }

            const status = `${{ steps.parse.outputs.status }}`; // 'true' | 'false' | 'unknown'
            const score  = `${{ steps.parse.outputs.score }}`;

            const header = "### 🏠 Home Inspection";
            const body = [
              header,
              `**Status:** ${status === 'true' ? '✅ Passing' : status === 'false' ? '❌ Failing' : '❓ Unknown'}`,
              `**Score:** ${score}`,
              `**Artifacts:** see **home-inspection-report** in the [CI run](${context.payload.workflow_run.html_url})`,
              ``,
              `> Merges remain blocked until all required checks are green.`
            ].join('\n');

            // Upsert: edit an existing comment with our header, otherwise create new
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner, repo: context.repo.repo, issue_number: pr.number, per_page: 100
            });
            const existing = comments.find(c => c.body && c.body.startsWith(header));

            if (existing) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner, repo: context.repo.repo, comment_id: existing.id, body
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner, repo: context.repo.repo, issue_number: pr.number, body
              });
            }
```

## Step 5: Create CODEOWNERS File

Create `.github/CODEOWNERS`:

```
# Global repository ownership
* @yourusername

# Project-specific areas (customize for your project)
/src/**                   @yourusername
/lib/**                   @yourusername

# Critical infrastructure
/.github/workflows/**     @yourusername
/ci/**                    @yourusername
```

> Replace `@yourusername` with your GitHub username

## Step 6: Create Sample Test

Create `tests/test_sample.py`:

```python
def test_placeholder():
    # Minimal test to ensure pytest runs in CI. Real unit tests should be added per project.
    assert 1 == 1
```

## Step 7: Configure Branch Protection (Manual)

This step must be done in the GitHub web interface:

1. Go to **Settings** → **Branches**
2. Click **Add rule**
3. Configure protection rule:
   - **Branch name pattern**: `main`
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**
     - Search and select: **"Tests + Home Inspection"**
   - ✅ **Require review from CODEOWNERS**
   - ✅ **Restrict pushes that create files that bypass path-based restrictions**
4. Click **Create**

## Step 8: Test the Quality Gates

1. **Commit all quality gate files**:
   ```bash
   git add .github/workflows/ci.yml .github/workflows/pr-quality-summary.yml
   git add .github/CODEOWNERS ci/ tests/
   git commit -m "Add quality gates system with CI pipeline and merge protection"
   git push origin main
   ```

2. **Create a test PR**:
   ```bash
   git checkout -b test/quality-gates
   echo "# Quality Gates Test" > quality-test.md
   git add quality-test.md
   git commit -m "Test: Verify quality gates system"
   git push -u origin test/quality-gates
   ```

3. **Create PR and verify**:
   - Go to GitHub and create a PR from `test/quality-gates` → `main`
   - Watch CI run automatically
   - Verify PR comment appears with quality score
   - Confirm merge is blocked until checks pass

## Expected Results

After setup, all code changes will:
- ✅ **Require PRs** - No direct pushes to main allowed
- ✅ **Trigger CI** - PostgreSQL testing + home inspection
- ✅ **Get scored** - Quality percentage with 90% threshold
- ✅ **Block merges** - Failed CI prevents merging
- ✅ **Require review** - CODEOWNERS approval needed
- ✅ **Show status** - Automated PR comments with pass/fail

## Quality Gate Behavior

| Scenario | CI Result | PR Status | Merge Allowed |
|----------|-----------|-----------|---------------|
| All checks pass, score ≥90% | ✅ Pass | ✅ Can merge | ✅ Yes |
| Some checks fail, score <90% | ❌ Fail | ❌ Blocked | ❌ No |
| CI error/timeout | ❌ Fail | ❌ Blocked | ❌ No |
| No CODEOWNERS approval | ⚠️ Pending | ❌ Blocked | ❌ No |

## Customization

### Adjust Quality Thresholds
Edit thresholds in `ci/run_home_inspection.py`:
```python
thresholds = {
    'min_artifacts': 3,
    'max_orphan_artifacts': 0,
    'min_embedding_coverage': 0.9,  # 90% embedding coverage
    'max_avg_latency_ms': 100
}
```

### Add Project-Specific Checks
Extend `run_integrity_checks()` with your own validation logic:
```python
# Check 5: Custom business logic
cur.execute("SELECT COUNT(*) FROM your_table WHERE condition;")
custom_result = cur.fetchone()[0]
results['custom_check'] = {
    'value': custom_result,
    'threshold': your_threshold,
    'pass': custom_result >= your_threshold
}
```

### Change Score Threshold
Modify the 90% threshold in both files:
- `ci/run_home_inspection.py`: Change `passed = overall_health >= 90.0`
- `.github/workflows/pr-quality-summary.yml`: Update comment text

## Next Steps

✅ **Quality gates configured**
➡️ **Return to `03-mobile-usage.md`** to test mobile workflows with quality enforcement
➡️ **Reference `04-troubleshooting.md`** for common quality gate issues

## Troubleshooting

- **"Resource not accessible by integration"**: Add `actions: read` permission to PR Quality Summary workflow
- **"No artifact found"**: Verify CI workflow name matches exactly in both workflows
- **"Always skipped"**: PR Quality Summary only runs on PR events, not direct pushes
- **"Merge not blocked"**: Configure branch protection rules in repository settings
- **"CI always fails"**: Check PostgreSQL service setup and database connection
- **"Missing CODEOWNERS"**: Add the file and assign the correct username

> **Note**: Quality gates apply universally - mobile AI, Claude Code, and manual development all follow the same rules.