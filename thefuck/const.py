# -*- encoding: utf-8 -*-
from collections import namedtuple


class _GenConst(object):
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return u'<const: {}>'.format(self._name)


KEY_UP = _GenConst('↑')
KEY_DOWN = _GenConst('↓')
KEY_CTRL_C = _GenConst('Ctrl+C')
KEY_CTRL_N = _GenConst('Ctrl+N')
KEY_CTRL_P = _GenConst('Ctrl+P')

KEY_MAPPING = {'\x0e': KEY_CTRL_N,
               '\x03': KEY_CTRL_C,
               '\x10': KEY_CTRL_P}

ACTION_SELECT = _GenConst('select')
ACTION_ABORT = _GenConst('abort')
ACTION_PREVIOUS = _GenConst('previous')
ACTION_NEXT = _GenConst('next')

ALL_ENABLED = _GenConst('All rules enabled')
DEFAULT_RULES = [ALL_ENABLED]
DEFAULT_PRIORITY = 1000

# Env-string coercions. Each turns a raw ``THEFUCK_*`` environment value into
# the Python type the corresponding setting expects. They are the single place
# where env parsing rules live; settings reference them from ``SETTINGS_SCHEMA``.
def _env_to_bool(val):
    """Parses a boolean env-string (``'true'`` is True, case-insensitive)."""
    return val.lower() == 'true'


def _env_to_int(val):
    """Parses an integer env-string."""
    return int(val)


def _env_to_list(val):
    """Parses a colon-separated env-string into a list."""
    return val.split(':')


def _env_to_rules(val):
    """Parses a colon-separated rules env-string, expanding ``DEFAULT_RULES``."""
    rules = val.split(':')
    if 'DEFAULT_RULES' in rules:
        rules = DEFAULT_RULES + [rule for rule in rules
                                 if rule != 'DEFAULT_RULES']
    return rules


def _env_to_priority(val):
    """Parses a colon-separated ``rule=priority`` env-string into a dict.

    Malformed pairs (missing ``=`` or a non-integer priority) are skipped.
    """
    priority = {}
    for part in val.split(':'):
        try:
            rule, value = part.split('=')
            priority[rule] = int(value)
        except ValueError:
            continue
    return priority


def _env_to_str(val):
    """Returns the env-string unchanged.

    Used only for ``repeat``: it has long been mapped in the environment but was
    never coerced, so ``THEFUCK_REPEAT`` yields the raw string (the file and CLI
    args still provide a real bool). Kept as-is to avoid changing public config
    semantics.
    """
    return val


# Declarative settings schema -- the single source of truth for every setting.
# Each row fully describes a setting; ``DEFAULT_SETTINGS``, ``ENV_TO_ATTR`` and
# ``SETTING_BY_ATTR`` below are derived from it, so adding a setting (or its env
# var / coercion) is a one-line change that stays in sync across file/env/args.
#
#   attr     -- the ``settings`` attribute name
#   env      -- the ``THEFUCK_*`` environment variable, or None for file-only
#   default  -- the default value (used for file/default loading)
#   from_env -- callable turning the env-string into the attr's type,
#               or None for file-only settings
_Setting = namedtuple('_Setting', ('attr', 'env', 'default', 'from_env'))

SETTINGS_SCHEMA = [
    _Setting('rules', 'THEFUCK_RULES', DEFAULT_RULES, _env_to_rules),
    _Setting('exclude_rules', 'THEFUCK_EXCLUDE_RULES', [], _env_to_rules),
    _Setting('wait_command', 'THEFUCK_WAIT_COMMAND', 3, _env_to_int),
    _Setting('require_confirmation', 'THEFUCK_REQUIRE_CONFIRMATION', True,
             _env_to_bool),
    _Setting('no_colors', 'THEFUCK_NO_COLORS', False, _env_to_bool),
    _Setting('debug', 'THEFUCK_DEBUG', False, _env_to_bool),
    _Setting('priority', 'THEFUCK_PRIORITY', {}, _env_to_priority),
    _Setting('history_limit', 'THEFUCK_HISTORY_LIMIT', None, _env_to_int),
    _Setting('alter_history', 'THEFUCK_ALTER_HISTORY', True, _env_to_bool),
    _Setting('wait_slow_command', 'THEFUCK_WAIT_SLOW_COMMAND', 15, _env_to_int),
    _Setting('slow_commands', 'THEFUCK_SLOW_COMMANDS',
             ['lein', 'react-native', 'gradle', './gradlew', 'vagrant'],
             _env_to_list),
    _Setting('repeat', 'THEFUCK_REPEAT', False, _env_to_str),
    _Setting('instant_mode', 'THEFUCK_INSTANT_MODE', False, _env_to_bool),
    _Setting('num_close_matches', 'THEFUCK_NUM_CLOSE_MATCHES', 3, _env_to_int),
    _Setting('env', None, {'LC_ALL': 'C', 'LANG': 'C', 'GIT_TRACE': '1'}, None),
    _Setting('excluded_search_path_prefixes',
             'THEFUCK_EXCLUDED_SEARCH_PATH_PREFIXES', [], _env_to_list),
]

DEFAULT_SETTINGS = {setting.attr: setting.default for setting in SETTINGS_SCHEMA}

ENV_TO_ATTR = {setting.env: setting.attr
               for setting in SETTINGS_SCHEMA if setting.env}

SETTING_BY_ATTR = {setting.attr: setting for setting in SETTINGS_SCHEMA}

SETTINGS_HEADER = u"""# The Fuck settings file
#
# The rules are defined as in the example bellow:
#
# rules = ['cd_parent', 'git_push', 'python_command', 'sudo']
#
# The default values are as follows. Uncomment and change to fit your needs.
# See https://github.com/nvbn/thefuck#settings for more information.
#

"""

ARGUMENT_PLACEHOLDER = 'THEFUCK_ARGUMENT_PLACEHOLDER'

CONFIGURATION_TIMEOUT = 60

USER_COMMAND_MARK = u'\u200B' * 10

LOG_SIZE_IN_BYTES = 1024 * 1024

LOG_SIZE_TO_CLEAN = 10 * 1024

DIFF_WITH_ALIAS = 0.5

SHELL_LOGGER_SOCKET_ENV = 'SHELL_LOGGER_SOCKET'

SHELL_LOGGER_LIMIT = 5
