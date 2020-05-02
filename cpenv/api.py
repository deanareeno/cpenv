# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

# Standard library imports
import os
from collections import OrderedDict
import warnings

# Local imports
from . import hooks, utils, compat
from .module import Module, ModuleSpec, module_header
from .repos import Repo, LocalRepo
from .resolver import (
    ResolveError,
    Resolver,
    Activator,
    Copier,
    Localizer,
)
from .vendor import appdirs, yaml


__all__ = [
    'activate',
    'deactivate',
    'clone',
    'create',
    'localize',
    'publish',
    'resolve',
    'set_home_path',
    'get_home_path',
    'get_home_modules_path',
    'get_cache_path',
    'get_user_path',
    'get_user_modules_path',
    'get_modules',
    'get_module_paths',
    'add_module_path',
    'get_active_modules',
    'add_active_module',
    'remove_active_module',
    'get_repos',
    'get_repo',
    'add_repo',
    'remove_repo',
    'sort_modules',
]
_registry = {
    'repos': OrderedDict(),
}
_active_modules = []


def resolve(*requirements):
    '''Resolve a list of module requirements.'''

    resolver = Resolver(get_repos())
    return resolver.resolve(requirements)


def localize(*requirements, to_repo='home', overwrite=False):
    '''Localize a list of requirements.'''

    to_repo = get_repo(to_repo)

    # Resolve modules
    resolver = Resolver(get_repos())
    module_specs = resolver.resolve(requirements)

    localizer = Localizer(to_repo)
    modules = localizer.localize(module_specs, overwrite)
    return modules

def activate(*requirements):
    '''Resolve and active a list of module requirements.

    Usage:
        >>> cpenv.activate('moduleA', 'moduleB')

    Arguments:
        requirements (List[str]): List of module requirements

    Returns:
        list of Module objects that have been activated
    '''

    # Resolve modules
    resolver = Resolver(get_repos())
    module_specs = resolver.resolve(requirements)

    # Activate modules
    activator = Activator()
    modules = activator.activate(module_specs)
    return modules


def deactivate():
    '''Deactivates an environment by restoring all env vars to a clean state
    stored prior to activating environments
    '''
    # TODO:
    # Probably need to store a clean environment prior to activate.
    # In practice it's uncommon to activate then deactivate in the same
    # python session.
    pass


def create(where, name, version, **kwargs):
    '''Create a new module.

    Arguments:
        where (str): Path to new module
        name (str): Name of module
        version (str): Version of module
        description (str): Optional description of module
        author (str): Optional author of module
        email (str): Optional email address of author
        requires (list): Optional modules that this module depends on
        environment (dict): Optional environment variables

    Returns:
        Module object
    '''

    # Setup configuration defaults
    config = OrderedDict([
        ('name', name),
        ('version', version),
        ('description', kwargs.get('description', '')),
        ('author', kwargs.get('author', '')),
        ('email', kwargs.get('email', '')),
        ('requires', kwargs.get('requires', [])),
        ('environment', kwargs.get('environment', {})),
    ])

    # Check if module already exists
    where = utils.normpath(where)
    if os.path.isdir(where):
        raise OSError('Module already exists at "%s"' % where)

    # Create a Module object - does not yet exist on disk
    module = Module(where, name, version)

    # Run global precreate hook
    # Allows users to inject data into a config prior to creating a new module
    hooks.run_global_hook('pre_create', module, config)

    # Create module folder structure
    utils.ensure_path_exists(where)
    utils.ensure_path_exists(where + '/hooks')

    data = module_header + yaml.dump(
        dict(config),
        default_flow_style=False,
        sort_keys=False,
    )
    with open(utils.normpath(where, 'module.yml'), 'w') as f:
        f.write(data)

    # Run global postcreate hook
    # Allows users to perform some action after a module is created
    hooks.run_global_hook('post_create', module)

    return module


def remove(module, from_repo=None):
    '''Remove a module.'''

    if isinstance(module, Module):
        return module.remove()

    if isinstance(module, ModuleSpec):
        return module.repo.remove(module)

    if from_repo is None:
        raise ValueError('from_repo is required when removing module by name.')

    if isinstance(from_repo, compat.string_types):
        from_repo = get_repo(from_repo)

    module_spec = from_repo.find(module)[0]
    return from_repo.remove(module_spec)


