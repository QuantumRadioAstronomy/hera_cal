# -*- coding: utf-8 -*-
# Copyright 2019 the HERA Project
# Licensed under the MIT License

"""Module for delay filtering data and related operations."""

import numpy as np
from copy import deepcopy
import argparse

from . import io
from . import version
from .vis_clean import VisClean

import pickle
import random
import glob
import os


class DelayFilter(VisClean):
    """
    DelayFilter object.

    Used for delay CLEANing and filtering.
    See vis_clean.VisClean for CLEAN functions.
    """

    def run_filter(self, to_filter=None, weight_dict=None, verbose=False, skip_wgt=0.1, **filter_kwargs):
        '''
        Run uvtools.dspec.vis_filter on data.

        Run on (a subset of) the data stored in the object.
        Uses stored flags unless explicitly overridden with weight_dict.

        Arguments:
            to_filter: list of visibilities to filter in the (i,j,pol) format.
                If None (the default), all visibilities are filtered.
            weight_dict: dictionary or DataContainer with all the same keys as self.data.
                Linear multiplicative weights to use for the delay filter. Default, use np.logical_not
                of self.flags. uvtools.dspec.delay_filter will renormalize to compensate
            skip_wgt: skips filtering rows with very low total weight (unflagged fraction ~< skip_wgt).
                Model is left as 0s, residual is left as data, and info is {'skipped': True} for that
                time. Skipped channels are then flagged in self.flags.
                Only works properly when all weights are all between 0 and 1.
            verbose: If True print feedback to stdout
            filter_kwargs: see fourier_filter for a full list of filter_specific arguments.

        Results are stored in:
            self.clean_resid: DataContainer formatted like self.data with only high-delay components
            self.clean_model: DataContainer formatted like self.data with only low-delay components
            self.clean_info: Dictionary of info from uvtools.dspec.delay_filter with the same keys as self.data
        '''
        # run delay CLEAN
        self.vis_clean(keys=to_filter, data=self.data, flags=self.flags, wgts=weight_dict, ax='freq',
                       horizon=horizon, standoff=standoff, min_dly=min_dly, tol=tol, maxiter=maxiter,
                       window=window, gain=gain, skip_wgt=skip_wgt, edgecut_low=edgecut_low,
                       edgecut_hi=edgecut_hi, alpha=alpha, overwrite=True, verbose=verbose)

    def get_filled_data(self):
        """Get data with flagged pixels filled with clean_model.

        Returns
            filled_data: DataContainer with original data and flags filled with CLEAN model
            filled_flags: DataContainer with flags set to False unless the time is skipped in delay filter
        """
        assert np.all([hasattr(self, n) for n in ['clean_model', 'clean_flags', 'data', 'flags']]), "self.data, self.flags, self.clean_model and self.clean_flags must all exist to get filled data"
        # construct filled data and filled flags
        filled_data = deepcopy(self.clean_model)
        filled_flags = deepcopy(self.clean_flags)

        # iterate over filled_data keys
        for k in filled_data.keys():
            # get original data flags
            f = self.flags[k]
            # replace filled_data with original data at f == False
            filled_data[k][~f] = self.data[k][~f]

        return filled_data, filled_flags

    def write_filtered_data(self, res_outfilename=None, CLEAN_outfilename=None, filled_outfilename=None, filetype='uvh5',
                            partial_write=False, clobber=False, add_to_history='', extra_attrs={}, **kwargs):
        '''
        Method for writing data products.

        Can write filtered residuals, CLEAN models, and/or original data with flags filled
        by CLEAN models where possible. Uses input_data from DelayFilter.load_data() as a template.

        Arguments:
            res_outfilename: path for writing the filtered visibilities with flags
            CLEAN_outfilename: path for writing the CLEAN model visibilities (with the same flags)
            filled_outfilename: path for writing the original data but with flags unflagged and replaced
                with CLEAN models wherever possible
            filetype: file format of output result. Default 'uvh5.' Also supports 'miriad' and 'uvfits'.
            partial_write: use uvh5 partial writing capability (only works when going from uvh5 to uvh5)
            clobber: if True, overwrites existing file at the outfilename
            add_to_history: string appended to the history of the output file
            extra_attrs : additional UVData/HERAData attributes to update before writing
            kwargs : extra kwargs to pass to UVData.write_*() call
        '''
        if not hasattr(self, 'data'):
            raise ValueError("Cannot write data without first loading")
        if (res_outfilename is None) and (CLEAN_outfilename is None) and (filled_outfilename is None):
            raise ValueError('You must specifiy at least one outfilename.')
        else:
            # loop over the three output modes if a corresponding outfilename is supplied
            for mode, outfilename in zip(['residual', 'CLEAN', 'filled'],
                                         [res_outfilename, CLEAN_outfilename, filled_outfilename]):
                if outfilename is not None:
                    if mode == 'residual':
                        data_out, flags_out = self.clean_resid, self.flags
                    elif mode == 'CLEAN':
                        data_out, flags_out = self.clean_model, self.clean_flags
                    elif mode == 'filled':
                        data_out, flags_out = self.get_filled_data()
                    if partial_write:
                        if not ((filetype == 'uvh5') and (getattr(self.hd, 'filetype', None) == 'uvh5')):
                            raise NotImplementedError('Partial writing requires input and output types to be "uvh5".')
                        self.hd.partial_write(outfilename, data=data_out, flags=flags_out, clobber=clobber,
                                              add_to_history=version.history_string(add_to_history), **kwargs)
                    else:
                        self.write_data(data_out, outfilename, filetype=filetype, overwrite=clobber, flags=flags_out,
                                        add_to_history=add_to_history, extra_attrs=extra_attrs, **kwargs)


