# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

# Standard library imports
import os
import sys

# Local imports
import cpenv
from cpenv import ResolveError, api, cli, shell, utils
from cpenv.module import parse_module_path


class CpenvCLI(cli.CLI):
    '''Cpenv Command Line Interface.'''

    name = 'cpenv'
    usage = 'cpenv [-h] <command> [<args>...]'

    def commands(self):
        return [
            Activate(self),
            Clone(self),
            Create(self),
            List(self),
            Localize(self),
            Publish(self),
            Remove(self),
            Version(self),
        ]


class Activate(cli.CLI):
    '''Activate a list of modules.'''

    usage = 'cpenv [-h] [<modules>...]'

    def setup_parser(self, parser):
        parser.add_argument(
            'modules',
            help='Space separated list of modules.',
            nargs='*',
        )

    def run(self, args):
        cli.echo()
        cli.echo('- Resolving modules...', end='')
        try:
            activated_modules = api.activate(*args.modules)
        except ResolveError:
            cli.echo('OOPS!')
            cli.echo()
            cli.echo('Error: failed to resolve %s' % args.modules)
            sys.exit(1)
        cli.echo('OK!')

        cli.echo()
        for module in activated_modules:
            cli.echo('  ' + module.real_name)
        cli.echo()

        cli.echo('- Launching subshell...')
        cli.echo()
        shell.launch('[*]')


class Clone(cli.CLI):
    '''Clone a module for development.

    The following repos are available by default:
        home - Local repo pointing to a computer-wide cpenv directory
        user - Local repo pointing to a user-specific cpenv directory

    For a full listing of available repos use the repo cli command:
        cpenv repo list
    '''

    def setup_parser(self, parser):
        parser.add_argument(
            'module',
            help='Module to clone.',
        )
        parser.add_argument(
            'where',
            help='Destination directory. (./<module_name>)',
            nargs='?',
            default=None,
        )
        parser.add_argument(
            '--from_repo',
            help='Specific repo to clone from.',
            default=None,
        )
        parser.add_argument(
            '--overwrite',
            help='Overwrite the destination directory. (False)',
            action='store_true',
        )

    def run(self, args):

        cli.echo('- Cloning %s...' % args.module, end='')
        try:
            module = api.clone(
                args.module,
                args.where,
                args.from_repo,
                args.overwrite,
            )
        except ResolveError:
            cli.echo()
            cli.echo('Error: Could not find module to clone.')
            sys.exit(1)

        cli.echo('OK!')
        cli.echo()
        cli.echo('Navigate to the following folder to make changes:')
        cli.echo('  ' + module.path)
        cli.echo()
        cli.echo("Use one of the following commands to publish your changes:")
        cli.echo('  cpenv publish .')
        cli.echo('  cpenv publish . --to_repo="repo_name"')


class Create(cli.CLI):
    '''Create a new module.'''

    def setup_parser(self, parser):
        parser.add_argument(
            'where',
            help='Path to new module',
        )
        parser.add_argument(
            '--name',
            help='Name of new module',
            default='',
        )
        parser.add_argument(
            '--version',
            help='Version of the new module',
            default='',
        )
        parser.add_argument(
            '--description',
            help='Details about the module',
            default='',
        )
        parser.add_argument(
            '--author',
            help='Author of the module',
            default='',
        )
        parser.add_argument(
            '--email',
            help="Author's email address",
            default='',
        )

    def run(self, args):
        cli.echo()
        where = utils.normpath(args.where)
        name, version = parse_module_path(where)

        api.create(
            where=where,
            name=args.name or name,
            version=args.version or version.string,
            description=args.description,
            author=args.author,
            email=args.email,
        )


class List(cli.CLI):
    '''List active and available modules.'''

    def setup_parser(self, parser):
        parser.add_argument(
            'matching',
            help='Space separated list of modules.',
            nargs='?',
            default=None,
        )
        parser.add_argument(
            '--verbose', '-v',
            help='Print more module info.',
            action='store_true',
        )

    def run(self, args):
        cli.echo()
        active_modules = api.get_active_modules()
        if args.matching:
            active_modules = [
                m for m in active_modules
                if args.matching == m.name
            ]

        if active_modules:
            cli.echo(cli.format_columns(
                '[*] Active',
                [m.real_name for m in api.sort_modules(active_modules)],
            ))

        cli.echo()
        all_modules = api.get_modules(matching=args.matching)
        available_modules = set(all_modules) - set(active_modules)
        if available_modules:
            cli.echo(cli.format_columns(
                '[ ] Available Modules',
                [m.real_name for m in api.sort_modules(available_modules)],
            ))
        else:
            cli.echo('No modules available.')


