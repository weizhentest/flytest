import io
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import yaml
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.auth import User
from app.db.models.projects import Project
from app.db.models.skills import Skill
from app.repositories.skills import SkillsRepository


REPO_ROOT = Path(__file__).resolve().parents[4]
DJANGO_MEDIA_ROOT = REPO_ROOT / "FlyTest_Django" / "media"


def _serialize_skill(skill: Skill) -> dict:
    script_path = None
    if skill.skill_path:
        root = DJANGO_MEDIA_ROOT / skill.skill_path
        if root.exists():
            for suffix in (".py", ".js"):
                candidates = list(root.rglob(f"*{suffix}"))
                if candidates:
                    try:
                        script_path = candidates[0].relative_to(DJANGO_MEDIA_ROOT).as_posix()
                    except Exception:
                        script_path = None
                    break

    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "skill_content": skill.skill_content,
        "skill_path": skill.skill_path,
        "script_path": script_path,
        "is_active": bool(skill.is_active),
        "project": skill.project_id,
        "project_name": skill.project.name if skill.project else "",
        "creator": skill.creator_id,
        "creator_name": skill.creator.username if skill.creator else "",
        "created_at": skill.created_at.isoformat() if skill.created_at else "",
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else "",
    }


def _serialize_skill_list_item(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "is_active": bool(skill.is_active),
        "creator_name": skill.creator.username if skill.creator else "",
        "created_at": skill.created_at.isoformat() if skill.created_at else "",
    }


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise AppError("妞ゅ湱娲版稉宥呯摠閸?", status_code=404)
    return project


def _get_creator(db: Session, creator_username: str) -> User:
    creator = db.query(User).filter(User.username == creator_username).first()
    if not creator:
        raise AppError("閸掓稑缂撴禍杞扮瑝鐎涙ê婀?", status_code=404)
    return creator


def _parse_skill_md(content: str) -> dict:
    if not content.startswith("---"):
        raise AppError("SKILL.md 蹇呴』浠?YAML frontmatter 寮€澶?(---)", status_code=400)

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise AppError("SKILL.md 鏍煎紡鏃犳晥锛岀己灏?YAML frontmatter 缁撴潫鏍囪", status_code=400)

    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise AppError(f"YAML frontmatter 瑙ｆ瀽澶辫触: {exc}", status_code=400)

    if not frontmatter or not isinstance(frontmatter, dict):
        raise AppError("YAML frontmatter 蹇呴』鏄璞?(mapping)", status_code=400)

    raw_name = frontmatter.get("name", "")
    raw_description = frontmatter.get("description", "")
    if not isinstance(raw_name, str) or not isinstance(raw_description, str):
        raise AppError("SKILL.md 鐨?name/description 蹇呴』鏄瓧绗︿覆", status_code=400)

    name = raw_name.strip()
    description = raw_description.strip()
    if not name:
        raise AppError("SKILL.md 缂哄皯 name 瀛楁", status_code=400)
    if not description:
        raise AppError("SKILL.md 缂哄皯 description 瀛楁", status_code=400)

    return {
        "name": name,
        "description": description,
        "body": parts[2].strip(),
    }


def _safe_extract_zip(
    zf: zipfile.ZipFile,
    dest_dir: str,
    *,
    max_files: int = 2000,
    max_total_size: int = 50 * 1024 * 1024,
) -> None:
    dest_path = Path(dest_dir).resolve(strict=False)
    file_count = 0
    total_size = 0

    for info in zf.infolist():
        name = (info.filename or "").replace("\\", "/")
        if not name or name.endswith("/"):
            continue

        file_count += 1
        if file_count > max_files:
            raise AppError("zip 鏂囦欢鍖呭惈杩囧鏂囦欢", status_code=400)

        total_size += int(getattr(info, "file_size", 0) or 0)
        if total_size > max_total_size:
            raise AppError("zip 瑙ｅ帇鍚庢€诲ぇ灏忚秴鍑洪檺鍒?", status_code=400)

        posix = PurePosixPath(name)
        if posix.is_absolute() or any(part == ".." for part in posix.parts):
            raise AppError("zip 鏂囦欢鍖呭惈闈炴硶璺緞", status_code=400)
        if posix.parts and ":" in posix.parts[0]:
            raise AppError("zip 鏂囦欢鍖呭惈闈炴硶璺緞", status_code=400)

        mode = (info.external_attr or 0) >> 16
        if stat.S_ISLNK(mode):
            raise AppError("zip 鏂囦欢鍖呭惈涓嶆敮鎸佺殑绗﹀彿閾炬帴", status_code=400)

        target_path = (dest_path / Path(*posix.parts)).resolve(strict=False)
        try:
            if os.path.commonpath([str(dest_path), str(target_path)]) != str(dest_path):
                raise AppError("zip 鏂囦欢鍖呭惈闈炴硶璺緞", status_code=400)
        except ValueError:
            raise AppError("zip 鏂囦欢鍖呭惈闈炴硶璺緞", status_code=400)

        zf.extract(info, str(dest_path))


