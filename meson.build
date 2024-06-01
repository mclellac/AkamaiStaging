project('akamaistaging',
         version: '0.1.0',
         meson_version: '>= 0.62.0',
         default_options: [ 'warning_level=2', 'werror=false', ],
)

i18n = import('i18n')
gnome = import('gnome')
python = import('python')
python3 = python.find_installation('python3')

if not python3.found()
    error('No valid python3 installation found!')
endif

# AkamaiStaging requires at least Python 3.10 for certain type annotations
if not python3.language_version().version_compare('>= 3.10')
  error('Python 3.10 or newer is required.')
endif

# Apply macOS-specific prefix correction
if host_machine.system() == 'darwin'
    prefix = '/usr/local'
endif


# Declare runtime dependency versions here to make packaging more obvious
dependency('glib-2.0', version: '>= 2.78.0')
dependency('gtk4', version: '>= 4.14.0')
dependency('libadwaita-1', version: '>= 1.4.0')
dependency('pygobject-3.0', version: '>= 3.46.0')

prefix = get_option('prefix')

bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
libexecdir = join_paths(prefix, get_option('libexecdir'))
localedir = join_paths(prefix, get_option('localedir'))
pkgdatadir = join_paths(datadir, meson.project_name())

pythondir = join_paths(prefix, python3.get_path('purelib'))

default_pkgappid = 'com.github.mclellac.AkamaiStaging'
pkgappid = default_pkgappid
appdatadir = join_paths(datadir, 'metainfo')
desktopdir = join_paths(datadir, 'applications')
akstagingdir = python3.get_install_dir(subdir: 'akstaging')
icondir = join_paths(datadir, 'icons', 'hicolor')
schemadir = join_paths(datadir, 'glib-2.0', 'schemas')

install_data('akamaistaging', install_dir: bindir)

subdir('akstaging')
subdir('data')
subdir('po')

gnome.post_install(
     glib_compile_schemas: true,
     gtk_update_icon_cache: true,
     update_desktop_database: true,
)

# The polkit Policy file
#policy_file = files('com.github.mclellac.AkamaiStaging.policy')
#install_data(policy_file, install_dir: '/usr/share/polkit-1/actions')

meson.add_install_script('meson-postinstall.py')
