"""scoring 模块测试：信号、评分确定性、测试输出解析。"""
from app.scoring.progress import compute_score, parse_unittest_output
from app.scoring.signals import ProgressSignals, action_fingerprint, detect_regression, normalize_action


class TestActionFingerprint:
    def test_same_action_same_fingerprint(self):
        fp1 = action_fingerprint("bash", {"command": "ls -la"})
        fp2 = action_fingerprint("bash", {"command": "ls -la"})
        assert fp1 == fp2

    def test_different_action_different_fingerprint(self):
        fp1 = action_fingerprint("bash", {"command": "ls"})
        fp2 = action_fingerprint("bash", {"command": "pwd"})
        assert fp1 != fp2

    def test_normalize_space(self):
        a = normalize_action("  BaSh  ", " ls -la ")
        b = normalize_action("bash", "ls -la")
        assert a == b


class TestDetectRegression:
    def test_regression_when_more_failures_no_diff(self):
        assert detect_regression(5, 1, 5, 3, 0) is True

    def test_regression_when_fewer_passed_no_diff(self):
        assert detect_regression(5, 0, 3, 0, 0) is True

    def test_no_regression_when_diff_present(self):
        assert detect_regression(5, 1, 5, 3, 10) is False

    def test_no_regression_when_improved(self):
        assert detect_regression(2, 3, 4, 1, 0) is False

    def test_no_regression_when_no_change(self):
        assert detect_regression(5, 2, 5, 2, 0) is False


class TestProgressSignals:
    def test_defaults(self):
        s = ProgressSignals()
        assert s.failed_tests_delta == 0
        assert s.to_dict()["failed_tests_delta"] == 0

    def test_roundtrip(self):
        s = ProgressSignals(failed_tests_delta=3, diff_lines=50, repeated_action=True)
        d = s.to_dict()
        s2 = ProgressSignals.from_dict(d)
        assert s2.failed_tests_delta == 3
        assert s2.diff_lines == 50
        assert s2.repeated_action is True


class TestComputeScore:
    def test_deterministic(self):
        signals = ProgressSignals(failed_tests_delta=2, diff_lines=10, new_evidence=3)
        s1 = compute_score(signals)
        s2 = compute_score(signals)
        assert s1 == s2

    def test_clamped_zero_to_one(self):
        signals = ProgressSignals(
            failed_tests_delta=20, passed_tests_delta=20, compile_errors_delta=20,
            diff_lines=100, new_evidence=100, plan_steps_completed=100,
        )
        score = compute_score(signals)
        assert 0.0 <= score <= 1.0

    def test_very_negative_clamped(self):
        signals = ProgressSignals(repeated_action=True, regression=True)
        score = compute_score(signals)
        assert 0.0 <= score <= 1.0  # idle penalty should not push below 0

    def test_idle_penalty(self):
        signals = ProgressSignals(diff_lines=0, new_evidence=0)
        score = compute_score(signals)
        assert score < 0.5  # idle penalty

    def test_custom_weights(self):
        signals = ProgressSignals(failed_tests_delta=1, diff_lines=1)
        s_default = compute_score(signals)
        s_custom = compute_score(signals, weights={"base": 0.5, "failed_tests_decrease": 1.0})
        assert s_custom > s_default

    def test_no_signals_baseline(self):
        signals = ProgressSignals()
        score = compute_score(signals)
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # idle penalty

    def test_repeated_action_penalty(self):
        a = compute_score(ProgressSignals(repeated_action=True, diff_lines=10, new_evidence=1))
        b = compute_score(ProgressSignals(repeated_action=False, diff_lines=10, new_evidence=1))
        assert a < b


class TestParseUnittestOutput:
    def test_unittest_ok(self):
        text = "..........\n----------------------------------------------------------------------\nRan 10 tests in 0.001s\n\nOK\n"
        p, f, s = parse_unittest_output(text)
        assert p == 10
        assert f == 0
        assert s == 0

    def test_unittest_ok_skipped(self):
        text = "Ran 5 tests in 0.001s\nOK (skipped=1)\n"
        p, f, s = parse_unittest_output(text)
        assert p == 4
        assert f == 0
        assert s == 1

    def test_unittest_failed(self):
        text = "Ran 10 tests in 0.001s\nFAILED (failures=2, skipped=1)\n"
        p, f, s = parse_unittest_output(text)
        assert p == 7
        assert f == 2
        assert s == 1

    def test_unittest_errors(self):
        text = "Ran 3 tests in 0.001s\nFAILED (errors=1)\n"
        p, f, s = parse_unittest_output(text)
        assert p == 2
        assert f == 1
        assert s == 0

    def test_pytest(self):
        text = "test_a PASSED\n======================== 3 passed, 1 failed, 2 skipped in 0.5s ========================"
        p, f, s = parse_unittest_output(text)
        assert p == 3
        assert f == 1
        assert s == 2

    def test_pytest_errors(self):
        text = "1 passed, 0 failed, 0 skipped, 2 errors"
        p, f, s = parse_unittest_output(text)
        assert p == 1
        assert f == 2
        assert s == 0

    def test_empty(self):
        p, f, s = parse_unittest_output("")
        assert (p, f, s) == (0, 0, 0)
