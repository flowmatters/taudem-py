
import numpy as _np
import osgeo.gdal as _gd
import pandas as _pd
from . import settings
from .utils import to_geotiff,to_point_shp,which

class TaudemCommandArgument(object):
    def __init__(self,name,flag=None,optional=False,type='inputgrid',pass_to_program=False,columns=None):
        self.name = name
        self.flag = flag
        self.optional = optional
        self.type = type
        self.pass_to_program = pass_to_program
        self.columns = columns

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

    def generate(self,value,transform):
        '''
        Ready `value` for passing to the program and return command line text

        May involve writing a grid to disk.
        '''
        import numpy as np
        if self.type.endswith('grid'):
            fn = self.flag or self.name
            fn += '.tif'

            if self.type.startswith('input'):
                transform = transform or (1.0,0.001,0.0,1.0,0.0,-0.001)

                # write to disk
                if hasattr(value,'GetRasterBand'):
                    transform = value.GetGeoTransform()
                    value = value.GetRasterBand(1)

                if hasattr(value,'ReadAsArray'):
                    value = value.ReadAsArray()

                if np.size(value) <= 1:
                    # Not an array.
                    raise Exception('Invalid parameter: %s',self.name)

                to_geotiff(value,transform,fn)

            return ('-%s %s'%(self.flag,fn)) if self.flag else fn

        if self.type.endswith('shp'):
            fn = self.flag or self.name
            fn += '.shp'

            if self.type.startswith('input'):
                # write to disk
                to_point_shp(value,fn)

            return ('-%s %s'%(self.flag,fn)) if self.flag else fn

        if self.type=='outputtxt':
            fn = self.flag or self.name
            fn += '.txt'

            return '-%s %s'%(self.flag,fn)

        if self.type=='flag':
            if value:
                return '-%s'%self.flag

        if self.type=='value':
            return '-%s %s'%(self.flag,str(value))

        raise Exception("Can't process argument: %s"%self.name)

    def read_result(self,as_array):
        if self.type=='outputgrid':
            fn = self.flag or self.name
            fn += '.tif'

            ds = _gd.Open(fn)
            band = ds.GetRasterBand(1)
            arr = ds.ReadAsArray()
            return arr

        if self.type=='outputshp':
            import geopandas as gpd
            fn = self.flag or self.name
            fn += '.shp'

            return gpd.read_file(fn)

        if self.type=='outputtxt':
            fn = self.flag or self.name
            fn += '.txt'

            if self.columns:
                return _pd.read_table(fn,delim_whitespace=True,header=None,names=self.columns,index_col=False)
            return _pd.read_table(fn,sep=' ')

        raise Exception("Can't read output: %s"%self.name)

def _match_arg(name,args):
    matches = [a for a in args if a.name.lower()==name.lower()]
    if len(matches):
        return matches[0]
    return None

class TaudemCommand(object):
    def __init__(self,name,arguments):
        if type(name)==list:
            self.name = name[0]
            self.alternative_names = name
        else:
            self.name = name
            self.alternative_names = None

        self.arguments = arguments
        self.arguments.append(TaudemCommandArgument('as_array',type='boolean',pass_to_program=False,optional=True))
        self.arguments.append(TaudemCommandArgument('geotransform',type='geotransform',pass_to_program=False,optional=True))

    def generate(self):
        import tempfile
        import shutil
        import os

        def result(*args,**kwargs):
            cmd_args = []
            available_args = self.arguments[::-1]
            transform = kwargs.get('geotransform',None)

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
                cmd_args.append((a,v))
                available_args.remove(a)

            output_params = [(a,None) for a in available_args if a.type.startswith('output')]

            missing = []
            for a in available_args:
                if a.type.startswith('output'):
                    continue;
                if not a.optional:
                    missing.append(a.name)

            if len(missing):
                raise Exception('Missing required argument(s): %s'%missing)

