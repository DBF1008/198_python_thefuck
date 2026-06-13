import sys
from .conf import settings
from .types import Rule
from .system import Path
from . import logs


def get_rules_import_paths():
    """Yields all rules import paths in source-priority order (lowest first).

    Load order:
      1. Bundled rules          (lowest priority)
      2. Third-party contrib packages
      3. User-defined rules     (highest priority)

    When multiple sources provide a rule with the same filename, the
    later source in this sequence wins (last-writer-wins).

    :rtype: Iterable[Path]

    """
    # Bundled rules (lowest priority):
    yield Path(__file__).parent.joinpath('rules')
    # Packages with third-party rules (middle priority):
    for path in sys.path:
        for contrib_module in Path(path).glob('thefuck_contrib_*'):
            contrib_rules = contrib_module.joinpath('rules')
            if contrib_rules.is_dir():
                yield contrib_rules
    # Rules defined by user (highest priority):
    yield settings.user_dir.joinpath('rules')


def _load_rules_from_directory(directory):
    """Yields (rule_name, Rule) pairs from a single directory.

    Skips ``__init__.py`` and any paths that fail to load.

    :type directory: Path
    :rtype: Iterable[(str, Rule)]

    """
    if not directory.is_dir():
        return
    for rule_path in sorted(directory.glob('*.py')):
        if rule_path.name == '__init__.py':
            continue
        rule = Rule.from_path(rule_path)
        if rule is not None:
            yield rule.name, rule, rule_path


def get_rules():
    """Returns all enabled rules, deduplicated by name.

    Rules are collected from every source returned by
    :func:`get_rules_import_paths` in order.  When two sources
    provide a rule with the same name the later (higher-priority)
    source wins — e.g. a user rule overrides a bundled rule.

    Excluded rules (``settings.exclude_rules``) are dropped during
    :meth:`Rule.from_path`.  After deduplication only enabled rules
    are kept and the result is sorted by ``rule.priority``.

    :rtype: [Rule]

    """
    registry = {}  # name -> (Rule, source_path)

    for source_directory in get_rules_import_paths():
        for name, rule, source_path in _load_rules_from_directory(source_directory):
            if name in registry:
                _, prev_path = registry[name]
                logs.debug(
                    u'Rule {} from {} overrides earlier rule from {}'.format(
                        name, source_path, prev_path))
            registry[name] = (rule, source_path)

    return sorted(
        (rule for rule, _ in registry.values() if rule.is_enabled),
        key=lambda rule: rule.priority)


def get_loaded_rules(rules_paths):
    """Yields all available rules from a flat list of paths.

    .. note::

       This helper does **not** deduplicate by name.  Prefer
       :func:`get_rules` which implements the full registry/dedup
       pipeline.  Kept for backward compatibility with callers that
       build their own path list.

    :type rules_paths: [Path]
    :rtype: Iterable[Rule]

    """
    for path in rules_paths:
        if path.name != '__init__.py':
            rule = Rule.from_path(path)
            if rule and rule.is_enabled:
                yield rule


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
