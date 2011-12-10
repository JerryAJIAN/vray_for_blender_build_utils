#
# V-Ray/Blender Build System
#
# http://vray.cgdo.ru
#
# Author: Andrey M. Izrantsev (aka bdancer)
# E-Mail: izrantsev@cgdo.ru
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# All Rights Reserved. V-Ray(R) is a registered trademark of Chaos Software.
#


import os
import sys
import subprocess

from builder import utils
from builder import Builder


class WindowsBuilder(Builder):
	def config(self):
		sys.stdout.write("Generating build configuration:\n")
		sys.stdout.write("  in: %s\n" % (self.user_config))
		
		if self.mode_test:
			return

		uc= open(self.user_config, 'w')

		build_options= {
			'True': [
				'WITH_BF_FFMPEG',
				'WITH_BF_OPENAL',
				'WITH_BF_SDL',
				'WITH_BF_BULLET',
				'WITH_BF_ZLIB',
				'WITH_BF_FTGL',
				'WITH_BF_RAYOPTIMIZATION',
				'WITH_BUILDINFO',
				'WITH_BF_OPENEXR',
				'WITH_BF_ICONV',
				'WITH_BF_GAMEENGINE',
			],
			'False': [
				'WITH_BF_QUICKTIME',
				'WITH_BF_FMOD',
				'WITH_BF_VERSE',
				'WITH_BF_GAMEENGINE',
				'WITH_BF_PLAYER',
				'WITH_BF_JACK',
				'WITH_BF_FFTW3',
			]
		}

		if self.build_arch == 'x86_64':
			build_options['False'].append('WITH_BF_JACK')
			build_options['False'].append('WITH_BF_SNDFILE')
			build_options['False'].append('WITH_BF_FFMPEG')
			build_options['False'].append('WITH_BF_OPENAL')
			
			uc.write("LCGDIR = '#../lib/win64'\n")
			uc.write("LIBDIR = '${LCGDIR}'\n")
			uc.write("BF_PNG_LIB = 'libpng'\n")
			uc.write("\n")

		if self.use_collada:
			build_options['True'].append('WITH_BF_COLLADA')
		else:
			build_options['False'].append('WITH_BF_COLLADA')

		if self.use_debug:
			build_options['True'].append('BF_DEBUG')

		# Windows git/scons issue - scons can't clear installation directory
		# when vb25 .git is installed
		if os.path.exists(self.dir_install_path):
			os.system("rmdir /Q /S %s" % (self.dir_install_path))

		uc.write("BF_INSTALLDIR     = '%s'\n" % (self.dir_install_path))
		uc.write("BF_BUILDDIR       = '%s'\n" % (self.dir_build))
		uc.write("BF_SPLIT_SRC      = True\n")
		uc.write("BF_TWEAK_MODE     = False\n")
		uc.write("BF_NUMJOBS        = %s\n" % (self.build_threads))

		uc.write("BF_PYTHON_VERSION = '3.2'\n")

		# Cycles
		#
		uc.write("WITH_BF_CYCLES    = True\n")
		uc.write("WITH_BF_OIIO      = True\n")
		uc.write("\n")

		# Write boolean options
		for key in build_options:
			for opt in build_options[key]:
				uc.write("{0:25} = {1}\n".format(opt, key))
		
		uc.write("\n")
		uc.close()


	def package(self):
		release_path = os.path.join(self.dir_release, "windows", self.build_arch)
		
		if not self.mode_test:
			utils.path_create(release_path)

		director_size = 0
		
		# Example: vrayblender-2.60-42181-windows-x86_64.exe
		installer_name = "%s-%s-%s-windows-%s.exe" % (self.project, self.version, self.revision, self.build_arch)
		installer_path = utils.path_slashify(utils.path_join(release_path, installer_name))
		installer_root = utils.path_join(self.dir_source, "vb25-patch", "installer")

		# Use NSIS log plugin
		installer_log  = False

		sys.stdout.write("Generating installer: %s\n" % (installer_name))
		sys.stdout.write("  in: %s\n" % (installer_path))

		nsis = open(utils.path_join(installer_root, "template.nsi"), 'r').read()

		nsis = nsis.replace('{IF64}', '64' if self.build_arch == 'x86_64' else "")
		nsis = nsis.replace('{INSTALLER_SCRIPT_ROOT}', installer_root)
		nsis = nsis.replace('{INSTALLER_OUTFILE}', installer_path)
		nsis = nsis.replace('{VERSION}', self.version)
		nsis = nsis.replace('{REVISION}', self.revision)
		
		installer_files   = ""
		uninstaller_files = []

		for dirpath, dirnames, filenames in os.walk(self.dir_install_path):
			if dirpath.endswith('__pycache__'):
				continue
			
			_dirpath = os.path.normpath(dirpath).replace( os.path.normpath(self.dir_install_path), "" )

			if installer_log:
				installer_files += '\tStrCpy $VB_TMP "$INSTDIR%s"\n' % (_dirpath)
				installer_files += '\t${SetOutPath} $VB_TMP\n'
			else:
				installer_files += '\tSetOutPath "$INSTDIR%s"\n' % (_dirpath)
				uninstaller_files.append( '\tRMDir "$INSTDIR%s"\n' % (os.path.normpath(_dirpath)) )

			for f in os.listdir(dirpath):
				f_path = os.path.join(dirpath, f)
				
				if os.path.isdir(f_path):
					continue
				
				basepath, basename = os.path.split(f_path)
				
				if installer_log:
					installer_files += '\t${File} "%s" "%s" "$VB_TMP"\n' % (basepath, basename)
				else:
					installer_files += '\tFile "%s"\n' % (f_path)
					uninstaller_files.append( '\tDelete "$INSTDIR%s\%s"\n' % (_dirpath, basename) )

				director_size += os.path.getsize(f_path)

		uninstaller_files.reverse()

		nsis = nsis.replace('{INSTALLER_FILES}', installer_files)
		nsis = nsis.replace('{UNINSTALLER_FILES}', ''.join(uninstaller_files))
		nsis = nsis.replace('{SIZE}', str(director_size / 1024))

		template = utils.path_join(self.dir_source, "installer.nsi")
		
		open(template, 'w').write(nsis)

		makensis_exe = utils.find_makensis()

		cmd= []
		cmd.append(makensis_exe)
		cmd.append(template)

		sys.stdout.write("Calling: %s\n" % (' '.join(cmd)))

		if not self.mode_test:
			os.chdir(utils.path_join(self.dir_source, "vb25-patch", "installer"))
			proc = subprocess.call(cmd)
	
	
	def post_init(self):
		pass