#           print('args',cmd_args)
#           print('outputs',output_params)

            if transform is None:
                for a,v in cmd_args:
                    if a.type=='inputgrid' and hasattr(v,'GetGeoTransform'):
#                       print('No Geotransform provided. Using geotransform from %s'%a.name)
                        transform = v.GetGeoTransform()
                        break

            working_dir = tempfile.mkdtemp(prefix='taudem_')
            save_dir = os.getcwd()
#           print(os.getcwd())
            try:
                all_args = cmd_args + output_params
                os.chdir(working_dir)
#               print(os.getcwd())
                if self.alternative_names:
                    for opt in self.alternative_names:
                        executable = '%s%s%s'%(settings.TAUDEM_PATH, opt,settings.SUFFIX)
                        if which(executable):
                            break
                else:
                    executable = '%s%s%s'%(settings.TAUDEM_PATH, self.name,settings.SUFFIX)

                cmd = '%s %s %s'%(settings.mpi_cmd(), executable,' '.join([a.generate(v,transform) for a,v in all_args]))

#               from glob import glob
#               print('\nFiles Before:\n'+ '\n'.join(glob('%s/*'%working_dir))+'\n')

#               print('command line:',cmd)

                os.system(cmd)

#               print('\nFiles After:\n'+ '\n'.join(glob('%s/*'%working_dir))+'\n')

                read_full_results = kwargs.get('as_array',True)

                results = [o.read_result(read_full_results) for o,_ in output_params[::-1]]

                if len(results) != 1:
                    return tuple(results)
                return results[0]

            finally:                
                os.chdir(save_dir)
                shutil.rmtree(working_dir)
                #print("\n******* Don't forget to remove contents of %s\n\n"%working_dir)
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

threshold = TaudemCommand('threshold',[
        TaudemCommandArgument('input','fel'),
        TaudemCommandArgument('output','ss',type='outputgrid'),
        TaudemCommandArgument('thresholdvalue','thresh',type='value'),
        TaudemCommandArgument('mask','mask',optional=True)
    ])

streamnet = TaudemCommand('streamnet',[
        TaudemCommandArgument('d8pointer','p'),
        TaudemCommandArgument('filled_dem','fel',optional=True),
        TaudemCommandArgument('upstreamareagrid','ad8'),
        TaudemCommandArgument('stream_raster','src'),
        TaudemCommandArgument('outlets','o',type='inputshp',optional=True),

        TaudemCommandArgument('treefile','tree',type='outputtxt',columns=[
                'Link_Number','Index_Start_Point','Index_End_Point',
                'Link_DS','Link_US1','Link_US2','Strahler_Order',
                'Monitoring_Point_DS','Network_Magniture']),
        TaudemCommandArgument('dn','dn',type='value',optional=True),

        TaudemCommandArgument('watersheds','w',type='outputgrid'),
        TaudemCommandArgument('streams','net',type='outputshp'),
        TaudemCommandArgument('network_coords','coord',type='outputtxt',columns=[
                'X','Y','Channel_Distance_to_end_terminal','Elevation','Contributing_Area']),
        TaudemCommandArgument('network_order','ord',type='outputgrid')
    ])

gagewatershed = TaudemCommand('gagewatershed',[
        TaudemCommandArgument('d8pointer','p'),
        TaudemCommandArgument('outlets','o',type='inputshp'),
        TaudemCommandArgument('gagewatersheds','gw',type='outputgrid'),
        TaudemCommandArgument('connectivity','id',type='outputtxt')
    ])

moveoutletstostrm = TaudemCommand(['moveoutletstostrm','MoveOutletsToStreams'],[
        TaudemCommandArgument('d8pointer','p'),
        TaudemCommandArgument('stream_raster','src'),
        TaudemCommandArgument('outlets','o',type='inputshp'),
        TaudemCommandArgument('outlets_moved','om',type='outputshp'),
        TaudemCommandArgument('max_dist','md',type='value',optional=True)
    ])

commands=[fillpits,d8p,aread8,threshold,streamnet,gagewatershed,moveoutletstostrm]
