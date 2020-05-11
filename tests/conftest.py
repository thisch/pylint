# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module
import contextlib
import os
import re
import sys
import warnings
from io import StringIO
from os.path import dirname

import pytest

from pylint import checkers
from pylint.lint import PyLinter, Run
from pylint.testutils import MinimalTestReporter


@pytest.fixture
def linter(checker, register, enable, disable, reporter):
    _linter = PyLinter()
    _linter.set_reporter(reporter())
    checkers.initialize(_linter)
    if register:
        register(_linter)
    if checker:
        _linter.register_checker(checker(_linter))
    if disable:
        for msg in disable:
            _linter.disable(msg)
    if enable:
        for msg in enable:
            _linter.enable(msg)
    os.environ.pop("PYLINTRC", None)
    return _linter


@pytest.fixture(scope="module")
def checker():
    return None


@pytest.fixture(scope="module")
def register():
    return None


@pytest.fixture(scope="module")
def enable():
    return None


@pytest.fixture(scope="module")
def disable():
    return None


@pytest.fixture(scope="module")
def reporter():
    return MinimalTestReporter


CLEAN_PATH = re.escape(dirname(dirname(__file__)) + "/")


@contextlib.contextmanager
def _patch_streams(out):
    sys.stderr = sys.stdout = out
    try:
        yield
    finally:
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__


class RunTester:
    @staticmethod
    def runtest(args, reporter=None, out=None, code=None):
        if out is None:
            out = StringIO()
        pylint_code = RunTester.run_pylint(args, reporter=reporter, out=out)
        if reporter:
            output = reporter.out.getvalue()
        elif hasattr(out, "getvalue"):
            output = out.getvalue()
        else:
            output = None
        msg = "expected output status %s, got %s" % (code, pylint_code)
        if output is not None:
            msg = "%s. Below pylint output: \n%s" % (msg, output)
        assert pylint_code == code, msg

    @staticmethod
    def run_pylint(args, out, reporter=None):
        args = args + ["--persistent=no"]
        with _patch_streams(out):
            with pytest.raises(SystemExit) as cm:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    Run(args, reporter=reporter)
            return cm.value.code

    @staticmethod
    def clean_paths(output):
        """Normalize path to the tests directory."""
        return re.sub(CLEAN_PATH, "", output.replace("\\", "/"), flags=re.MULTILINE)

    @staticmethod
    def check_output(args, expected_output):
        out = StringIO()
        RunTester.run_pylint(args, out=out)
        actual_output = RunTester.clean_paths(out.getvalue())
        expected_output = RunTester.clean_paths(expected_output)
        assert expected_output.strip() in actual_output.strip()


@pytest.fixture
def runtester():
    return RunTester()
