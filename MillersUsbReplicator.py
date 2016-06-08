import argparse
import ctypes
import os
import string
import shutil
from multiprocessing import Pool

__author__ = "Jeremy Michael Miller"
__copyright__ = "Copyright 2016, Miller's USB Replicator"
__credits__ = ["Jeremy Michael Miller"]
__license__ = "Fair use v0.9"
__version__ = "0.0.1"
__maintainer__ = "Jeremy Michael Miller"
__email__ = "maybe_later@mst.dnsalias.net"
__status__ = "beta, it works. Needs a verbosity setting and something to verbose about. Needs verification option"

# Please note, I purposely over commented this program. The intended audience required such detail.


class DriveDescriptor:
    def __init__(self, windows_drive_letter, is_removable):
        self.is_removable = is_removable
        self.drive_letter = windows_drive_letter


def discover_drives():
    # Notes from MSDN about this function:
    # If the function succeeds, the return value is a bitmask representing the currently available disk drives. Bit
    # position 0(the least - significant bit) is drive A, bit position 1 is drive B, bit position 2 is drive C, and so
    # on. If the function fails, the return value is zero.
    # My notes: This may seem a little confusing. However, it makes perfect since. It east for API user to consume
    # an 32 bit value and it's obvious 26 letters is less than 32 bits.
    logical_drives_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    if logical_drives_bitmask == 0:
        raise LookupError("Could not find any logical drives using windll.kernel32.GetLogicalDrives() from ctypes.")

    discovered_drives = list()
    for bitmask_index in range(len(string.ascii_uppercase)):
        # The ** operator might not be obvious to non-python programmers. This is the pow function.
        # I.e; 2 raised to bitmask_index exponent, sometimes written as 2^bitmask_index
        bit_mask = 2 ** bitmask_index
        if bit_mask & logical_drives_bitmask:
            # The 65 + bitmask_index is an ASCII table hack. Upper case alphabet letters start at 65 in the ASCII table.
            # therefore to convert the
            discovered_drive_letter = "%s:\\" % chr(65 + bitmask_index)
            # Notes from MSDN. The below function returns a value which specifies the type of drive, which can be one
            # of the following values.
            # DRIVE_UNKNOWN = 0         The drive type cannot be determined.
            # DRIVE_NO_ROOT_DIR = 1     The root path is invalid; for example, there is no volume mounted at the
            #                           specified path.
            # DRIVE_REMOVABLE = 2       The drive has removable media; for example, a floppy drive, thumb drive, or
            #                           flash card reader.
            # DRIVE_FIXED = 3           The drive has fixed media; for example, a hard disk drive or flash drive.
            # DRIVE_REMOTE = 4          The drive is a remote (network) drive.
            # DRIVE_CDROM = 5           The drive is a CD-ROM drive.
            # DRIVE_RAMDISK = 6         The drive is a RAM disk.
            discovered_drive_type = ctypes.windll.kernel32.GetDriveTypeA(
                ctypes.c_char_p(bytes(discovered_drive_letter, 'ascii')))
            discovered_drives.append(
                DriveDescriptor(discovered_drive_letter, True if discovered_drive_type == 2 else False))
    return discovered_drives


def change_labels(drive_list, new_label):
    for drive_letter in drive_list:
        set_label_result = ctypes.windll.kernel32.SetVolumeLabelA(
            ctypes.c_char_p(bytes(drive_letter, 'ascii')),
            ctypes.c_char_p(bytes(new_label, 'ascii')))
        if set_label_result is 0:
            raise WindowsError("Could not rename volume")


class CopyTreeDescription:
    def __init__(self, source_directory, destination_directory):
        self.source_directory = source_directory
        self.destination_directory = destination_directory


# Wrapper function to be called by process.map for processing more than one copy in parallel
def invoke_copy(copy_tree_description):
    shutil.copytree(copy_tree_description.source_directory, copy_tree_description.destination_directory)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='Multiprocess Removable Drive File Replicator')
        parser.add_argument('--source_folder', '-s', dest='source_folder',
                            default='',
                            help="Path to the source files to copy to the removable drives.",
                            required=True)
        parser.add_argument('--destination_folder', '-d', dest='destination_folder',
                            default='',
                            help="Path that will be created on the removable drives if it does not exist.",
                            required=True)
        parser.add_argument('--volume_label', '-vl', dest='volume_label',
                            default='',
                            help="New label of destination volume(s). The label must be less than 12 characters.")
        # Currently disabled and since this is current not under source control I want to comment this out for now
        # parser.add_argument('--keep_empty_directories', '-k', dest='keep_empty_directories',
        #                     type=bool,
        #                     default=False,
        #                     help="By default, this program will not copy empty directories unless this switch is \
        #                     present")
        parser.add_argument('--number_of_processes', '-p', dest='number_of_processes',
                            type=int,
                            default=os.cpu_count(),
                            help="Number of processes this program will launch. This should not be more the number of \
                            logical processors available to the operating system.")

        args = parser.parse_args()
        if os.path.exists(args.source_folder):
            source_folder = args.source_folder
        else:
            raise ValueError("Specified source folder: " + args.source_folder + "  does not exist")

        destination_folder = args.destination_folder

        if len(args.volume_label) < 12:
            volume_label = args.volume_label
        else:
            raise ValueError("Volume label " + args.volume_label + " is greater than or equal to 12 characters")

        if args.number_of_processes > 0:
            number_of_processes = args.number_of_processes
        else:
            raise ValueError("Number of processes which will do that copy must be larger than zero.")

        discovered_drive_list = discover_drives()
        removable_drives = [drive_descriptor.drive_letter for drive_descriptor in discovered_drive_list if
                            drive_descriptor.is_removable]

        if len(volume_label) > 0:
            change_labels(removable_drives, volume_label)

        print("Copying directory: " + source_folder + " to removable drives: " + ', '.join(removable_drives))
        copy_descriptions = [CopyTreeDescription(source_folder, os.path.join(drive_letter, destination_folder)) for
                             drive_letter in removable_drives]
        they_are_sure = input("Are you sure [Y/n]: ")

        if they_are_sure is 'Y':
            if number_of_processes > len(copy_descriptions):
                number_of_processes = len(copy_descriptions)
            process_pool = Pool(number_of_processes)
            process_pool.map(invoke_copy, copy_descriptions)

    except ValueError as valueError:
        print(valueError)
