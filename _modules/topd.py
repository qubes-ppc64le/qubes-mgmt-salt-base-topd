# -*- coding: utf-8 -*-
#
# vim: set ts=4 sw=4 sts=4 et :
'''
:maintainer:    Jason Mehring <nrgaway@gmail.com>
:maturity:      new
:depends:       none
:platform:      all

Formula Plugin to manage formulas.
'''

'''
- Maybe what we will do is soft-link config files to salt-config/formulas/SALTENV
  and use that location for parsing file?
  - Not sure if that is needed though
  - Need to consider though that this should work with a salt-master;
    so accessing files in /formulas dir will need a client-cache?

- Hrmm, maybe just load all the config files as pillar data; Once that is
  done once; it can be accessed by this and other modules much easier...
  - For instance; include complete file_roots, pillar roots, and then
    just receive from pillar data!

- So each function will call load first, or have some way... maybe via
  virtual() that will pre-load stuff... beware it may not get loaded b4
  pillars load though, so may need load
'''
'''
Developer:
--local state.highstate
--local bind.mount modules states utils saltenv=base

--no-color --local topd.debug
--no-color --local topd.report
--no-color --local topd.enabled
--no-color --local topd.status

Now:
--local topd.is_enabled topd.base|salt.directories topd.dev|bind

Should be:
    --local topd.is_enabled base|salt.directories dev|bind
Or:
    --local topd.is_enabled salt.directories test
    --local topd.is_enabled bind saltenv=dev
'''


# Import python libs
#import collections
import copy
import fnmatch
import functools
import itertools
import logging
import os

# Import salt libs
import salt.loader
import salt.fileclient
import salt.template
import salt.pillar
#import salt.utils
#import StringIO

# XXX: convert items to six
import salt.ext.six as six

#from salt.template import compile_template
#from salt.state import BaseHighState, State
from salt.exceptions import SaltRenderError

from salt.utils.odict import (
    OrderedDict,
    DefaultOrderedDict
    )

# Import custom libs
#import salt_path_utils as path_utils
import fileinfo
import matcher
from pathutils import PathUtils
from toputils import TopUtils

# Enable logging
log = logging.getLogger(__name__)

try:
    __context__['salt.loaded.ext.module.topd'] = True
except NameError:
    __context__ = {}

##ENABLE_UNKNOWN = False
##DEFAULT_PILLAR_DIR = '/srv/pillar'
##DEFAULT_FILE_DIR = '/srv/salt'
##SALT_CONFIG_DIR = '/srv/pillar/salt-config'
##PILLAR_ROOTS = 'pillar-roots'
##FILE_ROOTS = 'file-roots'

# Define the module's virtual name
__virtualname__ = 'topd'


def __virtual__():
    '''
    '''
    return __virtualname__


##def get_formula_dirs(env=None):
##    formula_dirs = {}
##    git_opts = __salt__['pillar.get']('salt_formulas:git_opts',  {})
##    for saltenv, items in git_opts.items():
##        if not env or env == saltenv:
##            formula_dirs[saltenv] = items.get('basedir', None)
##    return formula_dirs


##def formula_basedirs(env=None):
##    basedirs = {}
##    git_opts = __salt__['pillar.get']('salt_formulas:git_opts',  {})
##    for saltenv, items in git_opts.items():
##        if not env or env == saltenv:
##            basedirs[saltenv] = items.get('basedir', None)
##    return basedirs

def coerce_to_list(value):
    '''Converts value to a list.
    '''
    if not value:
        value = []
    elif isinstance(value, str):
        value = [value,]
    elif isinstance(value, tuple):
        value = list(value)
    return value

def get_opts(opts=None):
    if not opts:
        opts = __opts__
    return opts


def is_pillar(opts=None):
    opts = get_opts(opts)
    return True if opts['file_roots'] is opts['pillar_roots'] else False


def get_renderers(opts=None):
    if 'renderers' in __context__:
        return __context__['renderers']

    opts = get_opts(opts)
    renderers = salt.loader.render(opts, salt.loader.minion_mods(opts))
    __context__['renderers'] = renderers
    return renderers


def get_fileclient(opts=None):
    if 'fileclient' in __context__:
        return __context__['fileclient']

    opts = get_opts(opts)
    fileclient = salt.fileclient.get_file_client(opts, is_pillar(opts))
    __context__['fileclient'] = fileclient
    return fileclient


def get_environment(opts=None):
    opts = get_opts(opts)
    if is_pillar(opts):
        return 'pillarenv'
    else:
        return 'environment'


