from github import Github
from github.GithubIntegration import GithubIntegration
import os
from dotenv import load_dotenv
import time
import jwt  # pip install PyJWT cryptography
import requests
import base64


load_dotenv()
API = "https://api.github.com"

def gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def generate_app_jwt(app_id: str, private_key_pem: str) -> str:
    now = int(time.time())

    payload = {
        # GitHub 建议 iat 稍微往前打几秒，避免时钟偏差
        "iat": now - 10,
        # GitHub 要求 exp <= 10 min
        "exp": now + 9 * 60,
        # iss 是 GitHub App 的 App ID
        "iss": app_id,
    }

    token = jwt.encode(payload, private_key_pem, algorithm="RS256")
    return token

with open("fungun-test-gh-app-demo.2026-02-13.private-key.pem", "r", encoding="utf-8") as f:
    private_key_pem = f.read()

def list_app_installations(app_jwt: str, per_page: int = 100, page: int = 1):
    url = f"{GITHUB_API}/app/installations"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, params={"per_page": per_page, "page": page}, timeout=30)
    r.raise_for_status()
    return r.json()  # list

def get_installation_token(app_jwt: str, installation_id: int) -> str:
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.post(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["token"]

def list_accessible_repos(installation_token: str):
    url = "https://api.github.com/installation/repositories"
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    r = r.json()
    # extract (owner, repo) in to list [(owner, repo), ...]
    repos = [(item["owner"]["login"], item["name"]) for item in r["repositories"]]

    return repos

def get_repo(installation_token: str, owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()



def get_default_branch(inst_token: str, owner: str, repo: str) -> str:
    url = f"{API}/repos/{owner}/{repo}"
    r = requests.get(url, headers=gh_headers(inst_token), timeout=30)
    r.raise_for_status()
    return r.json()["default_branch"]


def get_branch_head_sha(inst_token: str, owner: str, repo: str, branch: str) -> str:
    url = f"{API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    r = requests.get(url, headers=gh_headers(inst_token), timeout=30)
    if r.status_code == 409:
        return None
    if r.status_code >= 400:
        print("Status:", r.status_code)
        print("Response:", r.text)          # <<< 关键
        print("Headers:", r.headers)
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(inst_token: str, owner: str, repo: str, new_branch: str, base_sha: str) -> None:
    url = f"{API}/repos/{owner}/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}
    r = requests.post(url, json=payload, headers=gh_headers(inst_token), timeout=30)
    if r.status_code == 422:
        die(f"Branch already exists: {new_branch}")
    r.raise_for_status()


def get_file_sha_if_exists(inst_token: str, owner: str, repo: str, path: str, branch: str) -> str | None:
    url = f"{API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=gh_headers(inst_token), params={"ref": branch}, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("sha")


def put_file(inst_token: str, owner: str, repo: str, path: str, branch: str, content_text: str, message: str) -> None:
    url = f"{API}/repos/{owner}/{repo}/contents/{path}"
    existing_sha = get_file_sha_if_exists(inst_token, owner, repo, path, branch)
    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": content_b64,
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha  # required for updates

    r = requests.put(url, json=payload, headers=gh_headers(inst_token), timeout=30)
    r.raise_for_status()


def create_pr(inst_token: str, owner: str, repo: str, base: str, head: str, title: str, body: str) -> str:
    url = f"{API}/repos/{owner}/{repo}/pulls"
    payload = {"title": title, "body": body, "head": head, "base": base}
    r = requests.post(url, json=payload, headers=gh_headers(inst_token), timeout=30)
    r.raise_for_status()
    return r.json()["html_url"]


installation_id = 109899039
branch_name = os.environ.get("GH_BRANCH", f"agent-fix-{int(time.time())}")
new_content = os.environ.get("GH_FILE_CONTENT", "hello from GitHub App agent\n")
file_path = os.environ.get("GH_FILE_PATH", "agent_demo.txt")
commit_msg = os.environ.get("GH_COMMIT_MSG", "Agent: demo change")
pr_title = os.environ.get("GH_PR_TITLE", "Agent: demo PR")
pr_body = os.environ.get("GH_PR_BODY", "This PR was created automatically by a GitHub App installation token.")


GITHUB_API = "https://api.github.com"
APP_ID = os.getenv('GITHUB_APP_ID')
token = generate_app_jwt(APP_ID, private_key_pem)
installation_token = get_installation_token(token, installation_id)  # 替换为实际的安装 ID
repos = list_accessible_repos(installation_token)
# print(repos) 
example_repo = repos[0]  # 取第一个仓库作为示例
owner, repo = example_repo
repo_info = get_repo(installation_token, owner, repo)

# print(repo_info)


# print(list_app_installations(token))
# print(installation_token)

# 3) Base branch and SHA
base_branch = get_default_branch(installation_token, owner, repo)
print("Base branch:", base_branch)
base_sha = get_branch_head_sha(installation_token, owner, repo, base_branch)
if base_sha is None:
    # bootstrap empty repo with an initial commit on default branch
    put_file(
        installation_token,
        owner,
        repo,
        file_path,
        base_branch,
        new_content,
        "Initial commit",
    )
    base_sha = get_branch_head_sha(installation_token, owner, repo, base_branch)

print("Base SHA:", base_sha)

# 4) Create new branch
create_branch(installation_token, owner, repo, branch_name, base_sha)

# 5) Commit change (create/update a file)
put_file(installation_token, owner, repo, file_path, branch_name, new_content, commit_msg)

# 6) Open PR
pr_url = create_pr(installation_token, owner, repo, base_branch, branch_name, pr_title, pr_body)
print("PR created:", pr_url)

