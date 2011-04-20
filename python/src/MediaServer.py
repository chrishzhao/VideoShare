# Author: Hao Zhang
# Created: 02/11/2011
# Class: MyThread - a customized threading class 
from socket import *
from time import *
from random import *
from struct import *
import threading
import thread
import hashlib
import shutil
import os
from math import ceil
from MyThread import *
from Configure import *
from Mytcpsocket import *
from MediaFileWrapper import *
from MediaClient import *

class MediaServer(object):
    '# Author: Hao Zhang\
     # Created: 02/11/2011\
     # Class: MediaServer - a TCP server that uploads data to users'
    def __init__(self, cwd, IS_SERVER = 1):
        self.__cwd = cwd                                     # current working directory
        self.__isserver = IS_SERVER                          # I mean the True server, not helper
        self.__tcpSerSock = Mytcpsocket()                    # initiate server socket
        self.__tcpTracSock = Mytcpsocket()                   # initiate tracker socket
        self.__PATH = self.__cwd+os.sep+SERVER_PATH + os.sep # set up video caching directory
        if not os.path.exists(self.__PATH):
                os.makedirs(self.__PATH)
                
        # movieList: vhash: vname; videoDict: vhash: vpath; videoStat: vhash: [NumofChunks, NumofLeftOverPieces]
        self.__movieList = {}; self.__videoDict = {}; self.__videoStat = {};
        # storeAlloc: vhash: vsize; storePrices: vhash: vprice
        self.__storeAlloc = {}; self.__storePrices = {};     
        # mediaReaders: vhash: [a list of open file readers for vhash]; mediaUpdaters: vhash: file writer
        self.__mediaReaders = {}
        self.__mediaUpdaters = {}
        
        if IS_SERVER:
            self.__MaxNumConn = MAX_SERV_CONNECTION
            self.__Addr = MEDIA_SERVER_ADDRESS
            # read all the movies and convert newly added movies
            f = open(self.__PATH+'movielist.txt','r+'); allLines = f.readlines(); f.close();
            for eachmovie in allLines:
                moviename = eachmovie.split('\n')[0]
                self.__movieList[hashlib.md5(moviename).hexdigest()] = moviename         #vhash: vname
            dirList = os.listdir(self.__PATH)
            for dname in dirList:
                if (not os.path.isdir(self.__PATH+dname)) and dname != 'movielist.txt':  # if video not converted, convert
                    hashname = hashlib.md5(dname.split('.')[0]).hexdigest()
                    if (hashname in self.__movieList and not hashname in dirList):
                        videopath = self.__PATH+hashname; os.makedirs(videopath)
                        self.__convertVideo(videopath+os.sep, self.__PATH + dname)       # convert the video
            dirList = os.listdir(self.__PATH)
            for dname in dirList:
                if os.path.isdir(self.__PATH + dname):
                    videopath = self.__PATH + dname + os.sep
                    if dname in self.__movieList:
                        self.__videoDict[dname] = videopath       # vhash: vpath
                        f = open(videopath+'length','rb'); dt= f.readlines();
                        self.__videoStat[dname]=dt[0].split(','); # vhash: [NumofChunks, NumofLeftoverPieces]
                        self.__mediaReaders[dname] = [];
                    else:
                        print videopath                           # not in list, to be deleted
                        shutil.rmtree(videopath)
        else:
            self.__MaxNumConn = MAX_PEER_CONNECTION
            # need to implement NAT traversal
            ##########start here############
            self.__Addr = (([ip for ip in 
                            gethostbyname_ex(gethostname())[2] 
                            if not ip.startswith("127.")][0]), choice(range(50000,60000)))
            ##########end   here############    
            dirList = os.listdir(self.__PATH) 
            for dname in dirList:
                if os.path.isdir(self.__PATH + dname):
                    videopath = self.__PATH + dname + os.sep
                    self.__videoDict[dname] = videopath
                    self.__mediaReaders[dname] = []
                    self.__mediaUpdaters[dname] = MediaFileWrapper(videopath, False) # write access
                    self.__storeAlloc[dname] = 0; self.__storePrices[dname] = 0;
                    
        self.__ClientNeighborhood = []  
        self.__NumofConnections = 0
        self.__ClientConnectionIPs = []
        self.__ClientConnectionSocks = []           
        self.__choketimer = 30
        
        self.__uploadBW = 0                   # KB/sec
        self.__uploadedBytes = 0              # uploaded bytes in a second
        
        self.__UploadThreads = []             # upload threads. used to control UploadBWControl
        
        self.__neighborLock = thread.allocate_lock()
        self.__connectionLock = thread.allocate_lock()
        self.__timerLock = thread.allocate_lock()
        self.__rateAllocLock = thread.allocate_lock()
        self.__mediaReaderLock = thread.allocate_lock()
        self.__uploadStatLock = thread.allocate_lock()
        self.__UploadThreadsLock = thread.allocate_lock()
        self.__BWControlBoot = threading.Event(); self.__BWControlBoot.clear();  # we don't need BW control all the time
        self.__uploadBWExceed = threading.Event(); self.__uploadBWExceed.clear();
        self.__RateAllocBoot = threading.Event(); self.__RateAllocBoot.clear();  # we don't need rate allocation all the time
            
    def boot(self, uploadBW):
        self.__uploadBW = uploadBW            # force a virtual upload bandwidth; for testing reasons
        if VERBOSE:
            print 'Server %s goes online at %s' % (self.__Addr,ctime())    
        ####### This is fake, just for testing purpose ################
        t = MyThread(self.__uploadBWControl,(1,),self.__uploadBWControl.__name__)
        t.start(); sleep(PROCESS_TIME);
        # rate allocation
        if not self.__isserver:
            t = MyThread(self.__rateallocation,(1,),self.__rateallocation.__name__)
            t.start(); sleep(PROCESS_TIME);
        # register to the tracker
        t = MyThread(self.__commtotracker,(1,),self.__commtotracker.__name__)
        t.start(); sleep(PROCESS_TIME);
        # listen to passive connections
        t = MyThread(self.__WaitforConnection,(1,),self.__WaitforConnection.__name__)
        t.start(); sleep(PROCESS_TIME);
        # actively connect to client
        t = MyThread(self.__Connect2Client,self.__MaxNumConn,self.__Connect2Client.__name__)
        t.start(); sleep(PROCESS_TIME);
        # choking
        t = MyThread(self.__choke,(1,),self.__choke.__name__)
        t.start(); sleep(PROCESS_TIME);
        # user prompt
        t = MyThread(self.__userprompt,(1,),self.__userprompt.__name__) # open a new thread for new requests
        t.start(); sleep(PROCESS_TIME);  
            
    # This is an artificial upload BW control mechanism; only used for debugging purpose
    def __uploadBWControl(self, *targs):
        checkInterval = 0.1
        while True:
            self.__BWControlBoot.wait();                 # wait till there is at least one upload thread running
            self.__uploadStatLock.acquire();
            exceededBytesPerInterval = self.__uploadedBytes - checkInterval*self.__uploadBW
            self.__uploadStatLock.release();
            if exceededBytesPerInterval > 0:
                self.__uploadBWExceed.clear()
                ## fake wait to get more upload BW
                print 'exceeded'
                sleep(exceededBytesPerInterval/self.__uploadBW)
                print 'sleep over'
            # if there does not exist excessive bytes, the uploadBW will expire
            #print self.__uploadedBytes
            self.__uploadStatLock.acquire(); self.__uploadedBytes = 0; self.__uploadStatLock.release();
            self.__uploadBWExceed.set()
            sleep(checkInterval)                         # check every second
            self.__UploadThreadsLock.acquire();
            ThreadstoRemove = []
            for eachThread in self.__UploadThreads:
                if not eachThread.isAlive():
                    ThreadstoRemove.append(eachThread)
            for eachRemoval in ThreadstoRemove:
                self.__UploadThreads.remove(eachRemoval)
            if len(self.__UploadThreads) == 0:
                self.__BWControlBoot.clear()             # if no threads are running, stop uploadBW control thread
            self.__UploadThreadsLock.release();
            
        return
    def __choke(self, *targs):
        while True:
            self.__connectionLock.acquire();
            if self.__NumofConnections >= self.__MaxNumConn:
                ## re-code the choking algorithm by allocating the probabilities##
                ## START ##
                sockind = choice(range(self.__NumofConnections-1))
                ## END ##
                self.__ClientConnectionSocks[sockind].close()
                del self.__ClientConnectionSocks[sockind]
                del self.__ClientConnectionIPs[sockind]
                self.__NumofConnections -= 1
            self.__connectionLock.release();
            if self.__NumofConnections < self.__MaxNumConn:
                self.__Connect2Client(1)             # connect to a new peer
            self.__timerLock.acquire(); sleep(self.__choketimer); self.__timerLock.release();    

    def __upload(self,*targs):
        args = targs[0]; myClisock = args[0]; cliAddr = args[1];
        ack = True; avaPieces = None; ClientFile = None;
        while True:
            self.__BWControlBoot.set(); self.__RateAllocBoot.set();
            data = myClisock.recvmsg(BUFSIZ)
            print data
            if data[0] == 'start':
                videohash = data[1]                          # receive movie hash name
                if not videohash in self.__videoDict.keys(): # this will happen for helpers only. Server needs all videos
                    print self.__videoDict
                    os.makedirs(self.__PATH + videohash)
                    self.__videoDict[videohash] = self.__PATH + videohash + os.sep
                    self.__mediaReaderLock.acquire(); 
                    self.__mediaReaders[videohash] = []; 
                    self.__mediaReaderLock.release();
                    if not self.__isserver:
                        self.__mediaUpdaters[videohash] = MediaFileWrapper(self.__videoDict[videohash],False) # write access
                        self.__rateAllocLock.acquire();
                        self.__storeAlloc[videohash] = 0; self.__storePrices[videohash] = 0;
                        self.__rateAllocLock.release();
                ClientFile = MediaFileWrapper(self.__videoDict[videohash])
                self.__mediaReaders[videohash].append(ClientFile)# add the file reader
                myClisock.sendmsg('ACK')              # send ack
            elif data[0] == 'piece':
                if not self.__isserver:
                    if avaPieces != None:
                        if len(avaPieces) > 0:            # more video than needed
                            self.__rateAllocLock.acquire();
                            self.__storePrices[videohash] -= 1# minus a token
                            print self.__storePrices
                            self.__rateAllocLock.release();
                        else:
                            pass;
                avaPieces = ClientFile.getPieceIdbyChunk(data[1])
                ack = myClisock.sendmsg(avaPieces)
                print avaPieces
            elif data[0] =='content':
                ChunkID,PieceID = data[1],data[2]
                datamsg = ClientFile.getPiecebyId(ChunkID,PieceID)
                if datamsg != None:                   # found the piece
                    ack = myClisock.sendmsg('OK')
                    ## this is a fake constraint on upBW; only for testing purpose
                    self.__uploadBWExceed.wait()      
                    ##############################################################
                    ack = myClisock.sendmsg(datamsg,True)
                    self.__uploadStatLock.acquire();
                    self.__uploadedBytes += BYTES_PER_PIECE
                    self.__uploadStatLock.release();
                    avaPieces = avaPieces.lstrip(PieceID) # remove the piece that is uploaded
                else:
                    ack = myClisock.sendmsg('XX')     # send out a none message
            elif data[0] =='request':
                if not self.__isserver:
                    if avaPieces!= None:
                        if len(avaPieces) == 0:               # could have more video
                            self.__rateAllocLock.acquire();
                            self.__storePrices[videohash] += 1# plus a token
                            print self.__storePrices
                            self.__rateAllocLock.release();
            if not ack or data == 'closed':
                self.__pruneconnections(myClisock, cliAddr)
                if ClientFile != None:
                    ClientFile.closeAll();
                    self.__mediaReaderLock.acquire();
                    self.__mediaReaders[videohash].remove(ClientFile);
                    self.__mediaReaderLock.release();
                break
    
    def __download(self,vhashname,segID,pieceIDs):
        helper = MediaClient(self.__cwd); 
        Success = helper.bootashelper(vhashname, segID, pieceIDs, self.__Addr);
        del helper
        return Success
    
    def __rateallocation(self,*targs):
        while True:
            self.__RateAllocBoot.wait();
            self.__rateAllocLock.acquire();
            if len(self.__storeAlloc) != 0:
                totalsiz = 0
                for vhash in self.__storeAlloc.keys():
                    self.__storeAlloc[vhash] = getFolderSize(self.__videoDict[vhash])
                    totalsiz += self.__storeAlloc[vhash]    # calculate the current total size
                pricevideos = zip(self.__storePrices.values(),self.__storePrices.keys())
                pricevideos.sort(); sortedValues, sortedVideos = zip(*pricevideos) 
                low = 0; high = len(sortedValues)-1;
                self.__rateAllocLock.release();
                while low <= high:
                    if totalsiz < STORAGE_CAP:
                        if sortedValues[high] > 0:
                            totalsiz += self.__storageupdate(sortedVideos[low],totalsiz)  # ++ storage of high
                            high -= 1; continue;
                        else:
                            break;                           # no update because not needed
                    if (abs(sortedValues[low]) < ST_ALLOC_TH # no update because it does not satisfy threshold
                        or abs(sortedValues[high]) < ST_ALLOC_TH):
                        break
                    if self.__mediaUpdaters[sortedVideos[low]].getNumofSeg() <= 0:
                        low += 1; continue;
                    if self.__mediaUpdaters[sortedVideos[high]].getNumofSeg() >= SEG_PER_CHUNK:
                        high -= 1;continue;
                    if sortedValues[low] < 0:
                        totalsiz += self.__storageupdate(sortedVideos[low],totalsiz,False)# -- storage of low
                    if sortedValues[high] > 0:
                        totalsiz += self.__storageupdate(sortedVideos[low],totalsiz);     # ++ storage of high
                self.__rateAllocLock.acquire();
                for vhash in self.__storePrices.keys():
                    self.__storePrices[vhash] = 0            # clear
                #self.__rateAllocLock.release();
            self.__rateAllocLock.release();
            sleep(INTERVAL_RATEALLOC)
            # don't need rate allocation when no download request is present
            self.__UploadThreadsLock.acquire();
            ThreadstoRemove = []
            for eachThread in self.__UploadThreads:
                if not eachThread.isAlive():
                    ThreadstoRemove.append(eachThread)
            for eachRemoval in ThreadstoRemove:
                self.__UploadThreads.remove(eachRemoval)
            if len(self.__UploadThreads) == 0:
                self.__RateAllocBoot.clear()             # if no threads are running, stop rate allocation thread
            self.__UploadThreadsLock.release();
            
    
    # perform the storage add or removal given a video name
    def __storageupdate(self, vhashname, totalsiz, added = True):
        mul = 1
        if added:
            pieceIDs = self.__mediaUpdaters[vhashname].getNewPieceIDs()
            segID = self.__mediaUpdaters[vhashname].getNumofSeg() + 1
            rsize = self.__videoStat[vhashname][0]*BYTES_PER_CHUNK/SEG_PER_CHUNK
            if rsize + totalsiz < STORAGE_CAP:           # write if not exceed storage limit
                if not self.__download(vhashname,segID,pieceIDs):# download data
                    rsize = 0
            else:
                rsize = 0
        else:
            mul = -1
        # the update process is self-locked because the MediaFileWrapper itself is a synchronized process 
        UpdateSuccess = True; 
        self.__mediaReaderLock.acquire();
        for eachClientFile in self.__mediaReaders[vhashname]:
            UpdateSuccess = UpdateSuccess and eachClientFile.UpdateAccess(added)# update file object for each peer
        self.__mediaReaderLock.release();
        self.__mediaUpdaters[vhashname].UpdateAccess(added) # update file access
        if not added and UpdateSuccess:                  # wait for close() before removal
            rsize = self.__mediaUpdaters[vhashname].removeSegment()
        return rsize*mul
    
    def __commtotracker(self, *targs):
        ack = False
        while not ack:
            ack = self.__tcpTracSock.Connect2Server(TRACKER_ADDRESS)
            if ack:
                countdown = 0
                while True:
                    if countdown == 0:
                        ack = self.__tcpTracSock.sendmsg('serv+' + repr(self.__Addr[1]))
                        newneighborhood = self.__tcpTracSock.recvmsg(BUFSIZ)
                        avaiMovieList = self.__tcpTracSock.recvmsg(BUFSIZ)
                        if (not ack) or newneighborhood=='closed' or avaiMovieList == 'closed':
                            ack = False
                            break
                        ACK = 'ACK'
                        if self.__isserver:
                            movienames = ""
                            for fhash, fname in  self.__movieList.iteritems():
                                movienames = (movienames + '+' + fname 
                                              + '#' + self.__videoStat[fhash][0]
                                              + '#' + self.__videoStat[fhash][1])
                            ack = self.__tcpTracSock.sendmsg('list' + movienames)
                            ACK = self.__tcpTracSock.recvmsg(BUFSIZ)
                            if (not ack) or ACK == 'closed':
                                ack = False
                                break
                        else:
                            del self.__videoStat; self.__videoStat = {};
                            for eachmovie in avaiMovieList.keys():
                                self.__videoStat[hashlib.md5(eachmovie).hexdigest()] = avaiMovieList[eachmovie]    
                        self.__neighborLock.acquire()
                        self.__ClientNeighborhood = union(self.__ClientNeighborhood,newneighborhood)
                        ## might have to set a maximum limit of neighborhood ##
                        self.__neighborLock.release()
                        countdown = OBTAIN_NEIGHBOR_PERIOD/INTERVAL_TRACKER_COMMUNICATION
                    else:
                        ack = self.__tcpTracSock.sendmsg('alive')
                        if not ack:
                            break
                        sleep(INTERVAL_TRACKER_COMMUNICATION); countdown -= 1
            sleep(TRY_INTERVAL)
            del self.__tcpTracSock; self.__tcpTracSock = Mytcpsocket();
    
    def __Connect2Client(self, number):
        self.__connectionLock.acquire(); self.__neighborLock.acquire();
        Neighborhood = lminus(self.__ClientNeighborhood, self.__ClientConnectionIPs)
        potentialconnect = sample(Neighborhood, min(len(Neighborhood),number))
        for eachClient in potentialconnect:
            if self.__NumofConnections < self.__MaxNumConn:  
                if eachClient not in self.__ClientConnectionIPs:              
                    cliSock = Mytcpsocket()
                    ack1 = cliSock.Connect2Server(eachClient)
                    ack2 = cliSock.sendmsg(self.__Addr[1])
                    ack3 = cliSock.recvmsg(BUFSIZ)          # receive ACK
                    if ack1 and ack2 and ack3!='closed':
                        self.__NumofConnections += 1
                        self.__ClientConnectionSocks.append(cliSock);
                        self.__ClientConnectionIPs.append(eachClient);
                        t = MyThread(self.__upload,(cliSock,eachClient),self.__upload.__name__)
                        self.__UploadThreadsLock.acquire(); self.__UploadThreads.append(t); self.__UploadThreadsLock.release()
                        self.__BWControlBoot.set();               # start BW control
                        self.__RateAllocBoot.set();               # start rate allocation
                        t.start(); sleep(PROCESS_TIME);
                    else:
                        self.__ClientNeighborhood.remove(eachClient)
            else:
                break;
        self.__connectionLock.release(); self.__neighborLock.release();
            
    def __WaitforConnection(self, *targs):
        self.__tcpSerSock.InitServSock(self.__Addr,self.__MaxNumConn)
        if VERBOSE:
            print "Waiting for connection..."
        while True:            
            (tcpClientSock, CLIENT_ADDR) = self.__tcpSerSock.WaitforConn()
            self.__connectionLock.acquire();
            clitcpsock = Mytcpsocket(tcpClientSock)
            if self.__NumofConnections < self.__MaxNumConn:
                servport = clitcpsock.recvmsg(BUFSIZ)
                ack = clitcpsock.sendmsg('ACK')
                CLIENT_SERV_ADDR = (CLIENT_ADDR[0],servport)
                if ((CLIENT_SERV_ADDR in self.__ClientConnectionIPs) 
                    or (not ack) or servport == 'closed'):
                    clitcpsock.close()
                else:
                    self.__ClientConnectionSocks.append(clitcpsock);
                    self.__ClientConnectionIPs.append(CLIENT_SERV_ADDR);
                    self.__NumofConnections += 1;
                    if VERBOSE:
                        print "...connected from:", CLIENT_ADDR
                    t = MyThread(self.__upload,(clitcpsock,CLIENT_SERV_ADDR),self.__upload.__name__)
                    self.__UploadThreadsLock.acquire(); self.__UploadThreads.append(t); self.__UploadThreadsLock.release()
                    self.__BWControlBoot.set();               # start BW control
                    self.__RateAllocBoot.set();               # start rate allocation
                    t.start(); sleep(PROCESS_TIME);
            else:
                clitcpsock.close()          # close if the number of connections exceeds max
            self.__connectionLock.release();
            
    # no random coding of the pieces yet. need to modify the function if needed to do so.
    def __convertVideo(self,path,fname):
        FILES = [];
        METAS = [];
        vidfile = open(fname,'rb')
        for segNum in range(SEG_PER_CHUNK):
            file = open(path+'seg'+repr(segNum+1)+FILE_SUFFIX,'wb+')
            meta = open(path+'seg'+repr(segNum+1)+META_SUFFIX,'wb+')
            FILES.append(file); METAS.append(meta)
            Ind = 0
        data = vidfile.read(BYTES_PER_SEG)
        numofchunks = 0; numofleftpieces = 0;
        while data!="":
            wlen = len(data)*1.0/BYTES_PER_PIECE
            if wlen < PIECE_PER_SEG:
                wlen = ceil(wlen)
                data = pack(str(int(wlen*BYTES_PER_PIECE))+'s',data)
            numofleftpieces += wlen
            FILES[Ind].write(data)
            METAS[Ind].write(PIECE_IDS[Ind*PIECE_PER_SEG:Ind*PIECE_PER_SEG+int(wlen)])
            Ind += 1; Ind = Ind%SEG_PER_CHUNK;
            data = vidfile.read(BYTES_PER_SEG)
        vidfile.close()
        numofchunks = int(numofleftpieces/PIECE_PER_CHUNK)
        numofleftpieces = int(numofleftpieces%PIECE_PER_CHUNK)
        if numofleftpieces ==0:
            numofleftpieces = PIECE_PER_CHUNK
        f = open(path+'length','wb+'); f.write(str(numofchunks)+','+str(numofleftpieces));
        f.close();
        for segNum in range(SEG_PER_CHUNK):
            FILES[segNum].close();
            METAS[segNum].close();
            
    def __userprompt(self, *args):
        while True:
            userinput = raw_input('Input your choice:\n[1] Print Neighbors\n[2] Print Connections\nYour choice>> ')
            if userinput == '1':
                self.__printAllNeighbors()
            if userinput == '2':
                self.__printAllConnections()
            else:
                pass;
    
    def __pruneconnections(self,tcpsock,Addr):
        self.__connectionLock.acquire();
        self.__ClientConnectionSocks.remove(tcpsock)
        self.__ClientConnectionIPs.remove(Addr)
        self.__NumofConnections -= 1
        self.__connectionLock.release();
        
    def __printAllNeighbors(self):
        for eachNeighbor in self.__ClientNeighborhood:
            print eachNeighbor

    def __printAllConnections(self):
        for eachConnectionIP in self.__ClientConnectionIPs:
            print eachConnectionIP
        for eachConnectionSock in self.__ClientConnectionSocks:
            print eachConnectionSock
        
