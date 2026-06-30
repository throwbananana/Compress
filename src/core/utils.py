import sys
import os

PYTHON_ENTRY_PRIORITY = (
    "__main__.py",
    "main.py",
    "app.py",
    "gui.py",
    "start.py",
)

PYTHON_SCAN_IGNORED_DIRS = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "node_modules",
    "tests",
    "test",
}

def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Dev mode: Resources are in src/resources relative to this utils.py
        # src/core/utils.py -> src/core -> src -> src/resources
        base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")

    return os.path.join(base_path, relative_path)

def list_python_entry_candidates(path, max_depth=3):
    """
    Return likely Python entry files for a file or folder input.
    """
    if not path:
        return []

    path = os.path.abspath(os.path.expanduser(path.strip()))
    if not os.path.exists(path):
        return []

    if os.path.isfile(path):
        return [path] if path.lower().endswith(".py") else []

    candidates = []
    seen = set()

    def add_candidate(candidate):
        candidate = os.path.abspath(candidate)
        if candidate in seen:
            return
        if os.path.isfile(candidate) and candidate.lower().endswith(".py"):
            seen.add(candidate)
            candidates.append(candidate)

    for priority_name in PYTHON_ENTRY_PRIORITY:
        add_candidate(os.path.join(path, priority_name))

    base_name = os.path.basename(path)
    for nested_dir in (os.path.join(path, base_name), os.path.join(path, "src")):
        for priority_name in PYTHON_ENTRY_PRIORITY:
            add_candidate(os.path.join(nested_dir, priority_name))

    try:
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(".py"):
                add_candidate(os.path.join(path, name))
    except OSError:
        return candidates

    for root, dirs, files in os.walk(path):
        rel_root = os.path.relpath(root, path)
        depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1

        dirs[:] = [
            directory
            for directory in dirs
            if directory not in PYTHON_SCAN_IGNORED_DIRS and depth < max_depth
        ]

        if depth == 0:
            continue

        for name in sorted(files):
            if name.lower().endswith(".py"):
                add_candidate(os.path.join(root, name))

    return candidates

def resolve_python_entry(path):
    """
    Resolve a file or folder path to a concrete Python entry file.
    """
    candidates = list_python_entry_candidates(path)
    return candidates[0] if candidates else None
