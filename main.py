import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.data import (
    parse_github_url,
    fetch_repo_metadata,
    fetch_repo_tree,
)
from src.llm import summarize_repository
from src.models import select_repo_files
from src.utils import fetch_file_contents

load_dotenv()
app = FastAPI()


class RepoRequest(BaseModel):
    github_url: str


@app.get("/")
def home():
    return {"message": "Hello, World!"}


async def get_candidates(owner: str, repo: str) -> tuple[dict, list[dict]]:
    try:
        repo_metadata = await fetch_repo_metadata(owner, repo)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to fetch repository metadata",
        )

    try:
        candidates = await fetch_repo_tree(owner, repo)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to fetch repository tree",
        )

    return repo_metadata, candidates


def optimize(candidates: list[dict]) -> list[dict]:
    try:
        return select_repo_files(candidates, token_budget=12000, max_files=15)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to select repository files: {str(e)}",
        )


async def summarize(
    owner: str,
    repo: str,
    repo_metadata: dict,
    selected_files: list[dict],
) -> dict:
    try:
        selected_file_contents = await fetch_file_contents(
            owner, repo, repo_metadata["default_branch"], selected_files
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to fetch file contents",
        )

    repo_payload = {
        "repo_metadata": repo_metadata,
        "selected_files": selected_files,
        "selected_file_contents": selected_file_contents,
    }

    try:
        return await summarize_repository(repo_payload)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"LLM summarization failed: {str(e)}"
        )


@app.post("/summarize")
async def summarize_route(request: RepoRequest):
    try:
        owner, repo = parse_github_url(request.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    repo_metadata, candidates = await get_candidates(owner, repo)
    selected_files = optimize(candidates)
    return await summarize(owner, repo, repo_metadata, selected_files)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8700)
