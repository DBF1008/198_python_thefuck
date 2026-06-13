# -*- encoding: utf-8 -*-

import os
import pytest
from mock import patch

from thefuck import const
from thefuck.output_readers import read_log


MARK = const.USER_COMMAND_MARK


def _build_log_content(commands):
    """Build log file content from a list of (script, output) tuples.

    Each entry becomes a command block in the log, matching the format
    that ``_group_by_calls`` expects: a line containing
    ``USER_COMMAND_MARK`` followed by output lines.

    """
    parts = []
    for script, output in commands:
        parts.append('{}{}\n{}'.format(MARK, script, output))
    return '\n'.join(parts).encode('utf-8')


@pytest.fixture
def log_env(monkeypatch, tmp_path):
    """Provide an isolated log file and the required env vars."""
    log_file = tmp_path / 'output.log'

    def _write(content):
        if isinstance(content, str):
            content = content.encode('utf-8')
        log_file.write_bytes(content)
        return log_file

    monkeypatch.setenv('PS1', MARK + r'\w $ ')
    monkeypatch.setenv('THEFUCK_OUTPUT_LOG', str(log_file))
    return _write


class TestGetOutputSmallFile(object):
    """Log file is smaller than ``LOG_SIZE_IN_BYTES``."""

    def test_returns_output(self, log_env):
        content = _build_log_content([('ls', 'file1.txt\nfile2.txt\n')])
        log_env(content)
        assert len(content) < const.LOG_SIZE_IN_BYTES

        result = read_log.get_output('ls')
        assert result is not None
        assert 'file1.txt' in result
        assert 'file2.txt' in result

    def test_returns_output_for_tiny_log(self, log_env):
        # A single short command – well under LOG_SIZE_IN_BYTES.
        content = _build_log_content([('echo hello', 'hello\n')])
        log_env(content)

        result = read_log.get_output('echo hello')
        assert result is not None
        assert 'hello' in result

    def test_empty_file_returns_none(self, log_env):
        log_env(b'')

        result = read_log.get_output('ls')
        assert result is None


class TestGetOutputLargeFile(object):
    """Log file is larger than ``LOG_SIZE_IN_BYTES``."""

    def test_returns_output_from_tail(self, log_env):
        # Pad the beginning with junk so the file exceeds LOG_SIZE_IN_BYTES,
        # then place the real command at the end.  ``_skip_old_lines`` should
        # seek past the junk and still find the command.
        #
        # We use newline-separated filler rather than a solid block of null
        # bytes so we don't trigger the pre-existing O(n²) worst-case in
        # the trailing-null regex inside ``_get_output_lines``.
        junk_line = b'x' * 200 + b'\n'
        padding_size = const.LOG_SIZE_IN_BYTES + 1024
        padding = (junk_line * (padding_size // len(junk_line) + 1))[:padding_size]
        tail = _build_log_content([('git status', 'On branch main\n')])
        content = padding + b'\n' + tail
        log_env(content)
        assert len(content) > const.LOG_SIZE_IN_BYTES

        result = read_log.get_output('git status')
        assert result is not None
        assert 'On branch main' in result


class TestGetOutputScriptNotFound(object):
    """Script that does not appear in the log should yield ``None``."""

    def test_missing_script_returns_none(self, log_env):
        content = _build_log_content([('ls', 'file1.txt\n')])
        log_env(content)

        result = read_log.get_output('command_that_was_never_run')
        assert result is None

    def test_missing_script_in_large_log_returns_none(self, log_env):
        junk_line = b'x' * 200 + b'\n'
        padding_size = const.LOG_SIZE_IN_BYTES + 512
        padding = (junk_line * (padding_size // len(junk_line) + 1))[:padding_size]
        tail = _build_log_content([('ls', 'file1.txt\n')])
        content = padding + b'\n' + tail
        log_env(content)

        result = read_log.get_output('nonexistent_command')
        assert result is None
