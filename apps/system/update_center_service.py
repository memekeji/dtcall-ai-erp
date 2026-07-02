# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings

logger = logging.getLogger("django")

BASE_DIR = Path(settings.BASE_DIR)
DEFAULT_UPDATE_CENTER = os.environ.get("DTCALL_UPDATE_CENTER_BASE_URL", "https://www.dtcall.cn")
DEFAULT_UPDATE_CHANNEL = os.environ.get("DTCALL_UPDATE_CHANNEL", "stable")
DEFAULT_UPDATE_PLATFORM = os.environ.get("DTCALL_UPDATE_PLATFORM", "linux-docker-x64")
DEFAULT_DEPLOY_ROOT = Path(os.environ.get("DTCALL_DEPLOY_ROOT", "/opt/dtcall"))
DEFAULT_HEALTHCHECK_URL = os.environ.get("DTCALL_UPDATE_HEALTHCHECK_URL", "http://127.0.0.1:8000/system/version/health/")
DEFAULT_HEALTHCHECK_TIMEOUT = int(os.environ.get("DTCALL_UPDATE_HEALTHCHECK_TIMEOUT", "60"))


def get_current_version() -> str:
    version_file = BASE_DIR / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0"


def get_current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def normalize_version(value: str) -> str:
    return str(value or "").strip().lower().lstrip("v")


def version_parts(value: str) -> list[int]:
    normalized = normalize_version(value)
    result: list[int] = []
    for part in normalized.split("."):
        if not part:
            result.append(0)
            continue
        digits = []
        for ch in part:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        result.append(int("".join(digits) or "0"))
    return result


def compare_versions(a: str, b: str) -> int:
    ap = version_parts(a)
    bp = version_parts(b)
    max_len = max(len(ap), len(bp))
    for idx in range(max_len):
        av = ap[idx] if idx < len(ap) else 0
        bv = bp[idx] if idx < len(bp) else 0
        if av > bv:
            return 1
        if av < bv:
            return -1
    return 0


def update_center_latest_url(
    version: Optional[str] = None,
    channel: Optional[str] = None,
    platform: Optional[str] = None,
    release_version: Optional[str] = None,
) -> str:
    query = {
        "channel": channel or DEFAULT_UPDATE_CHANNEL,
        "platform": platform or DEFAULT_UPDATE_PLATFORM,
    }
    if version:
        query["version"] = version
    if release_version:
        query["releaseVersion"] = release_version
    return f"{DEFAULT_UPDATE_CENTER.rstrip('/')}/api/public/updates/latest?{urlencode(query)}"


def fetch_latest_release_info(
    version: Optional[str] = None,
    channel: Optional[str] = None,
    platform: Optional[str] = None,
    release_version: Optional[str] = None,
    timeout: int = 20,
) -> dict[str, Any]:
    url = update_center_latest_url(
        version=version,
        channel=channel,
        platform=platform,
        release_version=release_version,
    )
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("更新中心返回的数据格式无效")
    return data


