# A file is divided into chunks, each chunk being 20Mbits = 2.5MB
# Each chunk has 20 pieces
# 5 pieces constitute a segment
# The file is stored on the disk in the following formats
# File 1: [segment1 in chunk 1, segment 1 in chunk 2, ..., segment 1 in chunk END]
# File 2: [segment2 in chunk 1, segment 2 in chunk 2, ..., segment 2 in chunk END]
# File 3: [segment3 in chunk 1, segment 3 in chunk 2, ..., segment 3 in chunk END]
# File 4: [segment4 in chunk 1, segment 4 in chunk 2, ..., segment 4 in chunk END]
import os
import threading
import thread
from Configure import *
from random import *

class MediaFileWrapper(object):
    def __init__(self, directory, READ = True):     # by default to gain read access; o.w. write.
        self.__READ = READ
        self.__directory = directory                # directory name maps to video name
        self.__numofsegs = 0
        self.__segmentMETA = []                     # META data for corresponding segments
        self.__segfilenames = []                    # segment file names
        self.__lock = thread.allocate_lock()
        if self.__READ:
            self.__segments = []                    # segment file pointers
        else:
            self.__fileupdater = None               # a single file pointer to the updating file
            self.__metaupdater = None               # a single metafile pointer to updating metafile
        dirList = os.listdir(self.__directory)         
        for fname in dirList:
            if fname.endswith(FILE_SUFFIX):         # get every segment file
                fname = self.__directory + fname    # file name with directory prefix
                self.__segfilenames.append(fname)
                if self.__READ:
                    self.__segments.append(open(fname,'r+b'))
                metafile = open(fname.split(FILE_SUFFIX)[0]+META_SUFFIX,'r+b')
                metadata = []; data = metafile.read(PIECE_PER_SEG);
                while (data!=""):
                    metadata.append(data);
                    data = metafile.read(PIECE_PER_SEG);
                metafile.close()
                self.__numofsegs += 1
                self.__segmentMETA.append(metadata) #[['12356','34523' ...](across chunks),[],[],[]] each segment is in one
                                                    # [], and within each [] it has the piece id for each chunk       
    # get the piece IDs by chunk ID
    def getPieceIdbyChunk(self, chunkID):
        self.__lock.acquire();
        pieceIDs = ""
        for eachSeg in range(self.__numofsegs):
            if chunkID < len(self.__segmentMETA[eachSeg]):
                pieceIDs += self.__segmentMETA[eachSeg][chunkID]
        self.__lock.release();
        return pieceIDs                             # get all the indices of pieces in a particular chunk and return in a string
            
    # get the actual file data by chunkID + pieceID               
    def getPiecebyId(self,chunkID,pieceID):         # chunkID is a integer while pieceID is a string
        self.__lock.acquire();
        for eachSeg in range(self.__numofsegs):
            if chunkID < len(self.__segmentMETA[eachSeg]):
                piecePos = self.__segmentMETA[eachSeg][chunkID].find(pieceID)
            else:
                piecePos = -1
            if piecePos >= 0:
                break
        if piecePos < 0:
            self.__lock.release();
            return None
        curbytesfromstart = self.__segments[eachSeg].tell()  # current bytes from beginning
        piecebytesfromstart = chunkID*BYTES_PER_SEG + piecePos*BYTES_PER_PIECE # bytes from begin to need
        if curbytesfromstart != piecebytesfromstart:         # if not as required, needs to seek
            self.__segments[eachSeg].seek(piecebytesfromstart-curbytesfromstart
                                          ,os.SEEK_CUR)      # set the file pointer to desired
        data = self.__segments[eachSeg].read(BYTES_PER_PIECE)# read a piece
        self.__lock.release();
        return data 

    ## only makes sense in write mode ##
    def getNewPieceIDs(self):
        ExistpieceIDs = self.getPieceIdbyChunk(0)
        return sorted(sample(lminus(PIECE_IDS,ExistpieceIDs),PIECE_PER_SEG))
        
    ## only makes sense in write mode ##
    def WriteNewSegment(self,pieceIDs,data):
        self.__lock.acquire();
        self.__numofsegs += 1
        fname = self.__directory + 'seg' + repr(self.__numofsegs) + FILE_SUFFIX
        self.__fileupdater = open(fname,'w+b')
        self.__metaupdater = open(fname.split(FILE_SUFFIX)[0]+META_SUFFIX,'w+b')
        self.__fileupdater.write(data)               # need a process to control sequential writing
        self.__metaupdater.write(pieceIDs)
        self.__fileupdater.close();
        self.__metaupdater.close();
        self.__lock.release();

    ## only makes sense in write mode ##
    def removeSegment(self):
        self.__lock.acquire();
        fpath = self.__directory + 'seg' + repr(self.__numofsegs) + FILE_SUFFIX;
        rsize = os.path.getsize(fpath)
        os.remove(fpath)
        os.remove(self.__directory + 'seg' + repr(self.__numofsegs) + META_SUFFIX)
        self.__numofsegs -= 1
        del self.__segmentMETA[-1]
        self.__lock.release();
        return rsize
    
    # update access after adding or removing content
    def UpdateAccess(self, ADDED = True):
        self.__lock.acquire();
        if ADDED:
            dirList = os.listdir(self.__directory)
            for fname in dirList:
                if fname.endswith(FILE_SUFFIX):         # get every segment file
                    fname = self.__directory + fname
                    if fname not in self.__segfilenames:
                        self.__segfilenames.append(fname)
                        if self.__READ:
                            self.__segments.append(open(fname,'r+b'))
                        metafile = open(fname.split(FILE_SUFFIX)[0]+META_SUFFIX,'r+b')
                        metadata = []; data = metafile.read(PIECE_PER_SEG);
                        while (data!=""):
                            metadata.append(data);
                            data = metafile.read(PIECE_PER_SEG);
                        metafile.close()
                        self.__numofsegs += 1
                        self.__segmentMETA.append(metadata) #[['12356','34523' ...],[],[],[]] each segment is in one
                                                        # [], and within each [] it has the piece id for each chunk
        else:                                           # release file pointers for write mode to delete files
            # must be used in conjunction with removeSegment functions. This is to
            # first stop the reading openings of the file
            del self.__segfilenames[-1]
            self.__segments[-1].close(); del self.__segments[-1]
            self.__numofsegs -= 1; del self.__segmentMETA[-1]
        self.__lock.release();
        return True

    def getNumofSeg(self):
        return self.__numofsegs
    
    def getSegMeta(self):
        return self.__segmentMETA
  
    def closeAll(self):
        if self.__READ:
            self.__lock.acquire();
            for eachSeg in range(self.__numofsegs):
                self.__segments[eachSeg].close()
            self.__lock.release();
 