def _clone_repo(git_url: str, branch: str, dest_dir: str) -> None:
    git_url = (git_url or "").strip()
    branch = (branch or "main").strip() or "main"

    parsed_url = urlparse(git_url)
    if parsed_url.scheme != "https":
        raise AppError("浠呮敮鎸?HTTPS 鍗忚鐨勪粨搴撳湴鍧€", status_code=400)
    if not parsed_url.netloc:
        raise AppError("鏃犳晥鐨?Git 浠撳簱鍦板潃", status_code=400)

    path_parts = [p for p in (parsed_url.path or "").split("/") if p]
    if len(path_parts) < 2:
        raise AppError("鏃犳晥鐨?Git 浠撳簱鍦板潃", status_code=400)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, git_url, dest_dir],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise AppError("Git 鍏嬮殕瓒呮椂锛?0绉掞級", status_code=400)
    except FileNotFoundError:
        raise AppError("鏈嶅姟鍣ㄦ湭瀹夎 git锛屾棤娉曞鍏?", status_code=500)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise AppError(f"Git 鍏嬮殕澶辫触: {stderr}" if stderr else "Git 鍏嬮殕澶辫触", status_code=400)


def _find_skill_dirs(repo_dir: str) -> list[str]:
    skill_dirs = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        if "SKILL.md" in files:
            skill_dirs.append(root)
            dirs.clear()
    return skill_dirs


def _persist_skill_from_dir(db: Session, *, skill_root: str, project: Project, creator: User) -> Skill:
    repo = SkillsRepository(db)
    skill_md_path = os.path.join(skill_root, "SKILL.md")
    try:
        with open(skill_md_path, "r", encoding="utf-8") as handle:
            skill_content = handle.read()
    except UnicodeDecodeError:
        raise AppError("SKILL.md 鏂囦欢缂栫爜蹇呴』涓?UTF-8", status_code=400)

    parsed = _parse_skill_md(skill_content)
    if repo.get_by_name(project_id=project.id, name=parsed["name"]):
        raise AppError(f"椤圭洰涓凡瀛樺湪鍚嶄负 '{parsed['name']}' 鐨?Skill", status_code=400)

    full_storage_path = None
    try:
        skill = repo.create_skill(
            Skill(
                project_id=project.id,
                creator_id=creator.id,
                name=parsed["name"],
                description=parsed["description"],
                skill_content=skill_content,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )

        skill_storage_path = f"skills/{project.id}/{skill.id}"
        full_storage_path = DJANGO_MEDIA_ROOT / skill_storage_path
        full_storage_path.mkdir(parents=True, exist_ok=False)

        for item in os.listdir(skill_root):
            if item in (".git", "__pycache__", "node_modules"):
                continue
            src = os.path.join(skill_root, item)
            if os.path.islink(src):
                continue
            dst = full_storage_path / item
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns(".git"))
            else:
                shutil.copy2(src, dst)

        skill.skill_path = skill_storage_path
        db.add(skill)
        db.flush()
        return skill
    except Exception:
        if full_storage_path and full_storage_path.is_dir():
            shutil.rmtree(full_storage_path, ignore_errors=True)
        raise


