# Contributing to Enterprise LLM Routing Gateway

Thank you for your interest in contributing! Contributions that keep the gateway correct, simple, and well-tested are welcome.

---

## Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Report unacceptable behavior to `manoj.elumalai@outlook.com`.

---

## Development Setup

### Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Git

### Initial Setup
```bash
# 1. Clone the repository
git clone https://github.com/manojelumalai/enterprise-llm-gateway.git
cd enterprise-llm-gateway

# 2. Install dependencies (including dev extras)
make install

# 3. Install git hooks (code style + commit message format)
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# 4. Verify everything passes
make check
```

---

## Git & Commit Conventions

This project adheres to **[Conventional Commits v1.0.0](https://www.conventionalcommits.org/)**, enforced by the `commit-msg` pre-commit hook.

### Format
```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed Types
- `feat`: A new feature or capability
- `fix`: A bug fix
- `docs`: Documentation updates or additions
- `style`: Formatting changes with no functional code changes
- `refactor`: Refactoring production code without changing behavior
- `perf`: Performance improvements
- `test`: Adding or correcting tests
- `build`: Changes to build systems or dependencies
- `ci`: CI configuration changes (e.g., GitHub Actions)
- `chore`: Maintenance tasks or tooling updates

### Examples
- `feat(router): add configurable provider priority ordering`
- `fix(rate_limiter): avoid negative token balances on burst refill`
- `test(cache): add eviction boundary test`

---

## Quality Standards

Before submitting a pull request, run the full check suite locally:

```bash
make check   # ruff check, ruff format --check, mypy, pytest --cov
```

Individually:
- **Lint & format:** `make lint` / `make format` (uses `ruff` only — no `black`, no `isort`, no `flake8`).
- **Type safety:** `make typecheck` (`mypy`); public functions must be fully annotated.
- **Tests:** `make test`; new behavior needs test coverage.

---

## Pull Request Process

1. Create a feature branch from `main`: `git checkout -b feat/your-feature-name`.
2. Commit with atomic, conventional commit messages.
3. Open a Pull Request using the PR template and fill in its checklist.
4. Ensure all CI checks pass.
