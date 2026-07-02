# -*- coding: utf-8 -*-
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), check=False, text=True)
    if result.returncode != 0:
        raise SystemExit(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def require_exists(path: Path, message: str) -> None:
    if not path.exists():
        raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DTCall Docker ZIP release package")
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.0.0")
    parser.add_argument("--build", required=True, help="Build identifier, e.g. 20260701.1")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--platform", default="linux-docker-x64")
    parser.add_argument("--output-dir", default=str(ROOT / "dist" / "releases"))
    parser.add_argument("--web-image", default=None, help="Existing web image tag, default dtcall-web:<version>")
    parser.add_argument("--orchestrator-image", default=None, help="Existing ai image tag, default dtcall-ai-orchestrator:<version>")
    parser.add_argument("--compose-file", default=str(ROOT / "docker-compose.yml"), help="Compose file to package")
    parser.add_argument("--env-example", default=str(ROOT / ".env.example"), help="Env example file to package")
    args = parser.parse_args()

    version = args.version.strip().lstrip("v")
    build = args.build.strip()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    web_image = args.web_image or f"dtcall-web:{version}"
    ai_image = args.orchestrator_image or f"dtcall-ai-orchestrator:{version}"
    compose_file = Path(args.compose_file)
    env_example = Path(args.env_example)

    package_name = f"dtcall-release-{version}-linux-x86_64"
    zip_path = output_dir / f"{package_name}.zip"

    with tempfile.TemporaryDirectory(prefix="dtcall_release_") as tmp:
        staging = Path(tmp) / package_name
        images_dir = staging / "images"
        compose_dir = staging / "compose"
        scripts_dir = staging / "scripts"
        app_dir = staging / "app"
        images_dir.mkdir(parents=True, exist_ok=True)
        compose_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)
        app_dir.mkdir(parents=True, exist_ok=True)

        web_tar = images_dir / f"dtcall-web-{version}.tar"
        ai_tar = images_dir / f"dtcall-ai-orchestrator-{version}.tar"

        run(["docker", "save", "-o", str(web_tar), web_image])
        run(["docker", "save", "-o", str(ai_tar), ai_image])

        require_exists(compose_file, f"Compose file not found: {compose_file}")
        require_exists(ROOT / "VERSION", f"VERSION file not found: {ROOT / 'VERSION'}")

        shutil.copy2(compose_file, compose_dir / "docker-compose.yml")
        copy_if_exists(env_example, compose_dir / ".env.example")
        copy_if_exists(ROOT / "VERSION", app_dir / "VERSION")
        copy_if_exists(ROOT / "scripts" / "release_install.sh", scripts_dir / "install.sh")
        copy_if_exists(ROOT / "scripts" / "release_update.sh", scripts_dir / "update.sh")
        copy_if_exists(ROOT / "scripts" / "release_rollback.sh", scripts_dir / "rollback.sh")

        release_notes = staging / "release-notes.md"
        release_notes.write_text(
            f"# DTCall {version}\n\n"
            f"- Release build: {build}\n"
            f"- Channel: {args.channel}\n"
            f"- Platform: {args.platform}\n"
            f"- Delivery: Docker offline ZIP package\n",
            encoding="utf-8",
        )

        manifest = {
            "version": version,
            "build": build,
            "channel": args.channel,
            "platform": args.platform,
            "package_file": zip_path.name,
            "package_size": 0,
            "package_sha256": "",
            "min_supported_version": "1.0.0",
            "force_update": False,
            "published_at": "",
            "release_notes": "release-notes.md",
            "deploy_root": "/opt/dtcall",
            "shared_dirs": [
                "shared/env",
                "shared/media",
                "shared/backups",
                "shared/runtime",
            ],
            "images": [
                {
                    "name": "dtcall-web",
                    "tag": web_image,
                    "file": str(web_tar.relative_to(staging)).replace("\\", "/"),
                    "sha256": sha256_of_file(web_tar),
                },
                {
                    "name": "dtcall-ai-orchestrator",
                    "tag": ai_image,
                    "file": str(ai_tar.relative_to(staging)).replace("\\", "/"),
                    "sha256": sha256_of_file(ai_tar),
                },
            ],
            "compose_files": [
                str((compose_dir / "docker-compose.yml").relative_to(staging)).replace("\\", "/"),
                str((compose_dir / ".env.example").relative_to(staging)).replace("\\", "/") if (compose_dir / ".env.example").exists() else "",
            ],
        }

        manifest_path = staging / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in staging.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(staging))

        package_sha256 = sha256_of_file(zip_path)
        package_size = zip_path.stat().st_size
        manifest["package_sha256"] = package_sha256
        manifest["package_size"] = package_size
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(manifest_path, "manifest.json")

        checksums = staging / "checksums.sha256"
        checksums.write_text(
            f"{sha256_of_file(web_tar)}  {web_tar.name}\n"
            f"{sha256_of_file(ai_tar)}  {ai_tar.name}\n"
            f"{package_sha256}  {zip_path.name}\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(checksums, "checksums.sha256")

    print(f"Created release package: {zip_path}")
    print(f"SHA256: {sha256_of_file(zip_path)}")


if __name__ == "__main__":
    main()
