import sys 
import os
sys.path.append('..'+os.sep+'python'+os.sep+'src') 
from MediaClient import MediaClient

m = MediaClient(os.getcwd())
m.bootasuser()