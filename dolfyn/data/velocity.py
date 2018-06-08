from __future__ import division
from .base import np, ma, TimeData, FreqData
from .binned import TimeBinner
import warnings
from .time import num2date
from ..rotate import rotate2


class Velocity(TimeData):
    """This is the base class for DOLfYN velocity-data objects.

    All ADV and ADP data objects inherit from this base class.

    See Also
    ========

    :class:`dict`

    NOTES
    =====

    DOLfYN Velocity objects are based on Python dicts, but have fancy
    interactive printing properties and indexing properties.

    First, the interactive printing::

        >>> import dolfyn as dlfn
        >>> dat = dlfn.read_example('BenchFile01.ad2cp')

    In an interactive interpreter, we view the contents of the data
    object by::

        >>> dat
        <ADP data object>
        . 9.11 minutes (started: Feb 24, 2017 10:01)
        . BEAM-frame
        . (38 bins, 1094 pings @ 2Hz)
        *------------
        | mpltime                  : <time_array; (1094,); float64>
        | range                    : <array; (38,); float64>
        | range_b5                 : <array; (38,); float64>
        | vel                      : <array; (4, 38, 1094); float32>
        | vel_b5                   : <array; (1, 38, 1094); float32>
        + alt                      : + DATA GROUP
        + altraw                   : + DATA GROUP
        + config                   : + DATA GROUP
        + env                      : + DATA GROUP
        + orient                   : + DATA GROUP
        + props                    : + DATA GROUP
        + signal                   : + DATA GROUP
        + sys                      : + DATA GROUP

    You can view the contents of a 'DATA GROUP' by::

        >>> dat['env']
        <class 'dolfyn.data.base.TimeData'>: Data Object with Keys:
        *------------
        | c_sound                  : <array; (1094,); float32>
        | press                    : <array; (1094,); float32>
        | temp                     : <array; (1094,); float32>

    Or you can also use attribute-style syntax::

        >>> dat.signal
        <class 'dolfyn.data.base.TimeData'>: Data Object with Keys:
        *------------
        | amp                      : <array; (4, 38, 1094); float16>
        | amp_b5                   : <array; (1, 38, 1094); float16>
        | corr                     : <array; (4, 38, 1094); uint8>
        | corr_b5                  : <array; (1, 38, 1094); uint8>


    Indexing
    ........

    You can directly access an item in a subgroup by::

        >>> dat['env.c_sound']
        array([1520.9   , 1520.8501, 1520.8501, ..., 1522.3   , 1522.3   ,
               1522.3   ], dtype=float32)

    # And you can test for the presence of a variable by::

        >>> 'signal.amp' in dat
        True

    """

    @property
    def n_time(self, ):
        """The number of timesteps in the data object."""
        try:
            return self['mpltime'].shape[-1]
        except KeyError:
            return self['vel'].shape[-1]

    @property
    def shape(self,):
        """The shape of 'scalar' data in this data object."""
        return self.u.shape

    @property
    def u(self,):
        """
        The first velocity component.

        This is simply a shortcut to self['vel'][0]. Therefore,
        depending on the coordinate system of the data object
        (self.props['coord_sys']), it is:

        - beam:      beam1
        - inst:      x
        - earth:     east
        - principal: streamwise
        """
        return self['vel'][0]

    @property
    def v(self,):
        """
        The second velocity component.

        This is simply a shortcut to self['vel'][1]. Therefore,
        depending on the coordinate system of the data object
        (self.props['coord_sys']), it is:

        - beam:      beam2
        - inst:      y
        - earth:     north
        - principal: cross-stream
        """
        return self['vel'][1]

    @property
    def w(self,):
        """
        The third velocity component.

        This is simply a shortcut to self['vel'][2]. Therefore,
        depending on the coordinate system of the data object
        (self.props['coord_sys']), it is:

        - beam:      beam3
        - inst:      z
        - earth:     up
        - principal: up
        """
        return self['vel'][2]

    @property
    def U(self,):
        "Horizontal velocity as a complex quantity."
        return self.u + self.v * 1j

    @property
    def U_mag(self,):
        """
        Horizontal velocity magnitude.
        """
        return np.abs(self.U)

    @property
    def U_angle(self,):
        """
        Angle of horizontal velocity vector (radians clockwise from
        east/X/streamwise).
        """
        return np.angle(self.U)

    def rotate2(self, out_frame, inplace=False):
        """Rotate the data object into a new coordinate system.

        Parameters
        ----------

        out_frame : string {'beam', 'inst', 'earth', 'principal'}
          The coordinate system to rotate the data into.

        inplace : bool
          Operate on self (True), or return a copy that
          has been rotated (False, default).

        Returns
        -------
        objout : :class:`Velocity <data.velocity.Velocity>`
          The rotated data object. This is `self` if inplace is True.

        See Also
        --------
        :func:`dolfyn.rotate2`

        """
        return rotate2(self, out_frame=out_frame, inplace=inplace)

    def calc_principal_angle(self, bin=None):
        """
        Compute the principal angle of the horizontal velocity.

        Parameters
        ----------

        bin : {int or None}
          For ADP objects, this is the depth bin where the principal
          angle is calculated. If it is None (default), the
          depth-averaged velocity is used.

        Notes
        -----

        This function sets (overwrites) the values of
        ``self.props['principal_angle']``, and
        ``self.props['coord_sys_principal_ref']``.

        .. morehere: document how exactly the principal angle is calculated.
        """
        if self.props['coord_sys'].lower() not in ['earth', 'inst',
                                                   'enu', 'xyz']:
            raise Exception("The principal angle should only be estimated "
                            "if the coordinate system is either 'earth' or "
                            "'inst'.")
        self.props['coord_sys_principal_ref'] = self.props['coord_sys']
        dt = self.U  # horizontal velocity as a complex number
        if bin is None:
            if dt.ndim > 1:
                dt = dt.mean(0)
        else:
            dt = dt[bin]
        dt[dt.imag <= 0] *= -1
        # Now double the angle, so that angles near pi and 0 get averaged
        # together correctly:
        dt *= np.exp(1j * np.angle(dt))
        dt = np.ma.masked_invalid(dt)
        # Divide the angle by 2 to remove the doubling done on the previous
        # line.
        self.props['principal_angle'] = np.angle(
            np.mean(dt, 0, dtype=np.complex128)) / 2
        # Angle returns values between -pi and pi.  I want the
        # principal angle always to be between 0 and pi.  Therefore,
        # add pi to the negative ones.
        if self.props['principal_angle'] < 0:
            self.props['principal_angle'] += np.pi

    @property
    def principal_angle(self,):
        """
        Return the principal angle of the data.
        """
        if 'principal_angle' not in self.props:
            self.calc_principal_angle()
        return self.props['principal_angle']

    @property
    def _repr_header(self, ):
        time_string = '{:.2f} {} (started: {})'
        if (not hasattr(self, 'mpltime')) or self.mpltime[0] < 1:
            time_string = '-->No Time Information!<--'
        else:
            tm = [self.mpltime[0], self.mpltime[-1]]
            dt = num2date(tm[0])
            delta = (tm[-1] - tm[0])
            if delta > 1:
                units = 'days'
            elif delta * 24 > 1:
                units = 'hours'
                delta *= 24
            elif delta * 24 * 60 > 1:
                delta *= 24 * 60
                units = 'minutes'
            else:
                delta *= 24 * 3600
                units = 'seconds'
            time_string = time_string.format(delta, units,
                                             dt.strftime('%b %d, %Y %H:%M'))

        if len(self.shape) > 1:
            shape_string = '({} bins, {} pings @ {}Hz)'.format(
                self.shape[0], self.shape[1], self.props['fs'])
        else:
            shape_string = '({} pings @ {}Hz)'.format(
                self.shape[0], self.props['fs'])
        return ("<%s data object>\n"
                "  . %s\n"
                "  . %s-frame\n"
                "  . %s\n" %
                (self.props['inst_type'],
                 time_string,
                 self.props['coord_sys'].upper(),
                 shape_string))

    @property
    def _make_model(self, ):
        """
        The make and model of the instrument that collected the data
        in this data object.
        """
        return '{} {}'.format(self.props['inst_make'],
                              self.props['inst_model']).lower()


