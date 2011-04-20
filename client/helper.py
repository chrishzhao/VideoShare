import sys 
import os
sys.path.append('..'+os.sep+'python'+os.sep+'src') 
from MediaServer import MediaServer
from Configure import *

# user input
uploadBW = 0.6                     # Mbits/sec

########################################################
uploadBW = uploadBW*1E6/8          # convert it to KB/sec
m = MediaServer(os.getcwd(),CLIENT);
m.boot(uploadBW);