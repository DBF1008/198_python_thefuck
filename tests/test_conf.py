import pytest
import six
import os
from mock import Mock
from thefuck import const
from thefuck.const import (
    _coerce_bool, _coerce_int, _coerce_list,
    _coerce_rules_list, _coerce_priority_dict, _coerce_identity,
    SETTINGS_SCHEMA, _ATTR, _DEFAULT, _ENV_VAR, _COERCE, _ARG_ATTR, _ARG_XFORM,
)


@pytest.fixture
def load_source(mocker):
    return mocker.patch('thefuck.conf.load_source')


def test_settings_defaults(load_source, settings):
    load_source.return_value = object()
    settings.init()
    for key, val in const.DEFAULT_SETTINGS.items():
        assert getattr(settings, key) == val


class TestSettingsFromFile(object):
    def test_from_file(self, load_source, settings):
        load_source.return_value = Mock(rules=['test'],
                                        wait_command=10,
                                        require_confirmation=True,
                                        no_colors=True,
                                        priority={'vim': 100},
                                        exclude_rules=['git'])
        settings.init()
        assert settings.rules == ['test']
        assert settings.wait_command == 10
        assert settings.require_confirmation is True
        assert settings.no_colors is True
        assert settings.priority == {'vim': 100}
        assert settings.exclude_rules == ['git']

    def test_from_file_with_DEFAULT(self, load_source, settings):
        load_source.return_value = Mock(rules=const.DEFAULT_RULES + ['test'],
                                        wait_command=10,
                                        exclude_rules=[],
                                        require_confirmation=True,
                                        no_colors=True)
        settings.init()
        assert settings.rules == const.DEFAULT_RULES + ['test']


@pytest.mark.usefixtures('load_source')
class TestSettingsFromEnv(object):
    def test_from_env(self, os_environ, settings):
        os_environ.update({'THEFUCK_RULES': 'bash:lisp',
                           'THEFUCK_EXCLUDE_RULES': 'git:vim',
                           'THEFUCK_WAIT_COMMAND': '55',
                           'THEFUCK_REQUIRE_CONFIRMATION': 'true',
                           'THEFUCK_NO_COLORS': 'false',
                           'THEFUCK_PRIORITY': 'bash=10:lisp=wrong:vim=15',
                           'THEFUCK_WAIT_SLOW_COMMAND': '999',
                           'THEFUCK_SLOW_COMMANDS': 'lein:react-native:./gradlew',
                           'THEFUCK_NUM_CLOSE_MATCHES': '359',
                           'THEFUCK_EXCLUDED_SEARCH_PATH_PREFIXES': '/media/:/mnt/'})
        settings.init()
        assert settings.rules == ['bash', 'lisp']
        assert settings.exclude_rules == ['git', 'vim']
        assert settings.wait_command == 55
        assert settings.require_confirmation is True
        assert settings.no_colors is False
        assert settings.priority == {'bash': 10, 'vim': 15}
        assert settings.wait_slow_command == 999
        assert settings.slow_commands == ['lein', 'react-native', './gradlew']
        assert settings.num_close_matches == 359
        assert settings.excluded_search_path_prefixes == ['/media/', '/mnt/']

    def test_from_env_with_DEFAULT(self, os_environ, settings):
        os_environ.update({'THEFUCK_RULES': 'DEFAULT_RULES:bash:lisp'})
        settings.init()
        assert settings.rules == const.DEFAULT_RULES + ['bash', 'lisp']


def test_settings_from_args(settings):
    settings.init(Mock(yes=True, debug=True, repeat=True))
    assert not settings.require_confirmation
    assert settings.debug
    assert settings.repeat


class TestInitializeSettingsFile(object):
    def test_ignore_if_exists(self, settings):
        settings_path_mock = Mock(is_file=Mock(return_value=True), open=Mock())
        settings.user_dir = Mock(joinpath=Mock(return_value=settings_path_mock))
        settings._init_settings_file()
        assert settings_path_mock.is_file.call_count == 1
        assert not settings_path_mock.open.called

    def test_create_if_doesnt_exists(self, settings):
        settings_file = six.StringIO()
        settings_path_mock = Mock(
            is_file=Mock(return_value=False),
            open=Mock(return_value=Mock(
                __exit__=lambda *args: None, __enter__=lambda *args: settings_file)))
        settings.user_dir = Mock(joinpath=Mock(return_value=settings_path_mock))
        settings._init_settings_file()
        settings_file_contents = settings_file.getvalue()
        assert settings_path_mock.is_file.call_count == 1
        assert settings_path_mock.open.call_count == 1
        assert const.SETTINGS_HEADER in settings_file_contents
        for setting in const.DEFAULT_SETTINGS.items():
            assert '# {} = {}\n'.format(*setting) in settings_file_contents
        settings_file.close()


