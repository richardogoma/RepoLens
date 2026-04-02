# RepoLens

> Understand any GitHub repository by selecting the **most informative files** under an LLM context budget.

RepoLens is a lightweight service that takes a public GitHub repository and returns a concise, human-readable summary of:

- **what the project does**
- **which technologies it uses**
- **how the repository is structured**

Instead of sending an entire codebase to an LLM, RepoLens first solves a **constrained optimization problem** to identify the best subset of files to read.

---

## Why RepoLens?

Large repositories contain a lot of noise:

- source code
- tests
- docs
- configs
- workflows
- assets
- generated or low-signal files

Sending all of that directly to an LLM is expensive and often unnecessary.

RepoLens asks a better question:

> **Given a limited context budget, which files maximize repository understanding?**

That turns repository summarization into a **budgeted file selection problem**, followed by **LLM-based summarization**.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/richardogoma/RepoLens.git RepoLens
cd RepoLens
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```bash
echo "NEBIUS_API_KEY=your_api_key_here" > .env
```

### 4. Run RepoLens

```bash
uv run main.py
```

---

## How It Works

RepoLens works in **three stages**:

### 1) Candidate Generation
We fetch repository metadata and file candidates from GitHub using:

- **GitHub Repository Metadata API**
- **GitHub Git Trees API**

This gives us:

- repository metadata
- recursive file paths
- file sizes

These files become the **candidate set**.

---

### 2) File Selection via Optimization
Each candidate file is assigned:

- a **value score** → how useful it is for understanding the repo
- a **token cost** → estimated LLM context cost
- **role labels** → what kind of understanding it contributes

We then solve a constrained optimization problem using:

- **Google OR-Tools CP-SAT model**

This selects the **most informative subset of files** under a token budget.

---

### 3) LLM Summarization
The selected files are passed to an LLM together with repository metadata.

The LLM receives:

- `repo_metadata`
- `selected_files`
- `selected_file_contents`

and returns:

```json
{
  "summary": "...",
  "technologies": ["..."],
  "structure": "..."
}
```

This project uses **Kimi K2.5** for summarization. Kimi K2.5 is an open-source, native multimodal agentic model built through continual pretraining on approximately 15 trillion mixed visual and text tokens atop Kimi-K2-Base

---

## Architecture

```text
GitHub Repo
   │
   ├── Stage 1: Candidate Generation
   │      ├── Repo Metadata API
   │      └── Git Trees API
   │
   ├── Candidate Files
   │      ├── path
   │      └── size
   │
   ├── Stage 2: Optimization
   │      └── OR-Tools CP-SAT
   │
   ├── Selected Files
   │
   ├── Stage 3: LLM Summarization
   │      ├── repo metadata
   │      ├── selected file metadata
   │      └── selected file contents
   │
   └── Output
          ├── summary
          ├── technologies
          └── structure
```

---

## Optimization Formulation

We model file selection as a **0–1 constrained optimization problem**.

Let:

<img width="392" height="106" alt="definitions" src="https://github.com/user-attachments/assets/8209180a-752e-4cf7-80ed-e1c74ec33c47" />

We maximize the total informativeness of selected files:

<img width="338" height="149" alt="optimization_model" src="https://github.com/user-attachments/assets/4c282210-122b-4ba8-9490-85c01867e8d6" />

---

## Coverage Constraints

A good repository summary needs more than “top-scoring” files.

We want coverage across key understanding dimensions, so we enforce constraints such as:

- at least **1 summary file**
- at least **1 technology/config file**
- at least **2 core source files**
- at least **1 structure-revealing file**

This prevents poor selections like:

- too many source files
- no docs
- no dependency/config files
- no high-level context

---

## Candidate File Schema

Each file is represented like this:

```json
{
  "path": "src/requests/api.py",
  "size_bytes": 7251,
  "tokens": 1909,
  "value": 171,
  "density": 0.0896,
  "categories": {
    "summary": 0,
    "technology": 0,
    "core_source": 1,
    "structure": 1,
    "docs": 0,
    "tests": 0,
    "ci_cd": 0
  }
}
```

---

## Scoring Design

Each file gets:

