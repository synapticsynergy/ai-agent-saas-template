# Git Workflow

The template uses a simple long-lived environment branch model.

```text
feature/* ──┐
bugfix/*  ──┼──► dev ──► staging ──► main
chore/*   ──┘
```

## Branches

### `main`

Production.

Rules:

- protected,
- PR only,
- required CI checks,
- no force pushes,
- no direct feature development,
- deploys to Railway `production` and Vercel Production on push.

### `staging`

Release candidate and demo environment.

Rules:

- normally receives merges from `dev`,
- deploys to Railway `staging` and a Vercel preview on push,
- must pass integration/E2E/evals before promotion.

### `dev`

Shared development integration branch.

Rules:

- feature branches merge here,
- deploys to Railway `dev` and a Vercel preview on push,
- expected to remain usable.

### `feature/<name>`

Example:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/evening-map
```

Commit:

```bash
git add .
git commit -m "feat: add itinerary map"
git push -u origin feature/evening-map
```

Open PR:

```text
feature/evening-map → dev
```

### `bugfix/<name>`

```bash
git checkout dev
git pull origin dev
git checkout -b bugfix/agent-timeout
```

### `hotfix/<name>`

Only for urgent production fixes.

```text
main → hotfix/* → main
                  ├→ staging
                  └→ dev
```

Avoid allowing `dev` to drift without the hotfix.

---

# Promotion Flow

## Feature → Dev

```bash
git checkout dev
git pull origin dev
git checkout -b feature/<name>

# work
make check

git add .
git commit -m "feat: <description>"
git push -u origin feature/<name>
```

PR:

```text
feature/<name> → dev
```

## Dev → Staging

Prefer PR:

```text
dev → staging
```

CLI equivalent:

```bash
git checkout staging
git pull origin staging
git merge origin/dev
git push origin staging
```

Staging deploys after CI passes.

## Staging → Production

Prefer PR:

```text
staging → main
```

CLI equivalent:

```bash
git checkout main
git pull origin main
git merge origin/staging
git push origin main
```

Production deploys after required checks and approval.

---

# Commit Convention

Recommended Conventional Commits:

```text
feat: add route optimization
fix: enforce tenant scope on saved plans
refactor: isolate event provider
test: add tool authorization cases
docs: document the backend deploy path
chore: upgrade dependencies
```

---

# Tags and Releases

On production releases:

```bash
git checkout main
git pull
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Use semantic versioning once the template has consumers.

---

# Installation From Template

For a new project:

```bash
git clone <template-repo> my-agent-app
cd my-agent-app

rm -rf .git
git init
git add .
git commit -m "chore: initialize from ai-agent-saas template"

git branch -M main
git checkout -b staging
git checkout -b dev
```

Then configure a new origin:

```bash
git remote add origin <new-repo-url>
git push -u origin main
git push -u origin staging
git push -u origin dev
```

Alternative: use GitHub's repository template feature and keep this history out of downstream projects.

---

# Pull Request Minimum

A PR should answer:

```text
What changed?
Why?
How was it tested?
Does it change infrastructure?
Does it change permissions/auth?
Does it change agent behavior?
Are new eval cases required?
```

Changes to tools, prompts, routing, permissions, or agent behavior should normally add or update evaluation/test coverage.
