from functools import lru_cache
import os
from pathlib import Path
import sys


@lru_cache(maxsize=1)
def ensure_django_setup() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    django_root = repo_root / "FlyTest_Django"
    if str(django_root) not in sys.path:
        sys.path.insert(0, str(django_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

    import django

    django.setup()


def check_password_with_django(raw_password: str, encoded_password: str) -> bool:
    ensure_django_setup()
    from django.contrib.auth.hashers import check_password

    return check_password(raw_password, encoded_password)


def make_password_with_django(raw_password: str) -> str:
    ensure_django_setup()
    from django.contrib.auth.hashers import make_password

    return make_password(raw_password)


def get_default_prompts_from_django() -> list[dict]:
    ensure_django_setup()
    from prompts.services import get_default_prompts

    return list(get_default_prompts())


def get_django_user(user_id: int):
    ensure_django_setup()
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(id=user_id).first()
