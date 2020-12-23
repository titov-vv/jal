from importlib.metadata import distribution

main_entry = distribution('jal').entry_points[0].load()

main_entry()