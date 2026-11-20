#!/usr/bin/env python3
"""Looks for secrets in what is about to go up to GitHub (used by the .githooks/pre-push hook; standard library only).

    python3 bin/check_secrets.py                    # the commits of the current branch that main does not have
    python3 bin/check_secrets.py --base dev         # against another branch
    python3 bin/check_secrets.py --revs "B --not --remotes=origin"   # the commits the remote does not have yet
Each commit is read on its own (a secret added and removed in the same push shows up too).
    python3 bin/check_secrets.py --all              # every versioned file (audit)

Exit code: 0 nothing that blocks; 1 found something that may not go up; 2 usage error. The warnings (personal paths,
e-mails) do not block. A secret's value is never printed in full. If gitleaks is installed, it runs too.

False positive on a line: after checking it is not a secret, put the text `scan-secrets: ok` on that line (in a
comment; in a .json, inside a string) and redo the commit that brought it (`git commit --amend`, if it is the last
one; otherwise, a rebase that edits that commit). A new commit on top is not enough: each commit is read on its own.
The marker does not apply to a file blocked by its name nor to gitleaks (which has its own, `gitleaks:allow`). Never
push with --no-verify.
"""
import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys

# File names that may not be versioned (compared with the lower-case name).
FORBIDDEN_FILES = [
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks", "*.kdbx",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "credentials.json", "credentials.*",
    "secrets.*", "secret.*", "config.local.*", "*.local.ini", "*.local.json", "*.local.toml",
    ".netrc", ".npmrc", ".pypirc", "token", "token.txt", "*.token", "service-account*.json",
    "client_secret*.json", ".htpasswd", ".aigen-denylist", "claude.local.md",
    # model weights and what AIGenerator generates: they never go into the repository (AGENTS.md, "Public repository")
    "*.safetensors", "*.ckpt", "*.pt", "*.pth", "*.onnx", "*.gguf",
    "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.bmp", "*.avif",
    "*.aigen.json", "aigen-web.log",
]
ALLOWED_FILES = [".env.example", ".env.sample", ".env.template", "example.env"]

