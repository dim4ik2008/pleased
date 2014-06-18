from collections import namedtuple
import scipy.io
import numpy
import re
import os
import sys
import csv

# number of data points after every stimulus to use
window_size = 100

stim_types = {
    'water': ['acqua piante'],
    'H2SO': ['h2so'],
    'ozone': ['ozone', 'ozono', 'o3'],
    'NaCL': ['nacl'],
    'light-on': ['light-on'],
    'light-off': ['light-off']
}

# a stimulus on the plant, defined as a type (such as 'ozone') and time
Stimulus = namedtuple('Stimulus', ['type', 'time'])

# data on a single experiment on a single plant
# readings is a 2D array where each column relates to an electrode on the plant
PlantData = namedtuple('PlantData', ['readings', 'stimuli'])


def load_all(path):
    """
    Load all plant data from .mat files in a directory.

    Args:
        path: Path to a directory.
    Returns: A list of PlantData
    """

    plants = []

    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".mat"):
                mat_path = os.path.join(root, f)
                plants += load_mat(mat_path)

    return plants


def load_mat(path):
    """
    Load plant data from a .mat file.

    Args:
        path: Path to a .mat file.
    Returns: A list of PlantData
    """
    mat = scipy.io.loadmat(path)

    # get astonishingly poorly-named matrix of readings
    readings = mat['b\x001\x00\x00\x00']

    # calculate sample rate
    total_time = readings[-1][0] - readings[0][0]
    sample_rate = total_time / len(readings)

    # get all labelled stimuli
    stimuli = []
    i = 0
    while 'm%03d' % i in mat:
        # get name and time value of stimulus in terrifyingly deep array WTF
        stim_data = mat['m%03d' % i]
        name = stim_data[0][0][1][0]
        time = stim_data[0][0][0][0][0]

        # calculate index of readings array from time and time step per reading
        index = time / sample_rate

        # format name
        name = re.sub(r'_?\d+$', '', name)  # remove trailing numbers
        name = name.lower()                # convert to lowercase

        # find type of stimulus
        type_ = None

        for t, aliases in stim_types.iteritems():
            for alias in aliases:
                if alias in name:
                    type_ = t
                    break

            if type_:
                break

        # if type recognized, add to stimuli
        if type_ is not None:
            stimuli.append(Stimulus(type_, index))

        i += 1

    # for every pair of readings, create a plant data object
    plants = []
    for r1, r2 in zip(readings.T[1::2], readings.T[2::2]):
        data = numpy.array([r1, r2]).T
        plant = PlantData(data, stimuli)
        plants.append(plant)

    return plants


def process(plant_data):
    """
    Process plant data to produce a list of classified data points.

    Returns:
        A list of tuples, where the first element of the tuple is the
        type of stimulus and the second element is the data.
    """
    new_data = []

    for stim in plant_data.stimuli:
        # create a window on each stimulus
        window = plant_data.readings[stim.time:stim.time+window_size]

        # skip if window is not large enough (e.g. stimulus near end of data)
        if len(window) != window_size:
            continue

        new_data.append((stim.type, window))

    return new_data


def process_all(plants):
    """
    Process a list of plant data.

    Args:
        plants: A list of PlantData
    Returns:
        A list of tuples, where the first element of the tuple is the type of
        stimulus and the second element is the data.
    """
    new_data = []

    for plant_data in plants:
        new_data += process(plant_data)

    return new_data


def save_datapoints(path, datapoints):
    """
    Save data points to a CSV file.

    Args:
        path: File to save data points to.
        datapoints:
            A list of tuples, where the first element of the tuple is the type
            of stimulus and the second element is the data.
    """

    with file(path, 'w') as f:
        writer = csv.writer(f)
        for stim_type, data in datapoints:
            # write a row for every data point
            writer.writerow([stim_type] + data.T.flatten().tolist())


def load_datapoints(path):
    """
    Load data points from a csv file.

    Args:
        path: File to load data points from.
    Returns:
        A list of tuples, where the first element of the tuple is the type of
        stimulus and the second element is the data.
    """

    datapoints = []

    with file(path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            stim_type = row[0]
            data = map(float, row[1:])
            data = numpy.array(data)
            data = numpy.reshape(data, (-1, 2))  # reshape into two columns
            datapoints.append((stim_type, data))

    return datapoints


# if called from command line, load mat files from given path
if __name__ == "__main__":
    # get directory from command line
    path = sys.argv[1]

    # load all plant data in directory
    print "Loading data"
    plants = load_all(path)

    # process all data
    print "Processing data"
    datapoints = process_all(plants)

    # write data to file
    print "Writing to data.csv"
    save_datapoints("data.csv", datapoints)
