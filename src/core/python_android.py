from __future__ import annotations

import os
import re
import shutil
import textwrap
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


DEFAULT_PACKAGE_DOMAIN = "org.compass"
DEFAULT_VERSION = "0.1.0"
DEFAULT_REQUIREMENTS = "python3"
DEFAULT_INCLUDE_EXTS = "py,png,jpg,jpeg,kv,atlas,json,txt,ini,ttf,otf,mp3,wav,xml,css,html,js"
KIVY_REQUIREMENTS = ("python3", "kivy")
ALLOWED_ORIENTATIONS = {"portrait", "landscape", "portrait-reverse", "landscape-reverse", "all"}
ALLOWED_BUILD_MODES = {"debug", "release"}
IGNORED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "venv",
}
ICON_CANDIDATES = (
    "icon.png",
    "app-icon.png",
    "assets/icon.png",
    "assets/app-icon.png",
    "data/icon.png",
)
PRESPLASH_CANDIDATES = (
    "presplash.png",
    "splash.png",
    "assets/presplash.png",
    "assets/splash.png",
    "data/presplash.png",
    "data/splash.png",
)
PROJECT_METADATA_FILES = ("requirements.txt", "setup.py", "pyproject.toml")
NATIVE_SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".rs", ".go", ".pyx", ".pxd"}
NATIVE_REQUIREMENT_HINTS = {"cython", "cffi", "pybind11", "maturin", "setuptools-rust", "rust"}
ARTIFACT_PATTERNS = ("*.apk", "*.aab")

def suggest_python_android_assets(entry: str) -> dict:
    entry_path = Path(entry).expanduser().resolve()
    if not entry_path.exists() or not entry_path.is_file() or entry_path.suffix.lower() != ".py":
        raise ValueError("Invalid Python entry file.")

    source_dir = entry_path.parent
    icon_path = find_candidate_asset(source_dir, ICON_CANDIDATES)
    presplash_path = find_candidate_asset(source_dir, PRESPLASH_CANDIDATES)
    return {
        "icon_path": icon_path,
        "presplash_path": presplash_path,
    }


def suggest_python_android_requirements(entry: str) -> dict:
    entry_path = Path(entry).expanduser().resolve()
    if not entry_path.exists() or not entry_path.is_file() or entry_path.suffix.lower() != ".py":
        raise ValueError("Invalid Python entry file.")

    source_dir = entry_path.parent
    imported_requirements, imported_sources = collect_project_requirement_candidates(source_dir)
    uses_kivy = detect_kivy_project(source_dir)
    requirements = sanitize_requirements(
        "",
        uses_kivy=uses_kivy,
        detected_requirements=imported_requirements,
    )
    return {
        "requirements": requirements,
        "sources": imported_sources,
        "uses_kivy": uses_kivy,
    }


