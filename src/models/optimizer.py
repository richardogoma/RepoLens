from ortools.sat.python import cp_model
from typing import List, Dict, Any
import math


# =========================================================
# CONFIG
# =========================================================

TOKEN_BUDGET = 12000
MAX_FILES = 15

MIN_SUMMARY = 1
MIN_TECH = 1
MIN_CORE_SOURCE = 2
MIN_STRUCTURE = 1

# Approximate bytes-per-token ratios by file type
TOKEN_RATIO_BY_TYPE = {
    ".py": 3.8,
    ".md": 4.2,
    ".rst": 4.3,
    ".toml": 3.6,
    ".ini": 3.5,
    ".yml": 3.5,
    ".yaml": 3.5,
    ".txt": 4.0,
    ".cfg": 3.6,
    ".json": 3.7,
    ".xml": 3.7,
    ".sh": 3.6,
    ".bat": 3.6,
}

DEFAULT_TOKEN_RATIO = 4.0

# Exclude obvious low-value / binary / unsafe-to-include files
EXCLUDE_PREFIXES = [
    ".git/",
    ".venv/",
    "venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    "coverage/",
    "dist/",
    "build/",
    "node_modules/",
    ".next/",
    ".nuxt/",
    "target/",
    "bin/",
    "obj/",
]

EXCLUDE_SUFFIXES = [
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dll",
    ".exe",
    ".zip",
    ".tar",
    ".gz",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".pdf",
    ".mp4",
    ".mp3",
    ".map",
    ".key",
    ".crt",
    ".pem",
    ".csr",
    ".srl",
    ".ai",
]

LOW_PRIORITY_PREFIXES = [
    ".github/ISSUE_TEMPLATE/",
    "docs/_static/",
    "docs/_templates/",
    "docs/_themes/",
    "ext/",
    "tests/certs/",
]

IMPORTANT_FILENAMES = {
    "README.md": 100,
    "pyproject.toml": 98,
    "setup.py": 95,
    "requirements.txt": 92,
    "requirements-dev.txt": 88,
    "tox.ini": 85,
    "MANIFEST.in": 82,
    "HISTORY.md": 80,
    "CHANGELOG.md": 80,
    "LICENSE": 70,
    "Makefile": 65,
    "__init__.py": 55,
    "__version__.py": 55,
    "conftest.py": 50,
    "Dockerfile": 85,
    "docker-compose.yml": 85,
    "package.json": 95,
    "go.mod": 95,
    "Cargo.toml": 95,
}

IMPORTANT_DIR_HINTS = {
    "src/": 30,
    "requests/": 45,
    "docs/": 30,
    "tests/": 25,
    ".github/workflows/": 18,
}


# =========================================================
# HELPERS
# =========================================================


def is_excluded_path(path: str) -> bool:
    return any(path.startswith(p) for p in EXCLUDE_PREFIXES) or any(
        path.endswith(s) for s in EXCLUDE_SUFFIXES
    )


def is_low_priority_path(path: str) -> bool:
    return any(path.startswith(p) for p in LOW_PRIORITY_PREFIXES)


def get_filename(path: str) -> str:
    return path.split("/")[-1]


def estimate_tokens_from_size(path: str, size_bytes: int) -> int:
    """
    Estimate token count from file size in bytes.
    Assumes mostly text/code files.
    """
    filename = get_filename(path)

    # exact filename overrides
    if filename in {"Dockerfile", "Makefile", "LICENSE"}:
        ratio = 3.8
        return max(1, math.ceil(size_bytes / ratio))

    for ext, ratio in TOKEN_RATIO_BY_TYPE.items():
        if path.endswith(ext):
            return max(1, math.ceil(size_bytes / ratio))

    return max(1, math.ceil(size_bytes / DEFAULT_TOKEN_RATIO))


def size_informativeness_bonus(size_bytes: int) -> int:
    """
    Small bonus/penalty based on file size.
    Very tiny files often aren't informative.
    Extremely large files can be expensive/noisy.
    """
    if size_bytes < 100:
        return -10
    elif size_bytes < 500:
        return -4
    elif size_bytes < 2000:
        return 3
    elif size_bytes < 15000:
        return 8
    elif size_bytes < 50000:
        return 5
    else:
        return -3