def get_pillar(opts=None):
    '''
    Getting the pillar will set file_roots to pillar_roots to allow jinja
    search path to find includes within pillar directory
    '''
    if 'pillar' in __context__:
        return __context__['pillar']

    opts = get_opts(opts)
    pillar = salt.pillar.get_pillar(
        opts,
        __grains__,
        opts['id'],
        opts[get_environment(opts)],
    )
    __context__['pillar'] = pillar
    return pillar


##def load_config():
##    pass
##    #    __salt__['file.find'](path=path, name='config.sls', maxdepth=1)


##def enabled(path, saltenv=None, default=ENABLE_UNKNOWN):
##    '''
##    If a config.sls file does not exist, use default.
##    '''
##    config = os.path.join(path, 'config.sls')
##    if os.path.exists(config):
##        salt_data = _render(config, saltenv=saltenv or 'base')[0]
##        if 'enable' in salt_data:
##            return salt_data['enable']
##    return default



def toputils():
    return TopUtils(__opts__)

'''
create -- create from existing tops
status -- include states iwthout tops files?
filter add/remove/list  -- custom override filters -- pillar dir?

create a state to implement tops files; can be pillar based?
topd    base topd dir; overrides go here; named saltenv|statename
  base  enabed - links to existing tops; or auto created
  all
  vm
'''
def debug(*varargs, **kwargs):
    '''
    XXX: Remove me
    Debug function used to call and test various functions.
    '''
    pathutils = PathUtils(__opts__)
    toputils = TopUtils(__opts__)
    tops = toputils.tops()

    #info = pathutils.report(tops)

    info = pathutils.salt_path(tops)

    return info


#def get(*varargs, **kwargs):
#    paths = kwargs.get('paths', varargs)
#    saltenv = kwargs.get('saltenv', None)
#    return TopUtils(__opts__).get(paths, saltenv)


# XXX:
# Missing salt states?  Only pillar shown?
def enabled(*varargs, **kwargs):
    paths = kwargs.get('paths', varargs)
    saltenv = kwargs.get('saltenv', None)
    return TopUtils(__opts__).enabled(paths, saltenv)


def disabled(*varargs, **kwargs):
    paths = kwargs.get('paths', varargs)
    saltenv = kwargs.get('saltenv', None)
    return TopUtils(__opts__).disabled(paths, saltenv)


def is_enabled(*varargs, **kwargs):
    paths = kwargs.get('paths', varargs)
    saltenv = kwargs.get('saltenv', None)
    return TopUtils(__opts__).is_enabled(paths, saltenv)


def report(*varargs, **kwargs):
    paths = kwargs.get('paths', varargs)
    saltenv = kwargs.get('saltenv', None)
    return TopUtils(__opts__).report(paths, saltenv)


def status(*varargs, **kwargs):
    '''
    List status of one or all top files.  If saltenv is not provided, all
    environments will be searched
    '''
    paths = kwargs.get('paths', varargs)
    saltenv = kwargs.get('saltenv', None)

    if paths or saltenv:
        return TopUtils(__opts__).tops(paths, saltenv)
    else:
        return TopUtils(__opts__).report()

def get_envs(opts=None):
    '''
    Pull the file server environments out of the master options
    '''
    opts = get_opts(opts)
    envs = set(['base'])
    if 'file_roots' in opts:
        envs.update(list(opts['file_roots']))
    return envs


##def gather_avail(opts=None):
##    '''
##    Gather the lists of available sls data from the master
##    '''
##    avail = {}
##    opts = get_opts(opts)
##    client = get_fileclient(opts)
##
##    for saltenv in get_envs(opts):
##        avail[saltenv] = client.list_states(saltenv)
##    return avail


def render(path, opts=None, saltenv='base', sls=''):
    opts = get_opts(opts)

    renderers = get_renderers(opts)
    client = get_fileclient(opts)
    #pillar = get_pillar(opts)

    template = client.cache_file(path, saltenv)
    if template:
        salt_data = salt.template.compile_template(
                template,
                renderers,
                opts['renderer'],
                saltenv=saltenv,
                sls=sls,
                _pillar_rend=is_pillar(opts)
            )
        return salt_data
    return OrderedDict()


