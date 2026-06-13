# -*- encoding: utf-8 -*-

import os
from mock import patch
from thefuck.output_readers import shell_logger


@patch('thefuck.output_readers.shell_logger._get_last_n')
@patch('thefuck.output_readers.shell_logger._get_output_lines')
@patch('thefuck.output_readers.shell_logger.logs')
class TestGetOutput(object):

    def test_get_output_first_command(
        self, logs_mock, get_output_lines_mock, get_last_n_mock,
    ):
        """Target command is the first record -- should return its output."""
        get_output_lines_mock.return_value = ['file1', 'file2']
        get_last_n_mock.return_value = [
            {'command': 'ls /tmp', 'output': 'file1\nfile2'},
            {'command': 'pwd', 'output': '/home'},
        ]
        result = shell_logger.get_output('ls /tmp')
        assert result == 'file1\nfile2'
        get_output_lines_mock.assert_called_once_with('file1\nfile2')

    def test_get_output_not_first_command(
        self, logs_mock, get_output_lines_mock, get_last_n_mock,
    ):
        """Target command appears later in the list -- must still be found."""
        get_output_lines_mock.return_value = ['file1', 'file2']
        get_last_n_mock.return_value = [
            {'command': 'pwd', 'output': '/home'},
            {'command': 'whoami', 'output': 'root'},
            {'command': 'ls /tmp', 'output': 'file1\nfile2'},
        ]
        result = shell_logger.get_output('ls /tmp')
        assert result == 'file1\nfile2'
        logs_mock.warn.assert_not_called()
        get_output_lines_mock.assert_called_once_with('file1\nfile2')

    def test_get_output_command_not_found(
        self, logs_mock, get_output_lines_mock, get_last_n_mock,
    ):
        """Target command does not appear at all -- warn and return None."""
        get_last_n_mock.return_value = [
            {'command': 'pwd', 'output': '/home'},
            {'command': 'whoami', 'output': 'root'},
        ]
        result = shell_logger.get_output('ls /tmp')
        assert result is None
        logs_mock.warn.assert_called_once()
        get_output_lines_mock.assert_not_called()

    def test_get_output_empty_commands(
        self, logs_mock, get_output_lines_mock, get_last_n_mock,
    ):
        """No commands recorded at all -- warn and return None."""
        get_last_n_mock.return_value = []
        result = shell_logger.get_output('ls /tmp')
        assert result is None
        logs_mock.warn.assert_called_once()
        get_output_lines_mock.assert_not_called()


@patch('thefuck.output_readers.shell_logger._get_last_n')
@patch('thefuck.output_readers.shell_logger.logs')
class TestGetOutputTerminalProcessing(object):
    """Verify that shell logger output still goes through pyte for
    terminal escape sequence handling."""

    @patch('thefuck.output_readers.shell_logger.get_terminal_size')
    def test_escape_sequences_are_stripped(
        self, terminal_size_mock, logs_mock, get_last_n_mock,
    ):
        """ANSI escape codes in output are processed by pyte and stripped."""
        terminal_size_mock.return_value = os.terminal_size((80, 24))
        # \x1b[31m = red foreground, \x1b[0m = reset
        raw_output = '\x1b[31merror:\x1b[0m file not found'
        get_last_n_mock.return_value = [
            {'command': 'cat missing', 'output': raw_output},
        ]
        result = shell_logger.get_output('cat missing')
        # Visible text is preserved
        assert 'error:' in result
        assert 'file not found' in result
        # Raw escape codes must NOT leak into the final output
        assert '\x1b[31m' not in result
        assert '\x1b[0m' not in result

    @patch('thefuck.output_readers.shell_logger.get_terminal_size')
    def test_not_first_match_still_processes_escapes(
        self, terminal_size_mock, logs_mock, get_last_n_mock,
    ):
        """Non-first match still goes through pyte terminal processing."""
        terminal_size_mock.return_value = os.terminal_size((80, 24))
        # \x1b[1m = bold, \x1b[0m = reset
        raw_output = '\x1b[1mPermission denied\x1b[0m'
        get_last_n_mock.return_value = [
            {'command': 'echo hello', 'output': 'hello'},
            {'command': 'cat /etc/shadow', 'output': raw_output},
        ]
        result = shell_logger.get_output('cat /etc/shadow')
        assert 'Permission denied' in result
        assert '\x1b[1m' not in result
        assert '\x1b[0m' not in result
        logs_mock.warn.assert_not_called()
