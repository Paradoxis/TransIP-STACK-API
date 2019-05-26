import os
from argparse import HelpFormatter


class CustomHelpFormatter(HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, indent_increment=2, max_help_position=7, width=None)

    # noinspection PyProtectedMember
    def _format_action(self, action):
        result = super(CustomHelpFormatter, self)._format_action(action) + "\n"

        if 'show this help message and exit' in result:
            result = result.replace('show', 'Show', 1)

        return result


def directories(directory):
    """Get all directories in a directory recursively"""
    return sorted(set(
        dir_.replace(directory, '', 1).lstrip('/')
        for dir_, _, _ in os.walk(directory)))


def files(directory):
    """Get all files in a directory recursively"""
    for dir_, _, files_ in os.walk(directory):
        dir_ = dir_.replace(directory, '', 1).lstrip('/')
        yield from (os.path.join(dir_, file) for file in files_)
