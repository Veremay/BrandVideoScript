from pathlib import Path


def repository_root() -> Path:
    """BrandVideo repo root (parent of `backend/`)."""
    return Path(__file__).resolve().parents[3]


def default_llm_wiki_root() -> Path:
    return repository_root() / "llm-wiki"
