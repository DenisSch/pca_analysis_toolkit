import argparse

import numpy as np
import tifffile
import tqdm

from skimage import io, segmentation, measure, exposure

def select_bbox(img, bbox):
    min_row, min_col, max_row, max_col = bbox
    return img[min_row:max_row, min_col:max_col]

if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('in_filepath', type=str,
            help='File path of the input ome.tif image')
    parser.add_argument('channel_index', type=int,
            help='Channel in input ome.tif image, starts at zero')
    parser.add_argument('start_threshold', type=int,
            help='Threshold to seed with, in uint16 range')
    parser.add_argument('stop_threshold', type=int,
            help='Threshold to stop growth at, in uint16 range')
    parser.add_argument('out_filepath', type=str,
            help='File path of the output .tif mask')
    args = parser.parse_args()

    # load data
    with tifffile.TiffFile(args.in_filepath) as tif:
        img = tif.series[0].pages[args.channel_index].asarray()
    img_scaled = exposure.rescale_intensity(img,
            in_range=tuple(np.percentile(img, (1, 99))))
    mask = (img_scaled > args.start_threshold).astype(int)

    start = img_scaled.max()
    stop = args.stop_threshold

    for threshold in tqdm.tqdm(range(start, stop, -1), disable=True):
        # check if any step needed
        if (img_scaled[np.logical_not(mask)]==threshold).sum() == 0:
            continue
        # region defined by the highlighting
        region_list = measure.regionprops(label_image=mask,
                intensity_image=img_scaled)
        # small chunks for faster iteration
        for region in region_list:
            # slice
            min_row, min_col, max_row, max_col = region.bbox
            img_small = select_bbox(img_scaled, region.bbox)
            mask_small = select_bbox(mask, region.bbox)
            # check if any space (potential) to grow
            potential_small = img_small >= threshold
            if potential_small.sum() == 0:
                continue
            # most compute-intensive step
            boundary_small = segmentation.find_boundaries(mask_small,
                    mode='outer')
            # step is reachable potential
            step_small = np.logical_and(boundary_small, potential_small)
            # keep growing until no further step available
            while step_small.sum() > 0:
                # combine new and old pixels
                mask_small += step_small
                # most compute-heavy step
                boundary_small = segmentation.find_boundaries(mask_small,
                        mode='outer')
                # check step again using the new boundary
                step_small = np.logical_and(boundary_small, potential_small)
            # put back to big mask
            mask[min_row:max_row, min_col:max_col] = mask_small

    # save
    io.imsave(args.out_filepath, mask)
