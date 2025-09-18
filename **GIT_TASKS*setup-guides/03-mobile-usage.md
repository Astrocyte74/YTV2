# Mobile-Friendly AI Task Execution

📱 **Complete guide to using your GitHub AI automation from your phone**

## Overview

Once set up, you can trigger AI task implementations directly from your mobile device using the GitHub app. No typing task IDs or complex parameters - just add a label and get automated PRs!

## Method 1: Label-Triggered (Recommended for Mobile)

### ✅ **Super Simple Phone Workflow**

1. **Open GitHub App** on your phone
2. **Navigate to Issues tab** in your repository
3. **Pick any task issue** (e.g., "(T-001) Setup development environment")
4. **Tap "Labels"**
5. **Add label**: `ai-run`
6. **Wait 2-3 minutes** for automation to complete
7. **Check notifications** for PR link and completion status

### 🎯 **What Happens Automatically**

- 🤖 **AI extracts Task ID** from issue title (e.g., T-001)
- 💭 **Posts progress comment**: "Starting AI run for T-001..."
- 🔧 **GPT-5 Mini processes** task with full project context
- 🌿 **Creates branch**: `feat/T-001-gpt`
- 📝 **Opens PR** with implementation
- ✅ **Comments back** with PR link
- 🧹 **Removes `ai-run` label** automatically

### 📱 **iPhone GitHub App Screenshots**

```
Issues Tab → Select Issue → Labels → Add "ai-run" → Done!
    ↓
Notifications → "Starting AI run..." → PR created → "Run complete"
```

## Method 2: Manual Workflow Dispatch

### 🎛️ **For Precise Control**

1. **Open GitHub App** → **Actions tab**
2. **Find "GPT Task Runner"** workflow
3. **Tap "Run workflow"**
4. **Fill inputs**:
   - **Task ID**: `T-001` (type the specific task)
   - **Target folder**: `.` (root) or specific subfolder
   - **Model**: Select from dropdown (gpt-5-mini, gpt-5, etc.)
5. **Tap "Run workflow"** button
6. **Monitor progress** in Actions tab
7. **Check Pull Requests** for created PR

### 🔧 **Model Selection Guide**

| Model | Best For | Speed | Cost |
|-------|----------|-------|------|
| `gpt-5-nano` | Documentation, simple tasks | ⚡ Fastest | 💰 Cheapest |
| `gpt-5-mini` | Most tasks, good balance | ⚡ Fast | 💰 Low |
| `gpt-5` | Complex architecture, planning | 🔧 Thorough | 💰💰 Higher |
| `gpt-4.1` | Fallback, comparison | 🔧 Capable | 💰💰 Medium |

## Method 3: Bulk Issue Sync

### 📋 **Syncing Tasks to Issues**

If you've added new tasks to `tasks.md`:

1. **Actions tab** → **"Sync Tasks to Issues"**
2. **Run workflow** → **Run workflow**
3. **Wait for completion** (may take 1-2 minutes with rate limiting)
4. **Check Issues tab** for new issues

**For Large Task Lists (20+ tasks)**:
- Use **"Sync Selected Tasks (Range)"** instead
- Set **start_task**: `20`, **end_task**: `25` (process 5 at a time)
- Repeat in batches to avoid rate limits

## Phone Usage Tips

### ✅ **Best Practices**

- **Use label triggers** for quick execution (`ai-run` method)
- **Check notifications** - GitHub will notify you of progress
- **Review PRs before merging** - AI implementations need human verification
- **Start with simple tasks** to test the system
- **Use selective sync** for large projects (20+ tasks)

### 📱 **GitHub App Navigation**

```
Repository Home
├── 📋 Issues (35+ auto-created from tasks.md)
│   ├── Add 'ai-run' label → triggers automation
│   └── Check comments for progress updates
├── 🔄 Pull Requests (AI-generated implementations)
│   ├── Review AI changes
│   └── Merge when ready
└── ⚙️ Actions (monitor workflows)
    ├── See real-time progress
    └── Download logs if needed
```

### 🔔 **Notification Flow**

1. **Add `ai-run` label** → GitHub notification
2. **"Starting AI run for T-XXX..."** → Progress comment
3. **Workflow completes** → Actions notification
4. **PR created** → Pull request notification
5. **"Run complete. PR: [link]"** → Final comment with link

## Advanced Mobile Workflows

### 🎯 **Task Prioritization**

1. **Filter issues by milestone** (Phase 0, Phase 1, etc.)
2. **Add `ai-run` to highest priority** tasks first
3. **Review and merge PRs** before triggering more tasks
4. **Use labels** like `ready-for-ai` to mark prepared tasks

### 🚀 **Batch Processing**

For multiple tasks:
1. **Add `ai-run`** to 2-3 issues simultaneously
2. **Monitor Actions tab** for parallel execution
3. **Review PRs** as they're created
4. **Merge approved changes** before next batch


### 📊 **Progress Tracking**

- **Issues**: Track completion via milestones
- **Pull Requests**: See AI implementations
- **Actions**: Monitor automation health
- **Notifications**: Stay updated on progress

### ⚡ Quick Model Switching on Mobile

- When using the manual workflow (`Actions → GPT Task Runner → Run workflow`), you can choose the model from a dropdown.
- Options include `gpt-5-mini` (default), `gpt-5`, `gpt-5-nano`, and legacy `gpt-4.1`.
- Recommended defaults:
  - 📄 Documentation & small tasks → `gpt-5-nano`
  - ⚖️ Balanced workloads → `gpt-5-mini`
  - 🧠 Complex planning → `gpt-5`
- Reminder: GPT‑5 models do not support custom `temperature`. If you see a "temperature unsupported" error, leave it unset.

## Mobile Troubleshooting

### ❌ **Common Issues**

**"No T-ID found in issue title"**
- ✅ Ensure issue title has format: `(T-001) Task Name`

**"AI workflow failed"**
- ✅ Check Actions tab for error details
- ✅ Verify OpenAI API key is set correctly
- ✅ Ensure the selected model is valid (`gpt-5-mini`, `gpt-5`, `gpt-5-nano`, `gpt-4.1`)

**"No PR created"**
- ✅ AI may not have found changes to make
- ✅ Check Actions logs for details

**"Rate limit exceeded"**
- ✅ Wait 10-15 minutes before next batch
- ✅ Use selective sync for large task lists

### 📱 **Mobile Limitations**

- **Can't view full logs** - use desktop for detailed debugging
- **Limited file editing** - review PRs on desktop for complex changes
- **Typing task IDs** - use label triggers instead of manual dispatch

## Success Examples

### 🎉 **What Good Automation Looks Like**

1. **Add `ai-run` label** to "(T-003) Create documentation"
2. **2 minutes later**: Get notification "Starting AI run for T-003..."
3. **5 minutes later**: Get PR notification with implementation
4. **Review on phone**: AI created proper README.md with setup guide
5. **Merge PR**: Documentation task complete!

### 📈 **Scaling Up**

- **Start small**: Test with 1-2 simple tasks
- **Verify quality**: Check AI implementations meet standards
- **Increase volume**: Process 5-10 tasks per session
- **Monitor closely**: Watch for API limits or errors
- **Iterate**: Improve task descriptions based on AI output quality

## Next Steps

✅ **Mobile workflow mastered**
➡️ **Continue to `04-troubleshooting.md`** for issue resolution
➡️ **See `05-customization.md`** for project-specific adaptations

---

*🚀 You now have a complete mobile-controlled AI development workflow! Add labels from your phone and get automated PRs delivered to your device.*
