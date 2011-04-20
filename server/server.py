import sys 
import os
sys.path.append('..'+os.sep+'python'+os.sep+'src') 
from MediaServer import MediaServer
from Configure import *

# input
uploadBW = 1                       # Mbits/sec

#### start server ####
uploadBW = uploadBW*1E6/8          # convert it to Bytes/sec
m = MediaServer(os.getcwd(),SERVER);
m.boot(uploadBW);