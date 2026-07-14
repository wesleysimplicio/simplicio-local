from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock


FIXTURE_DIR = Path(__file__).resolve().parent


def load_runner(name: str):
    path = FIXTURE_DIR / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunnerSkipContractTest(unittest.TestCase):
    def test_forward_runner_skips_without_compiling(self) -> None:
        runner = load_runner("run_engine_forward_oracles.py")
        output = io.StringIO()
        with (
            mock.patch.dict(runner.os.environ, {"CI": ""}, clear=False),
            mock.patch.object(runner, "require"),
            mock.patch.object(runner.shutil, "which", return_value=None),
            mock.patch.object(runner, "run") as compile_runner,
            contextlib.redirect_stdout(output),
        ):
            result = runner.main()

        self.assertEqual(runner.SKIP_RETURN_CODE, 77)
        self.assertEqual(result, 77)
        self.assertIn("SKIP", output.getvalue())
        compile_runner.assert_not_called()

    def test_forward_runner_fails_in_ci_without_compiling(self) -> None:
        runner = load_runner("run_engine_forward_oracles.py")
        output = io.StringIO()
        with (
            mock.patch.dict(runner.os.environ, {"CI": "1"}, clear=False),
            mock.patch.object(runner, "require"),
            mock.patch.object(runner.shutil, "which", return_value=None),
            mock.patch.object(runner, "run") as compile_runner,
            contextlib.redirect_stdout(output),
        ):
            result = runner.main()

        self.assertEqual(result, 1)
        self.assertNotEqual(result, runner.SKIP_RETURN_CODE)
        self.assertIn("ERROR", output.getvalue())
        self.assertNotIn("SKIP", output.getvalue())
        compile_runner.assert_not_called()

    def test_tokenizer_runner_skips_without_compiling(self) -> None:
        runner = load_runner("run_engine_tokenizer_contract.py")
        output = io.StringIO()
        with (
            mock.patch.dict(
                runner.os.environ,
                {"CC": "missing-compiler", "CI": ""},
                clear=False,
            ),
            mock.patch.object(runner.shutil, "which", return_value=None),
            mock.patch.object(runner.subprocess, "run") as compiler,
            contextlib.redirect_stdout(output),
        ):
            result = runner.main()

        self.assertEqual(runner.SKIP_RETURN_CODE, 77)
        self.assertEqual(result, 77)
        self.assertIn("SKIP", output.getvalue())
        compiler.assert_not_called()

    def test_tokenizer_runner_fails_in_ci_without_compiling(self) -> None:
        runner = load_runner("run_engine_tokenizer_contract.py")
        output = io.StringIO()
        with (
            mock.patch.dict(
                runner.os.environ,
                {"CC": "missing-compiler", "CI": "1"},
                clear=False,
            ),
            mock.patch.object(runner.shutil, "which", return_value=None),
            mock.patch.object(runner.subprocess, "run") as compiler,
            contextlib.redirect_stdout(output),
        ):
            result = runner.main()

        self.assertEqual(result, 1)
        self.assertNotEqual(result, runner.SKIP_RETURN_CODE)
        self.assertIn("ERROR", output.getvalue())
        self.assertNotIn("SKIP", output.getvalue())
        compiler.assert_not_called()


if __name__ == "__main__":
    unittest.main()
