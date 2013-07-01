import trackpy.tracking as pt
import numpy as np
import pandas as pd
import itertools

class Feature(pt.PointND):
    "Extends pt.PointND to carry meta information from feature identification."
    def tag_id(self, id):
        self.id = id # unique ID derived from sequential index
                     # of features DataFrame

def group_grid(df, cell_size):
    grid_designations = df.div(cell_size).apply(np.floor)
    grid = df.groupby(grid_designations)
    return grid

def pd_link(features, search_range):
    position_cols = ['x', 'y']
    t = features.reset_index(drop=True)[position_cols + ['frame']] 

    first_frame = t['frame'].min()
    N = len(t.loc[first_frame])
    t.loc[first_frame] = np.arange(N)
    probe_counter = itertools.count(N)

    previous = None
    for frame_no, f in t.groupby('frame'):
        if frame_no == first_frame:
            previous = group_grid(f[position_cols], search_range)
            continue
        print f
        grid = group_grid(f[position_cols], search_range)
        return grid
        for region, cands in grid:
            print region
        previous = f

def track(features, search_range=5, memory=0, box_size=100):
    """Link features into trajectories.

    Parameters
    ----------
    features : DataFrame including x, y, frame
    search_range : maximum displacement of a probe between two frames
        Default is 5 px.
    memory : Number of frames through which a probe is allowed to "disappear"
        and reappear and be considered the same probe. Default 0.
    box_size : A parameter of the underlying algorithm.
    """
    print "Building Feature objects..."
    frames = []
    # Make a sequential index and promote it to a column called 'index'.
    trajectories = features.reset_index(drop=True).reset_index()
    for frame_no, fs in trajectories.groupby('frame'):
        frame = []
        frames.append(frame)
        for i, vals in fs.iterrows():
            f = Feature(vals['frame'], (vals['x'], vals['y']))
            f.tag_id(vals['index'])
            frame.append(f)
    del trajectories['index']
    
    hash_generator = lambda: pt.Hash_table((1300,1000), box_size)
    print "Doing the actual work..."
    tracks = pt.link(frames, search_range, hash_generator, memory)
    print "Organizing the output..."
    trajectories['probe'] = np.nan
    for probe_id, t in enumerate(tracks):
        for p in t.points:
            trajectories.at[p.id, 'probe'] = probe_id
    return trajectories

def bust_ghosts(tracks, threshold=100):
    """Filter out trajectories with few points. They are often specious.

    Parameters
    ----------
    tracks : DataFrame with a 'probe' column
    threshold : minimum number of points to survive. 100 by default.

    Returns
    -------
    a subset of tracks
    """
    return tracks.groupby('probe').filter(lambda x: np.size(x.icol(0)) >= threshold)

def bust_clusters(tracks, quantile=0.8, threshold=None):
    """Filter out trajectories with a mean probe size above a given quantile.

    Parameters
    ----------
    tracks: DataFrame with 'probe' and 'size' columns
    quantile : quantile of probe 'size' above which to cut off
    threshold : If specified, ignore quantile.

    Returns
    -------
    a subset of tracks
    """
    if threshold is None:
        threshold = tracks['size'].quantile(quantile)
    f = lambda x: x['size'].mean() < threshold # filtering function
    return tracks.groupby('probe').filter(f)
