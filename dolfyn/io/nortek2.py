from struct import unpack, calcsize
import nortek2_defs as defs
import bitops as bo
import pdb
reload(defs)


class Ad2cpReader(object):

    def __init__(self, fname, endian=None, bufsize=None):

        self.fname = fname
        self._check_nortek(endian)
        self._estimate_bytes_per_ping()
        self.c = 0
        self._burst_readers = {}
        self.reopen(bufsize)

    def read_hdr(self, ):
        res = defs._header.read2dict(self.f)
        if res['sync'] != 165:
            raise Exception("Out of sync!")
        return res['id'], res['sz']

    def _check_nortek(self, endian):
        self.reopen(10)
        byts = self.f.read(2)
        if endian is None:
            if unpack('<' + 'BB', byts) == (165, 10):
                endian = '<'
            elif unpack('>' + 'BB', byts) == (165, 10):
                endian = '>'
            else:
                raise Exception(
                    "I/O error: could not determine the 'endianness' "
                    "of the file.  Are you sure this is a Nortek "
                    "AD2CP file?")
        self.endian = endian

    def _estimate_bytes_per_ping(self, npings=100):
        self.reopen()
        idx = 0
        sizes = []
        while idx < npings:
            id, sz = self.read_hdr()
            sizes.append(sz)
            idx += 1
            self.f.seek(sz, 1)
            print(hex(id), sz)
        return self.pos / npings + 1

    def reopen(self, bufsize=None):
        if bufsize is None:
            bufsize = 1000000
        try:
            self.f.close()
        except AttributeError:
            pass
        self.f = open(self.fname, 'rb', bufsize)

    def readfile(self, npings=None):
        print('Reading file %s ...' % self.fname)
        retval = None
        while not retval:
            id, sz = self.read_hdr()
            print id
            if id == 21:
                self.read_burst()
            else:
                self.f.seek(sz, 1)
            self.c += 1

    def _read(self, strct):
        nbyte = strct.size
        byts = self.f.read(nbyte)
        if not (len(byts) == nbyte):
            raise EOFError('Reached the end of the file')
        return strct.unpack(byts)

    def read(self, format):
        nbyte = calcsize(format)
        byts = self.f.read(nbyte)
        if not (len(byts) == nbyte):
            raise EOFError('Reached the end of the file')
        return unpack(self.endian + format, byts)

    def read_burst(self, echo=False):
        b_hd = defs._burst_hdr.read2dict(self.f)
        if not echo:
            bcfg = bo.bs16(b_hd['beam_config'])
            b_hd['n_cells'] = int(bcfg[-10:], 2)
            b_hd['coord_sys'] = ['ENU', 'XYZ',
                                 'BEAM', None][int(bcfg[-12:-10], 2)]
            b_hd['n_beams'] = int(bcfg[-16:-12], 2)
        else:
            b_hd['n_cells'] = b_hd['beam_config']
        reader_id = (b_hd['config'], b_hd['beam_config'])
        try:
            brdr = self._burst_readers[reader_id]
        except KeyError:
            brdr = self._burst_readers[reader_id] = defs.calc_burst_struct(
                b_hd['config'], b_hd['n_beams'], b_hd['n_cells'])
        dat = brdr.read2dict(self.f)
        print '!!!, ', b_hd['ver']
        # (ver, off, config, sn,
        #  year, month, day, hour, min, sec, usec,
        #  c_sound, temp, press,
        #  head, pitch, roll,
        #  nbeam_cs_cells,
        #  cell_size, blanking, nom_corr,
        #  temp_press, batt_V,
        #  mag_X, mag_Y, mag_Z,
        #  acc_X, acc_Y, acc_Z,
        #  vel_ambig, data_desc, xmit_e,
        #  vel_scale, power_level,
        #  mag_temp, clock_temp,
        #  error, status0, ens, ) = self.read('2BH4s6B2HhLH2h3H2BH')
        pdb.set_trace()
    
    def __exit__(self, type, value, trace,):
        self.f.close()

    def __enter__(self,):
        return self

    @property
    def pos(self, ):
        return self.f.tell()

if __name__ == '__main__':

    rdr = Ad2cpReader('../../example_data/BenchFile01.ad2cp')
    rdr.readfile()

