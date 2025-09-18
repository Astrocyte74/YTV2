# Initial Repository Setup

## Prerequisites

✅ **GitHub repository** with Actions enabled  
✅ **OpenAI API key** with GPT-5 access  
✅ **Local development environment** (Git, text editor)  
✅ **Optional**: Claude Code or compatible spec-kit IDE  
✅ **Optional**: Docker environment setup (ensure parity across dev and prod if using containers)

## Step 1: Repository Preparation

### 1.1 Clone and Set Up Repository
```bash
# Clone your target repository
git clone https://github.com/yourusername/your-repo.git
cd your-repo

# Ensure you're on main/master branch
git checkout main
git pull origin main
```
> Replace your-repo with the actual repo name (e.g., unified-platform-spec). This guide is repo-agnostic and works for any project.

### 1.2 Add Repository Secrets
1. Go to **Settings** → **Secrets and variables** → **Actions**  
2. Add required secret:  
   - **`OPENAI_API_KEY`**: Your OpenAI API key  
   > Default setup uses gpt-5-mini, but you can switch models in scripts/gpt_task_runner.py or at workflow runtime.

### 1.3 Configure Repository Permissions
1. Go to **Settings** → **Actions** → **General**  
2. Set **Workflow permissions** to **"Read and write permissions" (MANDATORY)**  
3. Check **"Allow GitHub Actions to create and approve pull requests" (MANDATORY)**  

## Step 2: Spec-Kit Installation

### 2.1 Install GitHub Spec-Kit (if using spec-kit framework)
```bash
# Option A: Use existing spec-kit template
# Clone or copy spec-kit structure from github.com/github/spec-kit

# Option B: Manual setup (create these files)
mkdir -p .specify/scripts/bash
mkdir -p .specify/templates
mkdir -p .claude/commands
```

### 2.2 Create Core Specification Files

> ⚠️ Each task MUST have a unique Task ID (T-001, T-002, …). These IDs are how automation parses and runs tasks.

#### `tasks.md` (Required)
```markdown
# Project Implementation Tasks

## Phase 0: Setup - Week 1

- [ ] (T-001) **Setup development environment**
  - **Implementation**: Configure local development setup
  - **Location**: Root directory
  - **Testing**: Verify all tools work correctly
  - **Acceptance**: Development environment fully functional

- [ ] (T-002) **Create project documentation**
  - **Implementation**: Add README, setup guides
  - **Location**: /docs/
  - **Testing**: Documentation is clear and complete
  - **Acceptance**: New contributors can follow setup guide

## Phase 1: Core Features - Weeks 2-3

- [ ] (T-003) **Implement core functionality**
  - **Implementation**: Build main features
  - **Location**: /src/
  - **Testing**: Unit tests pass
  - **Acceptance**: Core features working as specified
```

#### `spec.md` (Recommended)
```markdown
# Project Specification

## What We're Building
[Describe your project vision and goals]

## Core Capabilities
[List main features and functionality]

## Success Criteria
[Define measurable outcomes]
```

#### `CONSTITUTION.md` (Optional but recommended)
```markdown
# Project Constitution

## Non-Negotiable Principles
- [List architectural decisions that cannot be changed]
- [Performance requirements]
- [Quality standards]

## Technology Constraints
- [Required technologies]
- [Forbidden approaches]
```

## Step 3: Directory Structure

Create this structure in your repository:
```
your-repo/
├── .github/workflows/          # (Will be created in next guide)
├── scripts/                    # Python scripts for automation
├── tasks.md                   # Task definitions (REQUIRED)
├── spec.md                    # Project specification
├── CONSTITUTION.md            # Non-negotiable principles
├── GLOSSARY.md               # Terminology definitions
└── setup-guides/             # These setup guides
```

## Step 4: Validation

### 4.1 Verify File Structure
```bash
# Check that required files exist
ls -la tasks.md spec.md
```

### 4.2 Test GitHub Access
```bash
# Verify you can push to the repository
echo "# Setup Test" > setup-test.md
git add setup-test.md
git commit -m "Test: verify repository setup"
git push origin main
rm setup-test.md
git add setup-test.md
git commit -m "Cleanup: remove setup test file"
git push origin main
```

### 4.3 Check Repository Settings
1. **Actions tab**: Should show no workflows (yet)  
2. **Issues tab**: Should be enabled  
3. **Pull Requests tab**: Should be enabled  

## Step 5: Prepare for Workflows

### 5.1 Create Scripts Directory
```bash
mkdir -p scripts
touch scripts/gpt_task_runner.py
```

### 5.2 Commit Initial Structure
```bash
git add .
git commit -m "Initial setup: spec-kit structure and core files"
git push origin main
```

## Next Steps

✅ **Repository prepared**  
➡️ **Continue to `02-github-workflows.md`** to add automation

## Troubleshooting

### Common Issues
- **"Repository not found"**: Check repository URL and permissions  
- **"Permission denied"**: Verify you have write access to the repository  
- **"Secrets not working"**: Ensure OPENAI_API_KEY is added correctly in repository settings  
- **"Unsupported value: temperature"**: Remove or comment out the temperature parameter in scripts/gpt_task_runner.py. GPT-5 models only support the default value.

### Verification Commands
```bash
# Verify git configuration
git config --list | grep user

# Check repository remote
git remote -v

# Verify OpenAI API key (if testing locally)
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### Quick Checklist for Initial Setup
- [ ] GitHub repo created + Actions enabled  
- [ ] OPENAI_API_KEY added as repo secret  
- [ ] Actions workflow permissions = Read/Write + PR approval  
- [ ] Spec-kit core files added: tasks.md, spec.md, CONSTITUTION.md  
- [ ] scripts/gpt_task_runner.py created (no custom temperature param)  
- [ ] Initial commit pushed to main  
- [ ] Docker parity confirmed (if containers used in project)
