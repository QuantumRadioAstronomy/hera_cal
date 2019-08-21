# -*- coding: utf-8 -*-
# Copyright 2018 the HERA Project
# Licensed under the MIT License

from __future__ import print_function, division, absolute_import

import pytest
import os
import numpy as np
import sys
from collections import OrderedDict as odict
import copy
import glob
from six.moves import map, zip
from pyuvdata import UVCal, UVData
import warnings

from .. import io, abscal, redcal, utils
from ..data import DATA_PATH
from ..datacontainer import DataContainer
from ..utils import split_pol
from ..apply_cal import calibrate_in_place


@pytest.mark.filterwarnings("ignore:The default for the `center` keyword has changed")
@pytest.mark.filterwarnings("ignore:invalid value encountered in true_divide")
class Test_AbsCal_Funcs(object):
    def setup_method(self):
        np.random.seed(0)

        # load into pyuvdata object
        self.data_file = os.path.join(DATA_PATH, "zen.2458043.12552.xx.HH.uvORA")
        self.uvd = UVData()
        self.uvd.read_miriad(self.data_file)
        self.freq_array = np.unique(self.uvd.freq_array)
        self.antpos, self.ants = self.uvd.get_ENU_antpos(center=True, pick_data_ants=True)
        self.antpos = odict(zip(self.ants, self.antpos))
        self.time_array = np.unique(self.uvd.time_array)

        # configure data into dictionaries
        data, flgs = io.load_vis(self.uvd, pop_autos=True)
        wgts = odict()
        for k in flgs.keys():
            wgts[k] = (~flgs[k]).astype(np.float)
        wgts = DataContainer(wgts)

        # configure baselines
        bls = odict([(x, self.antpos[x[0]] - self.antpos[x[1]]) for x in data.keys()])

        # make mock data
        abs_gain = 0.5
        TT_phi = np.array([-0.004, 0.006, 0])
        model = odict()
        for i, k in enumerate(data.keys()):
            model[k] = data[k] * np.exp(abs_gain + 1j * np.dot(TT_phi, bls[k]))

        # assign data
        self.data = data
        self.bls = bls
        self.model = model
        self.wgts = wgts

    def test_data_key_to_array_axis(self):
        m, pk = abscal.data_key_to_array_axis(self.model, 2)
        assert m[(24, 25)].shape == (60, 64, 1)
        assert 'xx' in pk
        # test w/ avg_dict
        m, ad, pk = abscal.data_key_to_array_axis(self.model, 2, avg_dict=self.bls)
        assert m[(24, 25)].shape == (60, 64, 1)
        assert ad[(24, 25)].shape == (3,)
        assert 'xx' in pk

    def test_array_axis_to_data_key(self):
        m, pk = abscal.data_key_to_array_axis(self.model, 2)
        m2 = abscal.array_axis_to_data_key(m, 2, ['xx'])
        assert m2[(24, 25, 'xx')].shape == (60, 64)
        # copy dict
        m, ad, pk = abscal.data_key_to_array_axis(self.model, 2, avg_dict=self.bls)
        m2, cd = abscal.array_axis_to_data_key(m, 2, ['xx'], copy_dict=ad)
        assert m2[(24, 25, 'xx')].shape == (60, 64)
        assert cd[(24, 25, 'xx')].shape == (3,)

    def test_interp2d(self):
        # test interpolation w/ warning
        m, mf = abscal.interp2d_vis(self.data, self.time_array, self.freq_array,
                                    self.time_array, self.freq_array, flags=self.wgts, medfilt_flagged=False)
        assert m[(24, 25, 'xx')].shape == (60, 64)
        # downsampling w/ no flags
        m, mf = abscal.interp2d_vis(self.data, self.time_array, self.freq_array,
                                    self.time_array[::2], self.freq_array[::2])
        assert m[(24, 25, 'xx')].shape == (30, 32)
        # test flag propagation
        m, mf = abscal.interp2d_vis(self.data, self.time_array, self.freq_array,
                                    self.time_array, self.freq_array, flags=self.wgts, medfilt_flagged=True)
        assert np.all(mf[(24, 25, 'xx')][10, 0])
        # test flag extrapolation
        m, mf = abscal.interp2d_vis(self.data, self.time_array, self.freq_array,
                                    self.time_array + .0001, self.freq_array, flags=self.wgts, flag_extrapolate=True)
        assert np.all(mf[(24, 25, 'xx')][-1].min())

    def test_wiener(self):
        # test smoothing
        d = abscal.wiener(self.data, window=(5, 15), noise=None, medfilt=True, medfilt_kernel=(1, 13))
        assert d[(24, 37, 'xx')].shape == (60, 64)
        assert d[(24, 37, 'xx')].dtype == np.complex
        # test w/ noise
        d = abscal.wiener(self.data, window=(5, 15), noise=0.1, medfilt=True, medfilt_kernel=(1, 13))
        assert d[(24, 37, 'xx')].shape == (60, 64)
        # test w/o medfilt
        d = abscal.wiener(self.data, window=(5, 15), medfilt=False)
        assert d[(24, 37, 'xx')].shape == (60, 64)
        # test as array
        d = abscal.wiener(self.data[(24, 37, 'xx')], window=(5, 15), medfilt=False, array=True)
        assert d.shape == (60, 64)
        assert d.dtype == np.complex

    def test_Baseline(self):
        # test basic execution
        keys = list(self.data.keys())
        k1 = (24, 25, 'xx')    # 14.6 m E-W
        i1 = keys.index(k1)
        k2 = (24, 37, 'xx')    # different
        i2 = keys.index(k2)
        k3 = (52, 53, 'xx')   # 14.6 m E-W
        i3 = keys.index(k3)
        bls = list(map(lambda k: abscal.Baseline(self.antpos[k[1]] - self.antpos[k[0]], tol=2.0), keys))
        bls_conj = list(map(lambda k: abscal.Baseline(self.antpos[k[0]] - self.antpos[k[1]], tol=2.0), keys))
        assert bls[i1] == bls[i1]
        assert bls[i1] != bls[i2]
        assert (bls[i1] == bls_conj[i1]) == 'conjugated'
        # test different yet redundant baselines still agree
        assert bls[i1] == bls[i3]
        # test tolerance works as expected
        bls = list(map(lambda k: abscal.Baseline(self.antpos[k[1]] - self.antpos[k[0]], tol=1e-4), keys))
        assert bls[i1] != bls[i3]

    def test_match_red_baselines(self):
        model = copy.deepcopy(self.data)
        model = DataContainer(odict([((k[0] + 1, k[1] + 1, k[2]), model[k]) for i, k in enumerate(model.keys())]))
        del model[(25, 54, 'xx')]
        model_antpos = odict([(k + 1, self.antpos[k]) for i, k in enumerate(self.antpos.keys())])
        new_model = abscal.match_red_baselines(model, model_antpos, self.data, self.antpos, tol=2.0, verbose=False)
        assert len(new_model.keys()) == 8
        assert (24, 37, 'xx') in new_model
        assert (24, 53, 'xx') not in new_model

    def test_mirror_data_to_red_bls(self):
        # make fake data
        reds = redcal.get_reds(self.antpos, pols=['xx'])
        data = DataContainer(odict(list(map(lambda k: (k[0], self.data[k[0]]), reds[:5]))))
        # test execuation
        d = abscal.mirror_data_to_red_bls(data, self.antpos)
        assert len(d.keys()) == 16
        assert (24, 25, 'xx') in d
        # test correct value is propagated
        assert np.allclose(data[(24, 25, 'xx')][30, 30], d[(38, 39, 'xx')][30, 30])
        # test reweighting
        w = abscal.mirror_data_to_red_bls(self.wgts, self.antpos, weights=True)
        assert w[(24, 25, 'xx')].dtype == np.float
        assert np.allclose(w[(24, 25, 'xx')].max(), 16.0)

    def test_flatten(self):
        li = abscal.flatten([['hi']])
        assert np.array(li).ndim == 1

    @pytest.mark.filterwarnings("ignore:Casting complex values to real discards the imaginary part")
    def test_avg_data_across_red_bls(self):
        # test basic execution
        wgts = copy.deepcopy(self.wgts)
        wgts[(24, 25, 'xx')][45, 45] = 0.0
        data, flags, antpos, ants, freqs, times, lsts, pols = io.load_vis(self.data_file, return_meta=True)
        rd, rf, rk = abscal.avg_data_across_red_bls(data, antpos, wgts=wgts, tol=2.0, broadcast_wgts=False)
        assert rd[(24, 25, 'xx')].shape == (60, 64)
        assert rf[(24, 25, 'xx')][45, 45] > 0.0
        # test various kwargs
        wgts[(24, 25, 'xx')][45, 45] = 0.0
        rd, rf, rk = abscal.avg_data_across_red_bls(data, antpos, tol=2.0, wgts=wgts, broadcast_wgts=True)
        assert len(rd.keys()) == 9
        assert len(rf.keys()) == 9
        assert np.allclose(rf[(24, 25, 'xx')][45, 45], 0.0)
        # test averaging worked
        rd, rf, rk = abscal.avg_data_across_red_bls(data, antpos, tol=2.0, broadcast_wgts=False)
        v = np.mean([data[(52, 53, 'xx')], data[(37, 38, 'xx')], data[(24, 25, 'xx')], data[(38, 39, 'xx')]], axis=0)
        assert np.allclose(rd[(24, 25, 'xx')], v)
        # test mirror_red_data
        rd, rf, rk = abscal.avg_data_across_red_bls(data, antpos, wgts=self.wgts, tol=2.0, mirror_red_data=True)
        assert len(rd.keys()) == 21
        assert len(rf.keys()) == 21

    def test_match_times(self):
        dfiles = list(map(lambda f: os.path.join(DATA_PATH, f), ['zen.2458043.12552.xx.HH.uvORA',
                                                                 'zen.2458043.13298.xx.HH.uvORA']))
        mfiles = list(map(lambda f: os.path.join(DATA_PATH, f), ['zen.2458042.12552.xx.HH.uvXA',
                                                                 'zen.2458042.13298.xx.HH.uvXA']))
        # test basic execution
        relevant_mfiles = abscal.match_times(dfiles[0], mfiles, filetype='miriad')
        assert len(relevant_mfiles) == 2
        # test basic execution
        relevant_mfiles = abscal.match_times(dfiles[1], mfiles, filetype='miriad')
        assert len(relevant_mfiles) == 1
        # test no overlap
        mfiles = sorted(glob.glob(os.path.join(DATA_PATH, 'zen.2457698.40355.xx.HH.uvcA')))
        relevant_mfiles = abscal.match_times(dfiles[0], mfiles, filetype='miriad')
        assert len(relevant_mfiles) == 0

    def test_rephase_vis(self):
        dfile = os.path.join(DATA_PATH, 'zen.2458043.12552.xx.HH.uvORA')
        mfiles = list(map(lambda f: os.path.join(DATA_PATH, f), ['zen.2458042.12552.xx.HH.uvXA']))
        m, mf, mantp, mant, mfr, mt, ml, mp = io.load_vis(mfiles, return_meta=True)
        d, df, dantp, dant, dfr, dt, dl, dp = io.load_vis(dfile, return_meta=True)
        bls = odict(list(map(lambda k: (k, dantp[k[0]] - dantp[k[1]]), d.keys())))

        # basic execution
        new_m, new_f = abscal.rephase_vis(m, ml, dl, bls, dfr)

        k = list(new_m.keys())[0]
        assert new_m[k].shape == d[k].shape
        assert np.all(new_f[k][-1])
        assert not np.any(new_f[k][0])

    def test_cut_bl(self):
        Nbls = len(self.data)
        _data = abscal.cut_bls(self.data, bls=self.bls, min_bl_cut=20.0, inplace=False)
        assert Nbls == 21
        assert len(_data) == 9
        _data2 = copy.deepcopy(self.data)
        abscal.cut_bls(_data2, bls=self.bls, min_bl_cut=20.0, inplace=True)
        assert len(_data2) == 9
        _data = abscal.cut_bls(self.data, bls=self.bls, min_bl_cut=20.0, inplace=False)
        abscal.cut_bls(_data2, min_bl_cut=20.0, inplace=True)
        assert len(_data2) == 9

    def test_dft_phase_slope_solver(self):
        np.random.seed(21)

        # build a perturbed grid
        xs = np.zeros(100)
        ys = np.zeros(100)
        i = 0
        for x in np.arange(0, 100, 10):
            for y in np.arange(0, 100, 10):
                xs[i] = x + 5 * (.5 - np.random.rand())
                ys[i] = y + 5 * (.5 - np.random.rand())
                i += 1

        phase_slopes_x = (.2 * np.random.rand(5, 2) - .1)  # not too many phase wraps over the array
        phase_slopes_y = (.2 * np.random.rand(5, 2) - .1)  # (i.e. avoid undersampling of very fast slopes)
        data = np.array([np.exp(2.0j * np.pi * x * phase_slopes_x
                                + 2.0j * np.pi * y * phase_slopes_y) for x, y in zip(xs, ys)])

        x_slope_est, y_slope_est = abscal.dft_phase_slope_solver(xs, ys, data)
        np.testing.assert_array_almost_equal(phase_slopes_x - x_slope_est, 0, decimal=7)
        np.testing.assert_array_almost_equal(phase_slopes_y - y_slope_est, 0, decimal=7)


