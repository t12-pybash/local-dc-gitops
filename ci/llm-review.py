#!/usr/bin/env python3
"""
LLM-powered GitOps PR review.
Fetches the MR diff, sends it to LiteLLM, posts the review as an MR comment.
"""
import os, json, sys, urllib.request, urllib.error

LITELLM_URL = "http://litellm.ai-platform.svc.cluster.local:4000"
LITELLM_KEY = os.environ["LITELLM_API_KEY"]
GITLAB_URL  = os.environ["CI_API_V4_URL"]
PROJECT_ID  = os.environ["CI_PROJECT_ID"]
MR_IID      = os.environ["CI_MERGE_REQUEST_IID"]
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", os.environ.get("CI_JOB_TOKEN", ""))
MODEL       = os.environ.get("LLM_REVIEW_MODEL", "phi4-mini")
MAX_DIFF    = int(os.environ.get("LLM_REVIEW_MAX_DIFF", "6000"))


def gitlab_get(path):
    req = urllib.request.Request(
        f"{GITLAB_URL}/{path}",
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gitlab_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{GITLAB_URL}/{path}",
        data=data,
        headers={"Content-Type": "application/json", "PRIVATE-TOKEN": GITLAB_TOKEN}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def litellm_chat(prompt):
    data = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "cache": {"no-cache": True},
    }).encode()
    req = urllib.request.Request(
        f"{LITELLM_URL}/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LITELLM_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def main():
    print(f"Fetching diff for MR !{MR_IID}...")
    diffs = gitlab_get(f"projects/{PROJECT_ID}/merge_requests/{MR_IID}/diffs")

    # Build diff text — skip binary and very large files
    diff_text = ""
    for d in diffs:
        if d.get("diff") and not d.get("too_large") and not d.get("binary"):
            diff_text += f"\n--- {d['old_path']}\n+++ {d['new_path']}\n{d['diff']}"

    if not diff_text.strip():
        print("No reviewable diff found — skipping.")
        sys.exit(0)

    # Truncate to token budget
    if len(diff_text) > MAX_DIFF:
        diff_text = diff_text[:MAX_DIFF] + "\n\n[diff truncated]"

    print(f"Sending {len(diff_text)} chars to {MODEL} via LiteLLM...")

    prompt = f"""You are an expert SRE reviewing a GitOps Kubernetes infrastructure pull request.

Review ONLY what is present in the diff. Do not invent or assume resources that are not shown.

Check for:
- Correctness: resource names consistent across files, kustomization references match files actually in the diff
- Security: secrets in plaintext, overly permissive RBAC — only flag if visible in the diff
- Best practices: missing resource limits, :latest image tags, missing health probes — only flag if the resource is present in the diff and the field is absent
- Broken references: a kustomization.yaml that lists a file not included in this diff

Rules:
- If a file is in the diff, it exists — do not flag it as missing
- Do not flag hypothetical missing NetworkPolicies or RBAC unless this diff introduces a public-facing service with no policy at all
- Be concise and specific. Only raise real issues you can point to with a line number or filename.

Lead with a one-line verdict (✅ LGTM / ⚠️ Minor issues / ❌ Needs work). Use markdown.

```diff
{diff_text}
```"""

    review = litellm_chat(prompt)
    print("Review generated. Posting to MR...")

    comment = f"## 🤖 AI Review\n\n{review}\n\n---\n*{MODEL} via Olympus LiteLLM · [LLMOps dashboard](https://grafana.t-12.io/public-dashboards/bf7f2f489c574a418cb9fb3a49483dd6)*"
    note = gitlab_post(f"projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes", {"body": comment})
    print(f"Posted comment #{note['id']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} {e.reason}\n{e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
