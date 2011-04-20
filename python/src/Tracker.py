from time import *
from socket import *
from random import sample
import threading
from MyThread import *
import thread
from Mytcpsocket import *
from Configure import *

class Tracker(object):
    def __init__(self, Tracker_Addr = TRACKER_ADDRESS):
        self.__socket = Mytcpsocket()                  # a new socket
        self.__Addr = Tracker_Addr                     # IP address + port
        self.__MaxNumConn = MAX_TRAC_CONNECTION        
        self.__userDict = {}                           # connecting addresses of active (estimate) users
        self.__servDict = {}                           # connecting addresses of active (estimate) helpers
        #self.__servDict[MEDIA_SERVER_ADDRESS] = 1      # the central server
        self.__inputLock = thread.allocate_lock()      # lock for the input variables
        self.__EXIT = 0                                # exit the system or not
        self.__movieList = {}                          # list of movie names
   
    def __userprompt(self, *args):
        while True:
            userinput = raw_input('Input your choice:\n[0] Print All Movies\n[1] Print Registered Peers\n[2] Disconnect\nYour choice>> ')
            if userinput =='0':
                self.__printAllMovies()
            elif userinput == '1':
                self.__printAllregistered()
            elif userinput == '2':
                self.__inputLock.acquire(); self.__EXIT = 1; self.__inputLock.release();
                break;
            else:
                pass;
    
    def boot(self):
        t = MyThread(self.__userprompt,(1,),self.__userprompt.__name__) # open a new thread for new requests
        t.start(); sleep(PROCESS_TIME);
        
        self.__socket.InitServSock(self.__Addr,self.__MaxNumConn)             
        while True:
            (tcpCliSock, CIENT_ADDR) = self.__socket.WaitforConn()            
            t = MyThread(self.__registerpeer,(tcpCliSock,CIENT_ADDR),
                         self.__registerpeer.__name__) # open a new thread for new requests
            #self.__threads.append(t)         
            t.start(); sleep(PROCESS_TIME)             # allow process time for the thread
            self.__inputLock.acquire() 
            if self.__EXIT == 1:
                self.__socket.close(); 
                break;
            self.__inputLock.release()

    def __registerpeer(self,*targs):                    # register the peer and obtain a list of potential neighbors
        args = targs[0]
        CliSocket = args[0]; CliAddr = args[1];
        myClisock = Mytcpsocket(CliSocket)  
        IS_SERV = -1      
        while True:
            data = myClisock.recvmsg(BUFSIZ)
            if 'serv' in str.lower(data):
                IS_SERV = 1;
                CliAddr = (CliAddr[0],int(data.split('+')[1]))
                self.__servDict[CliAddr] = 1
                pc = self.__potentialconn(CliAddr, self.__userDict) # return a list of user addresses \ itself
                myClisock.sendmsg(pc)
                myClisock.sendmsg(self.__movieList)                 # send movie list to watch
            elif 'user' in str.lower(data):
                IS_SERV = 0;
                CliAddr = (CliAddr[0],int(data.split('+')[1]))
                self.__userDict[CliAddr] = 1
                pc = self.__potentialconn(CliAddr, self.__servDict) # return a list of serv addresses \ itself
                myClisock.sendmsg(pc)
                myClisock.sendmsg(self.__movieList)                 # send movie list to watch
            elif 'list' in str.lower(data):
                data = data.split('+')
                for i in range(1,len(data)):
                    videostat = data[i].split('#'); 
                    self.__movieList[videostat[0]] = [int(videostat[1]),int(videostat[2])]
                myClisock.sendmsg('ACK')
            elif str.lower(data) == 'alive':                        # still alive
                print data, ' from ', CliAddr 
                pass;
            else:
                if IS_SERV == 1:
                    self.__servDict.pop(CliAddr)
                elif IS_SERV == 0:
                    self.__userDict.pop(CliAddr)                             
                myClisock.close()                                           # close the connection
                break
            
            
    def __potentialconn(self, CliAddr, PotentialConnections):
        'return a list of potential connections -- list of IP/ports in the other Dictionary set-minus itself'
        def notself(query):
            return (CliAddr != query);
        return filter(notself,sample(PotentialConnections, 
                                     min(len(PotentialConnections),NUM_RETURNED_PEERS)))
    def __printAllregistered(self):
        print 'Registered users:'
        for eachUsr in self.__userDict:
            print eachUsr
        print '\nRegistered servers:'
        for eachServ in self.__servDict:
            print eachServ
     
    def __printAllMovies(self):
        for i, eachmovie in enumerate(self.__movieList):
            print repr(i+1)+'. ' + eachmovie   
        