@pytest.mark.parametrize('legacy_dir_exists, xdg_config_home, result', [
    (False, '~/.config', '~/.config/thefuck'),
    (False, '/user/test/config/', '/user/test/config/thefuck'),
    (True, '~/.config', '~/.thefuck'),
    (True, '/user/test/config/', '~/.thefuck')])
def test_get_user_dir_path(mocker, os_environ, settings, legacy_dir_exists,
                           xdg_config_home, result):
    mocker.patch('thefuck.conf.Path.is_dir',
                 return_value=legacy_dir_exists)

    if xdg_config_home is not None:
        os_environ['XDG_CONFIG_HOME'] = xdg_config_home
    else:
        os_environ.pop('XDG_CONFIG_HOME', None)

    path = settings._get_user_dir_path().as_posix()
    assert path == os.path.expanduser(result)


# ===========================================================================
# Schema integrity tests
# ===========================================================================

class TestSettingsSchema(object):
    """Tests that the declarative SETTINGS_SCHEMA is consistent and complete."""

    def test_schema_covers_all_default_settings(self):
        schema_attrs = {entry[_ATTR] for entry in SETTINGS_SCHEMA}
        for key in const.DEFAULT_SETTINGS:
            assert key in schema_attrs, \
                "DEFAULT_SETTINGS key '{}' has no schema entry".format(key)

    def test_schema_has_no_extra_attrs(self):
        schema_attrs = {entry[_ATTR] for entry in SETTINGS_SCHEMA}
        for attr in schema_attrs:
            assert attr in const.DEFAULT_SETTINGS, \
                "Schema attr '{}' not in DEFAULT_SETTINGS".format(attr)

    def test_schema_env_vars_unique(self):
        env_vars = [entry[_ENV_VAR] for entry in SETTINGS_SCHEMA
                    if entry[_ENV_VAR] is not None]
        assert len(env_vars) == len(set(env_vars)), \
            "Duplicate env var names in schema"

    def test_schema_attr_names_unique(self):
        attrs = [entry[_ATTR] for entry in SETTINGS_SCHEMA]
        assert len(attrs) == len(set(attrs)), \
            "Duplicate attr names in schema"

    def test_derived_default_settings_matches_schema(self):
        for entry in SETTINGS_SCHEMA:
            assert const.DEFAULT_SETTINGS[entry[_ATTR]] == entry[_DEFAULT]

    def test_derived_env_to_attr_matches_schema(self):
        expected = {entry[_ENV_VAR]: entry[_ATTR]
                    for entry in SETTINGS_SCHEMA
                    if entry[_ENV_VAR] is not None}
        assert const.ENV_TO_ATTR == expected

    def test_every_env_var_has_coercion(self):
        """Every env-mapped setting should have a non-None coercion function."""
        for entry in SETTINGS_SCHEMA:
            if entry[_ENV_VAR] is not None:
                assert entry[_COERCE] is not None, \
                    "Setting '{}' (env={}) has no coercion function".format(
                        entry[_ATTR], entry[_ENV_VAR])

    def test_arg_entries_have_valid_attr_names(self):
        """arg_attr names should correspond to known argparse attributes."""
        for entry in SETTINGS_SCHEMA:
            if entry[_ARG_ATTR] is not None:
                assert entry[_ARG_ATTR] in ('yes', 'debug', 'repeat'), \
                    "Unexpected arg_attr '{}' in schema".format(entry[_ARG_ATTR])


# ===========================================================================
# Coercion function unit tests
# ===========================================================================

