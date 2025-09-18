# Troubleshooting Guide

🔧 **Solutions for common issues when setting up and using GitHub AI automation**

## Setup Issues

### 🚫 **"Repository not found" or "Permission denied"**

**Symptoms**: Can't push to repository, workflows don't appear  
**Causes**: Insufficient repository permissions

**Solutions**:
```bash
# Check repository access
git remote -v
git push origin main  # Test push access

# Verify repository settings
# Go to Settings → Actions → General
# Ensure "Allow all actions and reusable workflows" is selected
# Set Workflow permissions to "Read and write permissions"
```

### 🛂 **"Actions can't open PRs / push branches"**

**Symptoms**: Workflows run but fail when creating branches or PRs  
**Causes**: Insufficient GitHub Actions workflow permissions

**Solutions**:
```bash
# In GitHub (UI):
# Settings → Actions → General
# - Workflow permissions: **Read and write permissions** (MANDATORY)
# - ✅ Allow GitHub Actions to create and approve pull requests (MANDATORY)

# In workflow YAML, ensure permissions (example):
permissions:
  contents: write
  pull-requests: write
```

### 🔑 **"OPENAI_API_KEY not found" or API errors**

**Symptoms**: GPT workflows fail with authentication errors  
**Causes**: Missing or incorrect API key

**Solutions**:
1. **Add API key**: Settings → Secrets and variables → Actions  
2. **Add secret**: `OPENAI_API_KEY` with your OpenAI key  
3. **Test locally**:
   ```bash
   export OPENAI_API_KEY="your_key_here"
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   ```
4. **Verify GPT-5 access**: Ensure your OpenAI account has GPT-5 model access  
5. **Model selection**: If you see "model not found"/"unsupported", pick a valid model in the workflow dropdown (e.g., `gpt-5-mini`, `gpt-5`, `gpt-5-nano`, or `gpt-4.1`) or update the default in `gpt_task_runner.py`.

### ❌ **"Workflow file invalid" or YAML syntax errors**

**Symptoms**: Workflows show as invalid in Actions tab  
**Causes**: YAML formatting issues

**Solutions**:
```bash
# Validate YAML syntax (requires PyYAML)
python -m pip install --quiet pyyaml
python - <<'PY'
import sys, yaml, glob
for p in glob.glob('.github/workflows/*.yml'):
    with open(p) as f:
        yaml.safe_load(f)
        print("✓ valid:", p)
PY

# Check indentation (use spaces, not tabs)
sed -n '1,40p' .github/workflows/<your-workflow>.yml | nl -ba
```

# Common fixes:
# 1. Ensure consistent indentation (2 spaces)
# 2. Remove trailing commas in script blocks
# 3. Escape special characters in strings

## Sync Issues

### ⚠️ **"API rate limit exceeded"**

**Symptoms**: Sync workflow fails after creating some issues  
**Causes**: Too many GitHub API calls too quickly

**Solutions**:
1. **Wait 10-15 minutes** for rate limit reset  
2. **Use selective sync**:
   ```
   Actions → "Sync Selected Tasks (Range)"
   start_task: 25, end_task: 29 (5 tasks at a time)
   delay_ms: 1000 (1 second between operations)
   ```
3. **Increase delays** in workflow (edit sync-tasks-v2.yml):
   ```javascript
   await delay(1000); // Increase from 750ms to 1000ms
   ```

### 📝 **"No tasks found" or issues not created**

**Symptoms**: Sync completes but no issues appear  
**Causes**: Task format doesn't match expected pattern

**Solutions**:
```markdown
# Correct task format in tasks.md:
- [ ] (T-001) **Task Title Here**
  - **Implementation**: Description
  - **Acceptance**: Success criteria

# Common mistakes:
❌ - [ ] T-001 **Task Title**          # Missing parentheses
❌ - [ ] (T-01) **Task Title**         # Wrong ID format
❌ - [x] (T-001) **Completed Task**    # Checked box
✅ - [ ] (T-001) **Task Title**        # Correct format
```

