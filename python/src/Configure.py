import socket
import string
import os  
ADDR = ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][0])
MEDIA_SERVER_ADDRESS = (ADDR,21567)
TRACKER_ADDRESS = (ADDR,21568) 
#MEDIA_SERVER_ADDRESS = ('192.168.0.16', 21567) # (serv_ip, serv_port)
#TRACKER_ADDRESS = ('192.168.0.13', 21568)      # (tracker_ip, tracker_port)  
#TRACKER_ADDRESS = ('192.168.122.128', 21568)      # (tracker_ip, tracker_port)
PEER_PORT = 21569                             # peer port 
MAX_SERV_CONNECTION = 1000                    # max No. of server connection
MAX_TRAC_CONNECTION = 2*MAX_SERV_CONNECTION   # max No. of tracker connection
MAX_PEER_CONNECTION = 15                      # max No. of peer connection
SERVER = 1                                    # used to check if IS_SERVER
CLIENT = 0                                    # used to check if IS_SERVER
BUFSIZ = 1024                                 # Instruction buffer size
VERBOSE = 1                                   # print out or not
DEBUG = 1                                     # debug or not
PROCESS_TIME = 1                              # process time for a thread 
NUM_RETURNED_PEERS = 4*MAX_PEER_CONNECTION    # number of returned peers by the tracker
INTERVAL_TRACKER_COMMUNICATION = 10           # time interval between when peers send 'alive' info to tracker
OBTAIN_NEIGHBOR_PERIOD = 30                   # time interval between new neighbor info requests
TRY_INTERVAL = 10                             # try intervals for errors
INTERVAL_RATEALLOC = 10                       # interval for rate allocation
##################FILE INFO###################
SERVER_PATH = 'cache'                         # path under root dir for server to cache video
CLIENT_PATH = 'streaming'                     # path under root dir for client to cache streaming video
FILE_SUFFIX = '.pph'                          # suffix of stored filename
META_SUFFIX = '.pphmeta'                      # meta data for the files
STORAGE_CAP = 1*1024*1E6                      # 1GB of storage cap
ST_ALLOC_TH = 3                               # storage allocation threshold
BUFFER_LENGTH = 10                            # buffer length in seconds
BITS_PER_CHUNK = 20*1E6                       # bits per chunk of file
BYTES_PIECE_HEADER = 0
#BYTES_PIECE_HEADER = 1 + 1 + LDPC_LENGTH/8    # header size per piece: chunk ID + piece ID + LDPC coefficients (in bits/8 bytes)
LDPC_LENGTH = 1000                            # LDPC length
CODING_MUL = 1                                # multiplier to get the total number of unique packets 
PIECE_PER_CHUNK = 20                          # number of pieces per chunk
PIECE_PER_SEG = 5                             # number of pieces per segment
PIECE_IDS = ((string.lowercase+
              string.uppercase)[0:PIECE_PER_CHUNK*CODING_MUL]) 
                                              # piece IDs (in string) 
BUFFER_EMERG_LEFT = BUFFER_LENGTH/5           # time left for emergency download if buffer not filled
BUFFER_TOO_MUCH = BUFFER_LENGTH*1.5           # time to stop download because of too much buffer content
BUFFER_CHECK_INTERVAL = 0.2                   # interval time to check buffer length; usually every segment
SEG_PER_CHUNK = PIECE_PER_CHUNK/PIECE_PER_SEG # number of segments per chunk
BYTES_PER_CHUNK = BITS_PER_CHUNK/8            # bytes per chunk of file
BYTES_PER_SEG = BYTES_PER_CHUNK/SEG_PER_CHUNK # bytes per segment (5 pieces)
BYTES_PER_PIECE = BYTES_PER_SEG/PIECE_PER_SEG # bytes per segment (5 pieces)
######## START : RE CAL BY ADDING HEADER ########  
BYTES_PER_PIECE = int(BYTES_PER_PIECE + BYTES_PIECE_HEADER)
BYTES_PER_SEG = int(BYTES_PER_PIECE*PIECE_PER_SEG)
BYTES_PER_CHUNK = int(BYTES_PER_SEG*SEG_PER_CHUNK)
BITS_PER_CHUNK = int(BYTES_PER_CHUNK * 8)
##################### END #######################
def intersect(a, b):      
    return list(set(a) & set(b))

def union(a, b):      
    return list(set(a) | set(b))

def lminus(a, b):
    return list(set(a) - set(b))

def PacketsDecode(Content, IDs):
    IDsandContent = zip(IDs,Content);
    IDsandContent.sort();
    sortedIDs, sortedContent = zip(*IDsandContent)
    Data = ""
    ID = ""
    for eachContent in sortedContent:
        Data += eachContent
    for eachID in sortedIDs:
        ID += eachID
    return ID,Data
    
def getFolderSize(folder):     
    total_size = os.path.getsize(folder)     
    for item in os.listdir(folder):         
        itempath = os.path.join(folder, item)         
        if os.path.isfile(itempath):             
            total_size += os.path.getsize(itempath)         
        elif os.path.isdir(itempath):             
            total_size += getFolderSize(itempath)     
    return total_size
