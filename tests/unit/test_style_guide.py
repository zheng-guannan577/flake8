"""Tests for the flake8.style_guide.StyleGuide class."""
from __future__ import annotations

import argparse
import logging
from unittest import mock

import pytest

from flake8 import statistics
from flake8 import style_guide
from flake8 import utils
from flake8.formatting import base


def create_options(**kwargs):
    """Create and return an instance of argparse.Namespace."""
    kwargs.setdefault("select", [])
    kwargs.setdefault("extended_default_select", [])
    kwargs.setdefault("extended_default_ignore", [])
    kwargs.setdefault("extend_select", [])
    kwargs.setdefault("ignore", [])
    kwargs.setdefault("extend_ignore", [])
    kwargs.setdefault("disable_noqa", False)
    kwargs.setdefault("enable_extensions", [])
    kwargs.setdefault("per_file_ignores", [])
    return argparse.Namespace(**kwargs)


def test_handle_error_does_not_raise_type_errors():
    """Verify that we handle our inputs better."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    guide = style_guide.StyleGuide(
        create_options(select=["T111"], ignore=[]),
        formatter=formatter,
        stats=statistics.Statistics(),
    )

    assert 1 == guide.handle_error(
        "T111", "file.py", 1, 1, "error found", "a = 1",
    )


def test_style_guide_manager():
    """Verify how the StyleGuideManager creates a default style guide."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options()
    guide = style_guide.StyleGuideManager(options, formatter=formatter)
    assert guide.default_style_guide.options is options
    assert len(guide.style_guides) == 1


@pytest.mark.parametrize(
        ('select', 'extend_select', 'expected'),
        [
                    # --select which still selects every installed plugin is useless
                    (
                                    ['E', 'W', 'F', 'C90'],
                        None,
                        '--select W,F,E,C90 is unnecessary: it already selects all '
                        'installed plugins',
            ),
                    # a prefix which covers a default code is enough
                    (
                                    ['E', 'W', 'F', 'C'],
                                    None,
                                    '--select W,F,E,C is unnecessary: it already selects all '
                                    'installed plugins',
                    ),
        ],
)
def test_useless_select_warns(select, extend_select, expected, caplog):
        formatter = mock.create_autospec(base.BaseFormatter, instance=True)
        options = create_options(
                    select=select,
                    extend_select=extend_select,
                    extended_default_select=['C90', 'F', 'E', 'W'],
        )
        style_guide.StyleGuideManager(options, formatter=formatter)

    assert caplog.record_tuples == [
                ('flake8.style_guide', logging.WARNING, expected),
    ]


@pytest.mark.parametrize(
        ('select', 'extend_select'),
        [
                    # no --select / --extend-select configured
                    (None, None),
                    # --select which restricts the default selection is useful
                    (['E'], None),
                    # --select=[] selects nothing
                    ([], []),
        ],
)
def test_useful_select_does_not_warn(select, extend_select, caplog):
        formatter = mock.create_autospec(base.BaseFormatter, instance=True)
        options = create_options(
                    select=select,
                    extend_select=extend_select,
                    extended_default_select=['C90', 'F', 'E', 'W'],
        )
        style_guide.StyleGuideManager(options, formatter=formatter)

    assert caplog.record_tuples == []


@pytest.mark.parametrize(
        ('extend_select', 'expected'),
        [
                    (
                                    ['E'],
                                    '--extend-select E is unnecessary: those codes are already '
                                    'selected by default',
                    ),
                    # a sub-code of an already selected code is also useless
                    (
                                    ['E4'],
                                    '--extend-select E4 is unnecessary: those codes are already '
                                    'selected by default',
                    ),
        ],
)
def test_useless_extend_select_warns(extend_select, expected, caplog):
        formatter = mock.create_autospec(base.BaseFormatter, instance=True)
        options = create_options(
                    select=None,
                    extend_select=extend_select,
                    extended_default_select=['C90', 'F', 'E', 'W'],
        )
        style_guide.StyleGuideManager(options, formatter=formatter)

    assert caplog.record_tuples == [
                ('flake8.style_guide', logging.WARNING, expected),
    ]