### 🏷️ **Issues created without proper labels/milestones**

**Symptoms**: Issues appear but missing phase labels or milestones  
**Causes**: Phase headers not properly formatted

**Solutions**:
```markdown
# Correct phase header format:
## Phase 1: Core Features - Week 2

# The workflow looks for this pattern:
# "## Phase X: Name - ..." or "## Phase X: Name — ..."

# Common mistakes:
❌ # Phase 1: Core Features              # Missing ##
❌ ## Phase 1 Core Features              # Missing colon
❌ ## Phase 1: Core Features (Week 2)    # No dash separator
✅ ## Phase 1: Core Features - Week 2    # Correct format
```

### 🏷️ **"Can't find `ai-run` label on mobile"**

**Symptoms**: Label-triggered workflow won't start because `ai-run` label isn't selectable  
**Causes**: Label not created in the repository yet

**Solutions**:
- **Create via Web**: Issues → Labels → New label → Name: `ai-run`  
- **Create via CLI**:
  ```bash
  gh label create ai-run --color "5319e7" --description "Trigger AI task runner"
  ```

## AI Execution Issues

### 🤖 **"No T-ID found in issue title"**

**Symptoms**: Label-triggered workflow fails immediately  
**Causes**: Issue title doesn't contain proper task ID

**Solutions**:
1. **Check issue title format**: Must be `(T-001) Task Name`  
2. **Manually fix titles**:
   ```
   Wrong: "T-001 Setup environment"
   Right: "(T-001) Setup environment"
   ```
3. **Re-sync issues** if many have wrong format

### 💭 **GPT workflow runs but creates empty/minimal PR**

**Symptoms**: PR created but with no meaningful changes  
**Causes**: Task description too vague or AI needs more context

**Solutions**:
1. **Improve task descriptions**:
   ```markdown
   # Vague (poor AI output):
   - [ ] (T-001) **Fix bugs**

   # Specific (good AI output):
   - [ ] (T-001) **Fix authentication timeout issue**
     - **Implementation**: Update session timeout from 30min to 2hrs
     - **Location**: /src/auth/session.py
     - **Testing**: Verify users stay logged in during long sessions
     - **Acceptance**: No timeout errors under 2 hours
   ```

2. **Add project context** (spec.md, CONSTITUTION.md):
   ```markdown
   # spec.md
   ## Technology Stack
   - Python 3.11 with Flask
   - PostgreSQL database
   - React frontend

   ## Coding Standards
   - Use type hints in Python
   - Include unit tests for all functions
   - Follow PEP 8 style guide
   ```

### 🔧 **"Unable to resolve action cli/cli-action"**

**Symptoms**: GPT workflow fails when trying to install GitHub CLI  
**Causes**: Using non-existent GitHub Action

**Solutions**:
Already fixed in the provided workflows, but if you see this:
```yaml
# Wrong:
- name: Install GitHub CLI
  uses: cli/cli-action@v2

# Right:
- name: Install GitHub CLI
  run: |
    sudo apt-get update
    sudo apt-get install -y gh
```

### 🌡️ **"BadRequestError: temperature parameter not supported"**

**Symptoms**: GPT-5 models fail with temperature error  
**Causes**: GPT-5 models don't accept custom temperature

**Solutions**:
```python
# Wrong (fails with GPT-5):
resp = client.chat.completions.create(
    model=MODEL,
    messages=[...],
    temperature=0.2  # Remove this line
)

# Right (works with all models):
resp = client.chat.completions.create(
    model=MODEL,
    messages=[...]
)
```

### 📦 **"gh: command not found" during PR creation**

**Symptoms**: Workflow reaches "Create PR" step and fails with `gh: command not found`  
**Causes**: GitHub CLI not installed in the runner

**Solutions**:
```yaml
# Add this step before creating PR:
- name: Install GitHub CLI
  run: |
    sudo apt-get update
    sudo apt-get install -y gh
```

