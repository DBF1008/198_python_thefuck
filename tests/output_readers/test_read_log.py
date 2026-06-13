# -*- encoding: utf-8 -*-

import pytest
from mock import patch
from thefuck import const
from thefuck.output_readers import read_log


MARK = const.USER_COMMAND_MARK

RECENT = (MARK + u'git brnch\n'
          u"git: 'brnch' is not a git command. See 'git --help'.\n")


@pytest.fixture
def write_log(os_environ, tmp_path):
    """Configures the env read_log needs and writes the log file.

    Returns a callable that takes the log contents (as text), writes them to a
    real file and points ``THEFUCK_OUTPUT_LOG`` at it, so the production mmap
    path is exercised end to end.
    """
    log_path = tmp_path / 'output.log'
    os_environ['PS1'] = MARK
    os_environ['THEFUCK_OUTPUT_LOG'] = str(log_path)

    def write(content):
        log_path.write_bytes(content.encode('utf-8'))
        return str(log_path)

    return write


@pytest.fixture(autouse=True)
def terminal_size():
    """Pin the terminal width so pyte renders deterministically."""
    with patch('thefuck.output_readers.read_log.get_terminal_size') as mock:
        mock.return_value.columns = 80
        yield mock


class TestGetOutput(object):
    def test_reads_log_smaller_than_window(self, write_log):
        # A fresh log is almost always smaller than ``LOG_SIZE_IN_BYTES``;
        # mmap'ing the fixed window length used to raise here.
        assert len(RECENT.encode('utf-8')) < const.LOG_SIZE_IN_BYTES
        write_log(RECENT)

        output = read_log.get_output('git brnch')

        assert output is not None
        assert 'is not a git command' in output

    def test_reads_log_larger_than_window(self, write_log):
        # Pad the front with more than a window's worth of old commands so the
        # recent command lives past the first ``LOG_SIZE_IN_BYTES`` bytes. Only
        # a tail map + seek can find it.
        old = (MARK + u'echo old\n' u'old output line\n') * 30000
        content = old + RECENT
        assert len(content.encode('utf-8')) > const.LOG_SIZE_IN_BYTES
        write_log(content)

        output = read_log.get_output('git brnch')

        assert output is not None
        assert 'is not a git command' in output
        # Only the matched (recent) group is returned, never the old filler.
        assert 'old output line' not in output

    def test_returns_none_when_script_not_in_log(self, write_log):
        write_log(MARK + u'ls\n' u'file_a\nfile_b\n')

        assert read_log.get_output('git brnch') is None

    def test_returns_none_for_empty_log(self, write_log):
        write_log(u'')

        assert read_log.get_output('git brnch') is None
