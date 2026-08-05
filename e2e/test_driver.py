import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "macos_real_ai_e2e.py"
SPEC = importlib.util.spec_from_file_location("macos_real_ai_e2e", SCRIPT)
driver = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(driver)


class DriverTests(unittest.TestCase):
    def test_redaction_covers_keys_and_bearer_values(self):
        value = driver.redact({"api_key": "secret", "nested": "Bearer sk-example123456"})
        self.assertEqual(value["api_key"], "[REDACTED]")
        self.assertNotIn("sk-example", value["nested"])

    def test_prompt_has_marker_and_deterministic_delivery_contract(self):
        prompt = driver.prompt_for("REAL-E2E-TEST")
        self.assertIn("REAL-E2E-TEST", prompt)
        self.assertIn("index.html", prompt)
        self.assertIn("整合发布 Agent", prompt)
        self.assertIn("REQUIREMENTS.md", prompt)
        self.assertIn("assets/data/app-copy.json", prompt)

    def test_role_boundaries_allow_only_declared_paths(self):
        self.assertTrue(driver.path_is_owned("assets/illustration.svg", ("assets/**",)))
        self.assertTrue(driver.path_is_owned("assets/data/app-copy.json", ("assets/data/app-copy.json",)))
        self.assertFalse(driver.path_is_owned("index.html", ("assets/**",)))
        self.assertTrue(driver.path_is_owned("assets/data/app-copy.json", ("assets/**",)))

    def test_site_validation_rejects_remote_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                "<main><h1>Test</h1><p>" + "content " * 60 + "</p><img alt='ok' src='https://example.com/a.png'></main>",
                encoding="utf-8",
            )
            with self.assertRaises(driver.DriverError):
                driver.validate_site(root)

    def test_root_clean_ignores_only_budgetloop_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            driver.run(["git", "init", "-q", str(root)])
            driver.run(["git", "-C", str(root), "config", "user.email", "test@example.com"])
            driver.run(["git", "-C", str(root), "config", "user.name", "Test"])
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            driver.run(["git", "-C", str(root), "add", "seed.txt"])
            driver.run(["git", "-C", str(root), "commit", "-qm", "seed"])
            (root / ".budgetloop/worktrees").mkdir(parents=True)
            (root / ".budgetloop/worktrees/state").write_text("ok", encoding="utf-8")
            self.assertTrue(driver.root_is_clean(root))
            (root / "unexpected.txt").write_text("no", encoding="utf-8")
            self.assertFalse(driver.root_is_clean(root))

    def test_container_discovery_falls_back_to_exact_prepared_directory(self):
        run_dir = Path("/tmp/budgetloop-real-ai-test")
        responses = {
            "/api/work-containers": {"containers": [{"id": "container-1", "name": "AI summarized title"}]},
            "/api/work-containers/container-1": {
                "id": "container-1",
                "preset_snapshot": {"workspace_access": {"project_dir": str(run_dir)}},
            },
        }
        with patch.object(driver, "api_json", side_effect=lambda _base, path: responses[path]):
            found = driver.find_container("http://example.invalid", "REAL-E2E-TEST", run_dir)
        self.assertEqual(found["id"], "container-1")

    def test_container_worktree_maps_only_known_mount_below_controlled_root(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            expected = (run_dir / ".budgetloop/worktrees/session-1").resolve()
            self.assertEqual(
                driver.host_worktree_path("/workspace/.budgetloop/worktrees/session-1", run_dir),
                expected,
            )
            for unsafe in ("/etc/passwd", "/workspace/../../etc/passwd", "/workspace/.budgetloop/other"):
                with self.assertRaises(driver.DriverError):
                    driver.host_worktree_path(unsafe, run_dir)


if __name__ == "__main__":
    unittest.main()