def categorize_file(path: str) -> Dict[str, int]:
    """
    Multi-label category flags.
    A file can contribute to more than one understanding dimension.
    """
    filename = get_filename(path)

    categories = {
        "summary": 0,
        "technology": 0,
        "core_source": 0,
        "structure": 0,
        "docs": 0,
        "tests": 0,
        "ci_cd": 0,
    }

    # Summary / repo identity
    if filename in {"README.md", "HISTORY.md", "CHANGELOG.md", "LICENSE"}:
        categories["summary"] = 1
        categories["structure"] = 1

    # Documentation
    if path.startswith("docs/"):
        categories["docs"] = 1
        categories["structure"] = 1

        if filename in {"index.rst", "quickstart.rst", "install.rst", "api.rst"}:
            categories["summary"] = 1

    # Tech stack / dependencies / setup
    if filename in {
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "requirements-dev.txt",
        "tox.ini",
        "Dockerfile",
        "docker-compose.yml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        ".pre-commit-config.yaml",
        ".readthedocs.yaml",
    }:
        categories["technology"] = 1

    # Core implementation
    if (path.startswith("src/") or path.startswith("requests/")) and path.endswith(
        ".py"
    ):
        categories["core_source"] = 1
        categories["structure"] = 1

    # Tests
    if path.startswith("tests/"):
        categories["tests"] = 1
        categories["structure"] = 1

    # CI/CD
    if path.startswith(".github/workflows/"):
        categories["ci_cd"] = 1
        categories["technology"] = 1
        categories["structure"] = 1

    return categories


def compute_value(path: str, size_bytes: int) -> int:
    """
    Utility score for optimization.
    This score is the optimizer input, not the final selector.
    """
    score = 0
    filename = get_filename(path)
    categories = categorize_file(path)

    # Strong filename signal
    if filename in IMPORTANT_FILENAMES:
        score += IMPORTANT_FILENAMES[filename]

    # Directory signal
    for prefix, value in IMPORTANT_DIR_HINTS.items():
        if path.startswith(prefix):
            score += value

    # Extension signal
    if path.endswith(".py"):
        score += 20
    elif path.endswith(".toml"):
        score += 18
    elif path.endswith(".ini"):
        score += 15
    elif path.endswith(".md") or path.endswith(".rst"):
        score += 12
    elif path.endswith(".yml") or path.endswith(".yaml"):
        score += 10

    # Top-level files often matter more
    if path.count("/") == 0:
        score += 15
    elif path.count("/") == 1:
        score += 8

    # Category contributions
    score += 35 * categories["summary"]
    score += 32 * categories["technology"]
    score += 40 * categories["core_source"]
    score += 18 * categories["structure"]
    score += 8 * categories["docs"]
    score += 6 * categories["tests"]
    score += 10 * categories["ci_cd"]

    # Size usefulness shaping
    score += size_informativeness_bonus(size_bytes)

    # Penalties
    if is_low_priority_path(path):
        score -= 35

    if path.startswith("tests/"):
        score -= 5

    if path.startswith("docs/"):
        score -= 2

    return max(score, 1)


# =========================================================
# CANDIDATE BUILDER
# =========================================================