def fetch_release_info_for_target(
    target_version: str,
    channel: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    data = fetch_latest_release_info(
        version=get_current_version(),
        channel=channel,
        platform=platform,
        release_version=target_version,
    )
    release = data.get("release") or {}
    release_version = release.get("version") or data.get("latestVersion")
    if normalize_version(release_version) != normalize_version(target_version):
        raise ValueError(f"更新中心未返回目标版本 {target_version} 的发布包")
    return data


def check_for_updates() -> dict[str, Any]:
    current_version = get_current_version()
    current_commit = get_current_commit()
    result: dict[str, Any] = {
        "current_version": current_version,
        "current_commit": current_commit,
        "latest_version": None,
        "update_available": False,
        "changelog": [],
        "checked_at": datetime.now().isoformat(),
        "source": "official_update_center",
        "release": None,
    }
    try:
        data = fetch_latest_release_info(version=current_version)
        release = data.get("release") or {}
        latest_version = data.get("latestVersion") or release.get("version")
        changelog = data.get("highlights") or []
        update_available = bool(data.get("updateAvailable"))
        result.update(
            {
                "latest_version": latest_version,
                "update_available": update_available,
                "changelog": changelog if isinstance(changelog, list) else [],
                "checked_at": datetime.now().isoformat(),
                "release": release,
                "release_notes": data.get("releaseNotes") or release.get("releaseNotesMarkdown") or "",
                "channel": data.get("channel") or release.get("channel") or DEFAULT_UPDATE_CHANNEL,
                "platform": data.get("platform") or release.get("platform") or DEFAULT_UPDATE_PLATFORM,
            }
        )
    except Exception as exc:
        logger.warning("update center check failed: %s", exc)
        result["error"] = str(exc)
    return result


def backup_database() -> dict[str, Any]:
    db_settings = settings.DATABASES.get("default", {})
    engine = db_settings.get("ENGINE", "")
    backup_dir = BASE_DIR / "backups" / "pre_update"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = get_current_version()

    if "postgresql" in engine or "postgis" in engine:
        filepath = backup_dir / f"pre_update_backup_{version}_{timestamp}.dump"
        env = os.environ.copy()
        env["PGPASSWORD"] = db_settings.get("PASSWORD", "")
        try:
            result = subprocess.run(
                [
                    "pg_dump",
                    "-h",
                    db_settings.get("HOST", "localhost"),
                    "-p",
                    str(db_settings.get("PORT", 5432)),
                    "-U",
                    db_settings.get("USER", "postgres"),
                    "-d",
                    db_settings.get("NAME", "dtcall"),
                    "-F",
                    "c",
                    "-f",
                    str(filepath),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
            if result.returncode == 0:
                return {"success": True, "file": str(filepath), "size_bytes": filepath.stat().st_size}
            return {"success": False, "error": result.stderr.strip()}
        except FileNotFoundError:
            return {"success": False, "error": "pg_dump not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    if "sqlite" in engine:
        db_path = Path(db_settings.get("NAME", BASE_DIR / "db.sqlite3"))
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path
        filepath = backup_dir / f"pre_update_backup_{version}_{timestamp}.sqlite3"
        if not db_path.exists():
            return {"success": False, "error": f"DB not found: {db_path}"}
        shutil.copy2(str(db_path), str(filepath))
        return {"success": True, "file": str(filepath), "size_bytes": filepath.stat().st_size}

    return {"success": False, "error": f"Unsupported engine: {engine}"}


def updater_runtime_root() -> Path:
    path = BASE_DIR / "runtime" / "updater"
    path.mkdir(parents=True, exist_ok=True)
    return path


def downloads_root() -> Path:
    path = updater_runtime_root() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_root() -> Path:
    path = updater_runtime_root() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_package(file_name: str, content) -> dict[str, Any]:
    safe_name = Path(file_name or "").name or f"dtcall-release-upload-{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    target = uploads_root() / safe_name
    with target.open("wb") as handle:
        for chunk in content.chunks():
            handle.write(chunk)
    return {"success": True, "file": str(target), "size_bytes": target.stat().st_size}


def staging_root() -> Path:
    path = updater_runtime_root() / "staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def update_state_path() -> Path:
    return updater_runtime_root() / "update_state.json"


def save_update_state(data: dict[str, Any]) -> None:
    update_state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_update_state() -> Optional[dict[str, Any]]:
    path = update_state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_release_package(release: dict[str, Any]) -> dict[str, Any]:
    package_url = str(release.get("packageUrl") or "").strip()
    if not package_url:
        return {"success": False, "error": "发布版本未配置更新包地址"}
    filename = package_url.rstrip("/").split("/")[-1] or f"dtcall-release-{release.get('version', 'unknown')}.zip"
    target = downloads_root() / filename
    try:
        with requests.get(package_url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
    except Exception as exc:
        return {"success": False, "error": f"下载更新包失败: {exc}"}
    return {"success": True, "file": str(target), "size_bytes": target.stat().st_size}


def verify_release_package(package_path: str | Path, expected_checksum: Optional[str] = None) -> dict[str, Any]:
    path = Path(package_path)
    if not path.exists():
        return {"success": False, "error": f"更新包不存在: {path}"}
    actual = sha256_of_file(path)
    if expected_checksum:
        normalized = str(expected_checksum).strip().lower().replace("sha256:", "")
        if normalized and actual.lower() != normalized:
            return {
                "success": False,
                "error": "更新包校验失败",
                "expected": normalized,
                "actual": actual,
            }
    return {"success": True, "checksum": actual, "file": str(path), "size_bytes": path.stat().st_size}


def extract_release_package(package_path: str | Path) -> dict[str, Any]:
    path = Path(package_path)
    if not path.exists():
        return {"success": False, "error": f"更新包不存在: {path}"}
    target = staging_root() / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            archive.extractall(target)
    except Exception as exc:
        return {"success": False, "error": f"解压更新包失败: {exc}"}
    return {"success": True, "staging_dir": str(target)}


def read_manifest(staging_dir: str | Path) -> dict[str, Any]:
    path = Path(staging_dir) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest.json not found in {staging_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def deploy_root() -> Path:
    return DEFAULT_DEPLOY_ROOT


def ensure_deploy_layout(root: Optional[Path] = None) -> dict[str, str]:
    base = root or deploy_root()
    shared = base / "shared"
    releases = base / "releases"
    downloads = base / "downloads"
    for path in [base, shared, releases, downloads, shared / "env", shared / "media", shared / "backups", shared / "runtime"]:
        path.mkdir(parents=True, exist_ok=True)
    return {
        "base": str(base),
        "shared": str(shared),
        "releases": str(releases),
        "downloads": str(downloads),
        "current": str(base / "current"),
    }


def release_dir(version: str, root: Optional[Path] = None) -> Path:
    layout = ensure_deploy_layout(root=root)
    return Path(layout["releases"]) / normalize_version(version)


def current_release_target(root: Optional[Path] = None) -> Optional[str]:
    base = root or deploy_root()
    current = base / "current"
    if not current.exists():
        return None
    try:
        return str(current.resolve())
    except Exception:
        return None


def stage_release_to_version_dir(staging_dir: str | Path, version: str, root: Optional[Path] = None) -> dict[str, Any]:
    target_dir = release_dir(version, root=root)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(str(staging_dir), str(target_dir))
    return {"success": True, "release_dir": str(target_dir)}


def switch_current_release(version: str, root: Optional[Path] = None) -> dict[str, Any]:
    base = root or deploy_root()
    target_dir = release_dir(version, root=root)
    current = base / "current"
    if not target_dir.exists():
        return {"success": False, "error": f"版本目录不存在: {target_dir}"}
    if current.exists() or current.is_symlink():
        current.unlink()
    current.symlink_to(target_dir, target_is_directory=True)
    return {"success": True, "current": str(current), "target": str(target_dir)}


def import_docker_images(staging_dir: str | Path) -> dict[str, Any]:
    images_dir = Path(staging_dir) / "images"
    if not images_dir.exists():
        return {"success": True, "imported": []}
    imported: list[str] = []
    for image_file in sorted(images_dir.glob("*.tar")):
        result = subprocess.run(
            ["docker", "load", "-i", str(image_file)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            return {"success": False, "error": f"导入 Docker 镜像失败: {image_file.name} - {result.stderr.strip()}"}
        imported.append(image_file.name)
    return {"success": True, "imported": imported}


def compose_file_for_release(version: str, root: Optional[Path] = None) -> Path:
    return release_dir(version, root=root) / "compose" / "docker-compose.yml"


def compose_file_for_target(target_dir: str | Path) -> Path:
    return Path(target_dir) / "compose" / "docker-compose.yml"


def run_compose_up(version: Optional[str] = None, root: Optional[Path] = None, target_dir: Optional[str | Path] = None) -> dict[str, Any]:
    if target_dir is not None:
        compose_file = compose_file_for_target(target_dir)
    elif version is not None:
        compose_file = compose_file_for_release(version, root=root)
    else:
        return {"success": False, "error": "缺少版本号或目标目录，无法启动 Docker Compose"}
    if not compose_file.exists():
        return {"success": False, "error": f"docker-compose.yml 不存在: {compose_file}"}

    commands = [
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
    ]
    last_error = None
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if result.returncode == 0:
                return {"success": True, "command": " ".join(cmd), "stdout": result.stdout}
            last_error = result.stderr.strip() or result.stdout.strip()
        except FileNotFoundError:
            last_error = f"command not found: {cmd[0]}"
        except Exception as exc:
            last_error = str(exc)
    return {"success": False, "error": last_error or "启动 Docker Compose 失败"}


def run_healthcheck(
    url: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    interval_seconds: int = 3,
) -> dict[str, Any]:
    health_url = url or DEFAULT_HEALTHCHECK_URL
    timeout_limit = timeout_seconds or DEFAULT_HEALTHCHECK_TIMEOUT
    started_at = datetime.now()
    last_error = None
    while (datetime.now() - started_at).total_seconds() < timeout_limit:
        try:
            response = requests.get(health_url, timeout=8)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.ok and payload.get("status") in {"healthy", "degraded"}:
                return {"success": True, "url": health_url, "payload": payload}
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:
            last_error = str(exc)
        import time
        time.sleep(interval_seconds)
    return {"success": False, "error": last_error or "healthcheck timeout", "url": health_url}


def rollback_current_symlink(previous_target: str) -> dict[str, Any]:
    current = deploy_root() / "current"
    target_path = Path(previous_target)
    if not target_path.exists():
        return {"success": False, "error": f"previous target missing: {previous_target}"}
    if current.exists() or current.is_symlink():
        current.unlink()
    current.symlink_to(target_path, target_is_directory=True)
    return {"success": True, "current": str(current), "target": previous_target}


def get_rollback_info() -> Optional[dict[str, Any]]:
    return load_update_state()


def perform_online_update(target_version: Optional[str] = None) -> dict[str, Any]:
    info = check_for_updates()
    release = info.get("release") or {}
    if target_version:
        target_data = fetch_release_info_for_target(target_version)
        release = target_data.get("release") or release
        latest_version = target_version
    else:
        latest_version = info.get("latest_version") or release.get("version")
    if not latest_version:
        return {"success": False, "error": "No target version available"}

    current_version = get_current_version()
    package_result = download_release_package(release)
    if not package_result.get("success"):
        return package_result

    verify_result = verify_release_package(package_result["file"], expected_checksum=release.get("checksum"))
    if not verify_result.get("success"):
        return verify_result

    extract_result = extract_release_package(package_result["file"])
    if not extract_result.get("success"):
        return extract_result

    return finalize_staged_release(
        staging_dir=extract_result["staging_dir"],
        version=latest_version,
        source="online",
        release_metadata=release,
        current_version=current_version,
    )


def validate_release_manifest(manifest: dict[str, Any], staging_dir: str | Path) -> dict[str, Any]:
    version = normalize_version(manifest.get("version"))
    if not version:
        return {"success": False, "error": "manifest 缺少 version"}
    compose_file = Path(staging_dir) / "compose" / "docker-compose.yml"
    if not compose_file.exists():
        return {"success": False, "error": "更新包缺少 compose/docker-compose.yml"}
    return {"success": True, "version": version, "compose_file": str(compose_file)}


def perform_offline_import(zip_path: str) -> dict[str, Any]:
    current_version = get_current_version()
    verify_result = verify_release_package(zip_path)
    if not verify_result.get("success"):
        return verify_result
    extract_result = extract_release_package(zip_path)
    if not extract_result.get("success"):
        return extract_result
    manifest = read_manifest(extract_result["staging_dir"])
    validation = validate_release_manifest(manifest, extract_result["staging_dir"])
    if not validation.get("success"):
        return validation
    version = validation.get("version") or "unknown"
    return finalize_staged_release(
        staging_dir=extract_result["staging_dir"],
        version=version,
        source="offline",
        release_metadata=manifest,
        current_version=current_version,
    )


def finalize_staged_release(
    staging_dir: str,
    version: str,
    source: str,
    release_metadata: Optional[dict[str, Any]] = None,
    current_version: Optional[str] = None,
) -> dict[str, Any]:
    current_version = current_version or get_current_version()
    layout = ensure_deploy_layout()
    previous_target = current_release_target()
    backup_result = backup_database()
    if not backup_result.get("success"):
        return backup_result

    try:
        manifest = read_manifest(staging_dir)
    except Exception as exc:
        return {"success": False, "error": f"读取 manifest 失败: {exc}"}
    validation = validate_release_manifest(manifest, staging_dir)
    if not validation.get("success"):
        return validation

    import_result = import_docker_images(staging_dir)
    if not import_result.get("success"):
        return import_result

    stage_result = stage_release_to_version_dir(staging_dir, version)
    if not stage_result.get("success"):
        return stage_result

    switch_result = switch_current_release(version)
    if not switch_result.get("success"):
        return switch_result

    compose_result = run_compose_up(version)
    if not compose_result.get("success"):
        if previous_target:
            rollback_current_symlink(previous_target)
            restore_result = run_compose_up(target_dir=previous_target)
            compose_result["rollback_restore"] = restore_result
        return compose_result

    health_result = run_healthcheck()
    if not health_result.get("success"):
        if previous_target:
            rollback_current_symlink(previous_target)
            restore_result = run_compose_up(target_dir=previous_target)
        else:
            restore_result = None
        return {
            "success": False,
            "error": f"健康检查失败: {health_result.get('error')}",
            "healthcheck": health_result,
            "rollback_restore": restore_result,
        }

    state = {
        "source": source,
        "previous_version": current_version,
        "previous_commit": get_current_commit(),
        "target_version": version,
        "previous_target": previous_target,
        "current_target": switch_result.get("target"),
        "deploy_root": layout["base"],
        "backup_file": backup_result.get("file"),
        "manifest": manifest,
        "release_metadata": release_metadata or {},
        "updated_at": datetime.now().isoformat(),
        "compose_result": compose_result,
        "health_result": health_result,
    }
    save_update_state(state)

    return {
        "success": True,
        "new_version": version,
        "previous_version": current_version,
        "release_dir": stage_result.get("release_dir"),
        "current_link": switch_result.get("current"),
        "backup_file": backup_result.get("file"),
        "imported_images": import_result.get("imported", []),
        "source": source,
        "compose_command": compose_result.get("command"),
        "healthcheck": health_result,
    }


def perform_rollback() -> dict[str, Any]:
    state = load_update_state()
    if not state:
        return {"success": False, "error": "No rollback state found"}
    previous_target = state.get("previous_target")
    previous_version = state.get("previous_version")
    current = deploy_root() / "current"
    if not previous_target:
        return {"success": False, "error": "Rollback state missing previous target"}
    if current.exists() or current.is_symlink():
        current.unlink()
    current.symlink_to(Path(previous_target), target_is_directory=True)
    compose_result = run_compose_up(target_dir=previous_target)
    if not compose_result.get("success"):
        return {"success": False, "error": compose_result.get("error"), "compose_result": compose_result}
    return {
        "success": True,
        "restored_version": previous_version,
        "restored_target": previous_target,
        "restored_commit": state.get("previous_commit"),
        "compose_result": compose_result,
    }


def get_system_health() -> dict[str, Any]:
    from django.db import connections

    db_ok = False
    try:
        connections["default"].cursor()
        db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": get_current_version(),
        "commit": get_current_commit(),
        "branch": get_current_branch(),
        "deploy_root": str(deploy_root()),
        "checked_at": datetime.now().isoformat(),
    }