# (name, pattern). Group 1, when there is one, is the value.
BLOCK = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("Anthropic key", re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})")),
    ("OpenAI key", re.compile(r"\b(sk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{32,})")),
    ("GitHub token", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("Hugging Face token", re.compile(r"\b(hf_[A-Za-z0-9]{30,})")),
    ("Civitai token", re.compile(r"(?i)\bcivitai\w*\s*[\"']?\s*[:=]\s*[\"']?([0-9a-f]{32})\b")),
    ("AWS key", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("Google key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})")),
    ("Slack token", re.compile(r"\b(xox[abprs]-[A-Za-z0-9\-]{10,})")),
    ("Discord token", re.compile(r"\b([MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,})")),
    ("Stripe key", re.compile(r"\b((?:sk|rk)_live_[A-Za-z0-9]{20,})")),
    ("JWT", re.compile(r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})")),
    ("password in a URL", re.compile(r"[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s:/@]{6,})@")),
    ("assigned secret", re.compile(
        r"(?i)\b(?:api[_\-]?key|apikey|secret|token|passwd|password|senha|client[_\-]?secret|access[_\-]?key|"
        r"auth[_\-]?token|private[_\-]?key)\w*\s*[\"']?\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']")),
]
WARN = [
    ("personal path", re.compile(r"(?i)(?:[A-Z]:[\\/]+Users[\\/]+|/c/Users/|/(?:home|Users)/)([A-Za-z0-9._\-]+)")),
    ("e-mail", re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")),
]
OK_EMAILS = ("noreply", "example.", "@users.noreply", "git@")
OK_USERS = {"user", "you", "name", "runner", "username"}
BINARIES = (".png", ".jpg", ".jpeg", ".webp", ".exr", ".glb", ".gltf", ".bin", ".blend", ".ico", ".svg", ".zip",
            ".npz", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".gguf", ".ttf", ".otf", ".woff", ".woff2",
            ".mp3", ".wav", ".ogg", ".mp4", ".pdf", ".exe", ".dll", ".so")
RELEASE = "scan-secrets: ok"  # a comment on a line: a checked false positive


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("ERROR: git %s: %s" % (" ".join(args), r.stderr.strip()), file=sys.stderr)
        sys.exit(2)
    return r.stdout


def mask(value):
    value = value.strip()
    return (value[:6] + "…" + value[-2:]) if len(value) > 12 else "…"


def is_placeholder(value, line):
    """An example or a placeholder, not a real secret."""
    v = value.lower()
    if any(m in value for m in ("…", "...", "<", ">", "${", "{{", "%(", "$(")) or v.startswith("$"):
        return True
    if any(p in v for p in ("xxxx", "example", "your", "changeme", "placeholder", "dummy", "fake", "os.environ",
                            "getenv", "process.env")):
        return True
    if len(set(value)) < 6:  # aaaaaaaa, 12121212
        return True
    return RELEASE in line


def is_forbidden(path):
    name = os.path.basename(path).lower()
    if name in ALLOWED_FILES:
        return False
    return any(fnmatch.fnmatch(name, p) for p in FORBIDDEN_FILES)


GIT_DIFF = ["-c", "core.quotePath=false"]  # names with accents as they are (no quotes nor \\303)
DIFF = ["--no-color", "--unified=0", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/", "--no-renames"]


def commits(revs):
    """The commits of `revs` (git rev-list arguments, for example "A..B" or "B --not --remotes=origin")."""
    return git("rev-list", *revs.split()).split()


def added_lines(commit_list):
    """(file, line number, text) of the lines added in each commit (one by one: a secret added in one commit and
    removed in the next shows up too)."""
    for c in commit_list:
        path, n, in_hunk = None, 0, False
        for line in git(*GIT_DIFF, "show", "--format=", *DIFF, c).splitlines():
            if line.startswith("diff --git "):
                path, in_hunk = None, False
            elif not in_hunk and line.startswith("+++ "):
                path = line[6:] if line.startswith("+++ b/") else None
            elif line.startswith("@@"):
                in_hunk = True
                m = re.search(r"\+(\d+)", line)
                n = int(m.group(1)) if m else 0
            elif in_hunk and line.startswith("+"):
                if path:
                    yield path, n, line[1:]
                n += 1


def added_files(commit_list):
    names = set()
    for c in commit_list:
        names.update(git(*GIT_DIFF, "show", "--format=", "--name-only", "--diff-filter=AMR", "--no-renames",
                         c).split("\n"))
    return sorted(x for x in names if x)


def all_lines():
    for path in git("ls-files").splitlines():
        if path.lower().endswith(BINARIES) or not os.path.isfile(path) or os.path.getsize(path) > 2_000_000:
            continue
        try:
            with open(path, encoding="utf-8", errors="strict") as f:
                for n, line in enumerate(f, 1):
                    yield path, n, line.rstrip("\n")
        except (UnicodeDecodeError, OSError):
            continue


def default_base():
    for b in ("origin/main", "origin/master", "main", "master"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", b], capture_output=True).returncode == 0:
            return b
    print("ERROR: could not find the main branch; use --base", file=sys.stderr)
    sys.exit(2)


def scan(files, lines):
    """(what blocks, warnings)."""
    blocked, warnings = [], {}
    for path in files:
        if is_forbidden(path):
            blocked.append("%s: a file that may not be versioned" % path)
    for path, n, text in lines:
        if path.lower().endswith(BINARIES) or len(text) > 500_000:
            continue
        seen = set()
        for name, rx in BLOCK:
            for m in rx.finditer(text):
                value = m.group(1) if m.groups() else m.group(0)
                if value in seen or is_placeholder(value, text):
                    continue
                seen.add(value)
                blocked.append("%s:%d: %s (%s)" % (path, n, name, mask(value)))
        for name, rx in WARN:
            for m in rx.finditer(text):
                v = m.group(1)
                if name == "e-mail" and any(k in v.lower() for k in OK_EMAILS):
                    continue
                if name == "personal path" and v.lower() in OK_USERS:
                    continue
                warnings.setdefault((name, v), []).append("%s:%d" % (path, n))
    return blocked, warnings


def main():
    p = argparse.ArgumentParser(description="Looks for secrets in what is about to go up to GitHub.")
    p.add_argument("--base", help="the branch to compare with (default: origin/main)")
    p.add_argument("--revs", help="the commits to read, as git rev-list arguments (\"A..B\" or "
                                  "\"B --not --remotes=origin\")")
    p.add_argument("--all", action="store_true", help="every versioned file, not only what is about to go up")
    a = p.parse_args()
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode != 0:
        print("ERROR: not a git repository", file=sys.stderr)
        sys.exit(2)
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    if a.all:
        revs, files, lines, scope = None, git("ls-files").splitlines(), all_lines(), "all files"
    else:
        revs = a.revs or (a.base or default_base()) + "..HEAD"
        commit_list = commits(revs)
        files = added_files(commit_list)
        lines, scope = added_lines(commit_list), "%s (%d commits, %d files)" % (revs, len(commit_list), len(files))
    blocked, warnings = scan(files, lines)
    if shutil.which("gitleaks"):
        cmd = ["gitleaks", "detect", "--no-banner", "--redact", "--exit-code", "1"]
        if revs:
            cmd += ["--log-opts", revs]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 1:
            blocked.append("gitleaks found secrets:\n" + (r.stdout + r.stderr).strip())
    print("check_secrets: " + scope)
    for (name, v), where in sorted(warnings.items()):
        print("  warning: %s '%s' in %d place(s): %s%s" % (name, v, len(where), ", ".join(where[:3]),
                                                           " ..." if len(where) > 3 else ""))
    if blocked:
        print("BLOCKED: %d finding(s) that may not go up:" % len(blocked))
        for b in blocked:
            print("  - " + b)
        if any(re.match(r".+:\d+: ", b) for b in blocked):  # a finding on a line (not by name nor from gitleaks)
            print("False positive on a line (checked)? Put '%s' on it and redo the commit that brought it (git commit"
                  " --amend, if it is the last one): a new commit on top is not enough." % RELEASE)
        sys.exit(1)
    print("ok: no secrets" + (" (%d warning(s))" % len(warnings) if warnings else ""))


if __name__ == "__main__":
    main()
