import socket
from time import sleep
import sys
import threading
import thread
from Configure import *
from struct import *
from MyThread import *

class Mytcpsocket(object):
    def __init__(self, sock = None):
        if sock == None:
            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.__socket = sock;
        self.__lock = thread.allocate_lock()
        self.__dataBuffer = [];      # buffer for data
        self.__instBuffer = [];      # buffer for instructions
    
    def InitServSock(self, SrcAddr, SrcMaxConn):
        self.__SrcAddr = SrcAddr
        self.__SrcMaxConn = SrcMaxConn
        while True:
            self.__lock.acquire();
            try:
                self.__socket.bind(SrcAddr)          # bind and listen to requests for registration
                self.__socket.listen(SrcMaxConn)
            except socket.error, msg:
                print msg, 'when trying to initialize TCP server.'
                self.__lock.release();
                sleep(TRY_INTERVAL)
                print 'Trying to initialize again...'
                continue
            self.__lock.release();
            break

    def WaitforConn(self):
        return self.__socket.accept()
    
    def Connect2Server(self, ServAddr):
        self.__lock.acquire();
        try:
            self.__socket.connect(ServAddr)
        except socket.error, msg:
            print msg, 'when trying to connect.'
            self.__socket.close()
            self.__lock.release();
            return False
        self.__lock.release();
        return True    

    def sendmsg(self,data,DATA = False):
        notSuccess = 0;
        #NumofBytes = 0;
        self.__lock.acquire(); 
        try:
            if not DATA:
                senddata = pack(str(BUFSIZ)+'s',repr(data)+'\n\n')     # send out an instruction
            else:
                senddata = data                             # send out a data   
            notSuccess = self.__socket.sendall(senddata)    # send out a data
            #NumofBytes = self.__socket.send(senddata)    # send out a data
        except socket.error, msg:
            print msg, 'when trying to send.'
            self.__socket.close()
            self.__lock.release();
            return False
        if notSuccess == None:                 # make the lock blocking because variables are dependent
        #if NumofBytes != len(senddata):         # make the lock blocking because variables are dependent
            self.__lock.release()
            return True
        print "Something weird was sent..."
        #print "The sent size was", NumofBytes
        #print "They should send", len(senddata)
        self.__socket.close()
        self.__lock.release()
        return False
            
    
    def recvmsg(self, bufsiz, DATA = False):
        data = "";
        if not DATA:
            bufsiz = BUFSIZ;
        self.__lock.acquire(); 
        tmpbufsiz = bufsiz
        while tmpbufsiz!=0:
            try:
                data += self.__socket.recv(tmpbufsiz)
            except socket.error, msg:
                print msg, 'when trying to receive.'
                self.__socket.close()
                self.__lock.release();
                return 'closed'
            tmpbufsiz = bufsiz - len(data)
            # need to work on this
            # sleep(0.1)
        if not DATA:
            data = eval(((unpack(str(BUFSIZ)+'s',data)[0]).split('\n\n'))[0])
            #if len(data) == BUFSIZ:
            #    data = eval(((unpack(str(BUFSIZ)+'s',data)[0]).split('\n\n'))[0])
            #else:
            #   # the following code would finally be removed
            #    print "Some weird instructions were received..."
            #    self.__socket.close()
            #    data = 'closed'
        #else:
        #    if len(data) != bufsiz:
        #        # the following code would finally be removed
        #        print "Some weird data format was received..."
        #        print "The data size is", len(data)
        #        print "The size should be", bufsiz
        #        self.__socket.close()
        #        data = 'closed'
        self.__lock.release();
        return data
    
    def close(self):
        self.__lock.acquire(); 
        try:
            self.__socket.close()
        except socket.error, msg:
            print msg, 'when trying to close.'
            self.__lock.release();
            return False
        self.__lock.release();
        return True
        
    def __encode(self,data):
        pass;
        
    def __decode(self,data):
        pass;   
             