def build_python_android_package(config: "PythonAndroidConfig") -> dict:
    entry_path = Path(config.entry).expanduser().resolve()
    if not entry_path.exists() or not entry_path.is_file():
        raise ValueError("Invalid Python entry file.")
    if entry_path.suffix.lower() != ".py":
        raise ValueError("Python Android packaging requires a .py entry file.")

    if os.name == "nt":
        raise RuntimeError(
            "Buildozer/python-for-android only runs on Linux or macOS. On Windows, use WSL and run Compass there."
        )

    source_dir = entry_path.parent
    project_dir = resolve_stage_dir(source_dir)
    app_dir = project_dir / "app"

    if project_dir.exists():
        shutil.rmtree(project_dir)
    app_dir.mkdir(parents=True, exist_ok=True)

    copy_source_tree(source_dir, app_dir)

    try:
        entry_relative = entry_path.relative_to(source_dir)
    except ValueError as exc:
        raise ValueError("Entry file must be inside the selected source folder.") from exc

    ensure_android_main(app_dir, entry_relative)

    app_name = sanitize_app_name(config.app_name or source_dir.name)
    package_name = sanitize_package_name(config.package_name or app_name)
    package_domain = sanitize_package_domain(config.package_domain or DEFAULT_PACKAGE_DOMAIN)
    version = sanitize_version(config.version or detect_version(entry_path) or DEFAULT_VERSION)
    uses_kivy = detect_kivy_project(app_dir)
    imported_requirements, imported_sources = collect_project_requirement_candidates(app_dir)
    requirements = sanitize_requirements(
        config.requirements,
        uses_kivy=uses_kivy,
        detected_requirements=imported_requirements,
    )
    orientation = sanitize_orientation(config.orientation)
    permissions = sanitize_permissions(config.permissions)
    min_sdk, target_sdk = sanitize_android_api_levels(config.min_sdk, config.target_sdk)
    build_mode = sanitize_build_mode(config.build_mode)
    buildozer_cmd = resolve_buildozer_command(config.buildozer_path)
    env_hints = collect_environment_hints(source_dir, buildozer_cmd)
    compatibility_hints = collect_compatibility_hints(
        raw_requirements=config.requirements,
        effective_requirements=requirements,
        app_dir=app_dir,
        imported_requirements=imported_requirements,
        imported_sources=imported_sources,
    )
    icon_file = resolve_optional_asset(config.icon_path, source_dir, app_dir, ICON_CANDIDATES)
    presplash_file = resolve_optional_asset(config.presplash_path, source_dir, app_dir, PRESPLASH_CANDIDATES)

    spec_text = render_buildozer_spec(
        app_name=app_name,
        package_name=package_name,
        package_domain=package_domain,
        version=version,
        requirements=requirements,
        orientation=orientation,
        permissions=permissions,
        min_sdk=min_sdk,
        target_sdk=target_sdk,
        icon_file=icon_file,
        presplash_file=presplash_file,
    )
    write_text(project_dir / "buildozer.spec", spec_text)
    write_text(project_dir / ".gitignore", render_gitignore())
    write_text(
        project_dir / "README.md",
        render_readme(
            app_name,
            package_domain,
            package_name,
            uses_kivy,
            icon_file,
            presplash_file,
            permissions,
            min_sdk,
            target_sdk,
            compatibility_hints,
            imported_requirements,
            imported_sources,
        ),
    )

    artifact_dir = str((project_dir / "bin").resolve())
    buildozer_spec_path = str((project_dir / "buildozer.spec").resolve())
    log_lines = [
        "Python Android packaging project generated successfully.",
        f"Entry File: {entry_path}",
        f"Stage Directory: {project_dir}",
        f"App Title: {app_name}",
        f"Package: {package_domain}.{package_name}",
        f"Version: {version}",
        f"Requirements: {requirements}",
        f"Kivy Detected: {'yes' if uses_kivy else 'no'}",
        f"Auto-imported Requirement Sources: {', '.join(imported_sources) if imported_sources else 'none'}",
        f"Auto-imported Project Requirements: {', '.join(imported_requirements) if imported_requirements else 'none'}",
        f"Orientation: {orientation}",
        f"Permissions: {permissions}",
        f"Min SDK: {min_sdk}",
        f"Target SDK: {target_sdk}",
        f"Icon: {icon_file or 'not set'}",
        f"Presplash: {presplash_file or 'not set'}",
        f"Build Mode: {build_mode}",
        f"Buildozer Command: {buildozer_cmd}",
        f"Buildozer Spec: {buildozer_spec_path}",
        f"Expected Output Folder: {artifact_dir}",
        "",
        "Notes:",
        "- Buildozer writes Android packages to the bin/ directory.",
        "- source.dir in buildozer.spec must contain main.py, so Compass stages your app under app/ and generates a wrapper main.py when needed.",
        "- When the requirements field is blank, Compass first tries a lightweight import from requirements.txt, pyproject.toml, or setup.py before falling back to python3 / python3,kivy.",
        "- When Kivy imports are detected and no custom requirements are supplied, Compass keeps kivy in the final requirement list.",
        "- Use the permissions field for manifest permissions such as INTERNET, CAMERA, RECORD_AUDIO, or WRITE_EXTERNAL_STORAGE.",
        "- Some dependencies still require python-for-android recipes or pure-Python packages that p4a can consume.",
    ]
    if env_hints:
        log_lines.extend(["", "Environment Hints:", *env_hints])
    if compatibility_hints:
        log_lines.extend(["", "Compatibility Hints:", *compatibility_hints])
    return {
        "project_dir": str(project_dir),
        "buildozer_spec": buildozer_spec_path,
        "log_text": "\n".join(log_lines),
        "cmd": [buildozer_cmd, "-v", "android", build_mode],
        "cwd": str(project_dir),
        "artifact_dir": artifact_dir,
        "build_mode": build_mode,
    }