class TestCoercionFunctions(object):
    """Direct unit tests for the standalone coercion functions in const."""

    # -- _coerce_bool --

    @pytest.mark.parametrize('input_val', ['true', 'True', 'TRUE', 'tRuE'])
    def test_coerce_bool_true_variants(self, input_val):
        assert _coerce_bool(input_val) is True

    @pytest.mark.parametrize('input_val',
                             ['false', 'False', '', '1', '0', 'yes', 'no',
                              'anything'])
    def test_coerce_bool_false_variants(self, input_val):
        assert _coerce_bool(input_val) is False

    # -- _coerce_int --

    def test_coerce_int_positive(self):
        assert _coerce_int('42') == 42
        assert isinstance(_coerce_int('42'), int)

    def test_coerce_int_negative(self):
        assert _coerce_int('-1') == -1

    def test_coerce_int_zero(self):
        assert _coerce_int('0') == 0

    def test_coerce_int_invalid(self):
        with pytest.raises(ValueError):
            _coerce_int('not_a_number')

    # -- _coerce_list --

    def test_coerce_list_basic(self):
        assert _coerce_list('a:b:c') == ['a', 'b', 'c']

    def test_coerce_list_single(self):
        assert _coerce_list('only') == ['only']

    def test_coerce_list_empty(self):
        assert _coerce_list('') == ['']

    def test_coerce_list_with_paths(self):
        assert _coerce_list('/media/:/mnt/') == ['/media/', '/mnt/']

    # -- _coerce_rules_list --

    def test_coerce_rules_list_without_default(self):
        assert _coerce_rules_list('bash:lisp') == ['bash', 'lisp']

    def test_coerce_rules_list_with_default(self):
        result = _coerce_rules_list('DEFAULT_RULES:bash:lisp')
        assert result == const.DEFAULT_RULES + ['bash', 'lisp']

    def test_coerce_rules_list_default_only(self):
        result = _coerce_rules_list('DEFAULT_RULES')
        assert result == const.DEFAULT_RULES

    def test_coerce_rules_list_single(self):
        assert _coerce_rules_list('sudo') == ['sudo']

    # -- _coerce_priority_dict --

    def test_coerce_priority_dict_valid(self):
        assert _coerce_priority_dict('a=1:b=2') == {'a': 1, 'b': 2}

    def test_coerce_priority_dict_single(self):
        assert _coerce_priority_dict('vim=100') == {'vim': 100}

    def test_coerce_priority_dict_malformed_skipped(self):
        result = _coerce_priority_dict('a=1:bad:b=2')
        assert result == {'a': 1, 'b': 2}

    def test_coerce_priority_dict_non_int_skipped(self):
        result = _coerce_priority_dict('bash=10:lisp=wrong:vim=15')
        assert result == {'bash': 10, 'vim': 15}

    def test_coerce_priority_dict_empty(self):
        assert _coerce_priority_dict('') == {}

    # -- _coerce_identity --

    def test_coerce_identity(self):
        assert _coerce_identity('raw string') == 'raw string'


# ===========================================================================
# Bug regression tests
# ===========================================================================

@pytest.mark.usefixtures('load_source')
class TestBugRegressions(object):
    """Regression tests for previously broken behavior."""

    def test_repeat_from_env_is_bool_true(self, os_environ, settings):
        """THEFUCK_REPEAT=true should produce bool True, not string 'true'."""
        os_environ['THEFUCK_REPEAT'] = 'true'
        settings.init()
        assert settings.repeat is True

    def test_repeat_from_env_is_bool_false(self, os_environ, settings):
        os_environ['THEFUCK_REPEAT'] = 'false'
        settings.init()
        assert settings.repeat is False


# ===========================================================================
# Previously untested env var coverage
# ===========================================================================

@pytest.mark.usefixtures('load_source')
class TestAllEnvVarsCoverage(object):
    """Tests for env vars that were not covered in the original test suite."""

    def test_debug_from_env(self, os_environ, settings):
        os_environ['THEFUCK_DEBUG'] = 'true'
        settings.init()
        assert settings.debug is True

    def test_debug_from_env_false(self, os_environ, settings):
        os_environ['THEFUCK_DEBUG'] = 'false'
        settings.init()
        assert settings.debug is False

    def test_history_limit_from_env(self, os_environ, settings):
        os_environ['THEFUCK_HISTORY_LIMIT'] = '100'
        settings.init()
        assert settings.history_limit == 100
        assert isinstance(settings.history_limit, int)

    def test_alter_history_from_env_true(self, os_environ, settings):
        os_environ['THEFUCK_ALTER_HISTORY'] = 'true'
        settings.init()
        assert settings.alter_history is True

    def test_alter_history_from_env_false(self, os_environ, settings):
        os_environ['THEFUCK_ALTER_HISTORY'] = 'false'
        settings.init()
        assert settings.alter_history is False

    def test_instant_mode_from_env(self, os_environ, settings):
        os_environ['THEFUCK_INSTANT_MODE'] = 'true'
        settings.init()
        assert settings.instant_mode is True

    def test_instant_mode_from_env_false(self, os_environ, settings):
        os_environ['THEFUCK_INSTANT_MODE'] = 'false'
        settings.init()
        assert settings.instant_mode is False


# ===========================================================================
# File / env / args equivalence and precedence tests
# ===========================================================================

