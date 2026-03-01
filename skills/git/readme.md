---
id: git
name: Git
description: Local git repository data — commits, branches, tags, and repo info
icon: icon.svg
color: "#F05032"

website: https://git-scm.com

auth: none

connects_to: git-scm

credits:
  - entity: repository
    operations: [get]
    relationship: needs

seed:
  - id: git-scm
    types: [software]
    name: Git
    data:
      software_type: cli
      url: https://git-scm.com
      launched: "2005"
      platforms: [macos, linux, windows]
      pricing: open_source
      wikidata_id: Q186055
    relationships:
      - role: created_by
        to: linus-torvalds

  - id: linus-torvalds
    types: [person]
    name: Linus Torvalds
    data:
      wikidata_id: Q34253

instructions: |
  Git skill wraps the local git CLI. All operations require a `path` parameter —
  the absolute path to the repository. In a coding session, this is typically
  the workspace directory.

  Commits are messages sent into a repository. The commit message subject
  becomes the entity name; the full message becomes searchable content.
  Authors are linked as email accounts via the person/claims/account graph.

  Use git_commit.list to see recent activity. Use branch.list to see what's
  being worked on. Use the status and diff utilities for live working tree state.

transformers:
  git_commit:
    terminology: Commit
    mapping:
      id: .hash
      name: .message
      content: .message
      hash: .hash
      short_hash: .short_hash
      timestamp: .timestamp
      author_name: .author_name
      author_email: .author_email
      committer_name: .committer_name
      committer_email: .committer_email
      files_changed: .files_changed
      insertions: .insertions
      deletions: .deletions
      sender:
        person:
          name: .author_name
          email: .author_email

  branch:
    terminology: Branch
    mapping:
      id: .name
      name: .name
      is_remote: .is_remote
      upstream: .upstream

  repository:
    terminology: Repository
    mapping:
      id: .full_name
      name: .name
      full_name: .full_name
      url: .url
      platform: .platform
      default_branch: .default_branch

  tag:
    terminology: Tag
    mapping:
      id: .name
      name: .name
      data.hash: .hash
      data.date: .date
      data.message: .message
      data.annotated: .annotated