def clone(module, from_repo=None, where=None, overwrite=False):
    '''Clone a module for local development.

    A typical development workflow using clone and publish:
        1. clone a module
        2. make changes
        3. test changes
        4. increment version in module.yml
        5. publish a new version of your module
    '''

    if not isinstance(module, (Module, ModuleSpec)):
        if from_repo is None:
            resolver = Resolver(get_repos())
            module_spec = resolver.resolve([module])[0]
        else:
            from_repo = get_repo(from_repo)
            module_spec = from_repo.find(module)[0]

    module = module_spec.repo.download(
        module_spec,
        where=utils.normpath(where or '.', module_spec.real_name),
        overwrite=overwrite,
    )

    return module


def publish(module, to_repo='home', overwrite=False):
    '''Publish a module to the specified repository.'''

    to_repo = get_repo(to_repo)

    if isinstance(module, compat.string_types):
        resolver = Resolver(get_repos())
        module = resolver.resolve([module])[0]

    if isinstance(module, ModuleSpec):
        if not isinstance(module.repo, LocalRepo):
            raise ValueError('Can only from modules in local repos.')
        else:
            module = Module(module.path)

    published = to_repo.upload(module, overwrite)
    return published


def copy(module, from_repo, to_repo, overwrite=False):
    '''Copy a module from one repo to another.'''

    from_repo = get_repo(from_repo)
    to_repo = get_repo(to_repo)

    # Resolve module
    resolver = Resolver([from_repo])
    module_spec = resolver.resolve([module])[0]

    copier = Copier(to_repo)
    copied = copier.copy([module_spec], overwrite)
    return copied


def get_active_modules():
    '''Returns a list of active :class:`Module` s'''

    return _active_modules


def add_active_module(module):
    '''Add a module to CPENV_ACTIVE_MODULES environment variable.

    Arguments:
        module (Module): Module to add to CPENV_ACTIVE_MODULES
    '''

    if module not in _active_modules:
        _active_modules.append(module)

    _active_modules.sort(key=lambda m: m.real_name)

    module_names = os.pathsep.join([m.real_name for m in _active_modules])
    os.environ['CPENV_ACTIVE_MODULES'] = str(module_names)


def remove_active_module(module):
    '''Remove a module from CPENV_ACTIVE_MODULES environment variable.

    Arguments:
        module (Module): Module to remove from CPENV_ACTIVE_MODULES
    '''

    if module in _active_modules:
        _active_modules.remove(module)

    module_names = os.pathsep.join([m.real_name for m in _active_modules])
    os.environ['CPENV_ACTIVE_MODULES'] = str(module_names)


def set_home_path(path):
    '''Convenient function used to set the CPENV_HOME environment variable.'''

    # Set new home path
    home = utils.normpath(path)
    os.environ['CPENV_HOME'] = home
    _init_home_path(home)

    # Add new LocalRepo
    update_repo(LocalRepo('home', get_home_modules_path()))

    return home


def _init_home_path(home):
    home_modules = utils.normpath(home, 'modules')
    home_cache = utils.normpath(home, 'cache')

    utils.ensure_path_exists(home)
    utils.ensure_path_exists(home_modules)
    utils.ensure_path_exists(home_cache)


def get_home_path():
    '''Returns the cpenv home directory.

    Default home paths:
        win - C:/ProgramData/cpenv
        mac - /Library/Application Support/cpenv
        linux - /usr/local/share/cpenv OR /usr/share/cpenv
    '''

    home_default = appdirs.site_data_dir('cpenv', appauthor=False)
    home = utils.normpath(os.getenv('CPENV_HOME', home_default))
    return home


def get_home_modules_path():
    '''Return the modules directory within the cpenv home directory.

    Default home modules paths:
        win - C:/ProgramData/cpenv/modules
        mac - /Library/Application Support/cpenv/modules
        linux - /usr/local/share/cpenv OR /usr/share/cpenv/modules
    '''

    return utils.normpath(get_home_path(), 'modules')


def get_cache_path(*paths):
    '''Return the cpenv cache directory within the cpenv home directory.

    Default cache paths:
        win - C:/ProgramData/cpenv/cache
        mac - /Library/Application Support/cpenv/cache
        linux - /usr/local/share/cpenv OR /usr/share/cpenv/cache

    Arguments:
        *paths (str) - List of paths to join with cache path
    '''

    return utils.normpath(get_home_path(), 'cache', *paths)


def _init_user_path(user):
    '''Initialize user path.'''

    user_modules = utils.normpath(user, 'modules')
    utils.ensure_path_exists(user)
    utils.ensure_path_exists(user_modules)


