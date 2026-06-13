import pytest
import six
import os
from mock import Mock
from thefuck import const


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


class TestSettingsSchema(object):
    """``const.SETTINGS_SCHEMA`` is the single source of truth for every
    setting. These invariants fail loudly if a future setting forgets to keep
    its default / env var / coercion in sync -- the maintainability boundary."""

    def test_defaults_derived_from_schema(self):
        assert const.DEFAULT_SETTINGS == {
            setting.attr: setting.default for setting in const.SETTINGS_SCHEMA}

    def test_env_map_derived_from_schema(self):
        assert const.ENV_TO_ATTR == {
            setting.env: setting.attr
            for setting in const.SETTINGS_SCHEMA if setting.env}

    def test_lookup_derived_from_schema(self):
        assert const.SETTING_BY_ATTR == {
            setting.attr: setting for setting in const.SETTINGS_SCHEMA}

    def test_env_settings_have_callable_coercion(self):
        for setting in const.SETTINGS_SCHEMA:
            if setting.env:
                assert callable(setting.from_env), setting.attr
            else:
                # File-only settings (e.g. ``env``) are never parsed from a
                # string, so they declare no coercion.
                assert setting.from_env is None, setting.attr

    def test_no_duplicate_attrs_or_env_vars(self):
        attrs = [setting.attr for setting in const.SETTINGS_SCHEMA]
        envs = [setting.env for setting in const.SETTINGS_SCHEMA if setting.env]
        assert len(attrs) == len(set(attrs))
        assert len(envs) == len(set(envs))

    def test_every_env_var_has_a_default(self):
        # An env var without a matching default would desync env from
        # file/default loading -- exactly the bug the schema prevents.
        for env, attr in const.ENV_TO_ATTR.items():
            assert attr in const.DEFAULT_SETTINGS, env


# (attr, env var, env-string, file value, expected coerced value). Each row is
# the contract that the file and env sources must agree: both must yield the
# same python value. ``repeat`` is intentionally excluded -- see its own test.
SOURCE_EQUIVALENCE = [
    ('require_confirmation', 'THEFUCK_REQUIRE_CONFIRMATION', 'false',
     False, False),
    ('wait_command', 'THEFUCK_WAIT_COMMAND', '55', 55, 55),
    ('slow_commands', 'THEFUCK_SLOW_COMMANDS', 'lein:gradle',
     ['lein', 'gradle'], ['lein', 'gradle']),
    ('rules', 'THEFUCK_RULES', 'bash:lisp', ['bash', 'lisp'], ['bash', 'lisp']),
    ('priority', 'THEFUCK_PRIORITY', 'vim=10:git=5',
     {'vim': 10, 'git': 5}, {'vim': 10, 'git': 5}),
]


class TestSourceEquivalence(object):
    """A value provided through the settings file and through the equivalent
    environment variable must coerce to the same python value."""

    @pytest.mark.parametrize('attr, env, env_str, file_val, expected',
                             SOURCE_EQUIVALENCE)
    def test_from_file(self, load_source, settings, attr, env, env_str,
                       file_val, expected):
        load_source.return_value = Mock(**{attr: file_val})
        settings.init()
        assert getattr(settings, attr) == expected

    @pytest.mark.parametrize('attr, env, env_str, file_val, expected',
                             SOURCE_EQUIVALENCE)
    def test_from_env(self, load_source, os_environ, settings, attr, env,
                      env_str, file_val, expected):
        os_environ[env] = env_str
        settings.init()
        assert getattr(settings, attr) == expected


@pytest.mark.usefixtures('load_source')
def test_repeat_from_env_is_string_not_bool(os_environ, settings):
    """``THEFUCK_REPEAT`` has always yielded the raw string: it is mapped in the
    environment but was historically never coerced. The schema preserves this
    so public config semantics don't change; the file and CLI args still give a
    real bool (see ``test_repeat_from_file_is_bool``). Pinned so the quirk
    cannot change silently."""
    os_environ['THEFUCK_REPEAT'] = 'true'
    settings.init()
    assert settings.repeat == 'true'
    assert settings.repeat is not True


def test_repeat_from_file_is_bool(load_source, settings):
    load_source.return_value = Mock(repeat=True)
    settings.init()
    assert settings.repeat is True


@pytest.mark.usefixtures('load_source')
def test_args_override_env(os_environ, settings):
    """Args are applied after file and env in ``init``, so they win."""
    os_environ.update({'THEFUCK_REQUIRE_CONFIRMATION': 'true',
                       'THEFUCK_DEBUG': 'false'})
    settings.init(Mock(yes=True, debug=True, repeat=False))
    assert settings.require_confirmation is False  # args yes=True -> not yes
    assert settings.debug is True                  # args win over env 'false'
