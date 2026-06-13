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


# ---------------------------------------------------------------------------
# Rule dedup / override tests
# ---------------------------------------------------------------------------

# A minimal valid rule module source.  ``priority`` can be overridden by
# writing a different value into the file.
_RULE_TEMPLATE = """\
{priority_line}
enabled_by_default = {enabled}

def match(command):
    return True

def get_new_command(command):
    return {cmd!r}
"""


def _write_rule(directory, name, priority=1000, cmd='fixed',
                enabled=True):
    """Write a minimal rule file and return its Path."""
    priority_line = 'priority = {}'.format(priority) if priority != 1000 else ''
    source = _RULE_TEMPLATE.format(
        priority_line=priority_line,
        enabled=enabled,
        cmd=cmd,
    )
    rule_path = directory.joinpath(name + '.py')
    rule_path.write_text(source)
    return rule_path


@pytest.fixture
def rule_dirs(tmp_path):
    """Create bundled / contrib / user rule directories and return them."""
    bundled = tmp_path / 'bundled' / 'rules'
    contrib = tmp_path / 'contrib' / 'rules'
    user = tmp_path / 'user' / 'rules'
    for d in (bundled, contrib, user):
        d.mkdir(parents=True)
    return bundled, contrib, user


@pytest.fixture(autouse=True)
def _patch_import_paths(rule_dirs, monkeypatch):
    """Point ``get_rules_import_paths`` at the temp directories."""
    bundled, contrib, user = rule_dirs

    def _fake_paths():
        yield bundled
        yield contrib
        yield user

    monkeypatch.setattr('thefuck.corrector.get_rules_import_paths', _fake_paths)


class TestRuleDedup(object):
    """Verify that same-named rules from different sources are deduplicated
    and that later sources (user > contrib > bundled) win."""

    def test_bundled_overridden_by_user(self, rule_dirs, settings):
        """A user rule with the same name as a bundled rule must replace it."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'git_push', priority=1000, cmd='bundled-fix')
        _write_rule(user, 'git_push', priority=500, cmd='user-fix')

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        assert names.count('git_push') == 1, \
            'Expected exactly one git_push rule, got {}'.format(names.count('git_push'))

        git_push = [r for r in rules if r.name == 'git_push'][0]
        assert git_push.priority == 500, \
            'User rule priority (500) should override bundled (1000)'
        # The user rule's get_new_command should be the one that survived
        assert git_push.get_new_command(None) == 'user-fix'

    def test_contrib_overridden_by_user(self, rule_dirs, settings):
        """A user rule with the same name as a contrib rule must replace it."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(contrib, 'npm_install', priority=800, cmd='contrib-fix')
        _write_rule(user, 'npm_install', priority=200, cmd='user-fix')

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        assert names.count('npm_install') == 1
        npm_rule = [r for r in rules if r.name == 'npm_install'][0]
        assert npm_rule.priority == 200
        assert npm_rule.get_new_command(None) == 'user-fix'

    def test_bundled_overridden_by_contrib(self, rule_dirs, settings):
        """A contrib rule with the same name as a bundled rule replaces it."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'apt_get', priority=1000, cmd='bundled-fix')
        _write_rule(contrib, 'apt_get', priority=700, cmd='contrib-fix')

        rules = corrector.get_rules()
        apt_rules = [r for r in rules if r.name == 'apt_get']

        assert len(apt_rules) == 1
        assert apt_rules[0].priority == 700
        assert apt_rules[0].get_new_command(None) == 'contrib-fix'

    def test_no_duplicates_distinct_names(self, rule_dirs, settings):
        """Rules with distinct names from all sources load without issue."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'git_push', priority=1000, cmd='bundled-git')
        _write_rule(bundled, 'apt_get', priority=900, cmd='bundled-apt')
        _write_rule(contrib, 'npm_install', priority=800, cmd='contrib-npm')
        _write_rule(user, 'my_custom', priority=100, cmd='user-custom')

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        assert len(names) == len(set(names)), \
            'Expected no duplicates, got {}'.format(names)
        assert set(names) == {'git_push', 'apt_get', 'npm_install', 'my_custom'}

    def test_priority_sorting_preserved(self, rule_dirs, settings):
        """After dedup, rules are still sorted by priority."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'low_prio', priority=2000)
        _write_rule(user, 'high_prio', priority=100)
        _write_rule(contrib, 'mid_prio', priority=500)

        rules = corrector.get_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)
        assert [r.name for r in rules] == ['high_prio', 'mid_prio', 'low_prio']

    def test_exclude_rules_still_works(self, rule_dirs, settings):
        """Excluded rules are dropped even when present in multiple sources."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={},
                        exclude_rules=['git_push'])

        _write_rule(bundled, 'git_push', priority=1000)
        _write_rule(user, 'git_push', priority=500)
        _write_rule(bundled, 'apt_get', priority=900)

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        assert 'git_push' not in names
        assert 'apt_get' in names

    def test_settings_rules_filter_still_works(self, rule_dirs, settings):
        """Only rules listed in settings.rules survive the is_enabled check."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=['apt_get'], priority={}, exclude_rules=[])

        _write_rule(bundled, 'git_push', priority=1000)
        _write_rule(user, 'apt_get', priority=500)

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        assert names == ['apt_get']

    def test_settings_priority_override(self, rule_dirs, settings):
        """settings.priority overrides the priority declared in the rule file."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES,
                        priority={'git_push': 42},
                        exclude_rules=[])

        _write_rule(bundled, 'git_push', priority=1000)

        rules = corrector.get_rules()
        git_push = [r for r in rules if r.name == 'git_push'][0]
        assert git_push.priority == 42

    def test_user_disabled_rule_overrides_bundled(self, rule_dirs, settings):
        """If user provides a disabled rule with the same name as a bundled
        enabled rule, the user version wins and is then filtered out by
        is_enabled — effectively disabling the bundled rule too."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'git_push', priority=1000, enabled=True)
        _write_rule(user, 'git_push', priority=500, enabled=False)

        rules = corrector.get_rules()
        names = [r.name for r in rules]

        # The user override wins; the rule is disabled so it's gone entirely.
        assert 'git_push' not in names

    def test_all_three_sources_same_name(self, rule_dirs, settings):
        """When all three sources provide the same rule, user wins."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'shared', priority=1000, cmd='bundled')
        _write_rule(contrib, 'shared', priority=700, cmd='contrib')
        _write_rule(user, 'shared', priority=300, cmd='user')

        rules = corrector.get_rules()
        shared = [r for r in rules if r.name == 'shared']

        assert len(shared) == 1
        assert shared[0].priority == 300
        assert shared[0].get_new_command(None) == 'user'

    def test_empty_source_directory(self, rule_dirs, settings):
        """An empty source directory contributes no rules."""
        bundled, contrib, user = rule_dirs
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'only_bundled', priority=500)
        # contrib and user dirs are empty

        rules = corrector.get_rules()
        names = [r.name for r in rules]
        assert names == ['only_bundled']

    def test_nonexistent_source_directory(self, monkeypatch, tmp_path, settings):
        """A missing source directory is silently skipped."""
        bundled = tmp_path / 'rules'
        bundled.mkdir()
        missing = tmp_path / 'nonexistent' / 'rules'

        def _fake_paths():
            yield bundled
            yield missing

        monkeypatch.setattr('thefuck.corrector.get_rules_import_paths', _fake_paths)
        settings.update(rules=const.DEFAULT_RULES, priority={}, exclude_rules=[])

        _write_rule(bundled, 'only_rule', priority=100)

        rules = corrector.get_rules()
        assert len(rules) == 1
        assert rules[0].name == 'only_rule'