def partial_load_delay_filter_and_write(infilename, calfile=None, Nbls=1, spw_range=None, cache_dir=None,
                                        read_cache=False, write_cache=False,
                                        res_outfilename=None, CLEAN_outfilename=None, filled_outfilename=None,
                                        clobber=False, add_to_history='', **filter_kwargs):
    '''
    Uses partial data loading and writing to perform delay filtering.

    Arguments:
        infilename: string path to data to uvh5 file to load
        cal: optional string path to calibration file to apply to data before delay filtering
        Nbls: the number of baselines to load at once.
        spw_range: spw_range of data to delay-filter.
        cache_dir: string, optional, path to cache file that contains pre-computed dayenu matrices.
                    see uvtools.dspec.dayenu_filter for key formats.
        write_cache: bool. If true, create new cache file with precomputed matrices
                           that were not in previously loaded cache files.
        read_cache: bool, If true, read existing cache files in cache_dir before running.
        res_outfilename: path for writing the filtered visibilities with flags
        CLEAN_outfilename: path for writing the CLEAN model visibilities (with the same flags)
        filled_outfilename: path for writing the original data but with flags unflagged and replaced
            with CLEAN models wherever possible
        clobber: if True, overwrites existing file at the outfilename
        add_to_history: string appended to the history of the output file
        filter_kwargs: additional keyword arguments to be passed to DelayFilter.run_filter()
    '''
    hd = io.HERAData(infilename, filetype='uvh5')
    #make sure that spw_range is within (0, Nf) if not, truncate it.
    if spw_range[0] < 0:
        warnings.warn("spw_range[0] cannot be less then 0. Setting to 0.")
        spw_range[0] = 0
    if spw_range[1] >= hd.Nfreqs:
        warnings.warn("spw_range[1] cannot be larger then number of frequency channels. Setting to hd.Nfreqs")
        spw_range[1] = hd.Nfreqs
    if calfile is not None:
        calfile = io.HERACal(calfile)
        calfile.read()
    # read in cache
    if read_cache:
        filter_cache = io.read_filter_cache(cache_dir)
    else:
        filter_cache = {}
    keys_before = list(filter_cache.keys())
    # loop over all baselines in increments of Nbls
    for i in range(0, len(hd.bls), Nbls):
        df = DelayFilter(hd, input_cal=calfile)
        df.read(bls=hd.bls[i:i + Nbls], frequencies=hd.freqs[spw_range[0]:spw_range[1]])
        df.run_filter(cache, **filter_kwargs, cache=cache)
        df.write_filtered_data(res_outfilename=res_outfilename, CLEAN_outfilename=CLEAN_outfilename,
                               filled_outfilename=filled_outfilename, partial_write=True,
                               clobber=clobber, add_to_history=add_to_history)
        df.hd.data_array = None  # this forces a reload in the next loop
    # write out cache
    if write_cache:
        filter_cache = io.write_filter_cache(filter_cache, cache_dir, keys_before)

