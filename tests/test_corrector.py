# -*- coding: utf-8 -*-

import pytest
from tests.utils import Rule, CorrectedCommand
from thefuck import corrector, const
from thefuck.system import Path
from thefuck.types import Command
from thefuck.corrector import get_corrected_commands, organize_commands


@pytest.fixture
def glob(mocker):
    results = {}
    mocker.patch('thefuck.system.Path.glob',
                 new_callable=lambda: lambda *_: results.pop('value', []))
    return lambda value: results.update({'value': value})


class TestGetRules(object):
    @pytest.fixture(autouse=True)
    def load_source(self, monkeypatch):
        monkeypatch.setattr('thefuck.types.load_source',
                            lambda x, _: Rule(x))

    def _compare_names(self, rules, names):
        assert {r.name for r in rules} == set(names)

    @pytest.mark.parametrize('paths, conf_rules, exclude_rules, loaded_rules', [
        (['git.py', 'bash.py'], const.DEFAULT_RULES, [], ['git', 'bash']),
        (['git.py', 'bash.py'], ['git'], [], ['git']),
        (['git.py', 'bash.py'], const.DEFAULT_RULES, ['git'], ['bash']),
        (['git.py', 'bash.py'], ['git'], ['git'], [])])
    def test_get_rules(self, glob, settings, paths, conf_rules, exclude_rules,
                       loaded_rules):
        glob([Path(path) for path in paths])
        settings.update(rules=conf_rules,
                        priority={},
                        exclude_rules=exclude_rules)
        rules = corrector.get_rules()
        self._compare_names(rules, loaded_rules)

    def _mock_sources(self, mocker, sources):
        """Mocks rule import paths and their `*.py` files.

        :param sources: list of ``(dir Path, [file Paths])`` in precedence
            order (lowest precedence first). Returns the mocked ``load_source``.

        """
        mocker.patch('thefuck.corrector.get_rules_import_paths',
                     return_value=[directory for directory, _ in sources])
        files = {str(directory): paths for directory, paths in sources}
        mocker.patch('thefuck.system.Path.glob',
                     new=lambda self, *_: files.get(str(self), []))
        return mocker.patch('thefuck.types.load_source',
                            side_effect=lambda name, path: Rule(name))

    def test_get_rules_import_paths_user_last(self, mocker, settings):
        """User rules dir must be loaded last so it overrides the others."""
        settings.user_dir = Path('/fake/user')
        # No contrib packages on `sys.path`:
        mocker.patch('thefuck.system.Path.glob', new=lambda *_: [])
        paths = list(corrector.get_rules_import_paths())
        assert paths[0] == Path(corrector.__file__).parent.joinpath('rules')
        assert paths[-1] == Path('/fake/user').joinpath('rules')

    def test_user_rules_override_bundled(self, mocker, settings):
        """A user rule shadows a bundled rule with the same name."""
        bundled = Path('/bundled/rules/git_push.py')
        user = Path('/user/rules/git_push.py')
        load_source = self._mock_sources(mocker, [
            (bundled.parent, [bundled]),
            (user.parent, [user])])
        rules = corrector.get_rules()
        assert [rule.name for rule in rules] == ['git_push']
        # The winning (user) module is the only one imported:
        load_source.assert_called_once_with('git_push', str(user))

    def test_user_rules_override_contrib(self, mocker, settings):
        """A user rule shadows a contrib rule with the same name."""
        contrib = Path('/site-packages/thefuck_contrib_foo/rules/git_push.py')
        user = Path('/user/rules/git_push.py')
        load_source = self._mock_sources(mocker, [
            (contrib.parent, [contrib]),
            (user.parent, [user])])
        rules = corrector.get_rules()
        assert [rule.name for rule in rules] == ['git_push']
        load_source.assert_called_once_with('git_push', str(user))

    def test_no_duplicates_preserves_load_order(self, mocker, settings):
        """Without name clashes every rule loads, in source then name order."""
        bundled_dir = Path('/bundled/rules')
        user_dir = Path('/user/rules')
        # Bundled files passed unsorted to prove they are sorted per source:
        load_source = self._mock_sources(mocker, [
            (bundled_dir, [bundled_dir.joinpath('git.py'),
                           bundled_dir.joinpath('apt.py')]),
            (user_dir, [user_dir.joinpath('my_rule.py')])])
        rules = corrector.get_rules()
        assert [rule.name for rule in rules] == ['apt', 'git', 'my_rule']
        assert load_source.call_count == 3



def test_get_rules_rule_exception(mocker, glob):
    load_source = mocker.patch('thefuck.types.load_source',
                               side_effect=ImportError("No module named foo..."))
    glob([Path('git.py')])
    assert not corrector.get_rules()
    load_source.assert_called_once_with('git', 'git.py')


def test_get_corrected_commands(mocker):
    command = Command('test', 'test')
    rules = [Rule(match=lambda _: False),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: x.script + '!', priority=100),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: [x.script + '@', x.script + ';'],
                  priority=60)]
    mocker.patch('thefuck.corrector.get_rules', return_value=rules)
    assert ([cmd.script for cmd in get_corrected_commands(command)]
            == ['test!', 'test@', 'test;'])


def test_organize_commands():
    """Ensures that the function removes duplicates and sorts commands."""
    commands = [CorrectedCommand('ls'), CorrectedCommand('ls -la', priority=9000),
                CorrectedCommand('ls -lh', priority=100),
                CorrectedCommand(u'echo café', priority=200),
                CorrectedCommand('ls -lh', priority=9999)]
    assert list(organize_commands(iter(commands))) \
        == [CorrectedCommand('ls'), CorrectedCommand('ls -lh', priority=100),
            CorrectedCommand(u'echo café', priority=200),
            CorrectedCommand('ls -la', priority=9000)]