def get_user_path():
    '''Returns the cpenv user directory.

    Default user paths:
        win - C:/Users/<username>/AppData/Roaming/cpenv
        mac - ~/Library/Application Support/cpenv
        linux - ~/.local/share/cpenv
    '''

    user_default = appdirs.user_data_dir('cpenv', appauthor=False)
    user = utils.normpath(user_default)

    return user


def get_user_modules_path():
    '''Returns the modules directory within the cpenv user directory.

    Default user paths:
        win - C:/Users/<username>/AppData/Roaming/cpenv/modules
        mac - ~/Library/Application Support/cpenv/modules
        linux - ~/.local/share/cpenv/modules
    '''

    return utils.normpath(get_user_path(), 'modules')


def get_module_paths():
    '''Returns a list of paths used to lookup local modules.

    The list of lookup paths contains:
        1. use modules path
        2. home modules path
        3. paths in CPENV_MODULES environment variable
    '''

    module_paths = [utils.normpath(os.getcwd()), get_user_modules_path()]

    cpenv_home_modules = get_home_modules_path()
    if cpenv_home_modules not in module_paths:
        module_paths.append(cpenv_home_modules)

    cpenv_modules_path = os.environ.get('CPENV_MODULES', None)
    if cpenv_modules_path:
        for module_path in cpenv_modules_path.split(os.pathsep):
            if module_path not in module_paths:
                module_paths.append(utils.normpath(module_path))

    return module_paths


def add_module_path(path):
    '''Add an additional lookup path for local modules.'''

    path = utils.normpath(path)
    module_paths = []

    # Get existing module lookup paths
    cpenv_modules = os.environ.get('CPENV_MODULES', '').split(os.pathsep)
    for module_path in cpenv_modules:
        if module_path:
            module_paths.append(module_path)

    # Add new module lookup path
    if path not in module_paths:
        module_paths.append(path)
        add_repo(LocalRepo(path, path))

    # Persist in CPENV_MODULES
    os.environ['CPENV_MODULES'] = os.pathsep.join(module_paths)

    return module_paths


def get_modules(*requirements):
    '''Returns a list of available modules.'''

    if requirements:
        resolver = Resolver(get_repos())
        return sort_modules(resolver.resolve(requirements))

    modules = []

    for repo in get_repos():
        modules.extend(repo.list())

    return sort_modules(list(modules))


def sort_modules(modules, reverse=False):
    return sorted(
        modules,
        key=lambda m: (m.real_name, m.version),
        reverse=reverse
    )


def update_repo(repo):
    '''Update a registered repo.'''

    _registry.update({repo.name: repo})


def add_repo(repo, idx=None):
    '''Register a Repo.

    Provide an idx to insert the Repo rather than append.
    '''

    if repo.name not in _registry['repos']:
        if idx is not None:
            items = list(_registry['repos'].items())
            items.insert(idx, (repo.name, repo))
            _registry['repos'] = OrderedDict(items)
        else:
            _registry['repos'][repo.name] = repo


def remove_repo(repo):
    '''Unregister a Repo.'''

    _registry['repos'].pop(repo.name, None)


def get_repo(name, **query):
    '''Get a repo by specifying an attribute to lookup'''

    if isinstance(name, Repo):
        return name

    query['name'] = name

    for repo in get_repos():
        if all([getattr(repo, k, False) == v for k, v in query.items()]):
            return repo


def get_repos():
    '''Get a list of all registered Repos.'''

    return list(_registry['repos'].values())


def _init():
    '''Responsible for initially configuraing cpenv.'''

    _init_home_path(get_home_path())
    _init_user_path(get_user_path())

    # Register all LocalRepos
    for path in get_module_paths():
        if path == utils.normpath(os.getcwd()):
            name = 'cwd'
        elif path == get_home_modules_path():
            name = 'home'
        elif path == get_user_modules_path():
            name = 'user'
        else:
            name = path
        add_repo(LocalRepo(name, path))

    # Set _active_modules from CPENV_ACTIVE_MODULES
    unresolved = []
    resolver = Resolver(get_repos())
    active_modules = os.getenv('CPENV_ACTIVE_MODULES')
    if active_modules:
        for module in active_modules.split(os.pathsep):
            if module:
                try:
                    resolved = resolver.resolve([module])[0]
                    _active_modules.append(resolved)
                except ResolveError:
                    unresolved.append(module)

    if unresolved:
        warnings.warn(
            'Unable to resolve %s from $CPENV_ACTIVE_MODULES:' % unresolved
        )
