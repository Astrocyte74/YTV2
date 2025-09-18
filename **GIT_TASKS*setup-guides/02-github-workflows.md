# GitHub Workflows Setup

## Overview

This guide sets up 4 powerful GitHub Actions workflows for AI task automation:
1. **Sync Tasks to Issues** - Auto-create Issues from tasks.md
2. **GPT Task Runner** - Manual AI task execution
3. **Label-triggered AI** - Phone-friendly automation
4. **Selective Sync** - Rate-limit safe syncing

**Note**: For complete setup, you'll also need the **Quality Gates** system (CI/CD pipeline) covered in `05-quality-gates.md`. Quality gates provide merge protection and automated code quality enforcement.

## Step 1: Create Workflow Directory

```bash
mkdir -p .github/workflows
```

## Step 2: Task Sync Workflows

### 2.1 Main Sync Workflow
Create `.github/workflows/sync-tasks-v2.yml`:

```yaml
name: Sync Tasks to Issues (v2 - Rate Limited)

on:
  push:
    paths:
      - 'tasks.md'
  workflow_dispatch: {}

jobs:
  sync-tasks:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4

      - name: Ensure labels and milestones from tasks.md
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            const md = fs.readFileSync('tasks.md', 'utf8');
            const lines = md.split('\n');

            // Add delay function to prevent rate limiting
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

            // Map phase headers -> milestone titles
            let currentMilestone = null;
            const tasks = [];

            for (let i = 0; i < lines.length; i++) {
              const line = lines[i];

              // Match "## Phase X: Name - ..."
              const phaseMatch = line.match(/^##\s+(Phase\s+\d+):\s+(.+?)\s*(?:-|—)/);
              if (phaseMatch) {
                currentMilestone = `${phaseMatch[1]}: ${phaseMatch[2].trim()}`;
                continue;
              }

              // Match "- [ ] (T-001) **Task Title**"
              const m = /^- \[ \] \((T-\d{3}[a-z]?)\) \*\*(.+?)\*\*/.exec(line);
              if (m) {
                const id = m[1];
                const title = `(${id}) ${m[2]}`;

                // Capture indented body until next top-level task
                let j = i + 1, bodyLines = [];
                while (j < lines.length && !lines[j].match(/^- \[ \] \(T-\d{3}[a-z]?\) \*\*/)) {
                  bodyLines.push(lines[j]); j++;
                }
                const body = bodyLines.join('\n');

                tasks.push({ id, title, body, milestone: currentMilestone });
              }
            }

            console.log(`Found ${tasks.length} tasks to sync`);

            async function ensureMilestone(title) {
              if (!title) return undefined;
              const { data: milestones } = await github.rest.issues.listMilestones({
                owner: context.repo.owner, repo: context.repo.repo, state: 'open'
              });
              let m = milestones.find(x => x.title === title);
              if (!m) {
                const created = await github.rest.issues.createMilestone({
                  owner: context.repo.owner, repo: context.repo.repo, title
                });
                m = created.data;
                console.log(`Created milestone: ${title}`);
              }
              return m.number;
            }

            for (const t of tasks) {
              const labels = [];
              if (t.milestone?.match(/^Phase 0/)) labels.push('phase-0');
              if (t.milestone?.match(/^Phase 1/)) labels.push('phase-1');
              if (t.milestone?.match(/^Phase 2/)) labels.push('phase-2');
              if (t.milestone?.match(/^Phase 3/)) labels.push('phase-3');
              if (t.milestone?.match(/^Phase 4/)) labels.push('phase-4');

              // ensure phase labels exist (ignore errors if already created)
              for (const L of labels) {
                try {
                  await github.rest.issues.createLabel({
                    owner: context.repo.owner, repo: context.repo.repo,
                    name: L, color: 'ededed'
                  });
                  await delay(100); // 100ms delay between label creations
                } catch (e) {}
              }

              // Search by exact title to avoid duplicates
              const { data: search } = await github.rest.search.issuesAndPullRequests({
                q: `repo:${context.repo.owner}/${context.repo.repo} in:title "${t.title}"`
              });
              let issueNumber = search.items?.find(i => i.title === t.title)?.number;

              const milestoneNumber = t.milestone ? await ensureMilestone(t.milestone) : undefined;

              const issueBody = t.body + '\n\n_Checklist:_\n- [ ] Implementation complete\n- [ ] Tests passing\n- [ ] Home inspection >90%\n- [ ] Git commit with ' + t.id + ' reference';

              if (!issueNumber) {
                const created = await github.rest.issues.create({
                  owner: context.repo.owner, repo: context.repo.repo,
                  title: t.title,
                  body: issueBody,
                  labels,
                  milestone: milestoneNumber
                });
                issueNumber = created.data.number;
                console.log(`✅ Created issue: ${t.title}`);
              } else {
                await github.rest.issues.update({
                  owner: context.repo.owner, repo: context.repo.repo,
                  issue_number: issueNumber,
                  body: issueBody,
                  labels,
                  milestone: milestoneNumber
                });
                console.log(`📝 Updated issue: ${t.title}`);
              }

              // Add delay between issue operations to prevent rate limiting
              await delay(750); // 750ms delay between each issue (slower but safer)
            }

      - name: Done
        run: echo "✅ All issues synced with rate limiting - no API errors!"
```

