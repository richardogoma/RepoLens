import asyncio

import httpx


async def _fetch_file(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    path: str,
) -> dict:
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = await client.get(url)
    resp.raise_for_status()
    return {"path": path, "content": resp.text}


async def fetch_file_contents(
    owner: str,
    repo: str,
    branch: str,
    selected_files: list[dict],
) -> list[dict]:
    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_file(client, owner, repo, branch, f["path"]) for f in selected_files
        ]
        return await asyncio.gather(*tasks)
