conf = configuration_data()
conf.set('PYTHON', python3.full_path())
conf.set('VERSION', meson.project_version())
conf.set('LOCALEDIR', join_paths(get_option('prefix'), get_option('datadir'), 'locale'))
conf.set('DATADIR', datadir)
conf.set('AKSTAGINGDIR', akstagingdir)
conf.set('PKGDATADIR', pkgdatadir)
conf.set('APPID', pkgappid)

configure_file(
  input: 'defs.py.in',
  output: 'defs.py',
  configuration: conf,
  install: true,
  install_dir: akstagingdir,
  install_mode: 'r-xr-xr-x'
)

gnome = import('gnome')

# Compile GNOME resources from an XML file. This bundles resources into a single binary file.
# - 'akamaistaging' is the target name for the resource bundle.
# - 'akamaistaging.gresource.xml' is the input file listing the resources.
# - 'gresource_bundle: true' creates a GResource bundle.
# - 'install: true' specifies that the resource bundle should be installed.
# - 'install_dir: pkgdatadir' sets the installation directory for the resource bundle.
gnome.compile_resources('akamaistaging',
  'akamaistaging.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), meson.project_name())
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
# - 'subdir: 'src'' specifies the source directory relative to the project root.
python3.install_sources(akamaistaging_sources, subdir: akstagingdir)