class Localize(cli.CLI):
    '''Localize a list of modules.

    Downloads modules from a remote Repo and places them in the home LocalRepo
    by default. Use the --to_repo option to specify a LocalRepo.
    '''

    def setup_parser(self, parser):
        parser.add_argument(
            'modules',
            help='Space separated list of modules.',
            nargs='*',
        )
        parser.add_argument(
            '--to_repo', '-r',
            help='Specific repo to localize to. (first match)',
            default=None,
        )
        parser.add_argument(
            '--overwrite', '-o',
            help='Overwrite the destination directory. (False)',
            action='store_true',
        )

    def run(self, args):

        cli.echo()

        if args.to_repo:
            to_repo = api.get_repo(name=args.to_repo)
        else:
            repos = [r for r in repos if isinstance(repo, LocalRepo)]
            to_repo = prompt_for_repo(
                [r for r in api.get_repos() if isinstance(repo, LocalRepo)],
                'Choose a repo to localize to',
                default_repo_name='home',
            )

        cli.echo()
        cli.echo(
            '- Localizing %s to %s...' % (args.modules, to_repo.name),
            end='',
        )
        modules = api.localize(*args.modules, to_repo, args.overwrite)
        cli.echo('OK!')
        cli.echo()

        cli.echo()
        cli.echo('Localized the following modules:')
        for module in modules:
            click.echo('  %s - %s' % (module.real_name, module.path))


class Publish(cli.CLI):
    '''Publish a module to a repo.'''

    def setup_parser(self, parser):
        parser.add_argument(
            'module',
            help='Path of module to publish. (".")',
            default='.',
            nargs='?',
        )
        parser.add_argument(
            '--to_repo',
            help='Specific repo to clone from.',
            default=None,
        )
        parser.add_argument(
            '--overwrite',
            help='Overwrite the destination directory. (False)',
            action='store_true',
        )

    def run(self, args):

        cli.echo()

        if args.to_repo:
            to_repo = api.get_repo(name=args.to_repo)
        else:
            to_repo = prompt_for_repo(
                api.get_repos(),
                'Choose a repo to publish to',
                default_repo_name='home',
            )

        cli.echo()
        cli.echo(
            '- Publishing %s to %s...' % (args.module, to_repo.name),
            end='',
        )
        module = api.publish(args.module, to_repo, args.overwrite)
        cli.echo('OK!', end='\n\n')

        cli.echo('Activate it using the following command:')
        cli.echo('  cpenv activate %s' % module.real_name)


class Remove(cli.CLI):
    '''Permanently remove a module from a repo.'''

    def setup_parser(self, parser):
        parser.add_argument(
            'module',
            help='Module to remove.',
        )
        parser.add_argument(
            '--from_repo',
            help='Specific repo to remove from.',
            default=None,
        )
        parser.add_argument(
            '--quiet',
            help='Overwrite the destination directory. (False)',
            action='store_true',
        )

    def run(self, args):

        cli.echo()

        if args.from_repo:
            from_repo = api.get_repo(name=args.from_repo)
        else:
            from_repo = prompt_for_repo(
                api.get_repos(),
                'Choose a repo to remove module from',
                default_repo_name='home',
            )

        cli.echo()
        cli.echo(
            '- Finding module %s to %s...' % (args.module, from_repo.name),
            end='',
        )
        module = from_repo.find_module(args.module)
        if not module:
            click.echo('ER!', end='\n\n')
            click.echo(
                'Error: %s not found in %s' % (args.module, from_repo.name)
            )
            sys.exit(1)
        cli.echo('OK!')
        cli.echo()
        cli.echo('%s - %s' % (module.name, module.path))
        cli.echo()
        choice = cli.prompt('Delete this module?(y/n)')
        if choice.lower() not in ['y', 'yes', 'yup']:
            cli.echo('Aborted.')
            sys.exit(1)

        cli.echo('- Removing module...', end='')
        api.remove(module, from_repo)
        cli.echo('OK!', end='\n\n')

        cli.echo('Successfully removed module.')


class Version(cli.CLI):
    '''Show version information.'''

    def run(self, args):

        cli.echo()
        cli.echo(cli.format_section(
            'Version Info',
            [
                ('version', cpenv.__version__),
                ('url', cpenv.__url__),
                ('package', utils.normpath(os.path.dirname(cpenv.__file__))),
                ('path', api.get_module_paths()),
            ]
        ), end='\n\n')

        # List package versions
        dependencies = []
        try:
            import Qt
            dependencies.extend([
                ('Qt.py', Qt.__version__),
                ('Qt Binding', Qt.__binding__ + '-' + Qt.__binding_version__),
            ])
        except ImportError:
            pass

        if not dependencies:
            return

        cli.echo(cli.format_section('Dependencies', dependencies), end='\n\n')


def prompt_for_repo(repos, message, default_repo_name='home'):
    '''Prompt a user to select a repository'''

    for i, from_repo in enumerate(repos):
        if from_repo.name == default_repo_name:
            default = i
        if from_repo.name == from_repo.path:
            line = '  [{}] {}'.format(i, from_repo.path)
        else:
            line = '  [{}] {} - {}'.format(
                i,
                from_repo.name,
                from_repo.path,
            )
        cli.echo(line)

    # Prompt user to choose a repo defaults to home
    cli.echo()
    choice = cli.prompt('{}: [{}]'.format(message, default))

    if not choice:
        choice = default
    else:
        choice = int(choice)
        if choice > len(repos) - 1:
            cli.echo()
            cli.echo('Error: {} is not a valid choice'.format(choice))
            sys.exit(1)

    # Get the repo the user chose
    return repos[choice]


def main():
    cli.run(CpenvCLI, sys.argv[1:])


if __name__ == '__main__':
    main()
