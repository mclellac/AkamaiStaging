# Determine if we're in a Flatpak build
is_flatpak_build = get_option('prefix') == '/app'
message('Is Flatpak build: ' + is_flatpak_build.to_string())
message('Prefix: ' + get_option('prefix'))

conf = configuration_data()
conf.set('PYTHON', python3.full_path())
conf.set('VERSION', meson.project_version())

python_install_dir = python3.get_install_dir()
message('Python install dir: ' + python_install_dir)

# Use the correct method to get site-packages directory
site_packages_dir = python3.get_install_dir(subdir: 'akstaging')
message('Site packages dir: ' + site_packages_dir)

if is_flatpak_build
    conf.set('LOCALEDIR', join_paths(get_option('prefix'), 'share', 'locale'))
    conf.set('DATADIR', join_paths(get_option('prefix'), 'share'))
    conf.set('AKSTAGINGDIR', site_packages_dir)
    conf.set('PKGDATADIR', join_paths(get_option('prefix'), 'share', meson.project_name()))
    resource_path = join_paths(get_option('prefix'), 'share', 'akamaistaging', 'akamaistaging.gresource')
else
    conf.set('LOCALEDIR', join_paths(get_option('prefix'), get_option('datadir'), 'locale'))
    conf.set('DATADIR', join_paths(get_option('prefix'), get_option('datadir')))
    conf.set('AKSTAGINGDIR', site_packages_dir)
    conf.set('PKGDATADIR', join_paths(get_option('prefix'), get_option('datadir'), meson.project_name()))
    resource_path = join_paths(get_option('prefix'), get_option('datadir'), 'akamaistaging', 'akamaistaging.gresource')
endif

conf.set('RESOURCE_PATH', resource_path)
conf.set('APPID', meson.project_name())
_abs_libexecdir = join_paths(get_option('prefix'), get_option('libexecdir'))
conf.set('libexecdir', _abs_libexecdir) # Ensure absolute path for LIBEXECDIR in defs.py

configure_file(
  input: 'defs.py.in',
  output: 'defs.py',
  configuration: conf,
  install: true,
  install_dir: conf.get('AKSTAGINGDIR'),
  install_mode: 'r-xr-xr-x'
)

gnome = import('gnome')

# Compile GNOME resources from an XML file. This bundles resources into a single binary file.
gnome.compile_resources('akamaistaging',
  'akamaistaging.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: conf.get('PKGDATADIR')
)

# python3 object should be available from the root meson.build
# If not, uncomment:
# python3 = import('python') # Already imported in root

akamaistaging_module_py_sources = files(
  '__init__.py',
  'aklib.py',
  'dns_utils.py',
  'helper_cli.py',
  'hosts.py',
  'i18n.py',
  'preferences.py',
  'status_codes.py',
  'window.py'
  # defs.py is handled by its own configure_file and install rule.
  # config.py will be handled separately using the passed File object.
)

# The prompt uses install_subdir, but the correct Meson argument is 'subdir'.
# conf.get('AKSTAGINGDIR') resolves to python3.get_install_dir(subdir: 'akstaging')
# So, using subdir: 'akstaging' directly is clearer if python3 is the current python module.
python3.install_sources(
  akamaistaging_module_py_sources,
  subdir: 'akstaging'
  # pure: false # This is usually a default or can be set on the python object in root
)

# The following block was a duplicate and has been removed.
# # List the regular Python source files for the akstaging module
# akamaistaging_module_py_sources = files(
#   '__init__.py',
#   'aklib.py',
#   'dns_utils.py',
#   'hosts.py',
#   'preferences.py',
#   'window.py'
#   # defs.py is handled by its own configure_file and install rule.
# )
# 
# # Install these regular module files
# python3.install_sources(
#   akamaistaging_module_py_sources,
#   subdir: 'akstaging' 
# )

# Reference the config.py file generated in the root build directory
# (output name from root meson.build's configure_file for akstaging/config.py.in is now 'config.py')
generated_config_py_from_build_root = meson.global_build_root() / 'config.py'

# Install the generated file. Since its basename is already 'config.py',
# no rename is needed.
python3.install_sources(
  [generated_config_py_from_build_root], # This is builddir/config.py
  subdir: 'akstaging'                   # Installs as .../akstaging/config.py
)
