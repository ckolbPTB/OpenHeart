'''
Author: Johannes Mayer
'''
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description="Postprocess Gadgetron DICOMs.")
parser.add_argument('-i', '--input', help='Directory of where the gadgetron_ismrmrd_client was called.')
parser.add_argument('-o', '--output', help='Name of the directory in which the Dicoms should be stored.')

args = parser.parse_args()

dir_in = Path(args.input)
dir_out = Path(args.output)

assert not dir_out.is_dir(), "You gave an output directory that already exists. That's too dangerous, hence the program is stopped."


def extract_dcm_number_from_gt_recon(fname_dcm):
    num_digits = 6
    num_slots_suffix=4
    return fname_dcm.parts[-1][-(num_digits+num_slots_suffix):-num_slots_suffix]

def main(input_dir, output_dir):
    print(f"--- Postprocessing gadgetron reconstruction: Searching for dicoms in {input_dir} and moving them to {output_dir}")

    flist_dcm=sorted(input_dir.glob("*.dcm"))
    output_dir.mkdir(parents=True, exist_ok=False)

    for dcm in flist_dcm:
        recon_number = extract_dcm_number_from_gt_recon(dcm)

        target = Path(dcm.parent / f"gt_recon_{recon_number}.dcm")
        dcm.rename(target)

        shutil.move(str(target), str(output_dir))

main(dir_in, dir_out)