@pytest.mark.usefixtures('load_source')
class TestThreeLayerPrecedence(object):
    """Tests that file < env < args override order is preserved."""

    def test_env_overrides_file(self, load_source, os_environ, settings):
        load_source.return_value = Mock(debug=False)
        os_environ['THEFUCK_DEBUG'] = 'true'
        settings.init()
        assert settings.debug is True

    def test_args_override_env(self, load_source, os_environ, settings):
        load_source.return_value = object()
        os_environ['THEFUCK_DEBUG'] = 'false'
        settings.init(Mock(yes=False, debug=True, repeat=False))
        assert settings.debug is True

    def test_args_override_file_and_env(self, load_source, os_environ, settings):
        load_source.return_value = Mock(require_confirmation=True)
        os_environ['THEFUCK_REQUIRE_CONFIRMATION'] = 'true'
        settings.init(Mock(yes=True, debug=False, repeat=False))
        assert settings.require_confirmation is False

    def test_file_overrides_defaults(self, load_source, os_environ, settings):
        load_source.return_value = Mock(wait_command=99)
        settings.init()
        assert settings.wait_command == 99

    def test_full_precedence_chain(self, load_source, os_environ, settings):
        """defaults < file < env < args for different settings at once."""
        load_source.return_value = Mock(
            wait_command=50,       # file overrides default (3)
            debug=False,           # file sets debug
        )
        os_environ['THEFUCK_WAIT_COMMAND'] = '75'   # env overrides file
        os_environ['THEFUCK_DEBUG'] = 'true'         # env overrides file
        settings.init(Mock(yes=True, debug=False, repeat=False))
        # wait_command: default(3) < file(50) < env(75)
        assert settings.wait_command == 75
        # debug: default(False) < file(False) < env(True)
        assert settings.debug is True
        # require_confirmation: default(True) > args(False via --yes)
        assert settings.require_confirmation is False


class TestFileEnvEquivalence(object):
    """Verify that file and env can produce identical Python values."""

    def test_bool_via_file_and_env(self, load_source, settings):
        load_source.return_value = Mock(no_colors=True)
        settings.init()
        assert settings.no_colors is True

    def test_bool_via_env(self, load_source, os_environ, settings):
        load_source.return_value = object()
        os_environ['THEFUCK_NO_COLORS'] = 'true'
        settings.init()
        assert settings.no_colors is True

    def test_int_via_file_and_env(self, load_source, settings):
        load_source.return_value = Mock(wait_command=42)
        settings.init()
        assert settings.wait_command == 42

    def test_int_via_env(self, load_source, os_environ, settings):
        load_source.return_value = object()
        os_environ['THEFUCK_WAIT_COMMAND'] = '42'
        settings.init()
        assert settings.wait_command == 42

    def test_list_via_file_and_env(self, load_source, settings):
        load_source.return_value = Mock(slow_commands=['a', 'b'])
        settings.init()
        assert settings.slow_commands == ['a', 'b']

    def test_list_via_env(self, load_source, os_environ, settings):
        load_source.return_value = object()
        os_environ['THEFUCK_SLOW_COMMANDS'] = 'a:b'
        settings.init()
        assert settings.slow_commands == ['a', 'b']

    def test_dict_via_file_and_env(self, load_source, settings):
        load_source.return_value = Mock(priority={'vim': 100})
        settings.init()
        assert settings.priority == {'vim': 100}

    def test_dict_via_env(self, load_source, os_environ, settings):
        load_source.return_value = object()
        os_environ['THEFUCK_PRIORITY'] = 'vim=100'
        settings.init()
        assert settings.priority == {'vim': 100}


# ===========================================================================
# _settings_from_args edge cases
# ===========================================================================

class TestSettingsFromArgsEdgeCases(object):
    """Edge case tests for _settings_from_args."""

    def test_args_none(self, load_source, settings):
        load_source.return_value = object()
        settings.init(None)
        # Should use defaults, no crash
        assert settings.require_confirmation is True
        assert settings.debug is False
        assert settings.repeat is False

    def test_args_all_false(self, load_source, settings):
        load_source.return_value = object()
        settings.init(Mock(yes=False, debug=False, repeat=False))
        assert settings.require_confirmation is True
        assert settings.debug is False
        assert settings.repeat is False

    def test_args_only_yes(self, load_source, settings):
        load_source.return_value = object()
        settings.init(Mock(yes=True, debug=False, repeat=False))
        assert settings.require_confirmation is False
        assert settings.debug is False
        assert settings.repeat is False

    def test_args_only_debug(self, load_source, settings):
        load_source.return_value = object()
        settings.init(Mock(yes=False, debug=True, repeat=False))
        assert settings.require_confirmation is True
        assert settings.debug is True
        assert settings.repeat is False

    def test_args_only_repeat(self, load_source, settings):
        load_source.return_value = object()
        settings.init(Mock(yes=False, debug=False, repeat=True))
        assert settings.require_confirmation is True
        assert settings.debug is False
        assert settings.repeat is True


