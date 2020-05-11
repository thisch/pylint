# -*- coding: utf-8 -*-
# Copyright (c) 2020 Thomas Hisch <t.hisch@gmail.com>

# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/master/COPYING

import contextlib
import re
import sys
import textwrap
import warnings
from io import StringIO
from os.path import abspath, dirname, join

import pytest

from pylint.lint import Run

HERE = abspath(dirname(__file__))
CLEAN_PATH = re.escape(dirname(dirname(__file__)) + "/")


@contextlib.contextmanager
def _patch_streams(out):
    sys.stderr = sys.stdout = out
    try:
        yield
    finally:
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__


def runtest(args, reporter=None, out=None, code=None):
    if out is None:
        out = StringIO()
    pylint_code = run_pylint(args, reporter=reporter, out=out)
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


def run_pylint(args, out, reporter=None):
    args = args + ["--persistent=no"]
    with _patch_streams(out):
        with pytest.raises(SystemExit) as cm:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                Run(args, reporter=reporter)
        return cm.value.code


def clean_paths(output):
    """Normalize path to the tests directory."""
    return re.sub(CLEAN_PATH, "", output.replace("\\", "/"), flags=re.MULTILINE)


def check_output(args, expected_output):
    out = StringIO()
    run_pylint(args, out=out)
    actual_output = clean_paths(out.getvalue())
    expected_output = clean_paths(expected_output)
    assert expected_output.strip() in actual_output.strip()


@pytest.mark.parametrize(
    "input_path,module,expected_path",
    [
        (join(HERE, "mymodule.py"), "mymodule", join(HERE, "mymodule.py")),
        ("mymodule.py", "mymodule", "mymodule.py"),
    ],
)
def test_stdin(input_path, module, expected_path, mocker):
    expected_output = (
        "************* Module {module}\n"
        "{path}:1:0: W0611: Unused import os (unused-import)\n\n"
    ).format(path=expected_path, module=module)

    mock_stdin = mocker.patch(
        "pylint.lint.pylinter._read_stdin", return_value="import os\n"
    )
    check_output(
        ["--from-stdin", input_path, "--disable=all", "--enable=unused-import"],
        expected_output=expected_output,
    )
    assert mock_stdin.call_count == 1


def test_stdin_missing_modulename():
    runtest(["--from-stdin"], code=32)


@pytest.mark.parametrize("write_bpy_to_disk", [False, True])
def test_relative_imports(write_bpy_to_disk, tmpdir, mocker):
    a = tmpdir.join("a")

    b_code = textwrap.dedent(
        """
        from .c import foobar
        from .d import bla  # module does not exist

        foobar('hello')
        bla()
        """
    )

    c_code = textwrap.dedent(
        """
        def foobar(arg):
            pass
        """
    )

    a.mkdir()
    a.join("__init__.py").write("")
    if write_bpy_to_disk:
        a.join("b.py").write(b_code)
    a.join("c.py").write(c_code)

    with tmpdir.as_cwd():
        # why don't we start pylint in a subprocess?
        expected = (
            "************* Module a.b\n"
            "a/b.py:3:0: E0401: Unable to import 'a.d' (import-error)\n\n"
        )

        if write_bpy_to_disk:
            # --from-stdin is not used here
            check_output(
                ["a/b.py", "--disable=all", "--enable=import-error"],
                expected_output=expected,
            )

        # this code needs to work w/ and w/o a file named a/b.py on the
        # harddisk.
        mocker.patch("pylint.lint.pylinter._read_stdin", return_value=b_code)
        check_output(
            [
                "--from-stdin",
                join("a", "b.py"),
                "--disable=all",
                "--enable=import-error",
            ],
            expected_output=expected,
        )


def test_stdin_syntaxerror(mocker):
    expected_output = (
        "************* Module a\n"
        "a.py:1:4: E0001: invalid syntax (<unknown>, line 1) (syntax-error)"
    )

    mock_stdin = mocker.patch("pylint.lint.pylinter._read_stdin", return_value="for\n")
    check_output(
        ["--from-stdin", "a.py", "--disable=all", "--enable=syntax-error"],
        expected_output=expected_output,
    )
    assert mock_stdin.call_count == 1
