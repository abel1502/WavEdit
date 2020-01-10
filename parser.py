class Parser:
    def __init__(self, ifile):
        if isinstance(ifile, str):
            ifile = open(ifile, "r")
        self.ifile = ifile
    