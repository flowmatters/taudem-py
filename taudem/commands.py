
import numpy as _np
import osgeo.gdal as _gd
from . import settings
#_NUMPY_TO_GDAL_TYPES={_np.dtype(v):k for k,v in _gd.array_modes.items()}
_NUMPY_TO_GDAL_TYPES={
	_np.dtype('f'):_gd.GDT_Float32,
	_np.dtype('d'):_gd.GDT_Float64
}

class TaudemCommandArgument(object):
	def __init__(self,name,flag=None,optional=False,type='inputgrid',pass_to_program=False):
		self.name = name
		self.flag = flag
		self.optional = optional
		self.type = type
		self.pass_to_program = pass_to_program

	def type_text(self):
		if self.type=='inputgrid':
			return 'grid'

		if  self.type=='outputgrid':
			return 'grid'

		if self.type=='inputshp':
			return 'vector coverage'

		return self.type

	def help_text(self):
		return '%s: %s (%s)'%(self.name,self.type_text(),'optional' if self.optional else 'required')

	def generate(self,value):
		'''
		Ready `value` for passing to the program and return command line text

		May involve writing a grid to disk.
		'''
		import numpy as np
		if self.type=='inputgrid':
			fn = self.flag or self.name
			fn += '.tif'

			transform = (1.0,0.001,0.0,1.0,0.0,-0.001)

			# write to disk
			if hasattr(value,'GetRasterBand'):
				transform = value.GetGeoTransform()
				value = value.GetRasterBand(1)

			if hasattr(value,'ReadAsArray'):
				value = value.ReadAsArray()

			if np.size(value) <= 1:
				# Not an array.
				raise Exception('Invalid parameter: %s',self.name)

			driver = _gd.GetDriverByName('GTiff')
			outRaster = driver.Create(fn, value.shape[1], value.shape[0], 1, _NUMPY_TO_GDAL_TYPES[value.dtype])
			outRaster.SetGeoTransform(transform)
			outband = outRaster.GetRasterBand(1)
			outband.WriteArray(value)
#			outRasterSRS = osr.SpatialReference()
#			outRasterSRS.ImportFromEPSG(4326)
#			outRaster.SetProjection(outRasterSRS.ExportToWkt())
			outband.FlushCache()

			return ('-%s %s'%(self.flag,fn)) if self.flag else fn

		if self.type=='outputgrid':
			fn = self.flag or self.name
			fn += '.tif'

			return ('-%s %s'%(self.flag,fn)) if self.flag else fn

		if self.type=='inputshp':
			fn = self.flag or self.name
			fn += '.shp'

			# write to disk

			return ('-%s %s'%(self.flag,fn)) if self.flag else fn

		return '-%s'%self.flag

	def read_result(self,as_array):
		if self.type=='outputgrid':
			fn = self.flag or self.name
			fn += '.tif'

			ds = _gd.Open(fn)
			band = ds.GetRasterBand(1)
			arr = ds.ReadAsArray()
			return arr

		raise Exception("Can't read output: %s"%self.name)

def _match_arg(name,args):
	matches = [a for a in args if a.name.lower()==name.lower()]
	if len(matches):
		return matches[0]
	return None

class TaudemCommand(object):
	def __init__(self,name,arguments):
		self.name = name
		self.arguments = arguments
		self.arguments.append(TaudemCommandArgument('as_array',type='boolean',pass_to_program=False,optional=True))

	def generate(self):
		import tempfile
		import shutil
		import os

		def result(*args,**kwargs):
			cmd_args = []
			available_args = self.arguments[::-1]

			for a in args:
				try:
					cmd_args.append((available_args.pop(),a))
				except:
					raise Exception('too many arguments')

			for k,v in kwargs.items():
				a = _match_arg(k,available_args)
				if a is None:
					if not _match_arg(k,self.arguments):
						raise Exception('unknown argument: %s'%k)
					raise Exception('argument provided by position and keyword: '%k)
				cmd_args.append(a,v)

			output_params = [(a,None) for a in available_args if a.type.startswith('output')]
			missing = []
			for a in available_args:
				if a.type.startswith('output'):
					continue;
				if not a.optional:
					missing.append(a.name)

			if len(missing):
				raise Exception('Missing required argument(s): %s'%missing)

			print('args',cmd_args)
			print('outputs',output_params)

			working_dir = tempfile.mkdtemp(prefix='taudem_')
			save_dir = os.getcwd()
			print(os.getcwd())
			try:
				all_args = cmd_args + output_params
				os.chdir(working_dir)
				print(os.getcwd())
				cmd = '%s %s%s %s'%(settings.mpi_cmd(), settings.TAUDEM_PATH, self.name,' '.join([a.generate(v) for a,v in all_args]))

				from glob import glob
				print(glob('%s/*'%working_dir))

				print('command line:',cmd)

				os.system(cmd)

				print(glob('%s/*'%working_dir))

				read_full_results = kwargs.get('as_array',True)

				results = [o.read_result(read_full_results) for o,_ in output_params]

				if len(results) != 1:
					return tuple(results)
				return results[0]

			finally:				
				shutil.rmtree(working_dir)
				os.chdir(save_dir)

			print(os.getcwd())


		return result

	def doc_string(self):
		result = '%s\n%s\n\n'%(self.name,''.join(['-']*len(self.name)))

		for a in self.arguments:
			if a.type.startswith('output'):
				continue

			result += '* %s\n\n'%a.help_text()

		result += 'Returns:\n'

		for a in self.arguments:
			if not a.type.startswith('output'):
				continue

			result += '* %s\n\n'%a.help_text()

		return result

fillpits = TaudemCommand('pitremove',[
		TaudemCommandArgument('demgrid','z'),
		TaudemCommandArgument('pitfilleddemgrid','fel',type='outputgrid'),
		TaudemCommandArgument('upserdirgrid','sfdr',optional=True)
	])

d8p = TaudemCommand('d8flowdir',[
		TaudemCommandArgument('pitfilleddem','fel'),
		TaudemCommandArgument('d8pointergrid','p',type='outputgrid'),
		TaudemCommandArgument('d8slopegrid','sd8',type='outputgrid'),
		TaudemCommandArgument('upserdirgrid','sfdr',optional=True)
	])

aread8 = TaudemCommand('aread8',[
		TaudemCommandArgument('d8pointergrid','p'),
		TaudemCommandArgument('upstreamareagrid','ad8',type='outputgrid'),
		TaudemCommandArgument('outlets','o',type='inputshp',optional=True),
		TaudemCommandArgument('weightgrid','wg',optional=True),
		TaudemCommandArgument('nc','nc',type='flag',optional=True)
	])

commands=[fillpits,d8p,aread8]
