
import numpy as _np
import osgeo.gdal as _gd

_NUMPY_TO_GDAL_TYPES={
	_np.dtype('f'):_gd.GDT_Float32,
	_np.dtype('d'):_gd.GDT_Float64,
	_np.dtype('int16'):_gd.GDT_Int16,
	_np.dtype('int32'):_gd.GDT_Int32
}

def to_geotiff(arr,gt,fn):
	driver = _gd.GetDriverByName('GTiff')
	outRaster = driver.Create(fn, arr.shape[1], arr.shape[0], 1, _NUMPY_TO_GDAL_TYPES[arr.dtype])
	outRaster.SetGeoTransform(gt)
	outband = outRaster.GetRasterBand(1)
	outband.WriteArray(arr)
#			outRasterSRS = osr.SpatialReference()
#			outRasterSRS.ImportFromEPSG(4326)
#			outRaster.SetProjection(outRasterSRS.ExportToWkt())
	outband.FlushCache()

def to_point_shp(points,fn):
	if hasattr(points,'to_file'):
		points.to_file(fn)
		return

	raise Exception('Unable to write shapefile. Unknown data representation.')

def clip(raster,polygons,all_touched=True):
	import rasterio as rio
	geom_bounds = tuple(polygons.bounds)

	fsrc = raster.read(bounds=geom_bounds)

	coverage_rst = rasterize_geom(geom,like=fsrc,all_touched=all_touched)

	masked = np.ma.MaskedArray(fsrc.arry,mask=np.logical_or(fsrc.array==fsrc.nodata,np.logical_not(coverage_rst)))

	return masked
