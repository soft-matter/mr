from __future__ import division
import mr
import numpy as np
import pandas as pd
from pandas import DataFrame, Series

import unittest
import nose
from numpy.testing import assert_almost_equal, assert_allclose
from numpy.testing.decorators import slow
from pandas.util.testing import (assert_series_equal, assert_frame_equal,
                                 assert_almost_equal)
from mr.utils import suppress_plotting

def random_walk(N):
    return np.cumsum(np.random.randn(N))

def conformity(df):
    "Organize toy data to look like real data."
    return df.set_index('frame', drop=False).sort(['frame', 'probe']). \
        astype('float64')

class TestDrift(unittest.TestCase):

    def setUp(self):
        N = 10
        Y = 1
        a = DataFrame({'x': np.zeros(N), 'y': np.zeros(N), 
                      'frame': np.arange(N), 'probe': np.zeros(N)})
        b = DataFrame({'x': np.zeros(N - 1), 'y': Y + np.zeros(N - 1), 
                       'frame': np.arange(1, N), 'probe': np.ones(N - 1)})
        self.dead_still = conformity(pd.concat([a, b]))

        P = 1000 # probes
        A = 0.00001 # step amplitude
        np.random.seed(0)
        probes = [DataFrame({'x': A*random_walk(N), 
            'y': A*random_walk(N), 
            'frame': np.arange(N), 'probe': i}) for i in range(P)]
        self.many_walks = conformity(pd.concat(probes))

        a = DataFrame({'x': np.arange(N), 'y': np.zeros(N), 
                      'frame': np.arange(N), 'probe': np.zeros(N)})
        b = DataFrame({'x': np.arange(1, N), 'y': Y + np.zeros(N - 1), 
                       'frame': np.arange(1, N), 'probe': np.ones(N - 1)})
        self.steppers = conformity(pd.concat([a, b]))

    def test_no_drift(self):
        N = 10
        expected = DataFrame({'x': np.zeros(N), 'y': np.zeros(N)}).iloc[1:]
        expected = expected.astype('float')
        expected.index.name = 'frame'
        expected.columns = ['x', 'y']
        # ^ no drift measured for Frame 0

        actual = mr.compute_drift(self.dead_still)
        assert_frame_equal(actual, expected)

        # Small random drift
        actual = mr.compute_drift(self.many_walks)
        assert_frame_equal(actual, expected)

    def test_constant_drift(self):
        N = 10
        expected = DataFrame({'x': np.arange(N), 'y': np.zeros(N)}).iloc[1:]
        expected = expected.astype('float')
        expected.index.name = 'frame'
        expected.columns = ['x', 'y']

        actual = mr.compute_drift(self.steppers)
        assert_frame_equal(actual, expected)

    def test_subtract_zero_drift(self):
        N = 10
        drift = DataFrame(np.zeros((N - 1, 2)), 
                          index=np.arange(1, N)).astype('float64')
        drift.columns = ['x', 'y']
        drift.index.name = 'frame'
        actual = mr.subtract_drift(self.dead_still, drift)
        assert_frame_equal(actual, self.dead_still)
        actual = mr.subtract_drift(self.many_walks, drift)
        assert_frame_equal(actual, self.many_walks)
        actual = mr.subtract_drift(self.steppers, drift)
        assert_frame_equal(actual, self.steppers)

    def test_subtract_constant_drift(self):
        N = 10
        # Add a constant drift here, and then use subtract_drift to 
        # subtract it.
        drift = DataFrame(np.outer(np.arange(N - 1), [1, 1]), 
                          index=np.arange(1, N))
        drift.columns = ['x', 'y']
        drift.index.name = 'frame'
        actual = mr.subtract_drift(
            self.dead_still.add(drift, fill_value=0), drift)
        assert_frame_equal(actual, self.dead_still)
        actual = mr.subtract_drift(
            self.many_walks.add(drift, fill_value=0), drift)
        assert_frame_equal(actual, self.many_walks)
        actual = mr.subtract_drift(
            self.steppers.add(drift, fill_value=0), drift)
        assert_frame_equal(actual, self.steppers)

class TestMSD(unittest.TestCase):

    def setUp(self):
        N = 10
        Y = 1
        a = DataFrame({'x': np.zeros(N), 'y': np.zeros(N),
                      'frame': np.arange(N), 'probe': np.zeros(N)})
        b = DataFrame({'x': np.zeros(N - 1), 'y': Y + np.zeros(N - 1),
                       'frame': np.arange(1, N), 'probe': np.ones(N - 1)})
        self.dead_still = conformity(pd.concat([a, b]))

        P = 50 # probes
        A = 1 # step amplitude
        np.random.seed(0)
        probes = [DataFrame({'x': A*random_walk(N),
            'y': A*random_walk(N),
            'frame': np.arange(N), 'probe': i}) for i in range(P)]
        self.many_walks = conformity(pd.concat(probes))

        a = DataFrame({'x': np.arange(N), 'y': np.zeros(N),
                      'frame': np.arange(N), 'probe': np.zeros(N)})
        b = DataFrame({'x': np.arange(1, N), 'y': Y + np.zeros(N - 1),
                       'frame': np.arange(1, N), 'probe': np.ones(N - 1)})
        self.steppers = conformity(pd.concat([a, b]))

    def test_zero_emsd(self):
        N = 10
        actual = mr.emsd(self.dead_still, 1, 1)
        expected = Series(np.zeros(N)).iloc[1:].astype('float64')
        assert_series_equal(actual, expected)

    def test_linear_emsd(self):
        A = 1
        EARLY = 7 # only early lag times have good stats
        actual = mr.emsd(self.many_walks, 1, 1, max_lagtime=EARLY)
        a = np.arange(EARLY, dtype='float64')
        expected = Series(2*A*a, index=a).iloc[1:]
        expected.name = 'msd'
        expected.index.name = 'lag time [s]'
        # HACK: Float64Index imprecision ruins index equality.
        # Test them separately. If that works, make them exactly the same.
        assert_almost_equal(actual.index.values, expected.index.values)
        actual.index = expected.index
        assert_series_equal(np.round(actual), expected)

class TestSpecial(unittest.TestCase):
    
    def setUp(self):
        N = 10
        Y = 1
        a = DataFrame({'x': np.arange(N), 'y': np.zeros(N),
                      'frame': np.arange(N), 'probe': np.zeros(N)})
        b = DataFrame({'x': np.arange(1, N), 'y': Y + np.zeros(N - 1),
                       'frame': np.arange(1, N), 'probe': np.ones(N - 1)})
        self.steppers = conformity(pd.concat([a, b]))

    def test_theta_entropy(self):
        # just a smoke test
        theta_entropy = lambda x: mr.motion.theta_entropy(x, plot=False)
        self.steppers.groupby('probe').apply(theta_entropy)
