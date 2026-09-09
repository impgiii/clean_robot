from pathlib import Path

def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def get_abs_path(relative_path: str|Path) -> Path:
    return (get_project_root() / relative_path).resolve()


