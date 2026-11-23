# Git & GitHub

Two repositories, two jobs:

| Repo                         | What it is                     | You…                                         |
| ---------------------------- | ------------------------------ | -------------------------------------------- |
| **5303-Database-Field-Guide** | the course materials          | clone it, `git pull` for updates, never edit |
| **5303-work** (yours)        | your FINDINGS, routes, schemas | create it, commit, push                      |

Keeping your work out of the field guide means `git pull` always succeeds:
there are no edits of yours for an update to collide with.

## 1. Install Git

| OS      | Install                                                                 |
| ------- | ----------------------------------------------------------------------- |
| macOS   | `xcode-select --install` (or `brew install git`)                        |
| Windows | [git-scm.com](https://git-scm.com/download/win). Keep the defaults; it includes **Git Bash**. |
| Linux   | `sudo apt install git` (or your distribution's package manager)        |

Tell Git who you are, once per machine:

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"    # the email on your GitHub account
git config --global init.defaultBranch main
```

## 2. Connect to GitHub

Create a free account at [github.com](https://github.com) if you don't have
one. Then let your machine push to it. The easiest way is the GitHub CLI:

```bash
# macOS: brew install gh      Windows: winget install GitHub.cli
gh auth login                  # choose GitHub.com, HTTPS, and "Login with a web browser"
```

## 3. Clone the field guide

```bash
mkdir -p ~/5303 && cd ~/5303
git clone https://github.com/rugbyprof/5303-Database-Field-Guide.git
```

When materials are updated:

```bash
cd ~/5303/5303-Database-Field-Guide
git pull
```

If `git pull` complains about local changes, you edited something in the
clone. `git stash` sets your edits aside, and `git pull` will then work.
Move anything you want to keep into your own repo.

## 4. Create your own repo

```bash
cd ~/5303
gh repo create 5303-work --private --clone
cd 5303-work
```

Share it with your instructor however they ask: usually by adding them as a
collaborator (**Settings → Collaborators** on GitHub).

A layout that keeps each unit's work together:

```
5303-work/
├── README.md
├── sqlite/
│   ├── FINDINGS_sqlite.md
│   ├── my_schema.sql
│   └── your_turn_checks.sql
├── duckdb/
└── api/                 your copy of lab/api/starter_code (see below)
```

### Working on files that come from the field guide

Some files start in the field guide and become yours once you fill them in,
like [your_turn_checks.sql](../engines/01_sqlite/04_model/your_turn_checks.sql).
Copy them into `5303-work` and edit the copy.

**The API starter code** works from a copy too. Tell it where the field
guide is, and it finds the SQL files there:

```bash
cp -R ~/5303/5303-Database-Field-Guide/lab/api/starter_code ~/5303/5303-work/api
export FIELD_GUIDE=~/5303/5303-Database-Field-Guide    # add to ~/.zshrc or ~/.bashrc
```

## 5. The everyday loop

```bash
cd ~/5303/5303-work
git add -A
git commit -m "SQLite 07: driver results and plan summaries"
git push
```

Commit when something works, not once at the end. A history of small
commits is a record of your progress, and a safety net when something
breaks.

## Check

```bash
git --version
cd ~/5303/5303-Database-Field-Guide && git pull     # "Already up to date."
cd ~/5303/5303-work && git status                   # "On branch main"
```

Then open your `5303-work` repo on github.com and confirm it's there and
private.
