class GcodeWriter:
    def __init__(self, filename):
        self.outfile = open(filename, "w")
    def close(self):
        self.outfile.close()
    def move(self, x, y, u, v):
        self.outfile.write("G1 X{} Y{} U{} V{}\n".format(x, y, u, v))
    def travel(self, x, y, u, v):
        self.outfile.write("G0 X{} Y{} U{} V{}\n".format(x, y, u, v))
    def set_speed(self, speed):
        self.outfile.write("F{}\n".format(speed))
    def absolute_coordinates(self):
        self.outfile.write("G90\n")



