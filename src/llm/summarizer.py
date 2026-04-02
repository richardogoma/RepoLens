import json
import os

from openai import AsyncOpenAI

SYSTEM_PROMPT = """
You are an expert software repository analyst.

Your task is to analyze a GitHub repository using:
1. repository metadata,
2. selected file metadata, and
3. the contents of selected files.

Your goal is to produce a concise, accurate, developer-friendly summary of the repository.

You must infer:
- what the project does,
- which technologies or major dependencies it uses,
- and how the repository is structured.

Output requirements:
- Return ONLY valid JSON.
- Do not include markdown fences.
- Do not include explanations outside the JSON.
- The JSON must exactly match this schema:

{
  "summary": "string",
  "technologies": ["string"],
  "structure": "string"
}

Rules:
- "summary" should be 2–5 sentences and explain the purpose of the project clearly.
- "technologies" should list the most important languages, libraries, frameworks, or tools actually evidenced in the input.
- "structure" should explain the repository layout in a concise paragraph.
- Do not hallucinate files, tools, or architecture that are not supported by the provided input.
- Prefer evidence from file contents over file metadata when there is a conflict.
- If some information is uncertain, make the most reasonable grounded inference without overclaiming.
"""

USER_PROMPT_TEMPLATE = """
Analyze this GitHub repository and return the required JSON output.

Input data:
{repo_payload}

Instructions:
- Use the repository metadata as high-level context.
- Use selected file metadata to understand importance and file roles.
- Use file contents as the primary evidence for your conclusions.
- Keep the response concise but informative.
- Return ONLY valid JSON matching the required schema.
"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
            api_key=os.environ["NEBIUS_API_KEY"],
        )
    return _client


async def summarize_repository(
    repo_payload: dict,
    model: str = "moonshotai/Kimi-K2.5-fast",
) -> dict:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        repo_payload=json.dumps(repo_payload, indent=2, ensure_ascii=False)
    )

    response = await _get_client().chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
        ],
    )

    return json.loads(response.choices[0].message.content)