def delay_filter_argparser():
    '''Arg parser for commandline operation of hera_cal.delay_filter.'''
    a = argparse.ArgumentParser(description="Perform delay filter of visibility data.")
    a.add_argument("infilename", type=str, help="path to visibility data file to delay filter")
    a.add_argument("--filetype_in", type=str, default='uvh5', help='filetype of input data files (default "uvh5")')
    a.add_argument("--filetype_out", type=str, default='uvh5', help='filetype for output data files (default "uvh5")')
    a.add_argument("--calfile", default=None, type=str, help="optional string path to calibration file to apply to data before delay filtering")
    a.add_argument("--partial_load_Nbls", default=None, type=int, help="the number of baselines to load at once (default None means load full data")
    a.add_argument("--res_outfilename", default=None, type=str, help="path for writing the filtered visibilities with flags")
    a.add_argument("--CLEAN_outfilename", default=None, type=str, help="path for writing the CLEAN model visibilities (with the same flags)")
    a.add_argument("--filled_outfilename", default=None, type=str, help="path for writing the original data but with flags unflagged and replaced with CLEAN models wherever possible")
    a.add_argument("--clobber", default=False, action="store_true", help='overwrites existing file at outfile')
    a.add_argument("--spw_range", type=int, nargs=2, help="spectral window of data to foreground filter.")
    a.add_argument("--cache_dir", type=str, default=None, help="directory to store cached filtering matrices in.")
    a.add_argument("--write_cache", default=False, action="store_true", help="if True, writes newly computed filter matrices to cache.")

    filt_options = a.add_argument_group(title='Options for the delay filter')
    filt_options.add_argument("--standoff", type=float, default=15.0, help='fixed additional delay beyond the horizon (default 15 ns)')
    filt_options.add_argument("--horizon", type=float, default=1.0, help='proportionality constant for bl_len where 1.0 (default) is the horizon\
                              (full light travel time)')
    filt_options.add_argument("--min_dly", type=float, default=0.0, help="A minimum delay threshold [ns] used for cleaning.")
    filt_options.add_argument("--tol", type=float, default=1e-9, help='CLEAN algorithm convergence tolerance (default 1e-9)')
    filt_options.add_argument("--window", type=str, default='blackman-harris', help='window function for frequency filtering (default "blackman-harris",\
                              see uvtools.dspec.gen_window for options')
    filt_options.add_argument("--skip_wgt", type=float, default=0.1, help='skips filtering and flags times with unflagged fraction ~< skip_wgt (default 0.1)')
    filt_options.add_argument("--maxiter", type=int, default=100, help='maximum iterations for aipy.deconv.clean to converge (default 100)')
    filt_options.add_argument("--edgecut_low", default=0, type=int, help="Number of channels to flag on lower band edge and exclude from window function.")
    filt_options.add_argument("--edgecut_hi", default=0, type=int, help="Number of channels to flag on upper band edge and exclude from window function.")
    filt_options.add_argument("--gain", type=float, default=0.1, help="Fraction of residual to use in each iteration.")
    filt_options.add_argument("--alpha", type=float, default=.5, help="If window='tukey', use this alpha parameter (default .5).")
    return a
