# Author: Hao Zhang
# Created: 02/11/2011
# Class: MediaClient - a user who downloads the content
from socket import *
from time import *
from random import *
import threading
import thread
import os
import hashlib
from MyThread import *
from Configure import *
from Mytcpsocket import *
from MediaFileWrapper import *

class MediaClient(object):
    '# Author: Hao Zhang\
     # Created: 02/11/2011\
     # Class: MediaClient - a TCP client  that downloads data from the servers'
    # Initialization -- set up address and port; initilize parameters
    def __init__(self,cwd):
        self.__cwd = cwd                                  # current working directory
        self.__BootedasUser = True
        self.__tcpTracSock = Mytcpsocket()
        self.__tcpListenSock = Mytcpsocket()
        self.__MaxNumConn = MAX_PEER_CONNECTION
        self.__Addr = (([ip for ip in 
                            gethostbyname_ex(gethostname())[2] 
                            if not ip.startswith("127.")][0]), choice(range(50000,60000)))
        
        self.__tcpCliSockets = []           
        self.__ServerNeighborhood = []
        self.__ServerConnectionIPs = []
        self.__ServerConnectionSocks = []           
        self.__NumofConnections = 0
        self.__ExcludedServerAddr = []
        self.__choketimer = 30
        self.__StartWaiting = False
        
        self.__receivedFile = None                        # streaming file object
        self.__avaiMovieList = {}                         # available movie list from the tracker
        self.__movieHashNames = {}
        self.__currentvid = 'None'                        # current video that is being watched
        self.__NumofChunks = 0
        self.__NumofLeftPieces = 0
        
        self.__neighborLock = thread.allocate_lock()      # lock for the neighborhood update
        self.__connectionLock = thread.allocate_lock()
        self.__timerLock = thread.allocate_lock()
        self.__streamingStatLock = thread.allocate_lock()
        self.__bufferStatLock = thread.allocate_lock()
        self.__emptyAvailable = threading.Event(); self.__emptyAvailable.clear();  # one of the download chunks is waiting for other corresponding threads to finish that chunk
        self.__DownloadWait = threading.Event(); self.__DownloadWait.clear();      # wait till download is finished
        self.__BufferFullWait = threading.Event(); self.__BufferFullWait.clear();  # buffer too much, wait before download
        self.__BufferEmptyWait = threading.Event(); self.__BufferEmptyWait.clear();# buffer not enough, download from server
        self.__streamingWait = threading.Event(); self.__streamingWait.clear();    # wait till buffer is ready to stream
        self.__downloadthreads = []
        self.__EXIT = False
        
    # Boot as a pure user with prompt
    def bootasuser(self):
        self.__streamingPath = self.__cwd + os.sep + CLIENT_PATH + os.sep
        if not os.path.exists(self.__streamingPath):
            os.makedirs(self.__streamingPath)
        self.__PiecestoDownload = PIECE_IDS       # as a user, download all the pieces
        self.__PiecesperChunk = PIECE_PER_CHUNK
        if VERBOSE:
            print 'User %s goes online at %s' % (self.__Addr,ctime())
        # register to the tracker
        t = MyThread(self.__commtotracker,(1,),self.__commtotracker.__name__)
        t.start(); sleep(PROCESS_TIME);
        # choking
        t = MyThread(self.__choke,(1,),self.__choke.__name__)
        t.start(); sleep(PROCESS_TIME);
        # enable user prompt
        t = MyThread(self.__userprompt,(1,),self.__userprompt.__name__) # open a new thread for new requests
        t.start(); sleep(PROCESS_TIME);  
    
    # Boot as a downloader to get packets (as a helper)
    def bootashelper(self, videohash, segID, piecestodownload, excludedServerAddr):
        self.__BootedasUser = False
        self.__ExcludedServerAddr = excludedServerAddr
        self.__PiecestoDownload = piecestodownload # as a helper, specify pieces to download
        self.__PiecesperChunk = len(piecestodownload)
        self.__streamingPath = self.__cwd + os.sep + SERVER_PATH + os.sep + videohash + os.sep + 'seg' + str(segID) + FILE_SUFFIX
        self.__MetaPath = self.__cwd + os.sep + SERVER_PATH + os.sep + videohash + os.sep + 'seg' + str(segID) + META_SUFFIX
        self.__BufferFullWait.set() # no need to buffer download for helper 
        #### need a mechanism to control this: need to be either too greedy or too conservative
        self.__BufferEmptyWait.set()
        ######
        
        # register to the tracker
        t = MyThread(self.__commtotracker,(1,),self.__commtotracker.__name__)
        t.start(); sleep(PROCESS_TIME*2);
        # choking
        t = MyThread(self.__choke,(1,),self.__choke.__name__)
        t.start(); sleep(PROCESS_TIME);
        # enable download
        self.__movieInitialize(videohash); sleep(PROCESS_TIME);
        self.__DownloadWait.wait();        # wait until download is finished
        self.__EXIT = True
        return True
        
    def __bufferControl(self, *targs):
        while True:
            if self.__EXIT:
                return
            self.__streamingStatLock.acquire();
            if self.__streamedNumofChunks >= self.__NumofChunks:
                print self.__NumofChunks, self.__streamedNumofChunks;
                self.__streamingWait.set();                                     # let the stream break
                self.__streamingStatLock.release();
                break
            if self.__streamingBufferLength < 1:                                # less than a second of buffer to play
                self.__streamingWait.clear()                                    # stop streaming
                self.__BufferEmptyWait.set(); self.__BufferFullWait.set();      # start downloading NOW!
            else:
                self.__streamingWait.set()                                      # let it stream
                if self.__streamingBufferLength >= BUFFER_TOO_MUCH:             # buffer too much
                    self.__BufferFullWait.clear();self.__BufferEmptyWait.clear()# stop downloading
                elif self.__streamingBufferLength >= BUFFER_LENGTH:
                    self.__BufferEmptyWait.clear()
                elif self.__streamingBufferLength < BUFFER_LENGTH:              # buffer less than required length
                    self.__BufferFullWait.set()                                 # download from helpers
                    if self.__streamingBufferLength < BUFFER_EMERG_LEFT:        # if less than emergency
                        self.__BufferEmptyWait.set()                            # download from the SERVER
                    else:
                        self.__BufferEmptyWait.clear()
            self.__streamingStatLock.release();
            sleep(BUFFER_CHECK_INTERVAL)

    def __streaming(self, *targs):
        speedup = 1
        while True:
            if self.__EXIT:
                return
            self.__streamingWait.wait()
            ### stream the video NOW for duration xxx ###
            ### Now it is Fake streaming ###
            sleep(1)
            self.__streamingStatLock.acquire()
            if self.__streamingBufferLength > 1:
                self.__streamingBufferLength -= speedup
                print 'subtracted, BufferLength = ', self.__streamingBufferLength
                self.__streamedNumofChunks += speedup*self.__streamingRate/BYTES_PER_CHUNK
            if self.__streamedNumofChunks >= self.__NumofChunks:
                print self.__NumofChunks, self.__streamedNumofChunks;
                self.__streamingStatLock.release();
                break
            self.__streamingStatLock.release()
            ################################
    
    def __choke(self, *targs):
        while True:
            if self.__EXIT:
                return
            self.__connectionLock.acquire();
            if self.__NumofConnections >= self.__MaxNumConn:
                ## re-code the choking algorithm by allocating the probabilities##
                ## START ##
                sockind = choice(range(self.__NumofConnections-1))
                ## END ##
                self.__ServerConnectionSocks[sockind].close()
                del self.__ServerConnectionSocks[sockind]
                del self.__ServerConnectionIPs[sockind]
                self.__NumofConnections -= 1
            self.__connectionLock.release();
            if self.__NumofConnections < self.__MaxNumConn and self.__currentvid != 'None':
                self.__Connect2Server((1,self.__currentvid))             # connect to a new peer
            self.__timerLock.acquire(); sleep(self.__choketimer); self.__timerLock.release();
            
    def __download(self,*targs):
        args = targs[0]; servSock = args[0]; servAddr = args[1]; videohash = args[2];
        self.__DownloadWait.clear();
        while True:
            if videohash == 'None':
                servSock.sendmsg('closed')
                self.__pruneconnections(servSock, servAddr)
                self.__DownloadWait.set();
                return
            ack = servSock.sendmsg(['start',videohash])  # send which video to watch
            ACK = servSock.recvmsg(BUFSIZ)               # receive acknowledgement
            if not ack or ACK == 'closed':
                self.__pruneconnections(servSock, servAddr)
                self.__DownloadWait.set();
                return
            currentChunkID = -1; piecesperchunk = self.__PiecesperChunk;
            while True:
                if self.__EXIT:
                    return
                if servAddr == MEDIA_SERVER_ADDRESS: # wait until buffer is too little
                    self.__BufferEmptyWait.wait()
                else:                                # wait until buffer is less than a certain threshold
                    self.__BufferFullWait.wait()
                self.__bufferStatLock.acquire();
                if videohash != self.__currentvid:
                    videohash = self.__currentvid
                    self.__bufferStatLock.release();
                    break 
                if currentChunkID < self.__bufferheadChunkID:
                    currentChunkID = self.__bufferheadChunkID
                    self.__bufferStatLock.release();
                    ack = servSock.sendmsg(['piece',currentChunkID])
                    #print ack
                    avaiPieceIDsfromServ = servSock.recvmsg(BUFSIZ)
                    #print avaiPieceIDsfromServ
                    if not ack or avaiPieceIDsfromServ == 'closed':
                        self.__pruneconnections(servSock, servAddr)
                        self.__DownloadWait.set();
                        return
                    continue
                avaiPieceIDsfromServ = intersect(avaiPieceIDsfromServ,self.__avaiPieceIDs)# Now I am sure no other peers are giving me the same data 
                RequestingSet = lminus(avaiPieceIDsfromServ,self.__PiecesNowRequested)
                #print RequestingSet, "from", servAddr
                if len(RequestingSet) == 0:
                    if len(lminus(self.__avaiPieceIDs,self.__PiecesNowRequested)) > 0:
                        ack = servSock.sendmsg(['request'])
                        if not ack:
                            self.__pruneconnections(servSock, servAddr)
                            self.__bufferStatLock.release(); self.__DownloadWait.set();
                            return
                    self.__bufferStatLock.release();
                    self.__emptyAvailable.wait(BUFFER_EMERG_LEFT)    # wait until this chunk is over
                    continue
                PiecesToRequest = choice(RequestingSet)              # randomly choose an available piece
                self.__PiecesNowRequested.extend(PiecesToRequest)    # put it into the requesting queue
                self.__bufferStatLock.release();
                ack = servSock.sendmsg(['content',currentChunkID,PiecesToRequest])# download the piece
                ACK = servSock.recvmsg(BUFSIZ)
                if ACK == 'OK':
                    data = servSock.recvmsg(BYTES_PER_PIECE,True)     # only receive if server still has it
                else:                                                 # if ACK == 'XX'
                    avaiPieceIDsfromServ.remove(PiecesToRequest)      # otherwise remove it and continue
                    self.__PiecesNowRequested = lminus(self.__PiecesNowRequested, PiecesToRequest)
                    continue
                #print data[0:5]
                print "data from server", servAddr
                self.__bufferStatLock.acquire();
                if videohash != self.__currentvid:                    # if no longer watching current video, leave
                    videohash = self.__currentvid
                    self.__bufferStatLock.release();
                    break 
                if not ack or data == 'closed':                       # check if the connection is still alive
                    self.__pruneconnections(servSock, servAddr)
                    self.__PiecesNowRequested = lminus(self.__PiecesNowRequested, PiecesToRequest)
                    self.__bufferStatLock.release();      
                    self.__DownloadWait.set();
                    return
                if currentChunkID < self.__bufferheadChunkID:         # if other processes have already advanced the chunk, then dump it
                    self.__bufferStatLock.release();
                    continue
                # finally I made sure the downloaded pieces is valid and needed
                self.__PiecesNowRequested = lminus(self.__PiecesNowRequested,PiecesToRequest) # change status requested to available
                self.__avaiPieceIDs = lminus(self.__avaiPieceIDs, PiecesToRequest)
                self.__bufferPieceIDs.extend(PiecesToRequest)
                self.__bufferContent.append(data)
                if len(self.__bufferPieceIDs) >= piecesperchunk:      # finished downloading of a chunk
                    sortedIDs, self.__bufferContent = PacketsDecode(self.__bufferContent,self.__bufferPieceIDs)
                    if self.__BootedasUser:
                        ##### feed the buffer to the streaming wrapper #####
                        ##### now just write the file #####
                        self.__receivedFile.write(self.__bufferContent)
                        ##### END #########################
                    else:
                        self.__MetaFile.write(sortedIDs)
                        self.__receivedFile.write(self.__bufferContent)
                    self.__streamingStatLock.acquire();              # change streaming buffer length in seconds
                    self.__streamingBufferLength += piecesperchunk*BYTES_PER_PIECE/self.__streamingRate
                    print 'added, BufferLength = ', self.__streamingBufferLength
                    self.__streamingStatLock.release();    
                    self.__bufferPieceIDs = []; self.__bufferContent = [];
                    self.__PiecesNowRequested = []; self.__avaiPieceIDs = self.__PiecestoDownload;
                    piecesperchunk = self.__PiecesperChunk; self.__bufferheadChunkID += 1;
                    if self.__bufferheadChunkID == self.__NumofChunks:
                        self.__avaiPieceIDs = intersect(PIECE_IDS[0:self.__NumofLeftPieces], self.__PiecestoDownload) # last chunk left pieces
                        piecesperchunk = len(self.__avaiPieceIDs)
                    if self.__bufferheadChunkID > self.__NumofChunks or piecesperchunk == 0:
                        self.__currentvid = 'None'                   # finish download
                        self.__NumofChunks = 0
                        self.__receivedFile.close()
                        if not self.__BootedasUser:
                            self.__MetaFile.close()
                        self.__DownloadWait.set();                   # set the wait to finish
                    self.__emptyAvailable.set();                     # release the available ID empty lock
                    self.__emptyAvailable.clear();                   # set the lock again for next round
                self.__bufferStatLock.release();
    
    def __movieInitialize(self, videohash):    
        ## dump all current                                # dump the current streaming if possible
        self.__bufferStatLock.acquire();
        if self.__currentvid == videohash:
                self.__bufferStatLock.release();
                return
        #### movie paramter initialization:
        self.__streamingRate = BYTES_PER_CHUNK/BUFFER_LENGTH
        self.__streamingBufferLength = 0                # in units of seconds
        self.__streamedNumofChunks = 0                  # number of chunks that are streamed
        self.__bufferheadChunkID = 0                    # the chunk ID in front of the buffer
        self.__bufferContent = []                       # integer IDs
        self.__bufferPieceIDs = []                      # string names
        self.__PiecesNowRequested = []                  # pieces that are now requested
        self.__avaiPieceIDs = self.__PiecestoDownload   # initialize available pieces to watch
        self.__streamingWait.clear(); self.__BufferFullWait.clear(); self.__BufferEmptyWait.clear();
        if videohash != 'None':                             # if a movie was requested
            self.__NumofChunks = self.__movieHashNames[videohash][0]
            self.__NumofLeftPieces = self.__movieHashNames[videohash][1]
            self.__currentvid = videohash
            if self.__receivedFile != None:                 # close the opened file
                self.__receivedFile.close()
            if self.__BootedasUser:
                writeFilePath = self.__streamingPath + videohash + '.flv'
                #writeFilePath = self.__streamingPath + 'hancock-tsr2_h480p' + '.flv'
            else:
                writeFilePath = self.__streamingPath
                self.__MetaFile = open(self.__MetaPath,'w+b')
            self.__receivedFile=open(writeFilePath,'w+b')   # open a writable file
            if self.__BootedasUser:
                t = MyThread(self.__bufferControl,(1,),self.__bufferControl.__name__);
                t.start(); sleep(PROCESS_TIME);                                 # start buffer control
                t = MyThread(self.__streaming,(1,),self.__streaming.__name__);  # start streaming
                t.start(); sleep(PROCESS_TIME);
            else:
                self.__BufferEmptyWait.set(); self.__BufferFullWait.set();
            t = MyThread(self.__Connect2Server,(self.__MaxNumConn,videohash),self.__Connect2Server.__name__);
            t.start(); sleep(PROCESS_TIME);
            if self.__StartWaiting == False:                # listen to active server to user connections
                self.__StartWaiting = True
                t = MyThread(self.__WaitforConnection,(1,),self.__WaitforConnection.__name__);
                t.start(); sleep(PROCESS_TIME);     
        else:
            self.__NumofChunks = 0
            self.__NumofLeftPieces = 0
            self.__currentvid = 'None'                      # not watching any videos
        self.__bufferStatLock.release();
    
    def __commtotracker(self, *targs):
        ack = False
        while not ack:
            if self.__EXIT:
                return
            ack = self.__tcpTracSock.Connect2Server(TRACKER_ADDRESS)
            #print TRACKER_ADDRESS
            if ack:
                countdown = 0
                while True:
                    if self.__EXIT:
                        return
                    if countdown == 0:
                        ack = self.__tcpTracSock.sendmsg('user+' + repr(self.__Addr[1]))
                        newneighborhood = self.__tcpTracSock.recvmsg(BUFSIZ)
                        self.__avaiMovieList = self.__tcpTracSock.recvmsg(BUFSIZ)
                        if (not ack) or newneighborhood =='closed' or self.__avaiMovieList == 'closed':
                            ack = False
                            break 
                        del self.__movieHashNames; self.__movieHashNames = {};
                        for eachmovie in self.__avaiMovieList.keys():
                            self.__movieHashNames[hashlib.md5(eachmovie).hexdigest()] = self.__avaiMovieList[eachmovie]
                        self.__neighborLock.acquire()
                        ## might have to set a maximum limit of neighborhood ##
                        self.__ServerNeighborhood = union(self.__ServerNeighborhood,newneighborhood)
                        self.__ServerNeighborhood = lminus(self.__ServerNeighborhood,self.__ExcludedServerAddr)
                        self.__neighborLock.release()
                        countdown = OBTAIN_NEIGHBOR_PERIOD/INTERVAL_TRACKER_COMMUNICATION
                    else:
                        ack = self.__tcpTracSock.sendmsg('alive')
                        if not ack:
                            break
                        sleep(INTERVAL_TRACKER_COMMUNICATION); countdown -= 1; # send alive msg interval 
            sleep(TRY_INTERVAL)       # obtain neighborhood/movielist interval
            del self.__tcpTracSock; self.__tcpTracSock = Mytcpsocket();
                    
    def __WaitforConnection(self, *targs):
        self.__tcpListenSock.InitServSock(self.__Addr,self.__MaxNumConn)
        while True:     
            if self.__EXIT:
                return       
            (tcpServSock, SERVER_ADDR) = self.__tcpListenSock.WaitforConn()
            self.__connectionLock.acquire();
            servtcpsock = Mytcpsocket(tcpServSock)
            if self.__NumofConnections < self.__MaxNumConn:
                servport = servtcpsock.recvmsg(BUFSIZ)
                ack = servtcpsock.sendmsg('ACK')                    # send ACK
                SERVER_SERV_ADDR = (SERVER_ADDR[0],servport)
                if ((SERVER_SERV_ADDR in self.__ServerConnectionIPs) or 
                    (SERVER_SERV_ADDR == self.__ExcludedServerAddr) or 
                    (not ack) or servport == 'closed'):
                    servtcpsock.close()
                else:
                    self.__ServerConnectionSocks.append(servtcpsock)
                    self.__ServerConnectionIPs.append(SERVER_SERV_ADDR)
                    self.__NumofConnections += 1
                    if VERBOSE:
                        print "...connected from:", SERVER_SERV_ADDR
                    t = MyThread(self.__download,
                                 (servtcpsock,SERVER_SERV_ADDR,self.__currentvid),self.__download.__name__)
                    t.start(); sleep(PROCESS_TIME);
                    self.__downloadthreads.append(t)
            else:
                servtcpsock.close()                                # close if the number of connections exceeds max
            self.__connectionLock.release();
            
    def __Connect2Server(self, *targs):
        args = targs[0]; number = args[0]; videohash = args[1];
        self.__connectionLock.acquire(); self.__neighborLock.acquire();
        Neighborhood = lminus(self.__ServerNeighborhood, self.__ServerConnectionIPs)
        potentialconnect = sample(Neighborhood, min(len(Neighborhood),number))
        for eachServer in potentialconnect:
            if self.__NumofConnections < self.__MaxNumConn:     
                if eachServer not in self.__ServerConnectionIPs:           
                    servSock = Mytcpsocket()
                    ack1 = servSock.Connect2Server(eachServer)
                    ack2 = servSock.sendmsg(self.__Addr[1])
                    ack3 = servSock.recvmsg(BUFSIZ)          # receive ACK
                    if ack1 and ack2 and ack3!='closed':
                        self.__NumofConnections += 1
                        self.__ServerConnectionSocks.append(servSock)
                        self.__ServerConnectionIPs.append(eachServer)
                        t = MyThread(self.__download,(servSock,eachServer,videohash),
                                     self.__download.__name__)
                        t.start(); sleep(PROCESS_TIME);
                        self.__downloadthreads.append(t);
                    else:
                        self.__ServerNeighborhood.remove(eachServer)
            else:
                break
        self.__connectionLock.release(); self.__neighborLock.release();
    
    def __userprompt(self, *args):
        while True:
            if self.__EXIT:
                return
            userinput = raw_input('<<<Select a function>>>:\n[-1] Exit\n[1] Watch a Movie\n[2] Print Neighbors\n[3] Print Connections\nYour choice>> ')
            if userinput == '1':
                numofmovies = len(self.__avaiMovieList)
                if numofmovies == 0:
                    print 'No movies to watch yet!'
                    continue
                print '<<<Select a movie>>>:'
                print '#. <<Go back>>'
                print '0. <<Stop the current movie>>'
                for i,fname in enumerate(self.__avaiMovieList):
                    print  repr(i+1)+'. '+fname
                input = raw_input('Your choice>> ')                   
                if input == '#':                                   # if the user wants to go back
                    pass;
                elif input >= '0' and input <= str(numofmovies):   
                    movieID = int(input)-1 
                    if movieID >=0:                                # watch a movie
                        for i, eachmovie in enumerate(self.__avaiMovieList):
                            if i == movieID:
                                videohash = hashlib.md5(eachmovie).hexdigest()
                                break;
                    else:
                        videohash = 'None'                         # stop watching the current movie
                    self.__movieInitialize(videohash)              # initialize movie download and watching
            elif userinput == '2':
                self.__printAllNeighbors()
            elif userinput == '3':
                self.__printAllConnections()
            elif userinput =='-1':
                self.__EXIT = True
                return;
            else:
                pass;    

    def __pruneconnections(self,tcpsock,Addr):
        self.__connectionLock.acquire();
        print tcpsock, Addr
        print self.__ServerConnectionSocks
        self.__ServerConnectionSocks.remove(tcpsock)
        self.__ServerConnectionIPs.remove(Addr)
        self.__NumofConnections -= 1
        self.__connectionLock.release();
    
    def __closeAllconnections(self):
        self.__connectionLock.acquire();
        for connection in self.__ServerConnectionSocks:
            connection.close()
        self.__ServerConnectionSocks = []
        self.__ServerConnectionIPs = []
        self.__NumofConnections = 0
        self.__connectionLock.release();
        
    def __printAllNeighbors(self):
        for eachNeighbor in self.__ServerNeighborhood:
            print eachNeighbor

    def __printAllConnections(self):
        for eachConnectionIP in self.__ServerConnectionIPs:
            print eachConnectionIP
        for eachConnectionSock in self.__ServerConnectionSocks:
            print eachConnectionSock    
