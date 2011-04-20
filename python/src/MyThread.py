# Author: Hao Zhang
# Created: 02/11/2011
# Class: MyThread - a customized threading class 

import threading
from time import ctime
from Configure import VERBOSE

class MyThread(threading.Thread):
    '# Author: Hao Zhang\
     # Created: 02/11/2011\
     # Class: MyThread - a customized threading class'
    def __init__(self,func,args,name=''):
        super(MyThread,self).__init__()
        self.__func = func
        self.__args = args,
        self.__name = name;
    def run(self):
        if VERBOSE:
            print 'starting', self.__name, 'at:', ctime()
        self.__func(*(self.__args))
        #apply(self.__func,self.__args)
        if VERBOSE:
            print self.__name, 'finished at:', ctime()
        
        
        