def upload_skill(*, db: Session, project_id: int, creator: User, filename: str, content: bytes) -> dict:
    if not filename or not filename.endswith(".zip"):
        raise AppError("閸欘亝鏁幐?.zip 閺傚洣娆?", status_code=400)

    project = _get_project(db, project_id)
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                _safe_extract_zip(zf, temp_dir)
        except zipfile.BadZipFile:
            raise AppError("鏃犳晥鐨?zip 鏂囦欢", status_code=400)

        skill_root = temp_dir
        items = os.listdir(temp_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(temp_dir, items[0])):
            skill_root = os.path.join(temp_dir, items[0])

        if not os.path.exists(os.path.join(skill_root, "SKILL.md")):
            raise AppError("zip 鏂囦欢涓湭鎵惧埌 SKILL.md", status_code=400)

        skill = _persist_skill_from_dir(db, skill_root=skill_root, project=project, creator=creator)
        db.commit()
        db.refresh(skill)
        return _serialize_skill(skill)


def import_skill_from_git(*, db: Session, project_id: int, creator: User, git_url: str, branch: str = "main") -> list[dict]:
    project = _get_project(db, project_id)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = os.path.join(temp_dir, "repo")
        _clone_repo(git_url, branch, repo_dir)
        skill_dirs = _find_skill_dirs(repo_dir)
        if not skill_dirs:
            raise AppError("浠撳簱涓湭鎵惧埌 SKILL.md", status_code=400)

        created = []
        errors = []
        for skill_dir in skill_dirs:
            try:
                skill = _persist_skill_from_dir(db, skill_root=skill_dir, project=project, creator=creator)
                created.append(skill)
            except AppError as exc:
                errors.append(exc.message)

        if not created:
            db.rollback()
            raise AppError(
                f"鎵€鏈?Skills 瀵煎叆澶辫触: {'; '.join(errors)}" if errors else "浠撳簱涓湭鎵惧埌鏈夋晥鐨?SKILL.md",
                status_code=400,
            )

        db.commit()
        return [_serialize_skill(skill) for skill in created]


def list_skills(*, db: Session, project_id: int) -> list[dict]:
    _get_project(db, project_id)
    return [_serialize_skill_list_item(item) for item in SkillsRepository(db).list_skills(project_id=project_id)]


def get_skill_detail(*, db: Session, project_id: int, skill_id: int) -> dict:
    _get_project(db, project_id)
    skill = SkillsRepository(db).get_skill(project_id=project_id, skill_id=skill_id)
    if not skill:
        raise AppError("Skill 娑撳秴鐡ㄩ崷?", status_code=404)
    return _serialize_skill(skill)


def toggle_skill(*, db: Session, project_id: int, skill_id: int, is_active: bool) -> dict:
    _get_project(db, project_id)
    skill = SkillsRepository(db).get_skill(project_id=project_id, skill_id=skill_id)
    if not skill:
        raise AppError("Skill 娑撳秴鐡ㄩ崷?", status_code=404)
    skill.is_active = bool(is_active)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return _serialize_skill(skill)


def delete_skill(*, db: Session, project_id: int, skill_id: int) -> str:
    _get_project(db, project_id)
    skill = SkillsRepository(db).get_skill(project_id=project_id, skill_id=skill_id)
    if not skill:
        raise AppError("Skill 娑撳秴鐡ㄩ崷?", status_code=404)
    name = skill.name
    full_path = DJANGO_MEDIA_ROOT / (skill.skill_path or "")
    if skill.skill_path and full_path.exists():
        expected = DJANGO_MEDIA_ROOT / "skills" / str(skill.project_id) / str(skill.id)
        try:
            if full_path.resolve(strict=False) == expected.resolve(strict=False):
                shutil.rmtree(full_path, ignore_errors=True)
        except Exception:
            pass
    db.delete(skill)
    db.commit()
    return name


def get_skill_content(*, db: Session, project_id: int, skill_id: int) -> dict:
    _get_project(db, project_id)
    skill = SkillsRepository(db).get_skill(project_id=project_id, skill_id=skill_id)
    if not skill:
        raise AppError("Skill 娑撳秴鐡ㄩ崷?", status_code=404)
    return {
        "name": skill.name,
        "description": skill.description,
        "content": skill.skill_content,
    }