## GitHub App Mobile Issues

### 📱 **Labels not applying from mobile app**

**Symptoms**: Adding `ai-run` label on mobile doesn't trigger workflow  
**Causes**: Mobile app sync delay or network issues

**Solutions**:
1. **Wait 30 seconds** after adding label  
2. **Refresh the issue** in mobile app  
3. **Check Actions tab** for workflow run  
4. **Try desktop GitHub** if mobile persists

### 🔔 **Not receiving notifications**

**Symptoms**: Workflows run but no mobile notifications  
**Causes**: GitHub notification settings

**Solutions**:
1. **Check GitHub app settings**: Notifications → Turn on all relevant alerts  
2. **Verify repository watching**: Watch → All Activity  
3. **Test with desktop**: Add label from desktop to verify workflow

## Performance Issues

### 🐌 **Workflows taking too long**

**Symptoms**: AI tasks take 10+ minutes  
**Causes**: Large task context or slow models

**Solutions**:
1. **Use faster models**: gpt-5-nano or gpt-5-mini instead of gpt-5  
2. **Reduce context size**: Shorten spec.md and task descriptions  
3. **Check workflow logs**: Look for timeouts or retries

### 💾 **High GitHub Actions usage**

**Symptoms**: Hitting GitHub Actions minute limits  
**Causes**: Running too many AI tasks or inefficient workflows

**Solutions**:
1. **Batch AI runs**: Process 5-10 tasks per session, not all at once  
2. **Use selective sync**: Process task ranges instead of full sync  
3. **Optimize workflows**: Remove unnecessary steps or logging

### 📏 **Context too large / tokens exceeded**

**Symptoms**: Model truncates output, empty diffs, or long stalls  
**Causes**: `spec.md`, `plan.md`, and task block exceed model context

**Solutions**:
1. Use a **smaller task slice**: tighten the T-ID’s description; move long rationale into linked docs  
2. Prefer **`gpt-5`** for heavy planning; use **`gpt-5-mini/nano`** for targeted diffs  
3. Split `spec.md` into sections and include only the necessary parts in the runner prompt  
4. Add a **"Context Budget"** note in tasks: specify which files the AI should read  

## Recovery Procedures

### 🗑️ **Clean up failed sync**

If sync fails partway through:
```bash
# 1. Delete incomplete issues manually (GitHub Issues tab)
# 2. Fix the underlying issue (rate limits, YAML errors, etc.)
# 3. Re-run sync workflow
# 4. Or use selective sync for remaining tasks
```

### 🔄 **Reset automation**

To start fresh:
```bash
# 1. Delete all workflow files
rm -rf .github/workflows/

# 2. Close all open PRs from AI runners
# 3. Delete all issues with "ai-run" label
# 4. Re-apply workflows from setup guide
# 5. Re-run sync
```

### 🏥 **Emergency stops**

If AI is creating bad PRs:
```bash
# 1. Go to Actions tab
# 2. Cancel running workflows
# 3. Remove "ai-run" labels from issues
# 4. Fix task descriptions
# 5. Test with one simple task first
```

## Debugging Tools

### 🔍 **Checking workflow logs**

1. **Actions tab** → **Click workflow run** → **Click job name**  
2. **Look for**: Error messages, API responses, timing issues  
3. **Download logs**: Use "Download logs" for offline analysis

### 📊 **Monitoring API usage**

```bash
# Check OpenAI usage:
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/usage

# GitHub API rate limits:
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

### 🧪 **Testing locally**

```bash
# Test GPT script locally:
export OPENAI_API_KEY="your_key"
export TASK_ID="T-001"
export WORKING_REPO="."
export OPENAI_MODEL="gpt-5-mini"
python scripts/gpt_task_runner.py

