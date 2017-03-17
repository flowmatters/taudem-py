
import os

TAUDEM_PATH = '' # Default assumes on path

USE_MPI = True

MPI_PROCESSORS = 4

MPI_PATH=''

MPI_CMD='mpiexec'

def mpi_cmd():
	if not USE_MPI:
		return ''

	return '%s -n %d'%(os.path.join(MPI_PATH,MPI_CMD),MPI_PROCESSORS)


