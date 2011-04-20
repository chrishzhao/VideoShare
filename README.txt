# The flex project to implement the GUI is in the '.' + os.sep + 'flex' folder.

# The main python codes to run the core of the algorithms is in the '.' + os.sep + 'python' folder. To modify the core algorithms, please refer to files under that folder.

# To run the python system:

## (1) to run the tracker, please create a folder, e.g. called 'server' (doesn't have to be 'server', can be other names), under the root of the project folder (paralell to 'python' and/or 'flex'). An examplar tracker.py file is provided. To run the tracker, go to the 'server' folder and run:

python tracker.py

The tracker will keep track of who is online, and is responsible of informing the users/helpers of their potential neighbors and records the movie list. The tracker will contact the peers periodically to update the parameters.

Follow the instructions on the command window screen, to print out registered users and servers/helpers and available movies to watch.

## (2) to run the server, please create a folder called 'server' (doesn't have to be 'server', can be other names) under the root of the project folder (paralell to 'python' and/or 'flex'). An examplar server.py file is provided. To run the server, go to the 'server' folder and run:

python server.py

One can specify a hyperthetical upload bandwdith in units of Mbits/s for the server. The server will keep all the videos and stream to the user only when needed.

To add a new video to the server, go to the server/cache folder, open the movielist.txt and add each movie title in the text as a separate line, and copy the corresponding video into the same folder.

On bootup, the server will check if any movies specified in the movielist.txt have been encoded, and will do so if it has not. Follow the instructions on the command window screen, to print out neighbors and active connections. 

## (3) to run the helper, please create a folder called 'client' (doesn't have to be 'client', can be other names) under the root of the project folder (paralell to 'python' and/or 'flex'). An examplar helper.py file is provided. To run the client, go to the 'client' folder and run:

python helper.py

One can also specify a hyperthetical upload bandwidth. Follow the instructions on the command window screen, to print out neighbors and active connections. 

## (4) to run the user, please create a folder called 'client' (doesn't have to be 'client', can be other names) under the root of the project folder (paralell to 'python' and/or 'flex'). An examplar helper.py file is provided. To run the client, go to the 'client' folder and run:

python client.py

Follow the instructions on the command window screen to select a movie to watch, stop the current movie, and print the neighborhood and connetions.

# Note that a single folder can only run one instance of the same class, as long as there are test files that run those instances. For example, a folder called 'server' can run instances of an actual client, a server, a tracker, but not a helper, because a helper and a server is of the same class. Similarly, a same folder cannot run two clients, or two helpers.

# There are only three classes: tracker, server and client.

# To run the GUI based client:

## Details will follow