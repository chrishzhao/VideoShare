import sys 
import os
sys.path.append('..'+os.sep+'python'+os.sep+'src') 
from Tracker import Tracker

m = Tracker();
m.boot();