operations:
  git_commit.list:
    description: List recent commits in a git repository. Returns commits newest first with diff stats.
    returns: git_commit[]
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      limit:
        type: integer
        description: Max commits to return (default 20)
      branch:
        type: string
        description: Branch to list commits from (default current branch)
      author:
        type: string
        description: Filter by author name or email
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git log {{#if params.branch}}"{{params.branch}}"{{/if}} {{#if params.author}}--author="{{params.author}}"{{/if}} -{{params.limit | default:100}} --pretty=format:'COMMIT_START%n{"hash":"%H","short_hash":"%h","author_name":"%an","author_email":"%ae","committer_name":"%cn","committer_email":"%ce","timestamp":"%aI","message":"%s"}' --shortstat 2>/dev/null | awk '
          /^COMMIT_START/ { if (json) print json; json=""; next }
          /^\{/ { json=$0; next }
          /^ [0-9]/ {
            files=0; ins=0; del=0
            for(i=1;i<=NF;i++) {
              if($(i+1) ~ /file/) files=$i
              if($(i+1) ~ /insertion/) ins=$i
              if($(i+1) ~ /deletion/) del=$i
            }
            sub(/\}$/, ",\"files_changed\":"files",\"insertions\":"ins",\"deletions\":"del"}", json)
          }
          END { if (json) print json }
          ' | jq -s '.'
      timeout: 30

  git_commit.get:
    description: Get a single commit with full details and diff stats.
    returns: git_commit
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      id:
        type: string
        required: true
        description: Commit hash (full or abbreviated)
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git show "{{params.id}}" --pretty=format:'{"hash":"%H","short_hash":"%h","author_name":"%an","author_email":"%ae","committer_name":"%cn","committer_email":"%ce","timestamp":"%aI","message":"%s"}' --shortstat 2>/dev/null | awk '
          /^\{/ { json=$0; next }
          /^ [0-9]/ {
            files=0; ins=0; del=0
            for(i=1;i<=NF;i++) {
              if($(i+1) ~ /file/) files=$i
              if($(i+1) ~ /insertion/) ins=$i
              if($(i+1) ~ /deletion/) del=$i
            }
            sub(/\}$/, ",\"files_changed\":"files",\"insertions\":"ins",\"deletions\":"del"}", json)
          }
          END { if (json) print json }
          '
      timeout: 30

  git_commit.search:
    description: Search commit messages by keyword.
    returns: git_commit[]
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      query:
        type: string
        required: true
        description: Search term to match in commit messages
      limit:
        type: integer
        description: Max results (default 20)
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git log --grep="{{params.query}}" -i -{{params.limit | default:100}} --pretty=format:'COMMIT_START%n{"hash":"%H","short_hash":"%h","author_name":"%an","author_email":"%ae","committer_name":"%cn","committer_email":"%ce","timestamp":"%aI","message":"%s"}' --shortstat 2>/dev/null | awk '
          /^COMMIT_START/ { if (json) print json; json=""; next }
          /^\{/ { json=$0; next }
          /^ [0-9]/ {
            files=0; ins=0; del=0
            for(i=1;i<=NF;i++) {
              if($(i+1) ~ /file/) files=$i
              if($(i+1) ~ /insertion/) ins=$i
              if($(i+1) ~ /deletion/) del=$i
            }
            sub(/\}$/, ",\"files_changed\":"files",\"insertions\":"ins",\"deletions\":"del"}", json)
          }
          END { if (json) print json }
          ' | jq -s '.'
      timeout: 30

  branch.list:
    description: List all branches (local and remote) in a repository.
    returns: branch[]
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git branch -a --format='%(refname:short)|%(upstream:short)|%(HEAD)' 2>/dev/null | while IFS='|' read name upstream head; do
            is_remote=false
            [[ "$name" == origin/* ]] && is_remote=true
            is_current=false
            [[ "$head" == "*" ]] && is_current=true
            printf '{"name":"%s","upstream":"%s","is_remote":%s,"is_current":%s}\n' "$name" "$upstream" "$is_remote" "$is_current"
          done | jq -s '.'
      timeout: 15

  branch.get:
    description: Get info about a specific branch.
    returns: branch
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      name:
        type: string
        required: true
        description: Branch name
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git branch -a --format='%(refname:short)|%(upstream:short)|%(HEAD)' 2>/dev/null | grep "^{{params.name}}|" | head -1 | {
            IFS='|' read name upstream head
            is_remote=false
            [[ "$name" == origin/* ]] && is_remote=true
            is_current=false
            [[ "$head" == "*" ]] && is_current=true
            printf '{"name":"%s","upstream":"%s","is_remote":%s,"is_current":%s}\n' "$name" "$upstream" "$is_remote" "$is_current"
          }
      timeout: 15

  repository.get:
    description: Get repository info from the local git repo — remote URL, platform, branch.
    returns: repository
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git_remote=$(git remote get-url origin 2>/dev/null || echo "")
          git_branch=$(git branch --show-current 2>/dev/null || echo "")
          repo_name=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
          full_name=$(echo "$git_remote" | sed -E 's#.*[:/]([^/]+/[^/.]+).*#\1#')
          platform="local"
          [[ "$git_remote" == *github.com* ]] && platform="github"
          [[ "$git_remote" == *gitlab.com* ]] && platform="gitlab"
          [[ "$git_remote" == *bitbucket.org* ]] && platform="bitbucket"
          [[ "$git_remote" == *codeberg.org* ]] && platform="codeberg"
          printf '{"name":"%s","full_name":"%s","url":"%s","platform":"%s","default_branch":"%s"}\n' \
            "$repo_name" "$full_name" "$git_remote" "$platform" "$git_branch"
      timeout: 15

  tag.list:
    description: List all tags in the repository.
    returns: tag[]
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git tag -l --format='%(refname:short)|%(objectname:short)|%(creatordate:iso-strict)|%(subject)|%(objecttype)' 2>/dev/null | while IFS='|' read name hash date message objtype; do
            annotated=false
            [[ "$objtype" == "tag" ]] && annotated=true
            printf '{"name":"%s","hash":"%s","date":"%s","message":"%s","annotated":%s}\n' \
              "$name" "$hash" "$date" "$message" "$annotated"
          done | jq -s '.'
      timeout: 15

  tag.get:
    description: Get info about a specific tag.
    returns: tag
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      name:
        type: string
        required: true
        description: Tag name
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git tag -l "{{params.name}}" --format='%(refname:short)|%(objectname:short)|%(creatordate:iso-strict)|%(subject)|%(objecttype)' 2>/dev/null | head -1 | {
            IFS='|' read name hash date message objtype
            annotated=false
            [[ "$objtype" == "tag" ]] && annotated=true
            printf '{"name":"%s","hash":"%s","date":"%s","message":"%s","annotated":%s}\n' \
              "$name" "$hash" "$date" "$message" "$annotated"
          }
      timeout: 15

utilities:
  status:
    description: Show working tree status — modified, staged, and untracked files. Returns live state, not stored data.
    returns: string
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          branch=$(git branch --show-current 2>/dev/null)
          tracking=$(git rev-parse --abbrev-ref @{u} 2>/dev/null || echo "")
          ahead=0; behind=0
          if [ -n "$tracking" ]; then
            ahead=$(git rev-list --count "$tracking..HEAD" 2>/dev/null || echo 0)
            behind=$(git rev-list --count "HEAD..$tracking" 2>/dev/null || echo 0)
          fi
          staged=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
          modified=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
          untracked=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
          printf '{"branch":"%s","tracking":"%s","ahead":%d,"behind":%d,"staged":%d,"modified":%d,"untracked":%d}\n' \
            "$branch" "$tracking" "$ahead" "$behind" "$staged" "$modified" "$untracked"
      timeout: 15

  diff:
    description: Show the diff of working tree changes, staged changes, or between two refs.
    returns: string
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      staged:
        type: boolean
        description: Show staged changes only (default false)
      ref1:
        type: string
        description: First ref to compare (e.g., HEAD~3, main)
      ref2:
        type: string
        description: Second ref to compare (e.g., HEAD, feature-branch)
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          {{#if params.ref1}}git diff "{{params.ref1}}"{{#if params.ref2}} "{{params.ref2}}"{{/if}}{{else}}{{#if params.staged}}git diff --cached{{else}}git diff{{/if}}{{/if}} 2>/dev/null
      timeout: 30

  log:
    description: Raw git log output with flexible formatting. Use commit.list for structured data.
    returns: string
    params:
      path:
        type: string
        required: true
        description: Absolute path to the git repository
      format:
        type: string
        description: Git log format string (default oneline)
      limit:
        type: integer
        description: Max entries (default 20)
      branch:
        type: string
        description: Branch to show log for
    command:
      binary: bash
      args:
        - "-c"
        - |
          cd "{{params.path}}" 2>/dev/null || exit 1
          git log {{#if params.branch}}"{{params.branch}}"{{/if}} -{{params.limit | default:100}} {{#if params.format}}--format="{{params.format}}"{{else}}--oneline{{/if}} 2>/dev/null
      timeout: 30

testing:
  exempt:
    reason: Requires a local git repository to be present

---

# Git

Local git repository data — commits, branches, tags, and repo info. Wraps the git CLI
to bring version control history into the Memex as searchable entities.

## No Auth Required

Git reads from local repositories. No API keys, no tokens — just the git binary
that's already on your machine.

## Entity Mappings

| Git Concept | AgentOS Entity | Relationship |
|-------------|----------------|--------------|
| Commits | `git_commit` (extends message) | Author → person, commit → in → repository |
| Branches | `branch` (extends place) | branch → in → repository |
| Tags | `tag` (existing entity) | tag → tag → git_commit |
| Repositories | `repository` (existing entity) | Populated from local git info |

## Usage

```bash
# List recent commits
git_commit.list (skill: git, path: "/Users/joe/dev/agentos")

# Search commit messages
git_commit.search (skill: git, path: "/Users/joe/dev/agentos", query: "readme")

# Get a specific commit
git_commit.get (skill: git, path: "/Users/joe/dev/agentos", id: "f9f9f57")

# List branches
branch.list (skill: git, path: "/Users/joe/dev/agentos")

# Get repo info
repository.get (skill: git, path: "/Users/joe/dev/agentos")

# Live status (not stored — computed fresh)
git.status (path: "/Users/joe/dev/agentos")

# View diff
git.diff (path: "/Users/joe/dev/agentos", staged: true)
```

## Design Decisions

**Commits are messages.** `git commit -m` — you're sending a message into a repository.
The inheritance chain is work → document → post → message → git_commit.

**Authors are people with email accounts.** Git gives us a name + email pair.
The transformer creates a person entity (deduped on email) and links it via the
sender relationship. The email becomes an account entity via claims.

**Only immutable data is stored.** A commit's hash, message, author, and diff stats
never change. Branch ahead/behind counts, working tree status, and other ephemeral
state come from utilities that query live.

**Tags reuse the existing tag entity.** A git tag is a named label applied to a
commit — exactly what the tag entity already represents.
