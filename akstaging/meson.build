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

blueprint_compiler = find_program('blueprint-compiler', required: false)
if blueprint_compiler.found()
  message('Found blueprint-compiler: compiling .blp templates to .ui XML')
  custom_target('window.ui',
    input: 'gtk/window.blp',
    output: 'window.ui',
    command: [blueprint_compiler, 'compile', '--output', '@OUTPUT@', '@INPUT@'],
    build_by_default: true
  )
  custom_target('help-overlay.ui',
    input: 'gtk/help-overlay.blp',
    output: 'help-overlay.ui',
    command: [blueprint_compiler, 'compile', '--output', '@OUTPUT@', '@INPUT@'],
    build_by_default: true
  )
endif

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

conf_data_akstaging_config = configuration_data()
conf_data_akstaging_config.set('AKSTAGING_HELPER_INSTALL_PATH', akstaging_helper_install_path)
conf_data_akstaging_config.set('MACOS_HELPER_EXECUTABLE_PATH', akstaging_macos_helper_install_path)

generated_akstaging_config_py_file_object = configure_file(
  input: 'config.py.in',
  output: 'config.py',
  configuration: conf_data_akstaging_config
)

# Install the generated config.py file object
python3.install_sources(
  [generated_akstaging_config_py_file_object],
  subdir: 'akstaging'
)
