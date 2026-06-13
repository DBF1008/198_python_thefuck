import pytest
from mock import Mock
from thefuck.entrypoints.fix_command import _get_raw_command


class TestGetRawCommand(object):
    def test_from_force_command_argument(self):
        known_args = Mock(force_command='git brunch')
        assert _get_raw_command(known_args) == ['git brunch']

    def test_from_command_argument(self, os_environ):
        os_environ['TF_HISTORY'] = None
        known_args = Mock(force_command=None,
                          command=['sl'])
        assert _get_raw_command(known_args) == ['sl']

    @pytest.mark.parametrize('history, result', [
        ('git br', 'git br'),
        ('git br\nfcuk', 'git br'),
        ('git br\nfcuk\nls', 'ls'),
        ('git br\nfcuk\nls\nfuk', 'ls')])
    def test_from_history(self, os_environ, history, result):
        os_environ['TF_HISTORY'] = history
        known_args = Mock(force_command=None,
                          command=None)
        assert _get_raw_command(known_args) == [result]

    @pytest.mark.parametrize('history, result', [
        # A lone trailing newline produces an empty last entry.
        ('git br\n', 'git br'),
        # Trailing blank line after alias noise must be skipped.
        ('git br\nfcuk\n', 'git br'),
        # Whitespace-only trailing line must be skipped, not returned.
        ('git br\nfcuk\n   ', 'git br'),
        # Several trailing blanks following the exact alias.
        ('git br\nfuck\n\n', 'git br'),
        # Blank line must not shadow a matching executable.
        ('git br\nls\n', 'ls')])
    def test_skips_trailing_blank_lines(self, os_environ, history, result):
        os_environ['TF_HISTORY'] = history
        known_args = Mock(force_command=None,
                          command=None)
        assert _get_raw_command(known_args) == [result]

    @pytest.mark.parametrize('history, result', [
        # The exact alias repeated several times.
        ('git br\nfuck\nfuck', 'git br'),
        # Mixed alias-noise variants in a row.
        ('git br\nfcuk\nfuk', 'git br'),
        ('git br\nfcuk\nfuk\nfcuk', 'git br'),
        # Consecutive aliases plus trailing blank lines combined.
        ('git br\nfuck\nfuck\n\n', 'git br')])
    def test_skips_consecutive_alias_noise(self, os_environ, history, result):
        os_environ['TF_HISTORY'] = history
        known_args = Mock(force_command=None,
                          command=None)
        assert _get_raw_command(known_args) == [result]