# Test task parsing:
python -c "
import re
tasks = open('tasks.md').read()
matches = re.findall(r'- \[ \] \((T-\d{3}[a-z]?)\) \*\*(.+?)\*\*', tasks)
print('Found tasks:', matches)
"
```

```bash
# Simulate label-triggered parsing of an issue title
python - <<'PY'
import re
title = "(T-023a) Add selective sync and delay controls"
m = re.search(r"\(T-\d{3}[a-z]?\)", title)
print("Parsed T-ID:", m.group(0) if m else "NOT FOUND")
PY
```

## Getting Help

## Quality Gates Issues

### 🚨 **"Resource not accessible by integration" (403 error)**

**Symptoms**: PR Quality Summary workflow fails when trying to read CI artifacts
**Causes**: Missing `actions: read` permission

**Solutions**:
```yaml
# In .github/workflows/pr-quality-summary.yml
permissions:
  actions: read          # Required to read artifacts from CI runs
  contents: read
  issues: write
  pull-requests: write
```

### ⏭️ **"Workflow always shows as 'skipped'"**

**Symptoms**: PR Quality Summary workflow never runs, always shows "skipped"
**Causes**: Workflow only runs on PR events, not push to main

**Solutions**:
This is normal behavior! The workflow should:
- ✅ **Skip** when you push directly to main
- ✅ **Run** when CI completes on a pull request
- ✅ **Post comment** with quality score on the PR

### 🏠 **"No artifact named 'home-inspection-report' found"**

**Symptoms**: PR Quality Summary can't find inspection report
**Causes**: CI workflow name mismatch or artifact not uploaded

**Solutions**:
```yaml
# 1. Verify workflow names match exactly:
# ci.yml should have: name: "CI Pipeline (T-000f)"
# pr-quality-summary.yml should have: workflows: ["CI Pipeline (T-000f)"]

# 2. Verify artifact upload in ci.yml:
- name: Upload inspection report
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: home-inspection-report  # Exact name matters
    path: ci/inspection_report.json
```

### 🛡️ **"Merge not blocked despite failed CI"**

**Symptoms**: Can still merge PR even when CI fails
**Causes**: Branch protection rules not configured

**Solutions**:
1. Go to **Settings** → **Branches** → **Add rule**
2. Branch name pattern: `main`
3. ✅ **Require status checks to pass before merging**
4. Search and select: **"Tests + Home Inspection"**
5. ✅ **Require pull request reviews before merging**

### 🐘 **"CI fails with PostgreSQL connection error"**

**Symptoms**: Home inspection can't connect to database
**Causes**: PostgreSQL service not ready or wrong connection string

**Solutions**:
```yaml
# Verify PostgreSQL service configuration:
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

# Verify environment variable:
env:
  DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
```

### 🏃 **"Home inspection script fails to run"**

**Symptoms**: CI fails during home inspection step
**Causes**: Missing dependencies or Python path issues

**Solutions**:
```bash
# Check ci/requirements.txt exists:
psycopg2-binary>=2.9
pytest>=7.0

# Verify script permissions:
chmod +x ci/run_home_inspection.py

# Test locally:
python ci/run_home_inspection.py
```

### 📚 **Resources**

- **GitHub Actions docs**: https://docs.github.com/en/actions  
- **OpenAI API docs**: https://platform.openai.com/docs  
- **GitHub API docs**: https://docs.github.com/en/rest  

### 🆘 **When to ask for help**

- Persistent YAML syntax errors  
- API authentication issues across multiple attempts  
- Workflows running but producing no output  
- Rate limiting despite using selective sync  

### 📋 **Information to provide**

When asking for help, include:  
1. **Exact error messages** from workflow logs  
2. **Repository settings** (Actions permissions, secrets)  
3. **Task format examples** from your tasks.md  
4. **Workflow run URLs** showing the failure  
5. **Steps you've already tried**  
6. **Workflow YAML snippets** for the failing step (Create PR, Install gh, etc.)

---

*🔧 Most issues are fixable with the solutions above. Start with the most common causes and work through systematically.*