### 2.2 Selective Sync (For Large Task Lists)
Create `.github/workflows/sync-selective.yml`:

```yaml
name: Sync Selected Tasks (Range)

on:
  workflow_dispatch:
    inputs:
      start_task:
        description: "Start task number (e.g., 23 for T-023)"
        required: true
        default: "23"
      end_task:
        description: "End task number (e.g., 27 for T-027)"
        required: true
        default: "27"
      delay_ms:
        description: "Delay between operations (ms)"
        required: false
        default: "1000"

jobs:
  sync-range:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync task range from tasks.md
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            const md = fs.readFileSync('tasks.md', 'utf8');
            const lines = md.split('\n');

            const startNum = parseInt('${{ github.event.inputs.start_task }}');
            const endNum = parseInt('${{ github.event.inputs.end_task }}');
            const delayMs = parseInt('${{ github.event.inputs.delay_ms }}');

            console.log(`Syncing tasks T-${startNum.toString().padStart(3, '0')} to T-${endNum.toString().padStart(3, '0')}`);
            console.log(`Using ${delayMs}ms delays between operations`);

            // Add delay function
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

            // Helper: delay to avoid API rate limits
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

            // Extract tasks from tasks.md
            let currentMilestone = null;
            const tasks = [];
            for (let i = 0; i < lines.length; i++) {
              const line = lines[i];

              // Match "## Phase X: Name - ..."
              const phaseMatch = line.match(/^##\s+(Phase\s+\d+):\s+(.+?)\s*(?:-|—)/);
              if (phaseMatch) {
                currentMilestone = `${phaseMatch[1]}: ${phaseMatch[2].trim()}`;
                continue;
              }

              // Match tasks "- [ ] (T-001) **Title**"
              const m = /^- \[ \] \(T-(\d{3}[a-z]?)\) \*\*(.+?)\*\*/.exec(line);
              if (m) {
                const idRaw = m[1]; // e.g., 023 or 023a
                const idNum = parseInt(idRaw.slice(0, 3), 10); // numeric part
                const title = `(T-${idRaw}) ${m[2]}`;

                // Collect body until next top‑level task
                let j = i + 1, bodyLines = [];
                while (j < lines.length && !lines[j].match(/^- \[ \] \(T-\d{3}[a-z]?\) \*\*/)) {
                  bodyLines.push(lines[j]); j++;
                }
                const body = bodyLines.join('\n');

                tasks.push({ idRaw, idNum, title, body, milestone: currentMilestone });
              }
            }

            // Filter by selected range
            const selected = tasks.filter(t => t.idNum >= startNum && t.idNum <= endNum);
            console.log(`Found ${selected.length} tasks in range`);

            async function ensureMilestone(title) {
              if (!title) return undefined;
              const { data: milestones } = await github.rest.issues.listMilestones({
                owner: context.repo.owner, repo: context.repo.repo, state: 'open'
              });
              let m = milestones.find(x => x.title === title);
              if (!m) {
                const created = await github.rest.issues.createMilestone({
                  owner: context.repo.owner, repo: context.repo.repo, title
                });
                m = created.data;
                console.log(`Created milestone: ${title}`);
              }
              return m.number;
            }

            for (const t of selected) {
              const labels = [];
              if (t.milestone?.match(/^Phase 0/)) labels.push('phase-0');
              if (t.milestone?.match(/^Phase 1/)) labels.push('phase-1');
              if (t.milestone?.match(/^Phase 2/)) labels.push('phase-2');
              if (t.milestone?.match(/^Phase 3/)) labels.push('phase-3');
              if (t.milestone?.match(/^Phase 4/)) labels.push('phase-4');

              // Ensure labels exist (ignore if already exist)
              for (const L of labels) {
                try {
                  await github.rest.issues.createLabel({
                    owner: context.repo.owner, repo: context.repo.repo,
                    name: L, color: 'ededed'
                  });
                  await delay(100);
                } catch (e) {}
              }

              // Upsert by exact title
              const { data: search } = await github.rest.search.issuesAndPullRequests({
                q: `repo:${context.repo.owner}/${context.repo.repo} in:title "${t.title}"`
              });
              let issueNumber = search.items?.find(i => i.title === t.title)?.number;

              const milestoneNumber = t.milestone ? await ensureMilestone(t.milestone) : undefined;

              const issueBody = `${t.body}