# XXX: Look at passing pathutils since it loads with each pass
def render_top(opts):
    '''
    Gather the top files
    '''
    tops = DefaultOrderedDict(list)
    include = DefaultOrderedDict(list)
    done = DefaultOrderedDict(list)

    pathutils = PathUtils(opts)
    renderers = get_renderers(opts)
    #client = get_fileclient(opts)
    environment = get_environment(opts)

    # Gather initial top files
    if opts['top_file_merging_strategy'] == 'same' and not opts[environment]:
        if not opts['default_top']:
            raise SaltRenderError('Top file merge strategy set to same, but no default_top '
                      'configuration option was set')
        opts[environment] = opts['default_top']

    if opts[environment]:
        salt_data = render(opts['state_top'], opts=opts, saltenv=opts[environment])
        if salt_data:
            tops[opts[environment]] = salt_data
    elif opts['top_file_merging_strategy'] == 'merge':
        if opts.get('state_top_saltenv', False):
            saltenv = opts['state_top_saltenv']
            salt_data = render(opts['state_top'], opts=opts, saltenv=saltenv)
            if salt_data:
                tops[saltenv].append(salt_data)
            else:
                log.debug('No contents loaded for env: {0}'.format(saltenv))
        else:
            for saltenv in get_envs(opts):
                salt_data = render(opts['state_top'], opts=opts, saltenv=saltenv)
                if salt_data:
                    tops[saltenv].append(salt_data)
                else:
                    log.debug('No contents loaded for env: {0}'.format(saltenv))

    # Search initial top files for includes
    for saltenv, ctops in six.iteritems(tops):
        for ctop in ctops:
            if 'include' not in ctop:
                continue
            for sls in ctop['include']:
                include[saltenv].append(sls)
            ctop.pop('include')

    # Go through the includes and pull out the extra tops and add them
    while include:
        pops = []
        for saltenv, states in six.iteritems(include):
            pops.append(saltenv)
            if not states:
                continue
            for sls_match in states:
                #avail = gather_avail(opts)
                avail = pathutils.states(saltenv)
                for sls in fnmatch.filter(avail[saltenv], sls_match):
                    if sls in done[saltenv]:
                        continue
                    #path = client.get_state(sls, saltenv).get('source', False)
                    #path = pathutils.salt_path(sls, saltenv)
                    #salt_data = render(path, opts=opts, saltenv=saltenv)
                    salt_data = render(sls, opts=opts, saltenv=saltenv)
                    if salt_data:
                        tops[saltenv].append(salt_data)
                    else:
                        log.debug('No contents loaded for include {0} env: {1}'.format(path, saltenv))
                    done[saltenv].append(sls)
        for saltenv in pops:
            if saltenv in include:
                include.pop(saltenv)
    return tops


# XXX: Look at only including pillar_roots?;
#      See if there are ever any cache_roots
def merge_tops(tops):
    '''
    Cleanly merge the top files

    Top structure
    OrderedDict - str(saltenv)
        OrderedDict - str(target)
            list [(str state...}]
            list [(OrderedDict matches), (str state..)]
    '''
    top = DefaultOrderedDict(OrderedDict)

    # List of complied tops
    for _top in tops:
        # Compiled tops of one tops file
        for ctops in six.itervalues(_top):
            # Targets in a list
            for ctop in ctops:
                for saltenv, targets in six.iteritems(ctop):
                    if saltenv == 'include':
                        continue
                    try:
                        for tgt in targets:
                            if tgt not in top[saltenv]:
                                top[saltenv][tgt] = ctop[saltenv][tgt]
                                continue
                            matches = []
                            states = set()
                            for comp in top[saltenv][tgt] + ctop[saltenv][tgt]:
                                if isinstance(comp, dict) and comp not in matches:
                                    matches.append(comp)
                                if isinstance(comp, six.string_types):
                                    states.add(comp)
                            top[saltenv][tgt] = matches
                            top[saltenv][tgt].extend(list(states))
                    except TypeError:
                        raise SaltRenderError('Unable to render top file. No targets found.')
    return top


def get_top(path, opts=None, saltenv='base'):
    '''
    Returns all merged tops from path.
    '''
    tops = []

    #opts = copy.deepcopy(get_opts(opts))
    opts = get_opts(opts)

    #pathutils = __salt__.pathutils.pathutils(opts)
    pathutils = PathUtils(opts)
    files = pathutils.files(
        saltenv,
        relpath='{0}*.top'.format(pathutils.relpath(path, saltenv)))

    try:
        for path in files:
            opts['state_top_saltenv'] = 'base'
            opts['state_top'] = pathutils.salt_path(path)
            tops.append(render_top(opts))
        tops = dict(merge_tops(tops))
    except SaltRenderError:
        tops = {}

    return tops


