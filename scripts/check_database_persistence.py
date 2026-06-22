from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(path, needle, message):
    content = read(path)
    if needle not in content:
        raise AssertionError(f"{path}: {message}")


def assert_not_contains(path, needle, message):
    content = read(path)
    if needle in content:
        raise AssertionError(f"{path}: {message}")


def main():
    for path in ("manage.py", "dtcall/settings.py"):
        assert_contains(
            path,
            "def _set_env_from_file",
            "env loader must allow saved .env database values to replace empty process env values",
        )
        assert_not_contains(
            path,
            "os.environ.setdefault(key.strip()",
            "setdefault keeps empty process env values and can ignore the saved database selection",
        )

    assert_contains(
        "apps/system/database_setup.py",
        "save_database_environment",
        "database setup must persist submitted database values",
    )
    assert_contains(
        "apps/system/database_setup.py",
        "_write_env(updates)",
        "database setup must write persisted values to .env",
    )


if __name__ == "__main__":
    main()
