""" A simple IRC server

Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor 
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis 
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
"""

from pydoc_data.topics import topics
import select
import socket
import queue as Queue
from unicodedata import name


class Channel:
    def __init__(self, name):
        self.name = name
        self.users = set()
        self.topic = ""

    # add user
    def add_user(self, user):
        self.users.add(user)
        
    # remove user
    def remove_user(self, user):
        self.users.remove(user)

    # get topic
    def get_topic(self):
        return self.topic

    # set topic
    def set_topic(self, topic):
        self.topic = topic
        

class ClientConnection:
    def __init__(self, socket, server):
        self.socket = socket
        self.server = server
        self.channels = {}
        self.nickname = ""
        self.realname = ""
        self.username = ""
        self.host, self.port, _, _ = socket.getpeername()
        self.write_queue = []

    # command format
    def command_format(self):
        pass
    
    # send command
    def send_command(self):
        pass

    # queue message

    # send all messages

    # command handlers & runners
    def run001(self, nickname, username, host):
        cmd = self.command_format("001", "Welcome to the IRC!:" + nickname + "!" + username + "@" + host)
        self.send_command(cmd)

    def run002(self, server):
        cmd = self.command_format("002", "Your host is " + self.server.name + " running version <version>") #store version somewhere???
        self.send_command(cmd)

    def run003(self):
        cmd = self.command_format("003", "This server was created <date>") #store date created
        self.send_command(cmd)

    def run004(self, server):
        cmd = self.command_format("004", self.server.name + " <version> <user_modes> <chan_modes>") #whatis this info????
        self.send_command(cmd)

    def run251(self, server):
        cmd = self.command_format("251", ":There are " + len(self.server.clients) + " users and <integer> services on <integer> servers") #whats invisible
        self.send_command(cmd)

    def run422(self):
        cmd = self.command_format("422", ":MOTD file is missing")
        self.send_command(cmd)

    def run375(self, server):
        cmd = self.command_format("375", ":- " + self.server.name + " Message of the day -")
        self.send_command(cmd)

    def run372(self):
        cmd = self.command_format("372", ":- <text>") # ADD MSG OF DAY HERE
        self.send_command(cmd)

    def run376(self):
        cmd = self.command_format("376", ":End of MOTD command") 
        self.send_command(cmd)

    def run331(self, channels):
        cmd = self.command_format("331", self.channels[name] + ":No topic is set")
        self.send_command(cmd)

    def run332(self, name):
        cmd = self.command_format(self.channels[name] + " :" + self.channels[name].topic)
        self.send_command(cmd)
    
    def run353(self, client, symbol, channel, prefix, nick):
        cmd = self.command_format("353", "") 
        self.send_command(cmd)

    def run366(self):
        cmd = self.command_format("366", self.channels[name] + " :End of NAMES list") 
        self.send_command(cmd)

    def runJOIN(self, channel, key):
        cmd = self.command_format("JOIN", "") # HELP ME 
        self.send_command(cmd)

    
    
    # calc_prefix
    def prefix_calc(self):
        #whats a prefix meant to look like
        pass


class Server:
    def __init__(self, name, port, motd):
        self.name = name
        self.port = port
        self.motd = motd
        self.channels = {} # name -> channel
        self.clients = {} # socket -> client
        self.nicks = {} # nick -> client

    def init_socket(self):
        # bind and shit
        pass

    def run(self):
        # select loop
        pass

    # add_client
    # add_nick
    # remove client
    # change nick
    # remove client from channel
    # remove channel
    # add client to channel


# Create a TCP/IP socket
server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
server.setblocking(0)

# Bind the socket to the port
server_address = ('::1', 10000)
print("Starting server")
server.bind(server_address)

# Listen for incoming connections
server.listen(5)

# Sockets from which we expect to read
inputs = [ server ]

# Sockets to which we expect to write
outputs = [ ]

# Outgoing message queues (socket:Queue)
message_queues = {}

while inputs:

    print("Waiting on activity")
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

     # Handle inputs
    for s in readable:

        if s is server:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            print("New connection")
            connection.setblocking(0)
            inputs.append(connection)

            # Give the connection a queue for data we want to send
            message_queues[connection] = Queue.Queue()

        else:
            data = s.recv(1024)
            if data:
                # A readable client socket has data
                print("receiving", data, s.getpeername())
                message_queues[s].put(data)
                # Add output channel for response
                if s not in outputs:
                    outputs.append(s)

            else:
                # Interpret empty result as closed connection
                print('closing', client_address, 'after reading no data')
                # Stop listening for input on the connection
                if s in outputs:
                    outputs.remove(s)
                inputs.remove(s)
                s.close()

                # Remove message queue
                del message_queues[s]

     # Handle outputs
    for s in writable:
        try:
            next_msg = message_queues[s].get_nowait()
        except Queue.Empty:
            # No messages waiting so stop checking for writability.
            print('output queue for', s.getpeername(), 'is empty')
            outputs.remove(s)
        else:
            print("sending", next_msg, s.getpeername())
            s.send(next_msg)

    # Handle "exceptional conditions"
    for s in exceptional:
        print('handling exceptional condition for', s.getpeername())
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()

        # Remove message queue
        del message_queues[s]