class VelTkeData(TimeData):

    @property
    def tauij(self, ):
        n = self.tke_vec
        s = self.stress
        return np.array([[n[0], s[0], s[1]],
                         [s[0], n[1], s[2]],
                         [s[1], s[2], n[2]]])

    def rotate(self, rmat):
        # Transpose second index of rmat for rotation
        t = np.einsum('ij...,jlm...,nl...->inm...', rmat, self.tauij, rmat)
        out = type(self)()
        out['tke_vec'] = np.stack((t[0, 0], t[1, 1], t[2, 2]), axis=0)
        out['stress'] = np.stack((t[0, 1], t[0, 2], t[1, 2]), axis=0)
        return out

    def tau_is_pd(self, ):
        t = np.moveaxis(self.tauij, [0, 1], [-2, -1])
        val = t[..., 0, 0] > 0
        for idx in [2, 3]:
            val &= np.linalg.det(t[..., :idx, :idx]) > 0
        return val

    @property
    def Ecoh(self,):
        """
        Niel Kelley's "coherent energy", i.e. the rms of the stresses.
        """
        # Why did he do it this way, instead of the sum of the magnitude of the
        # stresses?
        return (self.upwp_ ** 2 + self.upvp_ ** 2 + self.vpwp_ ** 2) ** (0.5)

    def Itke(self, thresh=0):
        """
        Turbulence kinetic energy intensity.

        Ratio of sqrt(tke) to velocity magnitude.
        """
        return np.ma.masked_where(self.U_mag < thresh,
                                  np.sqrt(self.tke) / self.U_mag)

    def I(self, thresh=0):
        """
        Turbulence intensity.

        Ratio of standard deviation of horizontal velocity magnitude
        to horizontal velocity magnitude.
        """
        return np.ma.masked_where(self.U_mag < thresh,
                                  self.sigma_Uh / self.U_mag)

    @property
    def tke(self,):
        """
        The turbulent kinetic energy (sum of the three components).
        """
        return self.tke_vec.sum(0) / 2

    @property
    def upvp_(self,):
        """
        u'v' Reynolds stress
        """
        return self.stress[0]

    @property
    def upwp_(self,):
        """
        u'w' Reynolds stress
        """
        return self.stress[1]

    @property
    def vpwp_(self,):
        """
        v'w' Reynolds stress
        """
        return self.stress[2]

    @property
    def upup_(self,):
        """
        u'u' component of the tke.
        """
        return self.tke_vec[0]

    @property
    def vpvp_(self,):
        """
        v'v' component of the tke.
        """
        return self.tke_vec[1]

    @property
    def wpwp_(self,):
        """
        w'w' component of the tke.
        """
        return self.tke_vec[2]