@pytest.mark.parametrize(
        'extend_select',
        [
                    # --extend-select adding a code from an uninstalled plugin
                    ['D'],
                    # --extend-select re-enabling a default-ignored code is useful
                    ['P002'],
        ],
)
def test_useful_extend_select_does_not_warn(extend_select, caplog):
        formatter = mock.create_autospec(base.BaseFormatter, instance=True)
        options = create_options(
                    select=None,
                    extend_select=extend_select,
                    extended_default_select=['C90', 'F', 'E', 'W'],
                    extended_default_ignore=['P002'],
        )
        style_guide.StyleGuideManager(options, formatter=formatter)

    assert caplog.record_tuples == []


PER_FILE_IGNORES_UNPARSED = [
    "first_file.py:W9",
    "second_file.py:F4,F9",
    "third_file.py:E3",
    "sub_dir/*:F4",
]


@pytest.mark.parametrize(
    "style_guide_file,filename,expected",
    [
        ("first_file.py", "first_file.py", True),
        ("first_file.py", "second_file.py", False),
        ("sub_dir/*.py", "first_file.py", False),
        ("sub_dir/*.py", "sub_dir/file.py", True),
        ("sub_dir/*.py", "other_dir/file.py", False),
    ],
)
def test_style_guide_applies_to(style_guide_file, filename, expected):
    """Verify that we match a file to its style guide."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options()
    guide = style_guide.StyleGuide(
        options,
        formatter=formatter,
        stats=statistics.Statistics(),
        filename=style_guide_file,
    )
    assert guide.applies_to(filename) is expected


def test_style_guide_manager_pre_file_ignores_parsing():
    """Verify how the StyleGuideManager creates a default style guide."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(per_file_ignores=PER_FILE_IGNORES_UNPARSED)
    guide = style_guide.StyleGuideManager(options, formatter=formatter)
    assert len(guide.style_guides) == 5
    expected = [
        utils.normalize_path(p)
        for p in [
            "first_file.py",
            "second_file.py",
            "third_file.py",
            "sub_dir/*",
        ]
    ]
    assert expected == [g.filename for g in guide.style_guides[1:]]


@pytest.mark.parametrize(
    "ignores,violation,filename,handle_error_return",
    [
        (["E1", "E2"], "F401", "first_file.py", 1),
        (["E1", "E2"], "E121", "first_file.py", 0),
        (["E1", "E2"], "F401", "second_file.py", 0),
        (["E1", "E2"], "F401", "third_file.py", 1),
        (["E1", "E2"], "E311", "third_file.py", 0),
        (["E1", "E2"], "F401", "sub_dir/file.py", 0),
    ],
)
def test_style_guide_manager_pre_file_ignores(
    ignores, violation, filename, handle_error_return,
):
    """Verify how the StyleGuideManager creates a default style guide."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(
        ignore=ignores,
        select=["E", "F", "W"],
        per_file_ignores=PER_FILE_IGNORES_UNPARSED,
    )
    guide = style_guide.StyleGuideManager(options, formatter=formatter)
    assert (
        guide.handle_error(violation, filename, 1, 1, "Fake text")
        == handle_error_return
    )


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("first_file.py", utils.normalize_path("first_file.py")),
        ("second_file.py", utils.normalize_path("second_file.py")),
        ("third_file.py", utils.normalize_path("third_file.py")),
        ("fourth_file.py", None),
        ("sub_dir/__init__.py", utils.normalize_path("sub_dir/*")),
        ("other_dir/__init__.py", None),
    ],
)
def test_style_guide_manager_style_guide_for(filename, expected):
    """Verify the style guide selection function."""
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(per_file_ignores=PER_FILE_IGNORES_UNPARSED)
    guide = style_guide.StyleGuideManager(options, formatter=formatter)

    file_guide = guide.style_guide_for(filename)
    assert file_guide.filename == expected