@pytest.mark.filterwarnings("ignore:The default for the `center` keyword has changed")
@pytest.mark.filterwarnings("ignore:invalid value encountered in true_divide")
@pytest.mark.filterwarnings("ignore:divide by zero encountered in true_divide")
@pytest.mark.filterwarnings("ignore:divide by zero encountered in log")
class Test_AbsCal(object):
    def setup_method(self):
        np.random.seed(0)
        # load into pyuvdata object
        self.data_fname = os.path.join(DATA_PATH, "zen.2458043.12552.xx.HH.uvORA")
        self.model_fname = os.path.join(DATA_PATH, "zen.2458042.12552.xx.HH.uvXA")
        self.AC = abscal.AbsCal(self.data_fname, self.model_fname, refant=24)
        self.input_cal = os.path.join(DATA_PATH, "zen.2458043.12552.xx.HH.uvORA.abs.calfits")

        # make custom gain keys
        d, fl, ap, a, f, t, l, p = io.load_vis(self.data_fname, return_meta=True, pick_data_ants=False)
        self.freq_array = f
        self.antpos = ap
        gain_pols = np.unique(list(map(split_pol, p)))
        self.ap = ap
        self.gk = abscal.flatten(list(map(lambda p: list(map(lambda k: (k, p), a)), gain_pols)))
        self.freqs = f

    def test_init(self):
        # init with no meta
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        assert AC.bls is None
        # init with meta
        AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.AC.antpos, freqs=self.AC.freqs)
        assert np.allclose(AC.bls[(24, 25, 'xx')][0], -14.607842046642745)
        # init with meta
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        # test feeding file and refant and bl_cut and bl_taper
        AC = abscal.AbsCal(self.model_fname, self.data_fname, refant=24, antpos=self.AC.antpos,
                           max_bl_cut=26.0, bl_taper_fwhm=15.0)
        # test ref ant
        assert AC.refant == 24
        assert np.allclose(np.linalg.norm(AC.antpos[24]), 0.0)
        # test bl cut
        assert not np.any(np.array(list(map(lambda k: np.linalg.norm(AC.bls[k]), AC.bls.keys()))) > 26.0)
        # test bl taper
        assert np.median(AC.wgts[(24, 25, 'xx')]) > np.median(AC.wgts[(24, 39, 'xx')])

        # test with input cal
        bl = (24, 25, 'xx')
        uvc = UVCal()
        uvc.read_calfits(self.input_cal)
        aa = uvc.ant_array.tolist()
        g = (uvc.gain_array[aa.index(bl[0])] * uvc.gain_array[aa.index(bl[1])].conj()).squeeze().T
        gf = (uvc.flag_array[aa.index(bl[0])] + uvc.flag_array[aa.index(bl[1])]).squeeze().T
        w = self.AC.wgts[bl] * ~gf
        AC2 = abscal.AbsCal(copy.deepcopy(self.AC.model), copy.deepcopy(self.AC.data), wgts=copy.deepcopy(self.AC.wgts), refant=24, input_cal=self.input_cal)
        np.testing.assert_array_almost_equal(self.AC.data[bl] / g * w, AC2.data[bl] * w)

    def test_abs_amp_logcal(self):
        # test execution and variable assignments
        self.AC.abs_amp_logcal(verbose=False)
        assert self.AC.abs_eta[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.abs_eta_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.abs_eta_arr.shape == (7, 60, 64, 1)
        assert self.AC.abs_eta_gain_arr.shape == (7, 60, 64, 1)
        # test Nones
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        assert AC.abs_eta is None
        assert AC.abs_eta_arr is None
        assert AC.abs_eta_gain is None
        assert AC.abs_eta_gain_arr is None
        # test propagation to gain_arr
        AC.abs_amp_logcal(verbose=False)
        AC._abs_eta_arr *= 0
        assert np.allclose(np.abs(AC.abs_eta_gain_arr[0, 0, 0, 0]), 1.0)
        # test custom gain
        g = self.AC.custom_abs_eta_gain(self.gk)
        assert len(g) == 47
        # test w/ no wgts
        AC.wgts = None
        AC.abs_amp_logcal(verbose=False)

    def test_TT_phs_logcal(self):
        # test execution
        self.AC.TT_phs_logcal(verbose=False)
        assert self.AC.TT_Phi_arr.shape == (7, 2, 60, 64, 1)
        assert self.AC.TT_Phi_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.abs_psi_arr.shape == (7, 60, 64, 1)
        assert self.AC.abs_psi_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.abs_psi[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.abs_psi_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.TT_Phi[(24, 'Jxx')].shape == (2, 60, 64)
        assert self.AC.TT_Phi_gain[(24, 'Jxx')].shape == (60, 64)
        assert np.allclose(np.angle(self.AC.TT_Phi_gain[(24, 'Jxx')]), 0.0)
        # test merge pols
        self.AC.TT_phs_logcal(verbose=False, four_pol=True)
        assert self.AC.TT_Phi_arr.shape == (7, 2, 60, 64, 1)
        assert self.AC.abs_psi_arr.shape == (7, 60, 64, 1)
        # test Nones
        AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.antpos)
        assert AC.abs_psi_arr is None
        assert AC.abs_psi_gain_arr is None
        assert AC.TT_Phi_arr is None
        assert AC.TT_Phi_gain_arr is None
        assert AC.abs_psi is None
        assert AC.abs_psi_gain is None
        assert AC.TT_Phi is None
        assert AC.TT_Phi_gain is None
        # test custom gain
        g = self.AC.custom_TT_Phi_gain(self.gk, self.ap)
        assert len(g) == 47
        g = self.AC.custom_abs_psi_gain(self.gk)
        assert g[(0, 'Jxx')].shape == (60, 64)
        # test w/ no wgts
        AC.wgts = None
        AC.TT_phs_logcal(verbose=False)

    def test_amp_logcal(self):
        self.AC.amp_logcal(verbose=False)
        assert self.AC.ant_eta[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_eta_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_eta_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_eta_arr.dtype == np.float
        assert self.AC.ant_eta_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_eta_gain_arr.dtype == np.complex
        # test Nones
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        assert AC.ant_eta is None
        assert AC.ant_eta_gain is None
        assert AC.ant_eta_arr is None
        assert AC.ant_eta_gain_arr is None
        # test w/ no wgts
        AC.wgts = None
        AC.amp_logcal(verbose=False)

    def test_phs_logcal(self):
        self.AC.phs_logcal(verbose=False)
        assert self.AC.ant_phi[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_phi_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_phi_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_phi_arr.dtype == np.float
        assert self.AC.ant_phi_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_phi_gain_arr.dtype == np.complex
        assert np.allclose(np.angle(self.AC.ant_phi_gain[(24, 'Jxx')]), 0.0)
        self.AC.phs_logcal(verbose=False, avg=True)
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        assert AC.ant_phi is None
        assert AC.ant_phi_gain is None
        assert AC.ant_phi_arr is None
        assert AC.ant_phi_gain_arr is None
        # test w/ no wgts
        AC.wgts = None
        AC.phs_logcal(verbose=False)

    def test_delay_lincal(self):
        # test w/o offsets
        self.AC.delay_lincal(verbose=False, kernel=(1, 3), medfilt=False)
        assert self.AC.ant_dly[(24, 'Jxx')].shape == (60, 1)
        assert self.AC.ant_dly_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_dly_arr.shape == (7, 60, 1, 1)
        assert self.AC.ant_dly_gain_arr.shape == (7, 60, 64, 1)
        # test w/ offsets
        self.AC.delay_lincal(verbose=False, kernel=(1, 3), medfilt=False)
        assert self.AC.ant_dly_phi[(24, 'Jxx')].shape == (60, 1)
        assert self.AC.ant_dly_phi_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.ant_dly_phi_arr.shape == (7, 60, 1, 1)
        assert self.AC.ant_dly_phi_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_dly_arr.shape == (7, 60, 1, 1)
        assert self.AC.ant_dly_arr.dtype == np.float
        assert self.AC.ant_dly_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.ant_dly_gain_arr.dtype == np.complex
        assert np.allclose(np.angle(self.AC.ant_dly_gain[(24, 'Jxx')]), 0.0)
        assert np.allclose(np.angle(self.AC.ant_dly_phi_gain[(24, 'Jxx')]), 0.0)
        # test exception
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        pytest.raises(AttributeError, AC.delay_lincal)
        # test Nones
        AC = abscal.AbsCal(self.AC.model, self.AC.data, freqs=self.freq_array)
        assert AC.ant_dly is None
        assert AC.ant_dly_gain is None
        assert AC.ant_dly_arr is None
        assert AC.ant_dly_gain_arr is None
        assert AC.ant_dly_phi is None
        assert AC.ant_dly_phi_gain is None
        assert AC.ant_dly_phi_arr is None
        assert AC.ant_dly_phi_gain_arr is None
        # test flags handling
        AC = abscal.AbsCal(self.AC.model, self.AC.data, freqs=self.freqs)
        AC.wgts[(24, 25, 'xx')] *= 0
        AC.delay_lincal(verbose=False)
        # test medfilt
        self.AC.delay_lincal(verbose=False, medfilt=False)
        self.AC.delay_lincal(verbose=False, time_avg=True)
        # test w/ no wgts
        AC.wgts = None
        AC.delay_lincal(verbose=False)

    def test_delay_slope_lincal(self):
        # test w/o offsets
        self.AC.delay_slope_lincal(verbose=False, kernel=(1, 3), medfilt=False)
        assert self.AC.dly_slope[(24, 'Jxx')].shape == (2, 60, 1)
        assert self.AC.dly_slope_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.dly_slope_arr.shape == (7, 2, 60, 1, 1)
        assert self.AC.dly_slope_gain_arr.shape == (7, 60, 64, 1)
        assert self.AC.dly_slope_ant_dly_arr.shape == (7, 60, 1, 1)
        assert np.allclose(np.angle(self.AC.dly_slope_gain[(24, 'Jxx')]), 0.0)
        g = self.AC.custom_dly_slope_gain(self.gk, self.ap)
        assert g[(0, 'Jxx')].shape == (60, 64)
        # test exception
        AC = abscal.AbsCal(self.AC.model, self.AC.data)
        pytest.raises(AttributeError, AC.delay_slope_lincal)
        # test Nones
        AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.antpos, freqs=self.freq_array)
        assert AC.dly_slope is None
        assert AC.dly_slope_gain is None
        assert AC.dly_slope_arr is None
        assert AC.dly_slope_gain_arr is None
        assert AC.dly_slope_ant_dly_arr is None
        # test medfilt and time_avg
        self.AC.delay_slope_lincal(verbose=False, medfilt=False)
        self.AC.delay_slope_lincal(verbose=False, time_avg=True)
        # test four pol
        self.AC.delay_slope_lincal(verbose=False, four_pol=True)
        assert self.AC.dly_slope[(24, 'Jxx')].shape == (2, 60, 1)
        assert self.AC.dly_slope_gain[(24, 'Jxx')].shape == (60, 64)
        assert self.AC.dly_slope_arr.shape == (7, 2, 60, 1, 1)
        assert self.AC.dly_slope_gain_arr.shape == (7, 60, 64, 1)
        # test flags handling
        AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.ap, freqs=self.freqs)
        AC.wgts[(24, 25, 'xx')] *= 0
        AC.delay_slope_lincal(verbose=False)
        # test w/ no wgts
        AC.wgts = None
        AC.delay_slope_lincal(verbose=False)

    def test_global_phase_slope_logcal(self):
        for solver in ['dft', 'linfit']:
            # test w/o offsets
            self.AC.global_phase_slope_logcal(verbose=False, edge_cut=31, solver=solver)
            assert self.AC.phs_slope[(24, 'Jxx')].shape == (2, 60, 1)
            assert self.AC.phs_slope_gain[(24, 'Jxx')].shape == (60, 64)
            assert self.AC.phs_slope_arr.shape == (7, 2, 60, 1, 1)
            assert self.AC.phs_slope_gain_arr.shape == (7, 60, 64, 1)
            assert self.AC.phs_slope_ant_phs_arr.shape == (7, 60, 1, 1)
            assert np.allclose(np.angle(self.AC.phs_slope_gain[(24, 'Jxx')]), 0.0)
            g = self.AC.custom_phs_slope_gain(self.gk, self.ap)
            assert g[(0, 'Jxx')].shape == (60, 64)
            # test Nones
            AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.antpos, freqs=self.freq_array)
            assert AC.phs_slope is None
            assert AC.phs_slope_gain is None
            assert AC.phs_slope_arr is None
            assert AC.phs_slope_gain_arr is None
            assert AC.phs_slope_ant_phs_arr is None
            AC = abscal.AbsCal(self.AC.model, self.AC.data, antpos=self.ap, freqs=self.freqs)
            AC.wgts[(24, 25, 'xx')] *= 0
            AC.global_phase_slope_logcal(verbose=False, solver=solver)
            # test w/ no wgts
            AC.wgts = None
            AC.global_phase_slope_logcal(verbose=False, solver=solver)

    def test_merge_gains(self):
        self.AC.abs_amp_logcal(verbose=False)
        self.AC.TT_phs_logcal(verbose=False)
        self.AC.delay_lincal(verbose=False)
        self.AC.phs_logcal(verbose=False)
        self.AC.amp_logcal(verbose=False)
        gains = [self.AC.abs_eta_gain, self.AC.TT_Phi_gain, self.AC.abs_psi_gain,
                 self.AC.ant_dly_gain, self.AC.ant_eta_gain, self.AC.ant_phi_gain]
        gains[0][(99, 'Jxx')] = 1.0
        # merge shared keys
        mgains = abscal.merge_gains(gains, merge_shared=True)
        assert (99, 'Jxx') not in mgains
        # merge all keys
        mgains = abscal.merge_gains(gains, merge_shared=False)
        assert (99, 'Jxx') in mgains
        # test merge
        k = (53, 'Jxx')
        assert mgains[k].shape == (60, 64)
        assert mgains[k].dtype == np.complex
        assert np.allclose(np.abs(mgains[k][0, 0]), np.abs(self.AC.abs_eta_gain[k] * self.AC.ant_eta_gain[k])[0, 0])
        assert np.allclose(np.angle(mgains[k][0, 0]), np.angle(self.AC.TT_Phi_gain[k] * self.AC.abs_psi_gain[k]
                                                               * self.AC.ant_dly_gain[k] * self.AC.ant_phi_gain[k])[0, 0])

        # test merge of flag dictionaries
        f1 = {(1, 'Jxx'): np.zeros(5, np.bool)}
        f2 = {(1, 'Jxx'): np.zeros(5, np.bool)}
        f3 = abscal.merge_gains([f1, f2])
        assert f3[(1, 'Jxx')].dtype == np.bool_
        assert not np.any(f3[(1, 'Jxx')])
        f2[(1, 'Jxx')][:] = True
        f3 = abscal.merge_gains([f1, f2])
        assert np.all(f3[(1, 'Jxx')])

    def test_fill_dict_nans(self):
        data = copy.deepcopy(self.AC.data)
        wgts = copy.deepcopy(self.AC.wgts)
        data[(25, 38, 'xx')][15, 20] *= np.nan
        data[(25, 38, 'xx')][20, 15] *= np.inf
        abscal.fill_dict_nans(data, wgts=wgts, nan_fill=-1, inf_fill=-2)
        assert data[(25, 38, 'xx')][15, 20].real == -1
        assert data[(25, 38, 'xx')][20, 15].real == -2
        assert np.allclose(wgts[(25, 38, 'xx')][15, 20], 0)
        assert np.allclose(wgts[(25, 38, 'xx')][20, 15], 0)
        data = copy.deepcopy(self.AC.data)
        wgts = copy.deepcopy(self.AC.wgts)
        data[(25, 38, 'xx')][15, 20] *= np.nan
        data[(25, 38, 'xx')][20, 15] *= np.inf
        abscal.fill_dict_nans(data[(25, 38, 'xx')], wgts=wgts[(25, 38, 'xx')], nan_fill=-1, inf_fill=-2, array=True)
        assert data[(25, 38, 'xx')][15, 20].real == -1
        assert data[(25, 38, 'xx')][20, 15].real == -2
        assert np.allclose(wgts[(25, 38, 'xx')][15, 20], 0)
        assert np.allclose(wgts[(25, 38, 'xx')][20, 15], 0)

    def test_mock_data(self):
        # load into pyuvdata object
        data_file = os.path.join(DATA_PATH, "zen.2458043.12552.xx.HH.uvORA")
        data, flgs, ap, a, f, t, l, p = io.load_vis(data_file, return_meta=True)
        wgts = odict()
        for k in flgs.keys():
            wgts[k] = (~flgs[k]).astype(np.float)
        wgts = DataContainer(wgts)
        # make mock data
        dly_slope = np.array([-1e-9, 2e-9, 0])
        model = odict()
        for i, k in enumerate(data.keys()):
            bl = np.around(ap[k[0]] - ap[k[1]], 0)
            model[k] = data[k] * np.exp(2j * np.pi * f * np.dot(dly_slope, bl))
        model = DataContainer(model)
        # setup AbsCal
        AC = abscal.AbsCal(model, data, antpos=ap, wgts=wgts, freqs=f)
        # run delay_slope_cal
        AC.delay_slope_lincal(time_avg=True, verbose=False)
        # test recovery: accuracy only checked at 10% level
        assert np.allclose(AC.dly_slope_arr[0, 0, 0, 0, 0], 1e-9, atol=1e-10)
        assert np.allclose(AC.dly_slope_arr[0, 1, 0, 0, 0], -2e-9, atol=1e-10)
        # make mock data
        abs_gain = 0.02
        TT_phi = np.array([1e-3, -1e-3, 0])
        model = odict()
        for i, k in enumerate(data.keys()):
            bl = np.around(ap[k[0]] - ap[k[1]], 0)
            model[k] = data[k] * np.exp(abs_gain + 1j * np.dot(TT_phi, bl))
        model = DataContainer(model)
        # setup AbsCal
        AC = abscal.AbsCal(model, data, antpos=ap, wgts=wgts, freqs=f)
        # run abs_amp cal
        AC.abs_amp_logcal(verbose=False)
        # run TT_phs_logcal
        AC.TT_phs_logcal(verbose=False)
        assert np.allclose(np.median(AC.abs_eta_arr[0, :, :, 0][AC.wgts[(24, 25, 'xx')].astype(np.bool)]),
                           -0.01, atol=1e-3)
        assert np.allclose(np.median(AC.TT_Phi_arr[0, 0, :, :, 0][AC.wgts[(24, 25, 'xx')].astype(np.bool)]),
                           -1e-3, atol=1e-4)
        assert np.allclose(np.median(AC.TT_Phi_arr[0, 1, :, :, 0][AC.wgts[(24, 25, 'xx')].astype(np.bool)]),
                           1e-3, atol=1e-4)


