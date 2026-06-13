import sys
from collections import OrderedDict
from .conf import settings
from .types import Rule
from .system import Path
from . import logs


def get_loaded_rules(rules_paths):
    """Yields all available rules.

    :type rules_paths: [Path]
    :rtype: Iterable[Rule]

    """
    for path in rules_paths:
        if path.name != '__init__.py':
            rule = Rule.from_path(path)
            if rule and rule.is_enabled:
                yield rule


def get_rules_import_paths():
    """Yields rules import paths, lowest precedence first.

    Bundled rules come first, then third-party contrib packages, and finally
    the user's own rules directory. Later paths override earlier ones by rule
    name (see `get_rule_paths`), so user rules override contrib and bundled
    rules, and contrib rules override bundled ones.

    :rtype: Iterable[Path]

    """
    # Bundled rules:
    yield Path(__file__).parent.joinpath('rules')
    # Packages with third-party rules:
    for path in sys.path:
        for contrib_module in Path(path).glob('thefuck_contrib_*'):
            contrib_rules = contrib_module.joinpath('rules')
            if contrib_rules.is_dir():
                yield contrib_rules
    # Rules defined by user (override bundled and contrib rules):
    yield settings.user_dir.joinpath('rules')


def get_rule_paths():
    """Returns deduplicated paths to rule modules.

    Rules are collected from each import path (lowest precedence first). When
    the same rule name appears in more than one source, the later (higher
    precedence) source wins, so user rules override contrib and bundled rules.
    Only the winning module for a given name is returned, so shadowed modules
    are never imported.

    :rtype: [Path]

    """
    registry = OrderedDict()  # rule name -> Path, last writer wins
    for import_path in get_rules_import_paths():
        for rule_path in sorted(import_path.glob('*.py')):
            if rule_path.name == '__init__.py':
                continue
            name = rule_path.name[:-3]
            if name in registry:
                logs.debug(u'Rule {} from {} overrides {}'.format(
                    name, rule_path, registry[name]))
            registry[name] = rule_path
    return list(registry.values())


def get_rules():
    """Returns all enabled rules, deduplicated by name.

    :rtype: [Rule]

    """
    return sorted(get_loaded_rules(get_rule_paths()),
                  key=lambda rule: rule.priority)


def organize_commands(corrected_commands):
    """Yields sorted commands without duplicates.

    :type corrected_commands: Iterable[thefuck.types.CorrectedCommand]
    :rtype: Iterable[thefuck.types.CorrectedCommand]

    """
    try:
        first_command = next(corrected_commands)
        yield first_command
    except StopIteration:
        return

    without_duplicates = {
        command for command in sorted(
            corrected_commands, key=lambda command: command.priority)
        if command != first_command}

    sorted_commands = sorted(
        without_duplicates,
        key=lambda corrected_command: corrected_command.priority)

    logs.debug(u'Corrected commands: {}'.format(
        ', '.join(u'{}'.format(cmd) for cmd in [first_command] + sorted_commands)))

    for command in sorted_commands:
        yield command


def get_corrected_commands(command):
    """Returns generator with sorted and unique corrected commands.

    :type command: thefuck.types.Command
    :rtype: Iterable[thefuck.types.CorrectedCommand]

    """
    corrected_commands = (
        corrected for rule in get_rules()
        if rule.is_match(command)
        for corrected in rule.get_corrected_commands(command))
    return organize_commands(corrected_commands)