def collect_compatibility_hints(
    raw_requirements: str,
    effective_requirements: str,
    app_dir: Path,
    imported_requirements: list[str],
    imported_sources: list[str],
) -> list[str]:
    hints: list[str] = []
    raw_items = [item.strip() for item in (raw_requirements or "").split(",") if item.strip()]
    effective_items = [item.strip() for item in (effective_requirements or "").split(",") if item.strip()]

    metadata_files = [name for name in PROJECT_METADATA_FILES if (app_dir / name).exists()]
    if imported_sources and not raw_items:
        hints.append(
            "Android requirements were auto-imported from " + ", ".join(imported_sources) + ". Compass uses lightweight parsing for these files, so review the generated requirement list before building."
        )
    elif metadata_files and not raw_items:
        hints.append(
            "Project metadata files were detected (" + ", ".join(metadata_files) + ") but no Android-friendly requirements could be auto-imported. Review dependencies manually."
        )

    if any("://" in item or item.startswith("git+") or item.endswith(".whl") or " @ " in item for item in raw_items):
        hints.append(
            "Direct URL, wheel, or VCS-style requirement entries were detected. Buildozer's requirements field is most reliable with recipe names or standard pure-Python package names, so these entries may need manual python-for-android work."
        )

    if any(any(op in item for op in (">=", "<=", "!=", "~=", ">", "<")) for item in raw_items):
        hints.append(
            "Version ranges were detected in the Android requirements. Exact pins are usually safer for python-for-android/Buildozer than open-ended constraints."
        )

    native_files = detect_native_source_files(app_dir)
    if native_files:
        hints.append(
            "Compiled/native source files were detected (for example: " + ", ".join(native_files[:3]) + "). Native extensions generally need compatible python-for-android recipes or custom packaging work."
        )

    lowered_effective = {item.lower() for item in effective_items}
    if lowered_effective & NATIVE_REQUIREMENT_HINTS:
        hints.append(
            "Requirements associated with native build steps were detected (for example cython/cffi/rust tooling). Double-check that your Android dependency chain is supported by python-for-android before expecting a one-click build."
        )

    if imported_requirements and raw_items:
        hints.append(
            "Project metadata also contained importable dependencies (" + ", ".join(imported_requirements[:5]) + "), but explicit Android requirements take precedence over auto-imported ones."
        )

    return hints


def detect_project_requirements_for_android(project_root: str | Path) -> str:
    items, _ = collect_project_requirement_candidates(Path(project_root))
    return ",".join(items)


def collect_project_requirement_candidates(app_dir: Path) -> tuple[list[str], list[str]]:
    collected: list[str] = []
    sources: list[str] = []

    parsers = [
        ("requirements.txt", parse_requirements_txt),
        ("pyproject.toml", parse_pyproject_dependencies),
        ("setup.py", parse_setup_py_install_requires),
    ]
    for filename, parser in parsers:
        path = app_dir / filename
        if not path.exists() or not path.is_file():
            continue
        items = parser(path)
        if items:
            collected.extend(items)
            sources.append(filename)

    normalized = []
    seen = set()
    for item in collected:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(item)
    return normalized, sources


def parse_requirements_txt(path: Path) -> list[str]:
    items: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return items

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "--requirement", "-c", "--constraint", "-e", "--editable", "--find-links", "-f", "--extra-index-url", "--index-url")):
            continue
        name = extract_requirement_name(line)
        if name:
            items.append(name)
    return items