##def file_roots(saltenv=None):
##    '''
##    Returns all active file roots.
##    '''
##    # Check if 'file_roots' is cached
##    if 'file_roots' in __context__ and 'file_roots_env' in __context__:
##        if __context__['file_roots_env'] == saltenv:
##            return __context__['file_roots']
##
##    file_roots = OrderedDict()
##    default_file_dir = __salt__['pillar.get']('default_file_dir', DEFAULT_FILE_DIR)
##    salt_config_dir = __salt__['pillar.get']('salt_config_dir', SALT_CONFIG_DIR)
##
##    # First get the default file_roots
##    path = os.path.join(salt_config_dir, FILE_ROOTS)
##    paths = __salt__['file.find'](path=path, name='*.sls')
##    for salt_data in _render(paths, saltenv='base'):
##        merge(file_roots, salt_data.get('file_roots', {}), create=True, append=True)
##
##    # Next get all active formual file_roots
##    paths = formula_basedirs(saltenv)
##    for env, path in paths.items():
##        if os.path.exists(path) and os.path.isdir(path):
##            #for file_dir in __salt__['file.find'](path=path, type='d', maxdepth=0):
##            for file_dir in __salt__['file.readdir'](path):
##                if os.path.exists(file_dir) and os.path.isdir(file_dir):
##                    if enabled(os.path.dirname(file_dir)):
##                        merge(file_roots, {env: [file_dir]}, create=True, append=True)
##
##    # Save in __context__ so it doen not need to be reloaded
##    __context__['file_roots_env'] = saltenv
##    __context__['file_roots'] = file_roots
##
##    return file_roots


##def pillar_roots(saltenv=None):
##    '''
##    Returns all active pillar roots.
##    '''
##    # Check if 'pillar_roots' is cached
##    if 'pillar_roots' in __context__ and 'pillar_roots_env' in __context__:
##        if __context__['pillar_roots_env'] == saltenv:
##            return __context__['pillar_roots']
##
##    pillar_roots = OrderedDict()
##    default_pillar_dir = __salt__['pillar.get']('default_pillar_dir', DEFAULT_PILLAR_DIR)
##    salt_config_dir = __salt__['pillar.get']('salt_config_dir', SALT_CONFIG_DIR)
##
##    # First get the default pillar_roots
##    path = os.path.join(salt_config_dir, PILLAR_ROOTS)
##    paths = __salt__['file.find'](path=path, name='*.sls')
##    for salt_data in _render(paths, saltenv='base'):
##        merge(pillar_roots, salt_data.get('pillar_roots', {}), create=True, append=True)
##
##    # Next find any pillars with formula directories
##    paths = formula_basedirs(saltenv)
##    for env, path in paths.items():
##        for pillar_dir in __salt__['file.find'](path=path, name='pillar', maxdepth=1):
##            if os.path.exists(pillar_dir) and os.path.isdir(pillar_dir):
##                if enabled(os.path.dirname(pillar_dir)):
##                    merge(pillar_roots, {env: [pillar_dir]}, create=True, append=True)
##
##    # Save in __context__ so it doen not need to be reloaded
##    __context__['pillar_roots_env'] = saltenv
##    __context__['pillar_roots'] = pillar_roots
##
##    return pillar_roots


##def merge(target, source, create=False, allowed=None, append=False):
##    '''
##    Merges the values of a nested dictionary of varying depth without over-
##    writing the targets root nodes.
##
##    target
##        Target dictionary to update
##
##    source
##        Source dictionary that will be used to update `target`
##
##    create
##        if True then new keys can be created during update, otherwise they will be tossed
##        if they do not exist in `target`.
##
##    allowed
##        list of allowed keys that can be created even if create is False
##
##    append [True] or ['list_of_keys', 'key4']
##        appends to strings or lists if append is True or key in list
##    '''
##    if not allowed:
##        allowed = []
##
##    if isinstance(target, list):
##        for t in target:
##            target_ = merge(t, source, create=create, allowed=allowed, append=append)
##        return target_
##
##    for key, value in source.items():
##        if isinstance(value, collections.Mapping):
##            if key in target.keys() or create or key in allowed:
##                replace = merge(target.get(key, {}), value, create=create, allowed=allowed, append=append)
##                target[key] = replace
##        else:
##            if key in target.keys() or create or key in allowed:
##                if append and (append is True or key in append):
##                    if isinstance(source[key], str) and isinstance(target.get(key, ''), str):
##                        target.setdefault(key, '')
##                        target[key] += source[key]
##                    elif isinstance(source[key], list) and isinstance(target.get(key, []), list):
##                        target.setdefault(key, [])
##                        target[key].extend(source[key])
##                    else:
##                        target[key] = source[key]
##                else:
##                    target[key] = source[key]
##    return target