### **1. Token Cost**
Estimated from file size using file-type-aware byte-to-token ratios.

This approximates how expensive a file is to include in LLM context.

---

### **2. Value**
A heuristic importance score based on:

- filename importance (`README.md`, `pyproject.toml`, `setup.py`, etc.)
- directory importance (`src/`, `docs/`, `tests/`)
- semantic role labels
- file size usefulness
- penalties for low-signal files

---

### **3. Density**
Defined as:

<img width="110" height="39" alt="density_scoring" src="https://github.com/user-attachments/assets/ad941abb-532c-473a-9746-f20b6fd2ae3e" />


This represents **information per token** and is useful for debugging and analysis.

---

## Role Labels

Each file can be assigned one or more semantic labels:

- `summary`
- `technology`
- `core_source`
- `structure`
- `docs`
- `tests`
- `ci_cd`

### Meaning

- **`summary`** → helps explain what the repo is and what it does  
- **`technology`** → reveals dependencies, tooling, frameworks, or setup  
- **`core_source`** → contains main implementation logic  
- **`structure`** → helps explain how the repo is organized  
- **`docs`** → documentation-oriented file  
- **`tests`** → test-related file  
- **`ci_cd`** → workflows / automation / pipeline files  

These labels are used to enforce **coverage constraints** during optimization.

---

## Example Output

For a repository like `google/or-tools`, RepoLens might produce:

```json
{
  "summary": "Google OR-Tools is an open-source software suite for solving combinatorial optimization problems, including constraint programming, linear and integer programming, vehicle routing, and graph algorithms. Written primarily in C++ with bindings for Python, Java, and C#, it provides multiple optimization engines such as the CP-SAT solver, GLOP (simplex-based LP), and PDLP (first-order methods). The project supports various build systems including Bazel, CMake, and Make, and offers wrappers for commercial and open-source solvers like SCIP, Gurobi, and CPLEX.",
  "technologies": [
    "C++",
    "Python",
    "Java",
    "C#",
    "Bazel",
    "CMake",
    "GNU Make",
    "Protocol Buffers",
    "SWIG",
    "pybind11",
    "Maven",
    "Docker",
    "Eigen",
    "Google Abseil-cpp",
    "Google Test",
    "SCIP",
    "GLPK",
    "COIN-OR"
  ],
  "structure": "The repository is organized with source code under `ortools/` containing specialized directories for different optimization domains: `sat/` (CP-SAT solver), `constraint_solver/` (CP and routing), `linear_solver/` (LP/IP wrappers), `glop/` and `pdlp/` (specific LP solvers), `graph/` (graph algorithms), `algorithms/` (bin packing, knapsack), `set_cover/`, and `math_opt/` (unified solver API). Language bindings reside in `ortools/python/` (SWIG/pybind11), `ortools/java/` (SWIG/JNI), and `ortools/csharp/`, while build configurations are split between `bazel/`, `cmake/`, and `makefiles/` (deprecated). Examples and documentation are located in `examples/` and `tools/`, with CI/CD workflows in `.github/workflows/`."
}
```

---

## Tech Stack

- **Python**
- **GitHub APIs**
  - Repository Metadata API
  - Git Trees API
- **Google OR-Tools**
  - CP-SAT solver
- **Kimi K2.5 Fast**
  - repository summarization

---

## Why CP-SAT?

A naive approach would sort files by score and take the top \(k\).

That often produces bad results.

RepoLens instead solves for the **best combination of files**, while respecting:

- a **token budget**
- **minimum coverage**
- optional **balancing constraints**

That makes the selected file set much more useful for summarization.

---

## Limitations

- file value is still partly heuristic
- token estimation from file size is approximate
- file importance is inferred before reading full contents
- quality depends on candidate scoring quality

Still, this gives a strong and practical foundation for repository understanding.

---

## Future Improvements

- two-stage optimization
- content-aware scoring
- better low-signal filtering
- support for different summary modes:
  - beginner summary
  - architecture summary
  - contributor onboarding summary

---

## Core Insight

> **Repository understanding is not just a retrieval problem — it is a budgeted selection problem.**

The challenge is not only finding relevant files, but selecting the **best combination of files** under limited context.

That is what RepoLens is built to solve.
