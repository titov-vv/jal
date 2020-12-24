#!/usr/bin/python

from jal.jal import main

if __name__ == "__main__":
    main()

# Below code is the same but initiates application via entry point defined in already installed package
# from importlib.metadata import distribution
#
# main_entry = distribution('jal').entry_points[0].load()
#
# main_entry()