_Checklist:_
- [ ] Implementation complete
- [ ] Tests passing
- [ ] Home inspection >90%
- [ ] Git commit with (T-${t.idRaw}) reference`;

              if (!issueNumber) {
                const created = await github.rest.issues.create({
                  owner: context.repo.owner, repo: context.repo.repo,
                  title: t.title,
                  body: issueBody,
                  labels,
                  milestone: milestoneNumber
                });
                issueNumber = created.data.number;
                console.log(`✅ Created issue: ${t.title}`);
              } else {
                await github.rest.issues.update({
                  owner: context.repo.owner, repo: context.repo.repo,
                  issue_number: issueNumber,
                  body: issueBody,
                  labels,
                  milestone: milestoneNumber
                });
                console.log(`📝 Updated issue: ${t.title}`);
              }

              await delay(delayMs);
            }

      - name: Done
        run: echo "✅ Selected task range synced successfully!"
```

## Step 3: AI Task Execution Workflows

### 3.1 Manual GPT Task Runner
Create `.github/workflows/gpt-task-runner.yml`:

```yaml
name: GPT Task Runner

on:
  workflow_dispatch:
    inputs:
      task_id:
        description: "Task ID (e.g., T-001)"
        required: true
      working_repo:
        description: "Target folder to change (. for root, or subfolder name)"
        required: true
        default: "."
      model:
        description: "Choose OpenAI model"
        required: true
        type: choice
        default: "gpt-5-mini"
        options:
          - gpt-5-nano
          - gpt-5-mini
          - gpt-5
          - gpt-4.1
          - gpt-4o
          - gpt-4o-mini

jobs:
  run-task:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install openai regex

      - name: Run GPT task
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          TASK_ID: ${{ github.event.inputs.task_id }}
          WORKING_REPO: ${{ github.event.inputs.working_repo }}
          OPENAI_MODEL: ${{ github.event.inputs.model }}
        run: |
          python scripts/gpt_task_runner.py

      - name: Install GitHub CLI
        run: |
          sudo apt-get update
          sudo apt-get install -y gh

      - name: Create PR
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          BRANCH="feat/${{ github.event.inputs.task_id }}-gpt"
          git config user.name "ai-runner"
          git config user.email "ai-runner@users.noreply.github.com"
          git checkout -b "$BRANCH" || true
          git add -A
          git commit -m "${{ github.event.inputs.task_id }}: GPT patch" || echo "Nothing to commit"
          git push -u origin "$BRANCH" || true
          gh pr create --title "${{ github.event.inputs.task_id }}: GPT implementation" \
            --body "Automated patch by GPT Task Runner.\nTask: ${{ github.event.inputs.task_id }}\nModel: ${{ github.event.inputs.model }}" \
            --base main || true
```

### 3.2 Label-Triggered AI (Phone-Friendly)
Create `.github/workflows/label-task-runner.yml`:

```yaml
name: Label-triggered AI Runner

on:
  issues:
    types: [labeled]

jobs:
  # Guard at workflow level (no-op if it's not the ai-run label)
  run-on-label:
    if: github.event.label.name == 'ai-run'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      issues: write
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Extract T-ID from issue title
        id: parse
        run: |
          title="${{ github.event.issue.title }}"
          if [[ "$title" =~ \(T-[0-9]{3}[a-z]?\) ]]; then
            tid=$(echo "$title" | sed -n 's/.*(\(T-[0-9][0-9][0-9][a-z]*\)).*/\1/p')
            echo "task_id=$tid" >> $GITHUB_OUTPUT
          else
            echo "No T-ID found in issue title"; exit 1
          fi

      - name: Post start comment
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              body: `🤖 Starting AI run for **${{ steps.parse.outputs.task_id }}**…`
            });

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install openai regex

      - name: Run GPT task
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          TASK_ID: ${{ steps.parse.outputs.task_id }}
          WORKING_REPO: .
          OPENAI_MODEL: gpt-5-mini
        run: |
          python scripts/gpt_task_runner.py

      - name: Install GitHub CLI
        run: |
          sudo apt-get update
          sudo apt-get install -y gh

      - name: Create PR
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          BRANCH="feat/${{ steps.parse.outputs.task_id }}-gpt"
          git config user.name "ai-runner"
          git config user.email "ai-runner@users.noreply.github.com"
          git checkout -b "$BRANCH" || true
          git add -A
          git commit -m "${{ steps.parse.outputs.task_id }}: GPT patch" || echo "Nothing to commit"
          git push -u origin "$BRANCH" || true
          gh pr create --title "${{ steps.parse.outputs.task_id }}: GPT implementation" \
            --body "Automated patch by AI Task Runner.\nTask: ${{ steps.parse.outputs.task_id }}" \
            --base main || true

      - name: Comment PR link & clean up label
        uses: actions/github-script@v7
        with:
          script: |
            const { data: prs } = await github.rest.pulls.list({
              owner: context.repo.owner, repo: context.repo.repo, state: 'open', head: `${context.repo.owner}:feat/${{ steps.parse.outputs.task_id }}-gpt`
            });
            const link = prs.length ? prs[0].html_url : '(no changes created)';
            await github.rest.issues.createComment({
              owner: context.repo.owner, repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              body: `✅ Run complete. PR: ${link}`
            });
            await github.rest.issues.removeLabel({
              owner: context.repo.owner, repo: context.repo.repo,
              issue_number: context.payload.issue.number, name: 'ai-run'
            });
```

