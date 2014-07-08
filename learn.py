from sklearn import base, svm, lda, qda, pipeline, preprocessing, grid_search
import pywt
import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from scipy.signal import decimate
from scipy.optimize import curve_fit
from itertools import chain, groupby

import plant
import datapoint


labels = ['null', 'ozone']


class FeatureExtractor(base.BaseEstimator):
    """ Extracts features from each datapoint. """

    def __init__(self, extractor=None):
        if extractor is not None:
            self.extractor = extractor

    def transform(self, X):
        return np.array([self.extractor(x) for x in X], ndmin=2)

    def fit(self, X, y):
        return self


class MeanSubtractTransform(FeatureExtractor):
    """ Subtracts the mean of the data from every point. """

    def extractor(self, x):
        m = mean(x)
        return [xx-m for xx in x]


class ClipTransform(FeatureExtractor):
    """ Cut some amount from the end of the data. """

    def __init__(self, size):
        self.size = size

    def extractor(self, x):
        return x[0:int(len(x)*self.size)]


class DecimateTransform(FeatureExtractor):
    """ Shrink signal by applying a low-pass filter. """

    def __init__(self, factor):
        self.factor = factor

    def extractor(self, x):
        return decimate(x, self.factor, ftype='fir')


class WindowTransform(FeatureExtractor):
    """ Apply a function to overlapping windows. """

    def __init__(self, f, N, hanning=True):
        self.f = f
        self.N = N
        self.hanning = hanning

    def extractor(self, x):
        window_size = 2 * len(x) / (self.N + 1)
        step = window_size / 2

        windows = []
        for i in range(0, len(x)-window_size+1, step):
            window = x[i:i+window_size]
            if self.hanning:
                window *= np.hanning(len(window))
            windows.append(self.f(window))

        return np.concatenate(windows)


class DiscreteWaveletTransform(FeatureExtractor):
    """ Perform a wavelet transform on the data. """

    def __init__(self, kind, L, D):
        self.kind = kind
        self.L = L
        self.D = D

    def extractor(self, x):
        wavelet = pywt.wavedec(x, self.kind, self.L)
        return np.concatenate(wavelet[0:self.L-self.D])


class DetrendTransform(FeatureExtractor):
    """ Remove any linear trends in the data. """

    def extractor(self, x):
        def linear(xs, m, c):
            return map(lambda xx: m*xx + c, xs)

        # find best fitting curve to pre-stimulus window
        times = range(0, len(x))
        params, cov = curve_fit(linear, times[0:-datapoint.window_offset], 
                                x[0:-datapoint.window_offset], (0, 0))
        # subtract extrapolated curve from data to produce new dataset
        return x - linear(times, *params)

class PostStimulusTransform(FeatureExtractor):
    """ Remove any pre-stimulus data from the datapoint. """

    def __init__(self, offset=0):
        self.offset = offset

    def extractor(self, x):
        return x[self.offset-datapoint.window_offset:]


class ElectrodeAvgTransform(FeatureExtractor):
    """ Take the average of the two electrode values. """

    def extractor(self, x):
        return [(xx[0] + xx[1]) / 2.0 for xx in x]


class ElectrodeDiffTransform(FeatureExtractor):
    """ Take the difference of the two electrode values. """

    def extractor(self, x):
        return [xx[0] - xx[1] for xx in x]


class MovingAvgTransform(FeatureExtractor):
    """ Take a moving average of time series data. """

    def __init__(self, n):
        self.n = n

    def extractor(self, x):
        mov_avg = []

        for i, xx in enumerate(x):
            start = i-self.n/2
            if start < 0:
                start = 0
            end = i+self.n/2
            if end > len(x):
                end = len(x)
            window = x[start:end]
            mov_avg.append(mean(window))

        return mov_avg


class FeatureEnsembleTransform(FeatureExtractor):
    """ Take an ensemble of different features from the data. """

    def extractor(self, x):
        diff = mean(map(abs, differential(x)))
        noise = mean(map(abs, differential(differential(x))))
        vari = var(x)
        vardiff = var(differential(x))
        varnoise = var(differential(differential(x)))
        hjorth_mob = vardiff**0.5 / vari**0.5
        hjorth_com = (varnoise**0.5 / vardiff**0.5) / hjorth_mob
        return [diff, noise, vari, vardiff, hjorth_mob, hjorth_com]


