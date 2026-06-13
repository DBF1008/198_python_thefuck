# -*- encoding: utf-8 -*-


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


# ---------------------------------------------------------------------------
# Env-string coercion functions
#
# Each function takes a raw environment-variable string and returns the
# Python value that should be stored in the settings dict.  They are
# referenced by SETTINGS_SCHEMA below and called by conf.Settings when
# loading settings from the environment.
# ---------------------------------------------------------------------------

def _coerce_bool(val):
    """Coerce env string to bool.  Only 'true' (case-insensitive) → True."""
    return val.lower() == 'true'


def _coerce_int(val):
    """Coerce env string to int."""
    return int(val)


def _coerce_list(val):
    """Coerce colon-separated env string to list of strings."""
    return val.split(':')


def _coerce_rules_list(val):
    """Coerce colon-separated rules list, expanding DEFAULT_RULES token."""
    parts = val.split(':')
    if 'DEFAULT_RULES' in parts:
        parts = DEFAULT_RULES + [r for r in parts if r != 'DEFAULT_RULES']
    return parts


def _coerce_priority_dict(val):
    """Coerce 'key=val:key=val' env string to {str: int} dict.

    Malformed entries (missing '=' or non-integer value) are silently
    skipped.
    """
    result = {}
    for part in val.split(':'):
        try:
            rule, priority = part.split('=')
            result[rule] = int(priority)
        except ValueError:
            continue
    return result


def _coerce_identity(val):
    """Return raw string unchanged (for settings with no special coercion)."""
    return val


# ---------------------------------------------------------------------------
# Declarative settings schema
#
# Single source of truth for every built-in setting.  DEFAULT_SETTINGS
# and ENV_TO_ATTR are *derived* from this list so adding a new setting
# only requires adding one entry here.
#
# Each entry is a 6-tuple:
#   (attr_name,        # str – key in the settings dict
#    default_value,    # any  – value used when no override is present
#    env_var,          # str | None – THEFUCK_* env var name
#    coerce_from_env,  # callable | None – converts env string → Python
#    arg_attr,         # str | None – argparse attribute name
#    arg_transform)    # callable | None – converts arg value → setting
#
# Index helper constants (for readability):
_ATTR = 0
_DEFAULT = 1
_ENV_VAR = 2
_COERCE = 3
_ARG_ATTR = 4
_ARG_XFORM = 5

SETTINGS_SCHEMA = [
    ('rules', DEFAULT_RULES,
     'THEFUCK_RULES', _coerce_rules_list,
     None, None),

    ('exclude_rules', [],
     'THEFUCK_EXCLUDE_RULES', _coerce_rules_list,
     None, None),

    ('wait_command', 3,
     'THEFUCK_WAIT_COMMAND', _coerce_int,
     None, None),

    ('require_confirmation', True,
     'THEFUCK_REQUIRE_CONFIRMATION', _coerce_bool,
     'yes', lambda v: not v),

    ('no_colors', False,
     'THEFUCK_NO_COLORS', _coerce_bool,
     None, None),

    ('debug', False,
     'THEFUCK_DEBUG', _coerce_bool,
     'debug', None),

    ('priority', {},
     'THEFUCK_PRIORITY', _coerce_priority_dict,
     None, None),

    ('history_limit', None,
     'THEFUCK_HISTORY_LIMIT', _coerce_int,
     None, None),

    ('alter_history', True,
     'THEFUCK_ALTER_HISTORY', _coerce_bool,
     None, None),

    ('wait_slow_command', 15,
     'THEFUCK_WAIT_SLOW_COMMAND', _coerce_int,
     None, None),

    ('slow_commands', ['lein', 'react-native', 'gradle',
                       './gradlew', 'vagrant'],
     'THEFUCK_SLOW_COMMANDS', _coerce_list,
     None, None),

    ('repeat', False,
     'THEFUCK_REPEAT', _coerce_bool,
     'repeat', None),

    ('instant_mode', False,
     'THEFUCK_INSTANT_MODE', _coerce_bool,
     None, None),

    ('num_close_matches', 3,
     'THEFUCK_NUM_CLOSE_MATCHES', _coerce_int,
     None, None),

    ('env', {'LC_ALL': 'C', 'LANG': 'C', 'GIT_TRACE': '1'},
     None, None,
     None, None),

    ('excluded_search_path_prefixes', [],
     'THEFUCK_EXCLUDED_SEARCH_PATH_PREFIXES', _coerce_list,
     None, None),
]


# Derived structures — do NOT edit these directly; update SETTINGS_SCHEMA.
DEFAULT_SETTINGS = {entry[_ATTR]: entry[_DEFAULT] for entry in SETTINGS_SCHEMA}

ENV_TO_ATTR = {entry[_ENV_VAR]: entry[_ATTR]
               for entry in SETTINGS_SCHEMA
               if entry[_ENV_VAR] is not None}

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