## Step 4: GPT Task Runner Script

Create `scripts/gpt_task_runner.py`:

```python
# scripts/gpt_task_runner.py
import os, re, subprocess, pathlib, sys
from openai import OpenAI

ROOT = pathlib.Path(".")
TASK_ID = os.environ["TASK_ID"]
WORKING_REPO = os.environ.get("WORKING_REPO", ".")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")

def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")

# Load spec files (create empty ones if they don't exist)
def safe_read(filename):
    try:
        return read(filename)
    except FileNotFoundError:
        return f"# {filename}\n(File not found - add content as needed)"

spec = safe_read("spec.md")
tasks = read("tasks.md")
constitution = safe_read("CONSTITUTION.md")
glossary = safe_read("GLOSSARY.md")

# Extract the task block by T-ID
m = re.search(rf"- \[ \] \({re.escape(TASK_ID)}\).*?(?=\n- \[ \] \(|\Z)", tasks, re.S)
if not m:
    print(f"Task {TASK_ID} not found in tasks.md", file=sys.stderr)
    sys.exit(1)
task_block = m.group(0)

system_prompt = """You are a senior engineer working from a project specification.
Follow any Constitutional principles if provided. Use available specs for context.
Produce minimal, targeted changes to implement EXACTLY the requested task.
Return a unified diff patch (git apply format) for existing files and/or explicit new files with full paths.
Include tests when appropriate. Focus on practical implementation."""

user_prompt = f"""
Project Context:
{spec}

Constitution (constraints):
{constitution}

Glossary (terminology):
{glossary}

Task to implement:
{task_block}

Working directory: {WORKING_REPO}

Goal: Implement ONLY {TASK_ID}.
Output format:
1) Brief implementation plan (3-5 bullets)
2) Unified diff patch starting with 'diff --git' OR 'NEW FILE:' sections
3) Testing/verification steps
"""

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

resp = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
)

content = resp.choices[0].message.content or ""
print(content)

# Try to auto-apply a unified diff if present
patch_start = content.find("diff --git")
if patch_start != -1:
    patch = content[patch_start:]
    (ROOT / "ai.patch").write_text(patch, encoding="utf-8")
    subprocess.run(["git", "apply", "ai.patch", "--directory", WORKING_REPO], check=False)
```

## Step 5: Commit and Test

```bash
# Commit all workflows
git add .github/workflows/ scripts/
git commit -m "Add GitHub AI automation workflows"
git push origin main

# Test the setup
# 1. Go to Actions tab - you should see 4 workflows
# 2. Run "Sync Tasks to Issues" manually
# 3. Check Issues tab for auto-created issues
# 4. Add 'ai-run' label to any issue to test automation
```

## Next Steps

✅ **Workflows configured**
➡️ **Continue to `05-quality-gates.md`** for CI/CD and merge protection setup
➡️ **Then proceed to `03-mobile-usage.md`** for phone-friendly usage

## Troubleshooting

- **"OPENAI_API_KEY not found"**: Add the secret in repository settings
- **"Permission denied"**: Check workflow permissions in repository settings
- **"Rate limit exceeded"**: Use selective sync for large task lists
- **"No task found"**: Ensure task IDs in tasks.md match format `(T-001)`

> Note: If you encounter `temperature` errors from the OpenAI API, remove the `temperature` parameter from your runner script. GPT‑5 family models only use the default temperature.
