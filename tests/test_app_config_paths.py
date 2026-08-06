import unittest
from pathlib import Path

from modules.app_config import resolve_runtime_root


class AppConfigPathTests(unittest.TestCase):
    def test_resolve_runtime_root_prefers_existing_localappdata_data(self) -> None:
        temp_root = Path(__file__).resolve().parent.parent / "tmp_test_paths"
        if temp_root.exists():
            for child in temp_root.iterdir():
                if child.is_dir():
                    for nested in sorted(child.rglob("*"), reverse=True):
                        if nested.is_file():
                            nested.unlink()
                        elif nested.is_dir():
                            nested.rmdir()
                    child.rmdir()
                else:
                    child.unlink()
            temp_root.rmdir()

        base_dir = temp_root / "new_app"
        base_dir.mkdir(parents=True, exist_ok=True)
        local_root = temp_root / "LocalAppData" / "ArezOne"
        (local_root / "data").mkdir(parents=True, exist_ok=True)
        (local_root / "data" / "arezone.db").write_text("legacy", encoding="utf-8")

        selected = resolve_runtime_root(base_dir, env={"LOCALAPPDATA": str(temp_root / "LocalAppData")})

        self.assertEqual(selected, local_root)


if __name__ == "__main__":
    unittest.main()
