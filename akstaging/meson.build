# Determine if we're in a Flatpak build
is_flatpak_build = get_option('prefix') == '/app'
message('Is Flatpak build: ' + is_flatpak_build.to_string())
message('Prefix: ' + get_option('prefix'))

conf = configuration_data()
conf.set('PYTHON', python3.full_path())
conf.set('VERSION', meson.project_version())

# Get the install directory for Python
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

# Define the list of source files for the 'akamaistaging' project.
akamaistaging_sources = files(
  '__init__.py',
  'window.py',
  'hosts.py',
  'aklib.py',
  'dns_utils.py',
)

# Use the python3.install_sources method to install the Python source files.
python3.install_sources(akamaistaging_sources, subdir: conf.get('AKSTAGINGDIR'))
