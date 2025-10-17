project('akamaistaging',
         version: '1.0.0',
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

if not python3.language_version().version_compare('>= 3.10')
  error('Python 3.10 or newer is required.')
endif

# Use get_option('prefix') consistently.
# If a specific prefix like /usr/local is desired on macOS,
# it should be set via the Meson command line (`meson setup --prefix=/usr/local build`)
# or be Meson's default for that platform.
prefix_opt = get_option('prefix')

dependency('glib-2.0', version: '>= 2.78.0')
dependency('gtk4', version: '>= 4.14.0')
dependency('libadwaita-1', version: '>= 1.7.0')
dependency('pygobject-3.0', version: '>= 3.46.0')

bindir = join_paths(prefix_opt, get_option('bindir'))
datadir = join_paths(prefix_opt, get_option('datadir'))
libexecdir = join_paths(prefix_opt, get_option('libexecdir'))
localedir = join_paths(prefix_opt, get_option('localedir'))

appdatadir = join_paths(datadir, 'metainfo')
desktopdir = join_paths(datadir, 'applications')
icondir = join_paths(datadir, 'icons', 'hicolor')
schemadir = join_paths(datadir, 'glib-2.0', 'schemas')

python_site_packages_for_script = python3.get_install_dir()
conf_data_main_script = configuration_data()
conf_data_main_script.set('PYTHON_SITE_PACKAGES', python_site_packages_for_script)

configured_main_script = configure_file(
    input: 'akamaistaging.in',
    output: 'akamaistaging',
    configuration: conf_data_main_script
)

install_data(
  configured_main_script, # File object from configure_file (output: 'akamaistaging')
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
  rename: [meson.project_name()]
)

akstaging_helper_script_name = 'akstaging_root_helper.py'
akstaging_helper_install_path = join_paths(prefix_opt, get_option('libexecdir'), meson.project_name(), akstaging_helper_script_name)

conf_data_akstaging_config = configuration_data()
conf_data_akstaging_config.set('AKSTAGING_HELPER_INSTALL_PATH', akstaging_helper_install_path)

# Define macOS helper path and add to config data *before* configuring config.py.in
akstaging_macos_helper_script_name = 'akstaging_macos_helper.py'
akstaging_macos_helper_install_path = join_paths(prefix_opt, get_option('libexecdir'), meson.project_name(), akstaging_macos_helper_script_name)
conf_data_akstaging_config.set('MACOS_HELPER_EXECUTABLE_PATH', akstaging_macos_helper_install_path)

generated_akstaging_config_py_file_object = configure_file(
  input : 'akstaging/config.py.in',
  output : 'config.py',
  configuration : conf_data_akstaging_config
)

subdir('akstaging')
subdir('data')
subdir('po')

gnome.post_install(
     glib_compile_schemas: true,
     gtk_update_icon_cache: true,
     update_desktop_database: true,
)

install_data('akstaging/akstaging_root_helper.py',
  install_dir: join_paths(libexecdir, meson.project_name()),
  install_mode: 'rwxr-xr-x'
)

install_data('akstaging/akstaging_macos_helper.py',
  install_dir: join_paths(libexecdir, meson.project_name()),
  install_mode: 'rwxr-xr-x'
)

conf_data_policy = configuration_data()
conf_data_policy.set('AKSTAGING_HELPER_INSTALL_PATH', akstaging_helper_install_path)

policy_file_configured = configure_file(
  input: 'com.github.mclellac.AkamaiStaging.policy.in',
  output: 'com.github.mclellac.AkamaiStaging.policy',
  configuration: conf_data_policy
)

install_data(policy_file_configured,
  install_dir: join_paths(datadir, 'polkit-1', 'actions')
)

meson.add_install_script('meson-postinstall.py')