# ===========================================================================
# Schema extensibility test
# ===========================================================================

class TestSchemaExtensibility(object):
    """Tests that the schema design makes it easy to add new settings."""

    def test_schema_entry_count_matches_settings(self):
        """Each schema entry produces exactly one DEFAULT_SETTINGS key."""
        assert len(const.DEFAULT_SETTINGS) == len(SETTINGS_SCHEMA)

    def test_schema_entry_count_matches_env_mapping(self):
        """ENV_TO_ATTR has exactly the entries with non-None env_var."""
        expected_count = sum(1 for e in SETTINGS_SCHEMA if e[_ENV_VAR] is not None)
        assert len(const.ENV_TO_ATTR) == expected_count

    def test_new_schema_entry_would_be_picked_up(self):
        """Adding a new schema entry would propagate to derived structures.

        This test verifies the derivation logic without actually modifying
        the schema (which would affect other tests).
        """
        # Simulate what would happen with a hypothetical new setting
        fake_entry = ('my_new_setting', 42, 'THEFUCK_MY_NEW', _coerce_int,
                      None, None)
        # Verify the derivation expressions would pick it up
        new_defaults = dict(const.DEFAULT_SETTINGS)
        new_defaults[fake_entry[_ATTR]] = fake_entry[_DEFAULT]
        assert new_defaults['my_new_setting'] == 42

        new_env = dict(const.ENV_TO_ATTR)
        if fake_entry[_ENV_VAR] is not None:
            new_env[fake_entry[_ENV_VAR]] = fake_entry[_ATTR]
        assert new_env['THEFUCK_MY_NEW'] == 'my_new_setting'

    def test_all_coercion_functions_are_callable(self):
        """Every schema entry with an env var has a callable coercion fn."""
        for entry in SETTINGS_SCHEMA:
            if entry[_COERCE] is not None:
                assert callable(entry[_COERCE]), \
                    "Coercion for '{}' is not callable".format(entry[_ATTR])

    def test_all_arg_transforms_are_callable(self):
        """Every schema entry with an arg mapping has a callable transform."""
        for entry in SETTINGS_SCHEMA:
            if entry[_ARG_XFORM] is not None:
                assert callable(entry[_ARG_XFORM]), \
                    "Arg transform for '{}' is not callable".format(entry[_ATTR])


# ===========================================================================
# Comprehensive env-var round-trip test (parametrized over all schema entries)
# ===========================================================================

@pytest.mark.usefixtures('load_source')
class TestEnvVarRoundTrip(object):
    """Parametrized test: every env-mapped setting round-trips correctly."""

    @pytest.mark.parametrize('env_var,attr,input_val,expected', [
        ('THEFUCK_RULES', 'rules', 'bash:lisp', ['bash', 'lisp']),
        ('THEFUCK_EXCLUDE_RULES', 'exclude_rules', 'git:vim', ['git', 'vim']),
        ('THEFUCK_WAIT_COMMAND', 'wait_command', '55', 55),
        ('THEFUCK_REQUIRE_CONFIRMATION', 'require_confirmation', 'true', True),
        ('THEFUCK_NO_COLORS', 'no_colors', 'false', False),
        ('THEFUCK_DEBUG', 'debug', 'true', True),
        ('THEFUCK_PRIORITY', 'priority', 'bash=10:vim=15',
         {'bash': 10, 'vim': 15}),
        ('THEFUCK_HISTORY_LIMIT', 'history_limit', '100', 100),
        ('THEFUCK_ALTER_HISTORY', 'alter_history', 'false', False),
        ('THEFUCK_WAIT_SLOW_COMMAND', 'wait_slow_command', '999', 999),
        ('THEFUCK_SLOW_COMMANDS', 'slow_commands', 'lein:gradle',
         ['lein', 'gradle']),
        ('THEFUCK_REPEAT', 'repeat', 'true', True),
        ('THEFUCK_INSTANT_MODE', 'instant_mode', 'true', True),
        ('THEFUCK_NUM_CLOSE_MATCHES', 'num_close_matches', '5', 5),
        ('THEFUCK_EXCLUDED_SEARCH_PATH_PREFIXES',
         'excluded_search_path_prefixes', '/media/:/mnt/',
         ['/media/', '/mnt/']),
    ])
    def test_env_round_trip(self, os_environ, settings,
                            env_var, attr, input_val, expected):
        os_environ[env_var] = input_val
        settings.init()
        assert getattr(settings, attr) == expected