@pytest.mark.filterwarnings("ignore:The default for the `center` keyword has changed")
class Test_Post_Redcal_Abscal_Run(object):
    def setup_method(self):
        self.data_file = os.path.join(DATA_PATH, 'test_input/zen.2458098.45361.HH.uvh5_downselected')
        self.redcal_file = os.path.join(DATA_PATH, 'test_input/zen.2458098.45361.HH.omni.calfits_downselected')
        self.model_files = [os.path.join(DATA_PATH, 'test_input/zen.2458042.60288.HH.uvRXLS.uvh5_downselected'),
                            os.path.join(DATA_PATH, 'test_input/zen.2458042.61034.HH.uvRXLS.uvh5_downselected')]

    def test_get_all_times_and_lsts(self):
        hd = io.HERAData(self.model_files)

        all_times, all_lsts = abscal.get_all_times_and_lsts(hd)
        assert len(all_times) == 120
        assert len(all_lsts) == 120
        np.testing.assert_array_equal(all_times, sorted(all_times))

        for f in hd.lsts.keys():
            hd.lsts[f] += 4.75
        all_times, all_lsts = abscal.get_all_times_and_lsts(hd, unwrap=True)
        assert all_lsts[-1] > 2 * np.pi
        np.testing.assert_array_equal(all_lsts, sorted(all_lsts))
        c = abscal.get_all_times_and_lsts(hd)
        assert all_lsts[0] < all_lsts[-1]

        hd = io.HERAData(self.data_file)
        hd.times = hd.times[0:4] + .5
        hd.lsts = hd.lsts[0:4] + np.pi
        all_times, all_lsts = abscal.get_all_times_and_lsts(hd, solar_horizon=0.0)
        assert len(all_times) == 0
        assert len(all_lsts) == 0

    def test_get_d2m_time_map(self):
        hd = io.HERAData(self.data_file)
        hdm = io.HERAData(self.model_files)
        all_data_times, all_data_lsts = abscal.get_all_times_and_lsts(hd)
        all_model_times, all_model_lsts = abscal.get_all_times_and_lsts(hdm)
        d2m_time_map = abscal.get_d2m_time_map(all_data_times, all_data_lsts, all_model_times, all_model_lsts)
        for dtime, mtime in d2m_time_map.items():
            dlst = all_data_lsts[np.argwhere(all_data_times == dtime)[0][0]]
            mlst = all_model_lsts[np.argwhere(all_model_times == mtime)[0][0]]
            assert np.abs(dlst - mlst) < np.median(np.ediff1d(all_data_lsts))
            assert np.min(np.abs(all_data_lsts - mlst)) == np.abs(dlst - mlst)

        hd = io.HERAData(self.data_file)
        hdm = io.HERAData(self.model_files[0])
        all_data_times, all_data_lsts = abscal.get_all_times_and_lsts(hd)
        all_model_times, all_model_lsts = abscal.get_all_times_and_lsts(hdm)
        d2m_time_map = abscal.get_d2m_time_map(all_data_times, all_data_lsts, all_model_times, all_model_lsts)
        for dtime, mtime in d2m_time_map.items():
            dlst = all_data_lsts[np.argwhere(all_data_times == dtime)[0][0]]
            if mtime is None:
                for mlst in all_model_lsts:
                    assert np.min(np.abs(all_data_lsts - mlst)) < np.abs(dlst - mlst)
            else:
                mlst = all_model_lsts[np.argwhere(all_model_times == mtime)[0][0]]
                assert np.abs(dlst - mlst) < np.median(np.ediff1d(all_data_lsts))
                assert np.min(np.abs(all_data_lsts - mlst)) == np.abs(dlst - mlst)

    def test_post_redcal_abscal(self):
        # setup
        hd = io.HERAData(self.data_file)
        hdm = io.HERAData(self.model_files)
        hc = io.HERACal(self.redcal_file)
        rc_gains, rc_flags, rc_quals, rc_tot_qual = hc.read()
        all_data_times, all_data_lsts = abscal.get_all_times_and_lsts(hd)
        all_model_times, all_model_lsts = abscal.get_all_times_and_lsts(hdm)
        d2m_time_map = abscal.get_d2m_time_map(all_data_times, all_data_lsts, all_model_times, all_model_lsts)
        tinds = [0, 1, 2]
        data, flags, nsamples = hd.read(times=hd.times[tinds], polarizations=['xx', 'yy'])
        model_times_to_load = [d2m_time_map[time] for time in hd.times[tinds]]
        model, model_flags, _ = io.partial_time_io(hdm, model_times_to_load, polarizations=['xx', 'yy'])
        model_bls = {bl: model.antpos[bl[0]] - model.antpos[bl[1]] for bl in model.keys()}
        utils.lst_rephase(model, model_bls, model.freqs, data.lsts - model.lsts,
                          lat=hdm.telescope_location_lat_lon_alt_degrees[0], inplace=True)
        for k in flags.keys():
            if k in model_flags:
                flags[k] += model_flags[k]
        data_ants = set([ant for bl in data.keys() for ant in utils.split_bl(bl)])
        rc_gains_subset = {k: rc_gains[k][tinds, :] for k in data_ants}
        rc_flags_subset = {k: rc_flags[k][tinds, :] for k in data_ants}
        calibrate_in_place(data, rc_gains_subset, data_flags=flags, 
                           cal_flags=rc_flags_subset, gain_convention=hc.gain_convention)

        # run function
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            delta_gains, AC = abscal.post_redcal_abscal(model, copy.deepcopy(data), flags, rc_flags_subset, min_bl_cut=1, verbose=False)

        # use returned gains to calibrate data
        calibrate_in_place(data, delta_gains, data_flags=flags, 
                           cal_flags=rc_flags_subset, gain_convention=hc.gain_convention)

        # basic shape & type checks
        for k in rc_gains.keys():
            assert k in delta_gains
            assert delta_gains[k].shape == (3, rc_gains[k].shape[1])
            assert delta_gains[k].dtype == np.complex
        for k in AC.model.keys():
            np.testing.assert_array_equal(model[k], AC.model[k])
        for k in AC.data.keys():
            np.testing.assert_array_almost_equal(data[k][~flags[k]], AC.data[k][~flags[k]], decimal=4)
        assert AC.ant_dly is None
        assert AC.ant_dly_arr is None
        assert AC.ant_dly_phi is None
        assert AC.ant_dly_phi_arr is None
        assert AC.dly_slope is not None
        assert AC.dly_slope_arr is not None
        assert AC.phs_slope is not None
        assert AC.dly_slope_arr is not None
        assert AC.abs_eta is not None
        assert AC.abs_eta_arr is not None
        assert AC.abs_psi is not None
        assert AC.abs_psi_arr is not None
        assert AC.TT_Phi is not None
        assert AC.TT_Phi_arr is not None

        # assert custom_* funcs with multiple pols returns different results
        # for different pols, as expected
        gkxx, gkyy = (0, 'Jxx'), (0, 'Jyy')
        for func, args in zip([AC.custom_abs_eta_gain, AC.custom_dly_slope_gain,
                               AC.custom_phs_slope_gain, AC.custom_TT_Phi_gain],
                              [(), (AC.antpos,), (AC.antpos,), (AC.antpos,)]):
            custom_gains = func([gkxx, gkyy], *args)
            assert not np.all(np.isclose(np.abs(custom_gains[gkxx] - custom_gains[gkyy]), 0.0, atol=1e-12))

    def test_post_redcal_abscal_run(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hca = abscal.post_redcal_abscal_run(self.data_file, self.redcal_file, self.model_files, phs_conv_crit=1e-4, 
                                                nInt_to_load=30, verbose=False, add_to_history='testing')
        pytest.raises(IOError, abscal.post_redcal_abscal_run, self.data_file, self.redcal_file, self.model_files, clobber=False)
        assert os.path.exists(self.redcal_file.replace('.omni.', '.abs.'))
        os.remove(self.redcal_file.replace('.omni.', '.abs.'))
        ac_gains, ac_flags, ac_quals, ac_total_qual = hca.build_calcontainers()
        hcr = io.HERACal(self.redcal_file)
        rc_gains, rc_flags, rc_quals, rc_total_qual = hcr.read()

        assert hcr.history.replace('\n', '').replace(' ', '') in hca.history.replace('\n', '').replace(' ', '')
        assert 'testing' in hca.history.replace('\n', '').replace(' ', '')
        for k in rc_gains:
            assert k in ac_gains
            assert ac_gains[k].shape == rc_gains[k].shape
            assert ac_gains[k].dtype == complex
        for k in rc_flags:
            assert k in ac_flags
            assert ac_flags[k].shape == rc_flags[k].shape
            assert ac_flags[k].dtype == bool
            np.testing.assert_array_equal(ac_flags[k][rc_flags[k]], rc_flags[k][rc_flags[k]])
        assert not np.all(list(ac_flags.values()))
        for pol in ['Jxx', 'Jyy']:
            assert pol in ac_total_qual
            assert ac_total_qual[pol].shape == rc_total_qual[pol].shape
            assert np.issubdtype(ac_total_qual[pol].dtype, np.floating)

        hd = io.HERAData(self.model_files[0])
        hd.read(return_data=False)
        hd.lst_array += 1
        temp_outfile = os.path.join(DATA_PATH, 'test_output/temp.uvh5')
        hd.write_uvh5(temp_outfile, clobber=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hca = abscal.post_redcal_abscal_run(self.data_file, self.redcal_file, [temp_outfile], phs_conv_crit=1e-4, 
                                                nInt_to_load=30, verbose=False, add_to_history='testing')
        assert os.path.exists(self.redcal_file.replace('.omni.', '.abs.'))
        np.testing.assert_array_equal(hca.total_quality_array, 0.0)
        np.testing.assert_array_equal(hca.gain_array, hcr.gain_array)
        np.testing.assert_array_equal(hca.flag_array, True)
        np.testing.assert_array_equal(hca.quality_array, 0.0)
        os.remove(self.redcal_file.replace('.omni.', '.abs.'))
        os.remove(temp_outfile)

    def test_post_redcal_abscal_argparser(self):
        sys.argv = [sys.argv[0], 'a', 'b', 'c', 'd', '--nInt_to_load', '6', '--verbose']
        a = abscal.post_redcal_abscal_argparser()
        assert a.data_file == 'a'
        assert a.redcal_file == 'b'
        assert a.model_files[0] == 'c'
        assert a.model_files[1] == 'd'
        assert len(a.model_files) == 2
        assert type(a.model_files) == list
        assert a.nInt_to_load == 6
        assert a.verbose is True
