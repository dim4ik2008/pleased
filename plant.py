from collections import namedtuple
import scipy.io
import numpy
import re
import os
import csv

stim_types = {
    'water': ['acqua piante'],
    'H2SO': ['h2so'],
    'ozone': ['ozone', 'ozono', 'o3'],
    'NaCL': ['nacl'],
    'light-on': ['light-on'],
    'light-off': ['light-off']
}

# a stimulus on the plant, defined as a type (such as 'ozone') and time
# the null (no) stimulus is named 'null'
Stimulus = namedtuple('Stimulus', ['type', 'time'])

# data on a single experiment on a single plant
# readings is a 2D array where each column relates to an electrode on the plant
PlantData = namedtuple('PlantData', 
                       ['name', 'readings', 'stimuli', 'sample_freq'])


def load_all(path):
    """
    Load all plant data from .txt files.

    Args:
        path: Path to a directory.
    Returns: A list of PlantData
    """

    plants = []

    for root, dirs, files in os.walk(path):
        if "blk0"  in dirs:
            print "Reading %s" % root
            plants += load_txt(root)

    return plants


def load_txt(path):
    """
    Load plant data from .txt files.

    Args:
        path: Path to a data folder.
    Returns: A list of PlantData
    """
    raw_data = []
    stimuli = []

    i = 0
    mark_offset = 0

    # read sample frequency from settings file
    with file(os.path.join(path, "blk0", "blk_setting.txt"), 'r') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if row[0] == 'SPEED ':
                sample_freq = 1.0 / float(row[1])
                break

    while os.path.exists(os.path.join(path, "blk%d" % i)):

        blk = os.path.join(path, "blk%d" % i)
        data = os.path.join(blk, "data2.txt")
        marks = os.path.join(blk, "marks.txt")

        with file(marks, 'r') as f:
            reader = csv.reader(f, delimiter=',')
            next(reader)  # skip header
            for row in reader:
                stimuli.append(Stimulus(row[0].strip(), 
                                        int(row[2].strip()) + mark_offset))

        with file(data, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            for num, row in enumerate(reader):
                new_data = row[0:-1]  # remove empty last column
                raw_data.append(map(float, new_data))

            mark_offset += num

        i += 1

    fname = os.path.basename(path)

    return format_raw(fname, raw_data, stimuli, sample_freq)

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

    # calculate sample frequency
    total_time = readings[-1][0] - readings[0][0]
    sample_freq = total_time / len(readings)
    # TODO: Worry about when the sample frequency is different (interpolate?)

    # get all labelled stimuli
    stimuli = []
    i = 0
    while 'm%03d' % i in mat:
        # get name and time value of stimulus in terrifyingly deep array WTF
        stim_data = mat['m%03d' % i]
        name = stim_data[0][0][1][0]
        time = stim_data[0][0][0][0][0]

        # calculate index of readings array from time and time step per reading
        index = time / sample_freq

        stimuli.append(Stimulus(name, index))

        i += 1

    fname = os.path.basename(path)

    return format_raw(fname, readings[:,1:], stimuli, sample_freq)

def format_raw(name, raw_data, raw_stimuli, sample_freq):
    """
    Process raw data from a file into plant data.

    Args:
        name: The name of the plant data.
        raw_data: A 2D array of readings with no time information.
        raw_stimuli: A list of Stimulus which are not necessarily valid.
    Returns: A list of PlantData
    """
    stimuli = []

    readings = numpy.array(raw_data)

    for stim in raw_stimuli:
        # format type
        t = re.sub(r'_?\d+$', '', stim.type)  # remove trailing numbers
        t = t.lower()  # convert to lowercase

        # find type of stimulus
        type_ = None

        for t, aliases in stim_types.iteritems():
            for alias in aliases:
                if alias in t:
                    type_ = t
                    break

            if type_:
                break

        # if type recognized, add to stimuli
        if type_ is not None:
            stimuli.append(Stimulus(type_, stim.time))

    # for every pair of readings, create a plant data object
    plants = []
    for i, (r1, r2) in enumerate(zip(readings.T[0::2], readings.T[1::2])):
        data = numpy.array([r1, r2]).T
        plant = PlantData("%s-%d" % (name, i), data, stimuli, sample_freq)
        plants.append(plant)

    return plants