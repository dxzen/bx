#!/bin/sh
# Install bx into the current project; Python uses only the standard library.
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'bx 安装失败：需要 Python 3.9+，请先安装 python3。' >&2
    exit 1
fi

exec python3 - "$@" <<'PY'
import sys

if sys.version_info < (3, 9):
    sys.exit("bx 安装失败：需要 Python 3.9+。")

import argparse
from datetime import datetime
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from urllib.error import URLError
from urllib.request import Request, urlopen


REPOSITORY = "https://github.com/dxzen/bx"
ARCHIVE_URL = REPOSITORY + "/archive/refs/heads/master.tar.gz"
SKILLS = ("bxf", "bxp")
REQUIRED = {
    "bxf": (
        "SKILL.md",
        "scripts/research.py",
        "scripts/model.py",
        "scripts/render_report.py",
        "references/research-plan.md",
        "references/calculation.md",
        "references/slides.md",
        "assets/report.html",
        "assets/example/brief.json",
        "assets/example/evidence.csv",
        "assets/example/model.json",
    ),
    "bxp": ("SKILL.md", "assets/prd.md"),
}
IGNORED = {"__pycache__", ".DS_Store"}


def ignored(path):
    return any(part in IGNORED for part in path.parts) or path.suffix in {".pyc", ".pyo"}


def download_source(work):
    archive = work / "bx.tar.gz"
    request = Request(ARCHIVE_URL, headers={"User-Agent": "bx-project-installer"})
    print("正在下载 {} 的 master 分支……".format(REPOSITORY), flush=True)
    with urlopen(request, timeout=30) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    source = work / "source"
    # Copy only skill resources, without extracting archive paths or symlinks.
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            parts = PurePosixPath(member.name).parts
            if len(parts) < 4 or parts[1:3] != (".agents", "skills") or parts[3] not in SKILLS:
                continue
            if ".." in parts or "\\" in member.name:
                raise ValueError("下载包含非法路径：{}".format(member.name))
            relative = Path(*parts[1:])
            if ignored(relative):
                continue
            destination = source / relative
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as input_file, destination.open("wb") as output:
                    shutil.copyfileobj(input_file, output)
            else:
                raise ValueError("下载包的技能资源必须为普通文件或目录：{}".format(member.name))
    return source


def validate_source(source):
    skill_root = source / ".agents" / "skills"
    if (source / ".agents").is_symlink() or skill_root.is_symlink():
        raise ValueError("源技能目录不能是符号链接。")
    for skill, required in REQUIRED.items():
        folder = skill_root / skill
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("源技能目录缺失或为符号链接：{}".format(folder))
        for path in folder.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise ValueError("源技能资源必须为普通文件或目录：{}".format(path))
        for name in required:
            if not (folder / name).is_file():
                raise ValueError("源技能资源不完整，缺少：{}".format(folder / name))
    return skill_root


def snapshot(folder):
    if not folder.is_dir() or folder.is_symlink():
        return None
    result = {}
    for path in folder.rglob("*"):
        relative = path.relative_to(folder)
        if ignored(relative):
            continue
        if path.is_symlink():
            return None
        if path.is_dir():
            result[relative] = None
        elif path.is_file():
            result[relative] = path.read_bytes()
        else:
            return None
    return result


def install(source, project, force):
    source_root = validate_source(source)
    agents = project / ".agents"
    target_root = agents / "skills"
    for path in (agents, target_root):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("安装位置必须是项目内的普通目录：{}".format(path))

    changes, existing = [], []
    for skill in SKILLS:
        target = target_root / skill
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError("同名目标不是普通目录，请先处理：{}".format(target))
        if target.exists() and snapshot(source_root / skill) == snapshot(target):
            print("{} 内容相同，跳过。".format(skill))
            continue
        changes.append(skill)
        if target.exists():
            existing.append(skill)

    if existing and not force:
        raise ValueError(
            "同名技能内容不同：{}。本次未安装任何技能；如需备份后更新，请加 --force。".format(", ".join(existing))
        )
    if not changes:
        print("bx 已安装，无需更改：{}".format(target_root))
        return

    backup_root = agents / "backups"
    if existing and (backup_root.is_symlink() or (backup_root.exists() and not backup_root.is_dir())):
        raise ValueError("备份位置必须是项目内的普通目录：{}".format(backup_root))

    target_root.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".bx-install-", dir=target_root) as staging:
        staging = Path(staging)
        for skill in changes:
            shutil.copytree(
                source_root / skill, staging / skill,
                ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc", "*.pyo"),
            )
        if existing:
            backup_root.mkdir(parents=True, exist_ok=True)
            prefix = "bx-{}-".format(datetime.now().strftime("%Y%m%d-%H%M%S"))
            backup = Path(tempfile.mkdtemp(prefix=prefix, dir=backup_root))

        saved, installed = [], []
        try:
            for skill in changes:
                target = target_root / skill
                if skill in existing:
                    target.rename(backup / skill)
                    saved.append(skill)
                (staging / skill).rename(target)
                installed.append(skill)
        except BaseException:
            for skill in reversed(installed):
                shutil.rmtree(target_root / skill)
            for skill in reversed(saved):
                (backup / skill).rename(target_root / skill)
            if backup is not None:
                backup.rmdir()
            raise

    print("已安装 {} 到 {}".format(", ".join(changes), target_root))
    if backup is not None:
        print("原有技能已备份到：{}".format(backup))
    print("在该项目中打开 Codex，使用 $bxf 或 $bxp；未显示时请重启 Codex。")


def main():
    parser = argparse.ArgumentParser(prog="install.sh", description="将 bx 技能安装到项目的 .agents/skills/ 中。")
    parser.add_argument("--project", default=".", metavar="DIR", help="目标项目目录，默认当前目录；目录须已存在")
    parser.add_argument("--source", metavar="DIR", help="从本地 bx 仓库根目录安装，跳过下载")
    parser.add_argument("--force", action="store_true", help="将内容不同的同名技能备份后替换")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        parser.error("目标项目目录不存在：{}".format(project))
    try:
        with tempfile.TemporaryDirectory(prefix="bx-download-") as work:
            source = Path(args.source).expanduser().resolve() if args.source else download_source(Path(work))
            install(source, project, args.force)
    except (OSError, URLError, ValueError, EOFError, tarfile.TarError) as error:
        parser.exit(1, "bx 安装失败：{}\n".format(error))
    except KeyboardInterrupt:
        parser.exit(130, "bx 安装已取消。\n")


if __name__ == "__main__":
    main()
PY