class VelBinner(TimeBinner):

    # This defines how cross-spectra and stresses are computed.
    _cross_pairs = [(0, 1), (0, 2), (1, 2)]

    def do_tke(self, indat, out=None):
        if out is None:
            out = VelTkeData()
        out['tke_vec'] = self.calc_tke(indat['vel'])
        out['stress'] = self.calc_stress(indat['vel'])
        return out

    def do_spec(self, indat, out=None, names=['vel']):
        if out is None:
            out = FreqData()
            out['props'] = dict(fs=indat['props']['fs'],
                                n_fft=self.n_fft,
                                n_bin=self.n_bin)
            out['omega'] = self.calc_omega()
        for nm in names:
            out[nm] = self.calc_vel_psd(indat[nm])
        return out

    def do_cross_spec(self, indat, out=None, names=['vel']):
        if out is None:
            out = FreqData()
        for nm in names:
            out[nm + '_cross'] = self.calc_vel_cpsd(indat[nm])
        return out

    def calc_tke(self, veldat, noise=[0, 0, 0]):
        """Calculate the tke (variances of u,v,w).

        Parameters
        ----------
        veldat : a velocity data array. The last dimension is assumed
                 to be time.

        noise : a three-element vector of the noise levels of the
                velocity data for ach component of velocity.

        Returns
        -------
        out : An array of tke values.
        """
        out = np.mean(self.detrend(veldat[:3]) ** 2,
                      -1, dtype=np.float64).astype('float32')
        out[0] -= noise[0] ** 2
        out[1] -= noise[1] ** 2
        out[2] -= noise[2] ** 2
        return out

    def calc_stress(self, veldat):
        """Calculate the stresses (cross-covariances of u,v,w).

        Parameters
        ----------
        veldat : a velocity data array. The last dimension is assumed
                 to be time.

        Returns
        -------
        out : An array of stress values.
        """
        out = np.empty(self._outshape(veldat[:3].shape)[:-1],
                       dtype=np.float32)
        for idx, p in enumerate(self._cross_pairs):
            out[idx] = np.mean(
                self.detrend(veldat[p[0]]) *
                self.detrend(veldat[p[1]]),
                -1, dtype=np.float64
            ).astype(np.float32)
        return out

    def calc_vel_psd(self, veldat,
                     rotate_u=False,
                     fs=None,
                     window='hann', noise=[0, 0, 0],
                     n_bin=None, n_fft=None, n_pad=None,
                     step=None):
        """
        Calculate the psd of velocity.

        Parameters
        ----------
        veldat   : np.ndarray
          The raw velocity data.
        rotate_u : bool (optional)
          If True, each 'bin' of horizontal velocity is rotated into
          its principal axis prior to calculating the psd.  (default:
          False).
        fs : float (optional)
          The sample rate (default: from the binner).
        window : string or array
          Specify the window function.
        noise : list(3 floats) (optional)
          Noise level of each component's velocity measurement
          (default 0).
        n_bin : int (optional)
          The bin-size (default: from the binner).
        n_fft : int (optional)
          The fft size (default: from the binner).
        n_pad : int (optional)
          The number of values to pad with zero (default: 0)
        step : int (optional)
          Controls amount of overlap in fft (default: the step size is
          chosen to maximize data use, minimize nens, and have a
          minimum of 50% overlap.).

        Returns
        -------
        Spec    : np.ndarray (3, M, N_FFT)
          The first-dimension of the spectrum is the three
          different spectra: 'uu', 'vv', 'ww'.
        """
        veldat = veldat.copy()
        if rotate_u:
            tmpdat = self.reshape(veldat[0] + 1j * veldat[1])
            tmpdat *= np.exp(-1j * np.angle(tmpdat.mean(-1)))
            veldat[0] = tmpdat.real
            veldat[1] = tmpdat.imag
            if noise[0] != noise[1]:
                warnings.warn(
                    'Noise levels different for u,v. This means '
                    'noise-correction cannot be done here when '
                    'rotating velocity.')
                noise[0] = noise[1] = 0
        out = np.empty(self._outshape_fft(veldat[:3].shape, ),
                       dtype=np.float32)
        for idx in range(3):
            out[idx] = self.psd(veldat[idx], fs=fs, noise=noise[idx],
                                window=window, n_bin=n_bin,
                                n_pad=n_pad, n_fft=n_fft, step=step,)
        if ma.valid:
            if self.hz:
                units = ma.unitsDict({'s': -2, 'm': -2, 'hz': -1})
            else:
                units = ma.unitsDict({'s': -1, 'm': -2})
            out = ma.marray(out,
                            ma.varMeta('S_{%s%s}', units,
                                       veldat.meta.dim_names + ['freq'])
                            )
        return out

    def calc_vel_cpsd(self, veldat,
                      rotate_u=False,
                      fs=None,
                      window='hann',
                      n_bin=None, n_fft=None, n_pad=None,
                      step=None):
        """
        Calculate the cross-spectra of velocity components.

        Parameters
        ----------
        veldat   : np.ndarray
          The raw velocity data.
        rotate_u : bool (optional)
          If True, each 'bin' of horizontal velocity is rotated into
          its principal axis prior to calculating the psd.  (default:
          False).
        fs : float (optional)
          The sample rate (default: from the binner).
        window : string or array
          Specify the window function.
        n_bin : int (optional)
          The bin-size (default: from the binner).
        n_fft : int (optional)
          The fft size (default: from the binner).
        n_pad : int (optional)
          The number of values to pad with zero (default: 0)
        step : int (optional)
          Controls amount of overlap in fft (default: the step size is
          chosen to maximize data use, minimize nens, and have a
          minimum of 50% overlap.).

        Returns
        -------
        CSpec    : np.ndarray (3, M, N_FFT)
          The first-dimension of the cross-spectrum is the three
          different cross-spectra: 'uv', 'uw', 'vw' (in that order).
        """
        n_fft = self._parse_nfft(n_fft)
        veldat = veldat.copy()
        if rotate_u:
            tmpdat = self.reshape(veldat[0] + 1j * veldat[1])
            tmpdat *= np.exp(-1j * np.angle(tmpdat.mean(-1)))
            veldat[0] = tmpdat.real
            veldat[1] = tmpdat.imag
        out = np.empty(self._outshape_fft(veldat[:3].shape, ), dtype='complex')
        for ip, ipair in enumerate(self._cross_pairs):
            out[ip] = self.cpsd(veldat[ipair[0]],
                                veldat[ipair[1]],
                                n_fft=n_fft)
        if ma.valid:
            if self.hz:
                units = ma.unitsDict({'s': -2, 'm': -2, 'hz': -1})
            else:
                units = ma.unitsDict({'s': -1, 'm': -2})
            out = ma.marray(out,
                            ma.varMeta('S_{%s%s}', units,
                                       veldat.meta.dim_names + ['freq'])
                            )
        return out
