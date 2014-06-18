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
PlantData = namedtuple('PlantData', ['name', 'readings', 'stimuli'])


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

    while os.path.exists(os.path.join(path, "blk%d" % i)):
        print "Reading blk%d" % i

        blk = os.path.join(path, "blk%d" % i)
        data = os.path.join(blk, "data2.txt")
        marks = os.path.join(blk, "marks.txt")

        with file(marks, 'r') as f:
            print "Reading %s" % marks
            reader = csv.reader(f, delimiter=',')
            next(reader)  # skip header
            for row in reader:
                stimuli.append(Stimulus(row[0].strip(), 
                                        int(row[2].strip()) + mark_offset))

        with file(data, 'r') as f:
            print "Reading %s" % data
            reader = csv.reader(f, delimiter='\t')
            for num, row in enumerate(reader):
                new_data = row[0:-1]  # remove empty last column
                raw_data.append(map(float, new_data))

            mark_offset += num

        i += 1

    return format_raw("name", raw_data, stimuli)

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
    # TODO: Worry about when the sample rate is different (interpolate?)

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

        stimuli.append(Stimulus(name, index))

        i += 1

    fname = os.path.basename(path)

    return format_raw(fname, readings[:,1:], stimuli)

def format_raw(name, raw_data, raw_stimuli):
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
        plant = PlantData("%s-%d" % (name, i), data, stimuli)
        plants.append(plant)

    return plants