pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'ludustier'
gnome = import('gnome')

gnome.compile_resources('ludustier',
  'ludustier.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'ludustier.in',
  output: 'ludustier',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

ludustier_sources = [
  '__init__.py',
  'config.py',
  'exporter.py',
  'game_card.py',
  'game_edit_dialog.py',
  'main.py',
  'preferences_dialog.py',
  'search_dialog.py',
  'steamgrid.py',
  'tier_dialog.py',
  'window.py',
]

install_data(ludustier_sources, install_dir: moduledir)