def parse_pyproject_dependencies(path: Path) -> list[str]:
    if tomllib is None:
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, tomllib.TOMLDecodeError):
        return []

    items: list[str] = []
    project_section = data.get("project") or {}
    for raw_dep in project_section.get("dependencies") or []:
        name = extract_requirement_name(str(raw_dep))
        if name:
            items.append(name)

    poetry_deps = (((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {})
    for key, value in poetry_deps.items():
        if str(key).lower() == "python":
            continue
        name = extract_requirement_name(str(key))
        if name:
            items.append(name)
    return items


def parse_setup_py_install_requires(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    items: list[str] = []
    match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, flags=re.S)
    if not match:
        return items

    for raw_item in re.findall(r"[\"']([^\"']+)[\"']", match.group(1)):
        name = extract_requirement_name(raw_item)
        if name:
            items.append(name)
    return items


def extract_requirement_name(raw_spec: str) -> str:
    spec = (raw_spec or "").strip()
    if not spec:
        return ""
    if spec.startswith((".", "/")):
        return ""

    name = spec.split(";", 1)[0].strip()
    if name.startswith(("git+", "http://", "https://")):
        egg_match = re.search(r"[#&]egg=([A-Za-z0-9_.-]+)", name)
        if egg_match:
            name = egg_match.group(1)
        else:
            return ""

    if " @ " in name:
        name = name.split(" @ ", 1)[0].strip()
    name = name.split("[", 1)[0].strip()
    split_match = re.split(r"\s*(?:==|>=|<=|~=|!=|>|<)\s*", name, maxsplit=1)
    name = split_match[0].strip()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return ""
    lowered = name.lower()
    if lowered in {"python", "pip", "setuptools", "wheel", "buildozer"}:
        return ""
    return name


def detect_native_source_files(app_dir: Path) -> list[str]:
    matches: list[str] = []
    for path in app_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in NATIVE_SOURCE_EXTENSIONS:
            matches.append(path.relative_to(app_dir).as_posix())
            if len(matches) >= 10:
                break
    return matches


def collect_environment_hints(source_dir: Path, buildozer_cmd: str) -> list[str]:
    hints: list[str] = []

    if is_probably_wsl() and is_windows_mount_path(source_dir):
        hints.append(
            "WSL detected and the project appears to be under /mnt/... . Buildozer builds are usually faster and more reliable when the project is copied into the Linux filesystem (for example under ~/projects)."
        )

    if not os.environ.get("JAVA_HOME", "").strip() and shutil.which("java") is None:
        hints.append(
            "JAVA_HOME and the java command were not detected. Buildozer's Android setup expects a working OpenJDK install (Buildozer's current Ubuntu instructions use OpenJDK 17, with 11 documented as the minimum fallback on older docs)."
        )

    if shutil.which("adb") is None:
        hints.append(
            "adb was not found in PATH. Builds can still succeed, but deploy/run/logcat workflows are easier once Android platform-tools are installed."
        )

    if shutil.which("sdkmanager") is None:
        hints.append(
            "sdkmanager was not found in PATH. The first Buildozer run may download SDK/NDK components itself and prompt for Android license acceptance."
        )

    hints.append(f"Build command: {buildozer_cmd} -v android debug/release")
    return hints


def is_probably_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        version_text = Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in version_text or "wsl" in version_text


def is_windows_mount_path(path: Path) -> bool:
    parts = path.resolve().parts
    return len(parts) >= 2 and parts[0] == "/" and parts[1] == "mnt"


def find_built_artifacts(artifact_dir: str) -> list[str]:
    root = Path(artifact_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    found: list[Path] = []
    for pattern in ARTIFACT_PATTERNS:
        found.extend(root.glob(pattern))
    found = sorted((path for path in found if path.is_file()), key=lambda item: item.stat().st_mtime, reverse=True)
    return [str(path) for path in found]


def resolve_stage_dir(source_dir: Path) -> Path:
    return (source_dir.parent / f"{source_dir.name}-android-buildozer").resolve()


def resolve_buildozer_command(custom_path: str) -> str:
    candidates = []
    if custom_path and custom_path.strip():
        candidates.append(Path(custom_path).expanduser().resolve())
    else:
        for cmd_name in ("buildozer",):
            path = shutil.which(cmd_name)
            if path:
                candidates.append(Path(path))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("Buildozer not found. Install Buildozer or select the buildozer executable first.")


def copy_source_tree(source_dir: Path, app_dir: Path) -> None:
    ignore = shutil.ignore_patterns(*IGNORED_DIRS)
    shutil.copytree(source_dir, app_dir, dirs_exist_ok=True, ignore=ignore)


def ensure_android_main(app_dir: Path, entry_relative: Path) -> None:
    staged_entry = app_dir / entry_relative
    if not staged_entry.exists():
        raise FileNotFoundError(f"Staged entry file is missing: {staged_entry}")

    main_path = app_dir / "main.py"
    if entry_relative.as_posix() == "main.py":
        return

    wrapper_target = entry_relative.as_posix()
    wrapper = textwrap.dedent(
        f"""
        # Generated by Compass to satisfy Buildozer's source.dir/main.py requirement.
        from __future__ import annotations

        import runpy
        from pathlib import Path

        TARGET = Path(__file__).resolve().parent / {wrapper_target!r}

        if __name__ == "__main__":
            runpy.run_path(str(TARGET), run_name="__main__")
        else:
            runpy.run_path(str(TARGET), run_name=__name__)
        """
    )
    write_text(main_path, wrapper)


def detect_version(entry_path: Path) -> str:
    try:
        content = entry_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1).strip() if match else ""


def detect_kivy_project(app_dir: Path) -> bool:
    for path in app_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".kv":
            return True
        if path.suffix.lower() != ".py":
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"(^|\n)\s*(from\s+kivy\b|import\s+kivy\b)", content):
            return True
    return False


def detect_asset_file(app_dir: Path, candidates: tuple[str, ...]) -> str:
    for raw_candidate in candidates:
        candidate = app_dir / raw_candidate
        if candidate.is_file():
            return candidate.relative_to(app_dir).as_posix()
    return ""


def find_candidate_asset(source_dir: Path, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        candidate_path = source_dir / candidate
        if candidate_path.exists() and candidate_path.is_file():
            return candidate.replace("\\", "/")
    return ""


def resolve_optional_asset(raw_path: str, source_dir: Path, app_dir: Path, auto_candidates: tuple[str, ...]) -> str:
    if raw_path and raw_path.strip():
        source_candidate = Path(raw_path).expanduser()
        if not source_candidate.is_absolute():
            source_candidate = (source_dir / source_candidate).resolve()
        else:
            source_candidate = source_candidate.resolve()

        try:
            relative_to_source = source_candidate.relative_to(source_dir)
        except ValueError as exc:
            raise ValueError("Optional icon/presplash file must be inside the selected source folder.") from exc

        staged_candidate = app_dir / relative_to_source
        if not staged_candidate.is_file():
            raise ValueError(f"Referenced asset file was not found after staging: {relative_to_source.as_posix()}")
        return relative_to_source.as_posix()

    return detect_asset_file(app_dir, auto_candidates)


def sanitize_app_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Compass Python Android"


def sanitize_package_name(package_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "", package_name.lower())
    if not cleaned:
        cleaned = "compasspythonapp"
    if cleaned[0].isdigit():
        cleaned = f"app{cleaned}"
    return cleaned


def sanitize_package_domain(package_domain: str) -> str:
    parts = []
    for raw_part in (package_domain or DEFAULT_PACKAGE_DOMAIN).strip().lower().split('.'):
        part = re.sub(r"[^a-z0-9]+", "", raw_part)
        if not part:
            continue
        if part[0].isdigit():
            part = f"org{part}"
        parts.append(part)
    return ".".join(parts) or DEFAULT_PACKAGE_DOMAIN


def sanitize_version(version: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", ".", (version or DEFAULT_VERSION).strip()).strip(".")
    return cleaned or DEFAULT_VERSION


def sanitize_requirements(requirements: str, uses_kivy: bool = False, detected_requirements: list[str] | None = None) -> str:
    raw_items = [item.strip() for item in (requirements or '').split(',') if item.strip()]
    auto_items = [item.strip() for item in (detected_requirements or []) if item.strip()] if not raw_items else []
    defaults = list(KIVY_REQUIREMENTS if uses_kivy else (DEFAULT_REQUIREMENTS,))
    items = []
    seen = set()
    for item in [*defaults, *auto_items, *raw_items]:
        lowered = item.lower()
        if lowered not in seen:
            seen.add(lowered)
            items.append(item)
    return ','.join(items)


def sanitize_orientation(orientation: str) -> str:
    value = (orientation or 'portrait').strip().lower()
    return value if value in ALLOWED_ORIENTATIONS else 'portrait'


def sanitize_permissions(permissions: str) -> str:
    raw_items = [item.strip() for item in re.split(r"[,;\n]+", permissions or "") if item.strip()]
    items = []
    seen = set()
    for item in raw_items or ["INTERNET"]:
        normalized = item.replace(" ", "")
        dedupe_key = normalized.upper()
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            items.append(normalized)
    return ",".join(items)


def sanitize_android_api_levels(min_sdk: int, target_sdk: int) -> tuple[int, int]:
    min_value = max(21, int(min_sdk or 24))
    target_value = max(min_value, int(target_sdk or 35))
    return min_value, target_value


def sanitize_build_mode(build_mode: str) -> str:
    value = (build_mode or 'debug').strip().lower()
    return value if value in ALLOWED_BUILD_MODES else 'debug'


def render_buildozer_spec(
    app_name: str,
    package_name: str,
    package_domain: str,
    version: str,
    requirements: str,
    orientation: str,
    permissions: str,
    min_sdk: int,
    target_sdk: int,
    icon_file: str,
    presplash_file: str,
) -> str:
    optional_lines = []
    if presplash_file:
        optional_lines.append(f"presplash.filename = app/{presplash_file}")
    if icon_file:
        optional_lines.append(f"icon.filename = app/{icon_file}")
    optional_block = "\n".join(optional_lines)
    if optional_block:
        optional_block += "\n"

    return textwrap.dedent(
        f"""
        [app]

        # Generated by Compass: Python Android Buildozer spec
        title = {app_name}
        package.name = {package_name}
        package.domain = {package_domain}

        source.dir = app
        source.include_exts = {DEFAULT_INCLUDE_EXTS}
        source.exclude_dirs = tests,bin,build,dist,.git,__pycache__,.pytest_cache,.mypy_cache,.venv,venv

        version = {version}
        requirements = {requirements}
        {optional_block}orientation = {orientation}
        fullscreen = 0

        android.api = {target_sdk}
        android.minapi = {min_sdk}
        android.accept_sdk_license = True
        android.permissions = {permissions}
        android.archs = arm64-v8a, armeabi-v7a

        [buildozer]
        log_level = 2
        warn_on_root = 1
        """
    )


def render_gitignore() -> str:
    return textwrap.dedent(
        """
        .buildozer/
        bin/
        *.apk
        *.aab
        """
    )


def render_readme(
    app_name: str,
    package_domain: str,
    package_name: str,
    uses_kivy: bool,
    icon_file: str,
    presplash_file: str,
    permissions: str,
    min_sdk: int,
    target_sdk: int,
    compatibility_hints: list[str],
    imported_requirements: list[str],
    imported_sources: list[str],
) -> str:
    extras = []
    extras.append(f"- Kivy auto-detected: {'yes' if uses_kivy else 'no'}")
    extras.append(f"- Permissions: `{permissions}`")
    extras.append(f"- Android API / min API: `{target_sdk}` / `{min_sdk}`")
    if icon_file:
        extras.append(f"- Auto-detected or selected icon: `app/{icon_file}`")
    if presplash_file:
        extras.append(f"- Auto-detected or selected presplash: `app/{presplash_file}`")
    if imported_requirements:
        extras.append(f"- Auto-imported Android requirements: `{','.join(imported_requirements)}`")
    if imported_sources:
        extras.append(f"- Requirement sources used for auto-import: `{', '.join(imported_sources)}`")
    extras_text = "\n".join(extras)
    compatibility_text = ""
    if compatibility_hints:
        bullet_lines = "\n".join(f"- {item}" for item in compatibility_hints)
        compatibility_text = f"\n## Compatibility Hints\n{bullet_lines}\n"
    return textwrap.dedent(
        f"""
        # {app_name}

        This folder was generated by Compass for Python -> Android packaging through Buildozer/python-for-android.

        ## Identifier
        - Android package id: `{package_domain}.{package_name}`
        {extras_text}

        ## Files
        - `buildozer.spec`: generated Buildozer configuration
        - `app/`: staged application sources copied from your project
        - `app/main.py`: wrapper entry generated only when your selected entry is not already named `main.py`

        ## Build
        1. Open a Linux or macOS shell (or WSL on Windows).
        2. Install Buildozer and its platform dependencies.
        3. Run `buildozer -v android debug` for a debug APK, or `buildozer -v android release` for a release build.
        4. Check the `bin/` folder for the generated APK/AAB.
        {compatibility_text}
        """
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.strip() + "\n"
    path.write_text(normalized, encoding="utf-8")
