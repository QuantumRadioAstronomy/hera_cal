# -*- coding: utf-8 -*-
# Copyright 2018 the HERA Project
# Licensed under the MIT License

import hera_cal.redcal as om
import numpy as np
import unittest
from copy import deepcopy
from hera_cal.utils import split_pol, conj_pol
from hera_cal.apply_cal import calibrate_in_place

np.random.seed(0)


def build_linear_array(nants, sep=14.7):
    antpos = {i: np.array([sep * i, 0, 0]) for i in range(nants)}
    return antpos


def build_hex_array(hexNum, sep=14.7):
    antpos, i = {}, 0
    for row in range(hexNum - 1, -(hexNum), -1):
        for col in range(2 * hexNum - abs(row) - 1):
            xPos = ((-(2 * hexNum - abs(row)) + 2) / 2.0 + col) * sep
            yPos = row * sep * 3**.5 / 2
            antpos[i] = np.array([xPos, yPos, 0])
            i += 1
    return antpos


class TestMethods(unittest.TestCase):

    def test_noise(self):
        n = om.noise((1024, 1024))
        self.assertEqual(n.shape, (1024, 1024))
        self.assertAlmostEqual(np.var(n), 1, 2)

    def test_sim_red_data(self):
        antpos = build_linear_array(10)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        gains, true_vis, data = om.sim_red_data(reds)
        self.assertEqual(len(gains), 10)
        self.assertEqual(len(data), 45)
        for bls in reds:
            bl0 = bls[0]
            ai, aj, pol = bl0
            ans0 = data[bl0] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
            for bl in bls[1:]:
                ai, aj, pol = bl
                ans = data[bl] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
                np.testing.assert_almost_equal(ans0, ans, 7)

        reds = om.get_reds(antpos, pols=['xx', 'yy', 'xy', 'yx'], pol_mode='4pol')
        gains, true_vis, data = om.sim_red_data(reds)
        self.assertEqual(len(gains), 20)
        self.assertEqual(len(data), 4 * (45))
        for bls in reds:
            bl0 = bls[0]
            ai, aj, pol = bl0
            ans0xx = data[(ai, aj, 'xx',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
            ans0xy = data[(ai, aj, 'xy',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jyy')].conj())
            ans0yx = data[(ai, aj, 'yx',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jxx')].conj())
            ans0yy = data[(ai, aj, 'yy',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jyy')].conj())
            for bl in bls[1:]:
                ai, aj, pol = bl
                ans_xx = data[(ai, aj, 'xx',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
                ans_xy = data[(ai, aj, 'xy',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jyy')].conj())
                ans_yx = data[(ai, aj, 'yx',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jxx')].conj())
                ans_yy = data[(ai, aj, 'yy',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jyy')].conj())
                np.testing.assert_almost_equal(ans0xx, ans_xx, 7)
                np.testing.assert_almost_equal(ans0xy, ans_xy, 7)
                np.testing.assert_almost_equal(ans0yx, ans_yx, 7)
                np.testing.assert_almost_equal(ans0yy, ans_yy, 7)

        reds = om.get_reds(antpos, pols=['xx', 'yy', 'xy', 'yX'], pol_mode='4pol_minV')
        gains, true_vis, data = om.sim_red_data(reds)
        self.assertEqual(len(gains), 20)
        self.assertEqual(len(data), 4 * (45))
        for bls in reds:
            bl0 = bls[0]
            ai, aj, pol = bl0
            ans0xx = data[(ai, aj, 'xx',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
            ans0xy = data[(ai, aj, 'xy',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jyy')].conj())
            ans0yx = data[(ai, aj, 'yx',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jxx')].conj())
            ans0yy = data[(ai, aj, 'yy',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jyy')].conj())
            np.testing.assert_almost_equal(ans0xy, ans0yx, 7)
            for bl in bls[1:]:
                ai, aj, pol = bl
                ans_xx = data[(ai, aj, 'xx',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jxx')].conj())
                ans_xy = data[(ai, aj, 'xy',)] / (gains[(ai, 'Jxx')] * gains[(aj, 'Jyy')].conj())
                ans_yx = data[(ai, aj, 'yx',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jxx')].conj())
                ans_yy = data[(ai, aj, 'yy',)] / (gains[(ai, 'Jyy')] * gains[(aj, 'Jyy')].conj())
                np.testing.assert_almost_equal(ans0xx, ans_xx, 7)
                np.testing.assert_almost_equal(ans0xy, ans_xy, 7)
                np.testing.assert_almost_equal(ans0yx, ans_yx, 7)
                np.testing.assert_almost_equal(ans0yy, ans_yy, 7)

    def test_check_polLists_minV(self):
        polLists = [['xy']]
        self.assertFalse(om.check_polLists_minV(polLists))
        polLists = [['xx', 'xy']]
        self.assertFalse(om.check_polLists_minV(polLists))
        polLists = [['xx', 'xy', 'yx']]
        self.assertFalse(om.check_polLists_minV(polLists))
        polLists = [['xy', 'yx'], ['xx'], ['yy'], ['xx'], ['yx', 'xy'], ['yy']]
        self.assertTrue(om.check_polLists_minV(polLists))

    def test_parse_pol_mode(self):
        reds = [[(0, 1, 'xx')]]
        self.assertEqual(om.parse_pol_mode(reds), '1pol')
        reds = [[(0, 1, 'xx')], [(0, 1, 'yy')]]
        self.assertEqual(om.parse_pol_mode(reds), '2pol')
        reds = [[(0, 1, 'xx')], [(0, 1, 'xy')], [(0, 1, 'yx')], [(0, 1, 'yy')]]
        self.assertEqual(om.parse_pol_mode(reds), '4pol')
        reds = [[(0, 1, 'xx')], [(0, 1, 'xy'), (0, 1, 'yx')], [(0, 1, 'yy')]]
        self.assertEqual(om.parse_pol_mode(reds), '4pol_minV')

        reds = [[(0, 1, 'xx')], [(0, 1, 'xy'), (0, 1, 'yx')], [(0, 1, 'LR')]]
        self.assertEqual(om.parse_pol_mode(reds), 'unrecognized_pol_mode')
        reds = [[(0, 1, 'xx')], [(0, 1, 'xy')]]
        self.assertEqual(om.parse_pol_mode(reds), 'unrecognized_pol_mode')
        reds = [[(0, 1, 'xy')]]
        self.assertEqual(om.parse_pol_mode(reds), 'unrecognized_pol_mode')
        reds = [[(0, 1, 'xx')], [(0, 1, 'xy'), (0, 1, 'yy')], [(0, 1, 'yx')]]
        self.assertEqual(om.parse_pol_mode(reds), 'unrecognized_pol_mode')

    def test_get_pos_red(self):

        pos = build_hex_array(3, sep=14.7)
        self.assertEqual(len(om.get_pos_reds(pos)), 30)

        pos = build_hex_array(7, sep=14.7)
        self.assertEqual(len(om.get_pos_reds(pos)), 234)
        for ant, r in pos.items():
            pos[ant] += [0, 0, 1 * r[0] - .5 * r[1]]
        self.assertEqual(len(om.get_pos_reds(pos)), 234)

        pos = build_hex_array(7, sep=1)
        self.assertLess(len(om.get_pos_reds(pos)), 234)
        self.assertEqual(len(om.get_pos_reds(pos, bl_error_tol=.1)), 234)

        pos = build_hex_array(7, sep=14.7)
        blerror = 1.0 - 1e-12
        error = blerror / 4
        for key, val in pos.items():
            th = np.random.choice([0, np.pi / 2, np.pi])
            phi = np.random.choice([0, np.pi / 2, np.pi, 3 * np.pi / 2])
            pos[key] = val + error * np.array([np.sin(th) * np.cos(phi), np.sin(th) * np.sin(phi), np.cos(th)])
        self.assertEqual(len(om.get_pos_reds(pos, bl_error_tol=1.0)), 234)
        self.assertGreater(len(om.get_pos_reds(pos, bl_error_tol=.99)), 234)

        pos = {0: np.array([0, 0, 0]), 1: np.array([20, 0, 0]), 2: np.array([10, 0, 0])}
        self.assertEqual(om.get_pos_reds(pos), [[(0, 2), (2, 1)], [(0, 1)]])
        self.assertEqual(om.get_pos_reds(pos, low_hi=True), [[(0, 2), (2, 1)], [(0, 1)]])

    def test_filter_reds(self):
        antpos = build_linear_array(7)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        # exclude ants
        r = om.filter_reds(reds, ex_ants=[0, 4])
        self.assertEqual(r, [[(1, 2, 'xx'), (2, 3, 'xx'), (5, 6, 'xx')], [(1, 3, 'xx'), (3, 5, 'xx')], [(2, 5, 'xx'), (3, 6, 'xx')], [(1, 5, 'xx'), (2, 6, 'xx')], [(1, 6, 'xx')]])
        # include ants
        r = om.filter_reds(reds, ants=[0, 1, 4, 5, 6])
        self.assertEqual(r, [[(0, 1, 'xx'), (4, 5, 'xx'), (5, 6, 'xx')], [(4, 6, 'xx')], [(1, 4, 'xx')], [(0, 4, 'xx'), (1, 5, 'xx')], [(0, 5, 'xx'), (1, 6, 'xx')], [(0, 6, 'xx')]])
        # exclued bls
        r = om.filter_reds(reds, ex_bls=[(0, 2), (1, 2), (0, 6)])
        self.assertEqual(r, [[(0, 1, 'xx'), (2, 3, 'xx'), (3, 4, 'xx'), (4, 5, 'xx'), (5, 6, 'xx')], [(1, 3, 'xx'), (2, 4, 'xx'), (3, 5, 'xx'), (4, 6, 'xx')], [(0, 3, 'xx'), (1, 4, 'xx'), (2, 5, 'xx'), (3, 6, 'xx')], [(0, 4, 'xx'), (1, 5, 'xx'), (2, 6, 'xx')], [(0, 5, 'xx'), (1, 6, 'xx')]])
        # include bls
        r = om.filter_reds(reds, bls=[(0, 1), (1, 2)])
        self.assertEqual(r, [[(0, 1, 'xx'), (1, 2, 'xx')]])
        # include ubls
        r = om.filter_reds(reds, ubls=[(0, 2), (1, 4)])
        self.assertEqual(r, [[(0, 2, 'xx'), (1, 3, 'xx'), (2, 4, 'xx'), (3, 5, 'xx'), (4, 6, 'xx')], [(0, 3, 'xx'), (1, 4, 'xx'), (2, 5, 'xx'), (3, 6, 'xx')]])
        # exclude ubls
        r = om.filter_reds(reds, ex_ubls=[(0, 2), (1, 4), (4, 5), (0, 5), (2, 3), (0, 6)])
        self.assertEqual(r, [[(0, 4, 'xx'), (1, 5, 'xx'), (2, 6, 'xx')]])
        # exclude crosspols
        # reds = omni.filter_reds(self.info.get_reds(), ex_crosspols=()
    
    def test_filter_reds_2pol(self):
        antpos = build_linear_array(4)
        reds = om.get_reds(antpos, pols=['xx', 'yy'], pol_mode='1pol')
        # include pols
        r = om.filter_reds(reds, pols=['xx'])
        self.assertEqual(r, [[(0, 1, 'xx'), (1, 2, 'xx'), (2, 3, 'xx')], [(0, 2, 'xx'), (1, 3, 'xx')], [(0, 3, 'xx')]])
        # exclude pols
        r = om.filter_reds(reds, ex_pols=['yy'])
        self.assertEqual(r, [[(0, 1, 'xx'), (1, 2, 'xx'), (2, 3, 'xx')], [(0, 2, 'xx'), (1, 3, 'xx')], [(0, 3, 'xx')]])
        # exclude ants
        r = om.filter_reds(reds, ex_ants=[0])
        self.assertEqual(r, [[(1, 2, 'xx'), (2, 3, 'xx')], [(1, 3, 'xx')], [(1, 2, 'yy'), (2, 3, 'yy')], [(1, 3, 'yy')]])
        # include ants
        r = om.filter_reds(reds, ants=[1, 2, 3])
        r = om.filter_reds(reds, ex_ants=[0])
        # exclued bls
        r = om.filter_reds(reds, ex_bls=[(1, 2), (0, 3)])
        self.assertEqual(r, [[(0, 1, 'xx'), (2, 3, 'xx')], [(0, 2, 'xx'), (1, 3, 'xx')], [(0, 1, 'yy'), (2, 3, 'yy')], [(0, 2, 'yy'), (1, 3, 'yy')]])
        # include bls
        r = om.filter_reds(reds, bls=[(0, 1), (1, 2)])
        self.assertEqual(r, [[(0, 1, 'xx'), (1, 2, 'xx')], [(0, 1, 'yy'), (1, 2, 'yy')]])
        # include ubls
        r = om.filter_reds(reds, ubls=[(0, 2)])
        self.assertEqual(r, [[(0, 2, 'xx'), (1, 3, 'xx')], [(0, 2, 'yy'), (1, 3, 'yy')]])
        # exclude ubls
        r = om.filter_reds(reds, ex_ubls=[(2, 3), (0, 3)])
        self.assertEqual(r, [[(0, 2, 'xx'), (1, 3, 'xx')], [(0, 2, 'yy'), (1, 3, 'yy')]])

    def test_add_pol_reds(self):
        reds = [[(1, 2)]]
        polReds = om.add_pol_reds(reds, pols=['xx'], pol_mode='1pol')
        self.assertEqual(polReds, [[(1, 2, 'xx')]])
        polReds = om.add_pol_reds(reds, pols=['xx', 'yy'], pol_mode='2pol')
        self.assertEqual(polReds, [[(1, 2, 'xx')], [(1, 2, 'yy')]])
        polReds = om.add_pol_reds(reds, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol')
        self.assertEqual(polReds, [[(1, 2, 'xx')], [(1, 2, 'xy')], [(1, 2, 'yx')], [(1, 2, 'yy')]])
        polReds = om.add_pol_reds(reds, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol_minV')
        self.assertEqual(polReds, [[(1, 2, 'xx')], [(1, 2, 'xy'), (1, 2, 'yx')], [(1, 2, 'yy')]])

        polReds = om.add_pol_reds(reds, pols=['xx', 'yy'], pol_mode='2pol', ex_ants=[(2, 'Jyy')])
        self.assertEqual(polReds, [[(1, 2, 'xx')], []])
        polReds = om.add_pol_reds(reds, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol', ex_ants=[(2, 'Jyy')])
        self.assertEqual(polReds, [[(1, 2, 'xx')], [], [(1, 2, 'yx')], []])
        polReds = om.add_pol_reds(reds, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol_minV', ex_ants=[(2, 'Jyy')])
        self.assertEqual(polReds, [[(1, 2, 'xx')], [(1, 2, 'yx')], []])


class TestRedundantCalibrator(unittest.TestCase):

    def test_build_eq(self):
        antpos = build_linear_array(3)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        gains, true_vis, data = om.sim_red_data(reds)
        info = om.RedundantCalibrator(reds)
        eqs = info.build_eqs(data.keys())
        self.assertEqual(len(eqs), 3)
        self.assertEqual(eqs['g_0_Jxx * g_1_Jxx_ * u_0_xx'], (0, 1, 'xx'))
        self.assertEqual(eqs['g_1_Jxx * g_2_Jxx_ * u_0_xx'], (1, 2, 'xx'))
        self.assertEqual(eqs['g_0_Jxx * g_2_Jxx_ * u_1_xx'], (0, 2, 'xx'))

        reds = om.get_reds(antpos, pols=['xx', 'yy', 'xy', 'yx'], pol_mode='4pol')
        gains, true_vis, data = om.sim_red_data(reds)
        info = om.RedundantCalibrator(reds)
        eqs = info.build_eqs(data.keys())
        self.assertEqual(len(eqs), 3 * 4)
        self.assertEqual(eqs['g_0_Jxx * g_1_Jyy_ * u_4_xy'], (0, 1, 'xy'))
        self.assertEqual(eqs['g_1_Jxx * g_2_Jyy_ * u_4_xy'], (1, 2, 'xy'))
        self.assertEqual(eqs['g_0_Jxx * g_2_Jyy_ * u_5_xy'], (0, 2, 'xy'))
        self.assertEqual(eqs['g_0_Jyy * g_1_Jxx_ * u_6_yx'], (0, 1, 'yx'))
        self.assertEqual(eqs['g_1_Jyy * g_2_Jxx_ * u_6_yx'], (1, 2, 'yx'))
        self.assertEqual(eqs['g_0_Jyy * g_2_Jxx_ * u_7_yx'], (0, 2, 'yx'))

        reds = om.get_reds(antpos, pols=['xx', 'yy', 'xy', 'yx'], pol_mode='4pol_minV')
        gains, true_vis, data = om.sim_red_data(reds)
        info = om.RedundantCalibrator(reds)
        eqs = info.build_eqs(data.keys())
        self.assertEqual(len(eqs), 3 * 4)
        self.assertEqual(eqs['g_0_Jxx * g_1_Jyy_ * u_4_xy'], (0, 1, 'xy'))
        self.assertEqual(eqs['g_1_Jxx * g_2_Jyy_ * u_4_xy'], (1, 2, 'xy'))
        self.assertEqual(eqs['g_0_Jxx * g_2_Jyy_ * u_5_xy'], (0, 2, 'xy'))
        self.assertEqual(eqs['g_0_Jyy * g_1_Jxx_ * u_4_xy'], (0, 1, 'yx'))
        self.assertEqual(eqs['g_1_Jyy * g_2_Jxx_ * u_4_xy'], (1, 2, 'yx'))
        self.assertEqual(eqs['g_0_Jyy * g_2_Jxx_ * u_5_xy'], (0, 2, 'yx'))

    def test_solver(self):
        antpos = build_linear_array(3)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds)
        w = {}
        w = dict([(k, 1.) for k in d.keys()])

        def solver(data, wgts, **kwargs):
            np.testing.assert_equal(data['g_0_Jxx * g_1_Jxx_ * u_0_xx'], d[0, 1, 'xx'])
            np.testing.assert_equal(data['g_1_Jxx * g_2_Jxx_ * u_0_xx'], d[1, 2, 'xx'])
            np.testing.assert_equal(data['g_0_Jxx * g_2_Jxx_ * u_1_xx'], d[0, 2, 'xx'])
            if len(wgts) == 0:
                return
            np.testing.assert_equal(wgts['g_0_Jxx * g_1_Jxx_ * u_0_xx'], w[0, 1, 'xx'])
            np.testing.assert_equal(wgts['g_1_Jxx * g_2_Jxx_ * u_0_xx'], w[1, 2, 'xx'])
            np.testing.assert_equal(wgts['g_0_Jxx * g_2_Jxx_ * u_1_xx'], w[0, 2, 'xx'])
            return
        info._solver(solver, d)
        info._solver(solver, d, w)

    def test_firstcal(self):
        NANTS = 18
        NFREQ = 64
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        fqs = np.linspace(.1, .2, NFREQ)
        #g, true_vis, d = om.sim_red_data(reds, shape=(1,NFREQ), gain_scatter=.1)
        g, true_vis, d = om.sim_red_data(reds, shape=(1, NFREQ), gain_scatter=0)
        delays = {k: np.random.randn() * 30 for k in g.keys()}  # in ns
        fc_gains = {k: np.exp(2j * np.pi * v * fqs) for k, v in delays.items()}
        delays = {k: np.array([[v]]) for k, v in delays.items()}
        fc_gains = {i: v.reshape(1, NFREQ) for i, v in fc_gains.items()}
        gains = {k: v * fc_gains[k] for k, v in g.items()}
        gains = {k: v.astype(np.complex64) for k, v in gains.items()}
        calibrate_in_place(d, gains, old_gains=g, gain_convention='multiply')
        d = {k: v.astype(np.complex64) for k, v in d.items()}
        sol = info.firstcal(d, df=fqs[1] - fqs[0], medfilt=False)
        sol_degen = info.remove_degen_gains(antpos, sol, degen_gains=delays, mode='phase')
        for i in xrange(NANTS):
            self.assertEqual(sol[(i, 'Jxx')].dtype, np.float32)
            self.assertEqual(sol[(i, 'Jxx')].shape, (1, 1))
            self.assertAlmostEqual(sol_degen[(i, 'Jxx')] - delays[(i, 'Jxx')], 0, 0)

    def test_logcal(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.05)
        w = dict([(k, 1.) for k in d.keys()])
        sol = info.logcal(d)
        for i in xrange(NANTS):
            self.assertEqual(sol[(i, 'Jxx')].shape, (10, 10))
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.shape, (10, 10))
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

    def test_omnical(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        #sol0 = info.logcal(d)
        #for k in sol0: sol0[k] += .01*capo.oqe.noise(sol0[k].shape)
        meta, sol = info.omnical(d, sol0, conv_crit=1e-12, gain=.5, maxiter=500, check_after=30, check_every=6)
        for i in xrange(NANTS):
            self.assertEqual(sol[(i, 'Jxx')].shape, (10, 10))
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.shape, (10, 10))
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

    def test_omnical64(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, shape=(2, 1), gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        d = {k: v.astype(np.complex64) for k, v in d.items()}
        sol0 = {k: v.astype(np.complex64) for k, v in sol0.items()}
        meta, sol = info.omnical(d, sol0, gain=.5, maxiter=500, check_after=30, check_every=6)
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.dtype, np.complex64)
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 6)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 6)

    def test_omnical128(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, shape=(2, 1), gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        d = {k: v.astype(np.complex128) for k, v in d.items()}
        sol0 = {k: v.astype(np.complex128) for k, v in sol0.items()}
        meta, sol = info.omnical(d, sol0, conv_crit=1e-12, gain=.5, maxiter=500, check_after=30, check_every=6)
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.dtype, np.complex128)
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

    def test_lincal(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        #sol0 = info.logcal(d)
        #for k in sol0: sol0[k] += .01*capo.oqe.noise(sol0[k].shape)
        meta, sol = info.lincal(d, sol0)
        for i in xrange(NANTS):
            self.assertEqual(sol[(i, 'Jxx')].shape, (10, 10))
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.shape, (10, 10))
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

    def test_lincal64(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, shape=(2, 1), gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        d = {k: v.astype(np.complex64) for k, v in d.items()}
        sol0 = {k: v.astype(np.complex64) for k, v in sol0.items()}
        meta, sol = info.lincal(d, sol0, maxiter=12, conv_crit=1e-6)
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.dtype, np.complex64)
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 6)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 6)

    def test_lincal128(self):
        NANTS = 18
        antpos = build_linear_array(NANTS)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        info = om.RedundantCalibrator(reds)
        gains, true_vis, d = om.sim_red_data(reds, shape=(2, 1), gain_scatter=.0099999)
        w = dict([(k, 1.) for k in d.keys()])
        sol0 = dict([(k, np.ones_like(v)) for k, v in gains.items()])
        sol0.update(info.compute_ubls(d, sol0))
        d = {k: v.astype(np.complex128) for k, v in d.items()}
        sol0 = {k: v.astype(np.complex128) for k, v in sol0.items()}
        meta, sol = info.lincal(d, sol0, maxiter=12)
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.dtype, np.complex128)
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

    def test_svd_convergence(self):
        for hexnum in (2, 3, 4):
            for dtype in (np.complex64, np.complex128):
                antpos = build_hex_array(hexnum)
                reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
                rc = om.RedundantCalibrator(reds)
                gains, _, d = om.sim_red_data(reds, shape=(2, 1), gain_scatter=.01)
                d = {k: dk.astype(dtype) for k, dk in d.items()}
                w = {k: 1. for k in d.keys()}
                gains = {k: gk.astype(dtype) for k, gk in gains.items()}
                sol0 = {k: np.ones_like(gk) for k, gk in gains.items()}
                sol0.update(rc.compute_ubls(d, sol0))
                meta, sol = rc.lincal(d, sol0)  # should not raise 'np.linalg.linalg.LinAlgError: SVD did not converge'
    
    def test_remove_degen_firstcal_1D(self):
        pol = 'xx'
        xhat = np.array([1., 0, 0])
        dtau_dx = 10.
        antpos = build_linear_array(10)
        reds = om.get_reds(antpos, pols=[pol], pol_mode='1pol')
        rc = om.RedundantCalibrator(reds)
        # put in a linear slope in delays, see that it is taken out
        true_dlys = {(i, split_pol(pol)[0]): np.array([[np.dot(xhat, antpos[i]) * dtau_dx]]) for i in range(len(antpos))}
        dlys = rc.remove_degen_gains(antpos, true_dlys, mode='phase')
        for k in dlys:
            np.testing.assert_almost_equal(dlys[k], 0, 10)
        dlys = rc.remove_degen_gains(antpos, true_dlys, degen_gains=true_dlys, mode='phase')
        for k in dlys:
            np.testing.assert_almost_equal(dlys[k], true_dlys[k], 10)

    def test_remove_degen_firstcal_2D(self):
        pol = 'xx'
        xhat = np.array([1., 0, 0])
        yhat = np.array([0., 1, 0])
        dtau_dx = 10.
        dtau_dy = -5.
        antpos = build_hex_array(5)
        reds = om.get_reds(antpos, pols=[pol], pol_mode='1pol')
        rc = om.RedundantCalibrator(reds)
        # put in a linear slope in delays, see that it is taken out
        true_dlys = {(i, split_pol(pol)[0]): 
                        np.array([[np.dot(xhat, antpos[i]) * dtau_dx + np.dot(yhat, antpos[i]) * dtau_dy]]) 
                        for i in range(len(antpos))}
        dlys = rc.remove_degen_gains(antpos, true_dlys, mode='phase')
        for k in dlys:
            np.testing.assert_almost_equal(dlys[k], 0, 10)

    def test_lincal_hex_end_to_end_1pol_with_remove_degen_and_firstcal(self):
        antpos = build_hex_array(3)
        reds = om.get_reds(antpos, pols=['xx'], pol_mode='1pol')
        rc = om.RedundantCalibrator(reds)
        freqs = np.linspace(.1, .2, 10)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.1, shape=(1, len(freqs)))
        fc_delays = {ant: 100 * np.random.randn() for ant in gains.keys()}  # in ns
        fc_gains = {ant: np.reshape(np.exp(-2.0j * np.pi * freqs * delay), (1, len(freqs))) for ant, delay in fc_delays.items()}
        for ant1, ant2, pol in d.keys():
            d[(ant1, ant2, pol)] *= fc_gains[(ant1, split_pol(pol)[0])] * np.conj(fc_gains[(ant2, split_pol(pol)[1])])
        for ant in gains.keys():
            gains[ant] *= fc_gains[ant]

        w = dict([(k, 1.) for k in d.keys()])
        sol0 = rc.logcal(d, sol0=fc_gains, wgts=w)
        meta, sol = rc.lincal(d, sol0, wgts=w)

        np.testing.assert_array_less(meta['iter'], 50 * np.ones_like(meta['iter']))
        np.testing.assert_almost_equal(meta['chisq'], np.zeros_like(meta['chisq']), decimal=10)

        np.testing.assert_almost_equal(meta['chisq'], 0, 10)
        for i in xrange(len(antpos)):
            self.assertEqual(sol[(i, 'Jxx')].shape, (1, len(freqs)))
        for bls in reds:
            ubl = sol[bls[0]]
            self.assertEqual(ubl.shape, (1, len(freqs)))
            for bl in bls:
                d_bl = d[bl]
                mdl = sol[(bl[0], 'Jxx')] * sol[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        ants = [key for key in sol_rd.keys() if len(key) == 2]
        gainSols = np.array([sol_rd[ant] for ant in ants])
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols), axis=0), 0, 10)

        for bls in reds:
            ubl = sol_rd[bls[0]]
            self.assertEqual(ubl.shape, (1, len(freqs)))
            for bl in bls:
                d_bl = d[bl]
                mdl = sol_rd[(bl[0], 'Jxx')] * sol_rd[(bl[1], 'Jxx')].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol, degen_sol=gains)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols), axis=0), 0, 10)

        for key, val in sol_rd.items():
            if len(key) == 2:
                np.testing.assert_almost_equal(val, gains[key], 10)
            if len(key) == 3:
                np.testing.assert_almost_equal(val, true_vis[key], 10)

        rc.pol_mode = 'unrecognized_pol_mode'
        with self.assertRaises(AssertionError):
            sol_rd = rc.remove_degen(antpos, sol)

    def test_lincal_hex_end_to_end_4pol_with_remove_degen_and_firstcal(self):
        antpos = build_hex_array(3)
        reds = om.get_reds(antpos, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol')
        rc = om.RedundantCalibrator(reds)
        freqs = np.linspace(.1, .2, 10)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.09, shape=(1, len(freqs)))
        fc_delays = {ant: 100 * np.random.randn() for ant in gains.keys()}  # in ns
        fc_gains = {ant: np.reshape(np.exp(-2.0j * np.pi * freqs * delay), (1, len(freqs))) for ant, delay in fc_delays.items()}
        for ant1, ant2, pol in d.keys():
            d[(ant1, ant2, pol)] *= fc_gains[(ant1, split_pol(pol)[0])] * np.conj(fc_gains[(ant2, split_pol(pol)[1])])
        for ant in gains.keys():
            gains[ant] *= fc_gains[ant]

        w = dict([(k, 1.) for k in d.keys()])
        sol0 = rc.logcal(d, sol0=fc_gains, wgts=w)
        meta, sol = rc.lincal(d, sol0, wgts=w)

        np.testing.assert_array_less(meta['iter'], 50 * np.ones_like(meta['iter']))
        np.testing.assert_almost_equal(meta['chisq'], np.zeros_like(meta['chisq']), decimal=10)

        np.testing.assert_almost_equal(meta['chisq'], 0, 10)
        for i in xrange(len(antpos)):
            self.assertEqual(sol[(i, 'Jxx')].shape, (1, len(freqs)))
            self.assertEqual(sol[(i, 'Jyy')].shape, (1, len(freqs)))
        for bls in reds:
            for bl in bls:
                ubl = sol[bls[0]]
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol[(bl[0], split_pol(bl[2])[0])] * sol[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol)

        ants = [key for key in sol_rd.keys() if len(key) == 2]
        gainPols = np.array([ant[1] for ant in ants])
        bl_pairs = [key for key in sol.keys() if len(key) == 3]
        visPols = np.array([[bl[2][0], bl[2][1]] for bl in bl_pairs])
        bl_vecs = np.array([antpos[bl_pair[0]] - antpos[bl_pair[1]] for bl_pair in bl_pairs])
        gainSols = np.array([sol_rd[ant] for ant in ants])
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols=='Jxx']), axis=0), 0, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols=='Jyy']), axis=0), 0, 10)

        for bls in reds:
            for bl in bls:
                ubl = sol_rd[bls[0]]
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol_rd[(bl[0], split_pol(bl[2])[0])] * sol_rd[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol, degen_sol=gains)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)

        gainSols = np.array([sol_rd[ant] for ant in ants])
        degenGains = np.array([gains[ant] for ant in ants])
        np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols == 'Jxx']), axis=0),
                                       np.mean(np.angle(degenGains[gainPols == 'Jxx']), axis=0), 10)
        np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols == 'Jyy']), axis=0),
                                       np.mean(np.angle(degenGains[gainPols == 'Jyy']), axis=0), 10)

        for key, val in sol_rd.items():
            if len(key) == 2:
                np.testing.assert_almost_equal(val, gains[key], 10)
            if len(key) == 3:
                np.testing.assert_almost_equal(val, true_vis[key], 10)

    def test_lincal_hex_end_to_end_4pol_minV_with_remove_degen_and_firstcal(self):

        antpos = build_hex_array(3)
        reds = om.get_reds(antpos, pols=['xx', 'xy', 'yx', 'yy'], pol_mode='4pol_minV')
        rc = om.RedundantCalibrator(reds)
        freqs = np.linspace(.1, .2, 10)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.1, shape=(1, len(freqs)))
        fc_delays = {ant: 100 * np.random.randn() for ant in gains.keys()}  # in ns
        fc_gains = {ant: np.reshape(np.exp(-2.0j * np.pi * freqs * delay), (1, len(freqs))) for ant, delay in fc_delays.items()}
        for ant1, ant2, pol in d.keys():
            d[(ant1, ant2, pol)] *= fc_gains[(ant1, split_pol(pol)[0])] * np.conj(fc_gains[(ant2, split_pol(pol)[1])])
        for ant in gains.keys():
            gains[ant] *= fc_gains[ant]

        w = dict([(k, 1.) for k in d.keys()])
        sol0 = rc.logcal(d, sol0=fc_gains, wgts=w)
        meta, sol = rc.lincal(d, sol0, wgts=w)

        np.testing.assert_array_less(meta['iter'], 50 * np.ones_like(meta['iter']))
        np.testing.assert_almost_equal(meta['chisq'], np.zeros_like(meta['chisq']), decimal=10)

        np.testing.assert_almost_equal(meta['chisq'], 0, 10)
        for i in xrange(len(antpos)):
            self.assertEqual(sol[(i, 'Jxx')].shape, (1, len(freqs)))
            self.assertEqual(sol[(i, 'Jyy')].shape, (1, len(freqs)))
        for bls in reds:
            ubl = sol[bls[0]]
            for bl in bls:
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol[(bl[0], split_pol(bl[2])[0])] * sol[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        ants = [key for key in sol_rd.keys() if len(key) == 2]
        gainPols = np.array([ant[1] for ant in ants])
        bl_pairs = [key for key in sol.keys() if len(key) == 3]
        visPols = np.array([[bl[2][0], bl[2][1]] for bl in bl_pairs])
        visPolsStr = np.array([bl[2] for bl in bl_pairs])
        bl_vecs = np.array([antpos[bl_pair[0]] - antpos[bl_pair[1]] for bl_pair in bl_pairs])
        gainSols = np.array([sol_rd[ant] for ant in ants])
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols), axis=0), 0, 10)

        for bls in reds:
            ubl = sol_rd[bls[0]]
            for bl in bls:
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol_rd[(bl[0], split_pol(bl[2])[0])] * sol_rd[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol, degen_sol=gains)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)

        for bls in reds:
            ubl = sol_rd[bls[0]]
            for bl in bls:
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol_rd[(bl[0], split_pol(bl[2])[0])] * sol_rd[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        gainSols = np.array([sol_rd[ant] for ant in ants])
        degenGains = np.array([gains[ant] for ant in ants])
        np.testing.assert_almost_equal(np.mean(np.angle(gainSols), axis=0),
                                       np.mean(np.angle(degenGains), axis=0), 10)

        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)

        visSols = np.array([sol_rd[bl] for bl in bl_pairs])
        degenVis = np.array([true_vis[bl] for bl in bl_pairs])
        np.testing.assert_almost_equal(np.mean(np.angle(visSols), axis=0),
                                       np.mean(np.angle(degenVis), axis=0), 10)

        for key, val in sol_rd.items():
            if len(key) == 2:
                np.testing.assert_almost_equal(val, gains[key], 10)
            if len(key) == 3:
                np.testing.assert_almost_equal(val, true_vis[key], 10)

    def test_lincal_hex_end_to_end_2pol_with_remove_degen_and_firstcal(self):

        antpos = build_hex_array(3)
        reds = om.get_reds(antpos, pols=['xx', 'yy'], pol_mode='2pol')
        rc = om.RedundantCalibrator(reds)
        freqs = np.linspace(.1, .2, 10)
        gains, true_vis, d = om.sim_red_data(reds, gain_scatter=.1, shape=(1, len(freqs)))
        fc_delays = {ant: 100 * np.random.randn() for ant in gains.keys()}  # in ns
        fc_gains = {ant: np.reshape(np.exp(-2.0j * np.pi * freqs * delay), (1, len(freqs))) for ant, delay in fc_delays.items()}
        for ant1, ant2, pol in d.keys():
            d[(ant1, ant2, pol)] *= fc_gains[(ant1, split_pol(pol)[0])] * np.conj(fc_gains[(ant2, split_pol(pol)[1])])
        for ant in gains.keys():
            gains[ant] *= fc_gains[ant]

        w = dict([(k, 1.) for k in d.keys()])
        sol0 = rc.logcal(d, sol0=fc_gains, wgts=w)
        meta, sol = rc.lincal(d, sol0, wgts=w)

        np.testing.assert_array_less(meta['iter'], 50 * np.ones_like(meta['iter']))
        np.testing.assert_almost_equal(meta['chisq'], np.zeros_like(meta['chisq']), decimal=10)

        np.testing.assert_almost_equal(meta['chisq'], 0, 10)
        for i in xrange(len(antpos)):
            self.assertEqual(sol[(i, 'Jxx')].shape, (1, len(freqs)))
            self.assertEqual(sol[(i, 'Jyy')].shape, (1, len(freqs)))
        for bls in reds:
            for bl in bls:
                ubl = sol[bls[0]]
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol[(bl[0], split_pol(bl[2])[0])] * sol[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol)

        ants = [key for key in sol_rd.keys() if len(key) == 2]
        gainPols = np.array([ant[1] for ant in ants])
        bl_pairs = [key for key in sol.keys() if len(key) == 3]
        visPols = np.array([[bl[2][0], bl[2][1]] for bl in bl_pairs])
        bl_vecs = np.array([antpos[bl_pair[0]] - antpos[bl_pair[1]] for bl_pair in bl_pairs])
        gainSols = np.array([sol_rd[ant] for ant in ants])
        g, v = om.get_gains_and_vis_from_sol(sol_rd)

        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, 1, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols=='Jxx']), axis=0), 0, 10)
        #np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols=='Jyy']), axis=0), 0, 10)

        for bls in reds:
            for bl in bls:
                ubl = sol_rd[bls[0]]
                self.assertEqual(ubl.shape, (1, len(freqs)))
                d_bl = d[bl]
                mdl = sol_rd[(bl[0], split_pol(bl[2])[0])] * sol_rd[(bl[1], split_pol(bl[2])[1])].conj() * ubl
                np.testing.assert_almost_equal(np.abs(d_bl), np.abs(mdl), 10)
                np.testing.assert_almost_equal(np.angle(d_bl * mdl.conj()), 0, 10)

        sol_rd = rc.remove_degen(antpos, sol, degen_sol=gains)
        g, v = om.get_gains_and_vis_from_sol(sol_rd)
        gainSols = np.array([sol_rd[ant] for ant in ants])
        degenGains = np.array([gains[ant] for ant in ants])

        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jxx' and key2[1] == 'Jxx' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)
        meanSqAmplitude = np.mean([np.abs(g[key1] * g[key2]) for key1 in g.keys()
                                   for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        degenMeanSqAmplitude = np.mean([np.abs(gains[key1] * gains[key2]) for key1 in g.keys()
                                        for key2 in g.keys() if key1[1] == 'Jyy' and key2[1] == 'Jyy' and key1[0] != key2[0]], axis=0)
        np.testing.assert_almost_equal(meanSqAmplitude, degenMeanSqAmplitude, 10)

        np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols == 'Jxx']), axis=0),
                                       np.mean(np.angle(degenGains[gainPols == 'Jxx']), axis=0), 10)
        np.testing.assert_almost_equal(np.mean(np.angle(gainSols[gainPols == 'Jyy']), axis=0),
                                       np.mean(np.angle(degenGains[gainPols == 'Jyy']), axis=0), 10)

        for key, val in sol_rd.items():
            if len(key) == 2:
                np.testing.assert_almost_equal(val, gains[key], 10)
            if len(key) == 3:
                np.testing.assert_almost_equal(val, true_vis[key], 10)

    def test_count_redcal_degeneracies(self):
        pos = build_hex_array(3)
        self.assertEqual(om.count_redcal_degeneracies(pos, bl_error_tol=1), 4)
        pos[0] += [.5, 0, 0]
        self.assertEqual(om.count_redcal_degeneracies(pos, bl_error_tol=.1), 6)
        self.assertEqual(om.count_redcal_degeneracies(pos, bl_error_tol=1), 4)

    def test_is_redundantly_calibratable(self):
        pos = build_hex_array(3)
        self.assertTrue(om.is_redundantly_calibratable(pos, bl_error_tol=1))
        pos[0] += [.5, 0, 0]
        self.assertFalse(om.is_redundantly_calibratable(pos, bl_error_tol=.1))
        self.assertTrue(om.is_redundantly_calibratable(pos, bl_error_tol=1))


if __name__ == '__main__':
    unittest.main()