def build_candidates(repo_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Input format:
    [
        {"path": "README.md", "size": 11032},
        {"path": "src/requests/api.py", "size": 7251},
    ]
    """
    candidates = []

    for item in repo_files:
        path = item["path"]
        size_bytes = int(item.get("size", 0) or 0)

        # Ignore directories if they appear in the list
        if path.endswith("/"):
            continue

        # Skip paths without useful file semantics
        if is_excluded_path(path):
            continue

        categories = categorize_file(path)
        tokens = estimate_tokens_from_size(path, size_bytes)
        value = compute_value(path, size_bytes)

        candidates.append(
            {
                "path": path,
                "size_bytes": size_bytes,
                "tokens": tokens,
                "value": value,
                "density": round(value / max(tokens, 1), 4),
                "categories": categories,
            }
        )

    return candidates


# =========================================================
# CP-SAT OPTIMIZER
# =========================================================


def select_files_cp_sat(
    candidates: List[Dict[str, Any]],
    token_budget: int = TOKEN_BUDGET,
    max_files: int = MAX_FILES,
    min_summary: int = MIN_SUMMARY,
    min_tech: int = MIN_TECH,
    min_core_source: int = MIN_CORE_SOURCE,
    min_structure: int = MIN_STRUCTURE,
) -> List[Dict[str, Any]]:
    """
    Solve file selection as a constrained optimization problem.

    Maximize total value subject to:
    - total estimated tokens <= token_budget
    - max number of files
    - enough repo understanding coverage
    """
    model = cp_model.CpModel()
    n = len(candidates)

    x = [model.NewBoolVar(f"x_{i}") for i in range(n)]

    # Token budget
    model.Add(sum(candidates[i]["tokens"] * x[i] for i in range(n)) <= token_budget)

    # Max number of files
    model.Add(sum(x[i] for i in range(n)) <= max_files)

    # Coverage constraints
    summary_idx = [
        i for i, f in enumerate(candidates) if f["categories"]["summary"] == 1
    ]
    tech_idx = [
        i for i, f in enumerate(candidates) if f["categories"]["technology"] == 1
    ]
    core_idx = [
        i for i, f in enumerate(candidates) if f["categories"]["core_source"] == 1
    ]
    structure_idx = [
        i for i, f in enumerate(candidates) if f["categories"]["structure"] == 1
    ]
    tests_idx = [i for i, f in enumerate(candidates) if f["categories"]["tests"] == 1]
    docs_idx = [i for i, f in enumerate(candidates) if f["categories"]["docs"] == 1]

    if summary_idx:
        model.Add(sum(x[i] for i in summary_idx) >= min_summary)

    if tech_idx:
        model.Add(sum(x[i] for i in tech_idx) >= min_tech)

    if core_idx:
        model.Add(sum(x[i] for i in core_idx) >= min_core_source)

    if structure_idx:
        model.Add(sum(x[i] for i in structure_idx) >= min_structure)

    # Optional balancing constraints
    if tests_idx:
        model.Add(sum(x[i] for i in tests_idx) <= 3)

    if docs_idx:
        model.Add(sum(x[i] for i in docs_idx) <= 3)

    # Objective: maximize total utility
    model.Maximize(sum(candidates[i]["value"] * x[i] for i in range(n)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "No feasible file selection found. "
            "Try increasing token_budget or relaxing coverage constraints."
        )

    selected = [candidates[i] for i in range(n) if solver.Value(x[i]) == 1]

    # Sort selected files by value desc, then density desc
    selected = sorted(selected, key=lambda d: (-d["value"], -d["density"], d["tokens"]))

    return selected


# =========================================================
# REPORTING
# =========================================================


def print_selection_report(selected: List[Dict[str, Any]], token_budget: int):
    total_tokens = sum(f["tokens"] for f in selected)
    total_value = sum(f["value"] for f in selected)
    total_bytes = sum(f["size_bytes"] for f in selected)

    print("=" * 100)
    print("SELECTED FILES")
    print("=" * 100)
    print(f"Files selected: {len(selected)}")
    print(f"Total estimated tokens: {total_tokens}/{token_budget}")
    print(f"Total bytes: {total_bytes}")
    print(f"Total utility score: {total_value}")
    print()

    for f in selected:
        cats = [k for k, v in f["categories"].items() if v == 1]
        print(f"- {f['path']}")
        print(
            f"  size={f['size_bytes']} bytes | "
            f"tokens≈{f['tokens']} | "
            f"value={f['value']} | "
            f"density={f['density']}"
        )
        print(f"  categories={cats}")
        print()


# =========================================================
# MAIN ENTRYPOINT
# =========================================================


def select_repo_files(
    repo_files: List[Dict[str, Any]],
    token_budget: int = TOKEN_BUDGET,
    max_files: int = MAX_FILES,
) -> List[Dict[str, Any]]:
    candidates = build_candidates(repo_files)
    selected = select_files_cp_sat(
        candidates=candidates,
        token_budget=token_budget,
        max_files=max_files,
    )
    return selected


# =========================================================
# EXAMPLE USAGE
# =========================================================

if __name__ == "__main__":
    repo_files = [
        {"path": "README.md", "size": 11032},
        {"path": "pyproject.toml", "size": 4172},
        {"path": "setup.py", "size": 2520},
        {"path": "requirements-dev.txt", "size": 891},
        {"path": "tox.ini", "size": 2400},
        {"path": "docs/index.rst", "size": 5021},
        {"path": "docs/user/quickstart.rst", "size": 6100},
        {"path": ".github/workflows/run-tests.yml", "size": 1800},
        {"path": "src/requests/__init__.py", "size": 2800},
        {"path": "src/requests/api.py", "size": 7251},
        {"path": "src/requests/sessions.py", "size": 19200},
        {"path": "src/requests/models.py", "size": 17500},
        {"path": "src/requests/adapters.py", "size": 14800},
        {"path": "src/requests/auth.py", "size": 6900},
        {"path": "src/requests/utils.py", "size": 16000},
        {"path": "tests/test_requests.py", "size": 10500},
        {"path": "tests/test_adapters.py", "size": 8400},
        {"path": "ext/requests-logo.png", "size": 55000},  # excluded
    ]

    selected = select_repo_files(repo_files, token_budget=12000, max_files=15)
    print_selection_report(selected, token_budget=12000)
