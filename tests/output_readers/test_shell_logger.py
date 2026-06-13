# -*- encoding: utf-8 -*-

from mock import patch

from thefuck.output_readers import shell_logger


class TestGetOutput(object):
    def setup_method(self, test_method):
        self.patcher = patch(
            'thefuck.output_readers.shell_logger._get_last_n')
        self.get_last_n_mock = self.patcher.start()

    def teardown_method(self, test_method):
        self.patcher.stop()

    @patch('thefuck.output_readers.shell_logger._get_output_lines')
    def test_get_output_returns_matching_command(self, get_output_lines_mock):
        get_output_lines_mock.return_value = ['output']
        self.get_last_n_mock.return_value = [
            {'command': 'ls', 'output': 'raw'},
        ]
        assert shell_logger.get_output('ls') == 'output'
        get_output_lines_mock.assert_called_once_with('raw')

    @patch('thefuck.output_readers.shell_logger.logs')
    @patch('thefuck.output_readers.shell_logger._get_output_lines')
    def test_get_output_scans_past_non_matching_commands(
            self, get_output_lines_mock, logs_mock):
        # The target command is not the most recent entry: older shell-logger
        # records must still be scanned instead of bailing out on the first miss.
        get_output_lines_mock.return_value = ['target output']
        self.get_last_n_mock.return_value = [
            {'command': 'git status', 'output': 'git output'},
            {'command': 'whoami', 'output': 'whoami output'},
            {'command': 'ls', 'output': 'ls raw'},
        ]
        assert shell_logger.get_output('ls') == 'target output'
        get_output_lines_mock.assert_called_once_with('ls raw')
        assert not logs_mock.warn.called

    @patch('thefuck.output_readers.shell_logger.logs')
    @patch('thefuck.output_readers.shell_logger._get_output_lines')
    def test_get_output_returns_none_when_command_missing(
            self, get_output_lines_mock, logs_mock):
        self.get_last_n_mock.return_value = [
            {'command': 'git status', 'output': 'git output'},
            {'command': 'whoami', 'output': 'whoami output'},
        ]
        assert shell_logger.get_output('ls') is None
        assert not get_output_lines_mock.called
        logs_mock.warn.assert_called_once()

    @patch('thefuck.output_readers.shell_logger.logs')
    def test_get_output_returns_none_for_empty_history(self, logs_mock):
        self.get_last_n_mock.return_value = []
        assert shell_logger.get_output('ls') is None
        logs_mock.warn.assert_called_once()

    @patch('thefuck.output_readers.shell_logger.get_terminal_size')
    def test_get_output_strips_terminal_escapes(self, get_terminal_size_mock):
        # Output is rendered through pyte, so SGR colour codes are dropped.
        get_terminal_size_mock.return_value.columns = 80
        self.get_last_n_mock.return_value = [
            {'command': 'ls', 'output': u'\x1b[31mred\x1b[0m'},
        ]
        assert shell_logger.get_output('ls') == 'red'

    @patch('thefuck.output_readers.shell_logger.get_terminal_size')
    def test_get_output_applies_terminal_control_chars(
            self, get_terminal_size_mock):
        # Carriage returns overwrite earlier text, matching real terminal output.
        get_terminal_size_mock.return_value.columns = 80
        self.get_last_n_mock.return_value = [
            {'command': 'ls', 'output': u'aaa\rbbb'},
        ]
        assert shell_logger.get_output('ls') == 'bbb'
