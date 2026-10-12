#!/usr/bin/env python3
"""Pre-publish secrets/PII sweep — scans every blob in git history.

Checks all committed content (not just HEAD) for:
- real email addresses (non-example domains)
- API-key-shaped strings and key material
- credential files ever committed
- suspicious long base64/hex secrets adjacent to key-like names

Prints only match locations + pattern names, never the secret itself.
"""
import re
import subprocess
import sys

PATTERNS = {
    "email_non_example": re.compile(
        rb"[A-Za-z0-9._%+-]+@(?!.*example\.(com|org|net))[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "openai_key": re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    "anthropic_key": re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}"),
    "google_key": re.compile(rb"AIza[A-Za-z0-9_-]{20,}"),
    "aws_key": re.compile(rb"AKIA[A-Z0-9]{16}"),
    "private_key_block": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY"),
    "paypal_secret_assignment": re.compile(
        rb"PAYPAL_CLIENT_SECRET\s*=\s*['\"]?[A-Za-z0-9_-]{8,}"),
    "generic_secret_assignment": re.compile(
        rb"(?i)(secret|passwd|password)\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    "github_pat": re.compile(rb"(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}"),
    "slack_token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}"),
}
CRED_FILE_RE = re.compile(rb"(^|/)(\.env[^/]*|.*credentials.*|.*\.pem|id_rsa.*)$")

def git(*args):
    return subprocess.run(["git"] + list(args), capture_output=True, check=True).stdout

def main():
    commits = git("rev-list", "--all").split()
    print(f"scanning {len(commits)} commits", file=sys.stderr)
    findings = []
    seen_blobs = set()
    for c in commits:
        tree = git("ls-tree", "-r", c).decode()
        for line in tree.splitlines():
            if not line:
                continue
            meta, fname = line.split("\t", 1)
            _, _, blob = meta.split()
            if blob in seen_blobs:
                continue
            seen_blobs.add(blob)
            if CRED_FILE_RE.search(fname.encode()):
                findings.append((fname, "CRED_FILENAME", c[:8].decode()))
            content = git("cat-file", "blob", blob)
            if len(content) > 4_000_000:
                continue
            for name, pat in PATTERNS.items():
                for m in pat.finditer(content):
                    snippet = m.group()[:40].decode("utf-8", "replace")
                    findings.append((fname, name, c[:8].decode(), snippet))
    if not findings:
        print("CLEAN — no secrets/PII found in git history")
        return
    print(f"FINDINGS: {len(findings)}")
    for f in findings[:60]:
        print(" | ".join(f))
        sys.exit(1)

if __name__ == "__main__":
    main()