def differential(x):
    """
    Returns: The change in x.
    """
    return [x2 - x1 for (x1, x2) in zip(x[:-1], x[1:])]


def mean(x):
    """ Returns: The average of x. """
    return sum(x) / len(x)


def var(x):
    """ Returns: The variance of x. """
    m = mean(x)
    return sum([(xx-m)**2 for xx in x]) / len(x)


def stdev(x):
    """ Returns: The standard deviation of x. """
    return var(x)**0.5


def preprocess(plants):
    # extract windows from plant data
    datapoints = datapoint.generate_all(plants)
    # filter to relevant datapoint types
    datapoints = datapoint.filter_types(datapoints, labels)
    # balance the dataset
    datapoints = datapoint.balance(datapoints, False)
    
    return datapoints


def extract(datapoints):
    datapoints = list(datapoints)
    labels = [d[0] for d in datapoints]
    data = [d[1] for d in datapoints]

    # take the average and detrend the data ahead of time
    data = ElectrodeAvgTransform().transform(data)
    data = DetrendTransform().transform(data)
    data = PostStimulusTransform(60).transform(data)

    return data, np.asarray(labels)


def plot_features(f1, f2):
    # load plant data from files
    plants = plant.load_all()
    # preprocess data
    datapoints = preprocess(plants)

    # scale data
    X, y = extract(datapoints)
    X = FeatureEnsembleTransform().transform(X)
    scaler = preprocessing.StandardScaler()
    scaler.fit(X)

    groups = lambda: datapoint.group_types(datapoints)

    # visualize the feature extractor
    colors = iter(cm.rainbow(np.linspace(0, 1, len(list(groups())))))
    for dtype, points in groups():
        X, y = extract(points)
        X = FeatureEnsembleTransform().transform(X)
        X = scaler.transform(X)
        plt.scatter(X[:,f1], X[:,f2], c=next(colors), label=dtype)
    plt.legend()
    plt.show()


def plot_histogram(feature):
    # load plant data from files
    plants = plant.load_all()
    # preprocess data
    datapoints = preprocess(plants)

    groups = lambda: datapoint.group_types(datapoints)

    # visualize a histogram of the feature
    for dtype, points in groups():
        X, y = extract(points)
        X = FeatureEnsembleTransform().transform(X)
        plt.hist(X[:,feature], bins=40, alpha=0.5, label=dtype)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    # load plant data from files
    plants = plant.load_all()

    # split plant data into training and validation sets
    random.shuffle(plants)
    train_len = int(0.75 * len(plants))
    train_plants = plants[:train_len]
    valid_plants = plants[train_len:]

    print "Experiments in training set:", len(train_plants)
    print "Experiments in validation set:", len(valid_plants)

    # get X data and y labels
    X_train, y_train = extract(preprocess(train_plants))
    X_valid, y_valid = extract(preprocess(valid_plants))

    print "Datapoints in training set:", len(X_train)
    class_train = [(d[0], len(list(d[1]))) for d in groupby(y_train)]
    print "Classes in training set:", class_train 
    print "Datapoints in validation set:", len(X_valid)
    class_valid = [(d[0], len(list(d[1]))) for d in groupby(y_valid)]
    print "Classes in validation set:", class_valid

    # set up pipeline
    ensemble = FeatureEnsembleTransform().extractor
    pipeline = pipeline.Pipeline(
        [
         ('feature', WindowTransform(ensemble, 3, False)),
         ('scaler', preprocessing.StandardScaler()), 
         ('svm', svm.SVC())
        ])

    params = [{}]

    # perform grid search on pipeline, get best parameters from training data
    grid = grid_search.GridSearchCV(pipeline, params, cv=5, verbose=2)
    grid.fit(X_train, y_train)
    classifier = grid.best_estimator_

    print "Grid search results:"
    print grid.best_score_

    # test the classifier on the validation data set
    validation_score = classifier.fit(X_train, y_train).score(X_valid, y_valid)

    print "Validation data results:"
    print validation_score
