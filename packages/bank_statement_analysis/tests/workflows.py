"""This project's GitHub workflows: the ones in the repository that name its folder."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
PROJECT_FOLDER = ROOT.relative_to(REPO_ROOT).as_posix()


def project_workflows(repo_root: Path = REPO_ROOT) -> list[Path]:
    """A workflow that runs this project names its folder. The rest belong to the repository's other projects."""
    return sorted(path for path in (repo_root / ".github" / "workflows").iterdir()
                  if path.suffix in (".yml", ".yaml") and PROJECT_FOLDER in path.read_text(encoding="utf-8"))
