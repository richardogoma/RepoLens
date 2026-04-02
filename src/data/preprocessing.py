import re
import httpx


GIT_BASE_URL = "https://api.github.com/repos/{owner}/{repo}"


def parse_github_url(url: str) -> tuple[str, str]:
    match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not match:
        raise ValueError("Invalid GitHub URL")
    return match.group(1), match.group(2)


async def fetch_repo_metadata(owner: str, repo: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    base_url = GIT_BASE_URL.format(owner=owner, repo=repo)

    async with httpx.AsyncClient() as client:
        resp = await client.get(base_url, headers=headers)
        resp.raise_for_status()

    return {
        "name": resp.json().get("full_name"),
        "description": resp.json().get("description"),
        "language": resp.json().get("language"),
        "default_branch": resp.json().get("default_branch"),
        "topics": resp.json().get("topics"),
    }


async def fetch_repo_tree(owner: str, repo: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    base_url = GIT_BASE_URL.format(owner=owner, repo=repo)

    async with httpx.AsyncClient() as client:
        repo_resp = await client.get(base_url, headers=headers)
        repo_resp.raise_for_status()
        default_branch = repo_resp.json()["default_branch"]

        tree_resp = await client.get(
            f"{base_url}/git/trees/{default_branch}",
            headers=headers,
            params={"recursive": "1"},
        )
        tree_resp.raise_for_status()
        all_paths = tree_resp.json().get("tree", [])

    return [
        {"path": item["path"], "size": item.get("size", 0)}
        for item in all_paths
        if item["type"] == "blob"
    ]
