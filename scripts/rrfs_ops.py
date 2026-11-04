"""Herbie template for the operational RRFS (NOAA's 3 km Rapid Refresh Forecast System), CONUS grid.

Herbie's own `rrfs` template points at the retired prototype bucket (noaa-rrfs-pds, 2024 retro runs only). The
operational feed is the public bucket noaa-rrfs-ops-pds (also on NOMADS under rrfs/prod):

    rrfs.YYYYMMDD/HH/rrfs.tHHz.2dfld.3km.fFFF.conus.grib2   (+ .idx)

Hourly cycles; the 00/06/12/18Z cycles run to f084. Importing this module registers the model as `rrfs_ops`:

    import rrfs_ops
    H = Herbie(cycle, model="rrfs_ops", fxx=12)
"""
import herbie.models as _models


class rrfs_ops:
    def template(self):
        self.DESCRIPTION = "Rapid Refresh Forecast System (RRFS), operational, CONUS 3 km"
        self.DETAILS = {"aws product description": "https://registry.opendata.aws/noaa-rrfs-ops/"}
        self.PRODUCTS = {"2dfld": "2-D surface fields, 3 km CONUS"}
        base = f"rrfs.{self.date:%Y%m%d/%H}/rrfs.t{self.date:%H}z.2dfld.3km.f{self.fxx:03d}.conus.grib2"
        self.SOURCES = {"aws": f"https://noaa-rrfs-ops-pds.s3.amazonaws.com/{base}"}
        self.LOCALFILE = f"{self.get_remoteFileName}"


_models.rrfs_ops = rrfs_ops
