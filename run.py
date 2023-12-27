#!/usr/bin/python
import faulthandler
from jal.jal import main

if __name__ == "__main__":
    log_file_fd = open("jal_faults.log", "a")
    faulthandler.enable(log_file_fd)
    main()

# Below code is the same but initiates application via entry point defined in already installed package
# from importlib.metadata import distribution
#
# main_entry = distribution('jal').entry_points[0].load()
#
# main_entry()