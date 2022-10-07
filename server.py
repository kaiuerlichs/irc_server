""" A simple IRC server

An IRC server module that is capable of instantiating a simple server and correctly
answer the most common IRC commands. It can handle multiple clients and channels.
"""


import select
import socket
import utils.logger as logger


class Channel:
    """ Channel stores all the information about each channel.

    Attributes:
        name: The name of the channel
        users: A set of all the users which are in the channel
        topic: The topic given to each channel
    """
    def __init__(self, name):
        self.name = name
        self.users = set()
        self.topic = ""

    def add_user(self, user):
        self.users.add(user)
        
    def remove_user(self, user):
        self.users.remove(user)

    def get_topic(self):
        return self.topic

    def set_topic(self, topic):
        self.topic = topic
        

class ClientConnection:
    """ ClientConnection stores the socket and information of a connected IRC client and handles the message parsing, formatting and transmission

    Attributes:
        socket: The socket of the connection
        server: The server it is connected to
    """
    
    def __init__(self, socket, server):
        self.socket = socket
        self.server = server
        self.channels = {}
        self.nickname = ""
        self.realname = ""
        self.username = ""
        self.host, self.port, _, _ = socket.getpeername()
        self.write_queue = []
        self.encoding = "utf-8"


    # UTILITIES AND SOCKET INTERFACES
    def prefix(self):
        return ":" + self.nickname + "!" + self.username + "@" + self.host

    def command_format(self, prefix, command, message):
        return prefix + " " + command + " " + message + "\r\n"

    def queue_command(self, command)->None:
        self.write_queue.append(command)
        
    def sendall(self):
        """ Sends all transmissions in the write queue """
        
        transfer_string = ""
        while len(self.write_queue)>0:
            transmission = self.write_queue.pop(0)
            transfer_string += transmission
            logger.log_outgoing(self.host, self.port, transmission)
        self.socket.sendall(transfer_string.encode(self.encoding))

    def handle_incoming(self, data):
        """ Deconstruct the received data and call the correct command handler
        
        Args:
            data: The data received from the client
        """

        transmissions = data.decode(self.encoding).split("\r\n")
        for t in transmissions:
            if t == "":
                continue
            logger.log_incoming(self.host, self.port, t)
            prefix = ""
            command = ""
            params = ""
            # Check if command is prefixed or not
            if t[0] == ":":
                deconstructed = t.split(' ', 2)
                prefix = deconstructed[0]
                command = deconstructed[1]
                if len(deconstructed) > 2:
                    params = deconstructed[2]
            else:
                deconstructed=t.split(' ', 1)
                command = deconstructed[0]
                if len(deconstructed) > 1:
                    params = deconstructed[1]

            # Call event handler
            match command:
                case "JOIN":
                    self.on_join(params)
                case "NICK":
                    self.on_nick(params)
                case "USER":
                    self.on_user(params)
                case "WHO":
                    self.on_who(params)
                case "PING":
                    self.on_ping(params)
                case _:
                    self.run421(command)


    # COMMAND RUNNERS
    def run001(self): # RPL_WELCOME
        cmd = self.command_format(self.server.prefix(), "001", self.nickname + " Welcome to the IRC!:" + self.nickname + "!" + self.username + "@" + self.host)
        self.queue_command(cmd)

    def run002(self): #RPL_YOURHOST
        cmd = self.command_format(self.server.prefix(),"002", self.nickname + " Your host is " + self.server.name + " running version " + self.server.version)
        self.queue_command(cmd)

    def run003(self): #RPL_CREATED
        cmd = self.command_format(self.server.prefix(), "003", self.nickname + " This server was created sometime.")
        self.queue_command(cmd)

    def run004(self): #RPL_MYINFO
        cmd = self.command_format(self.server.prefix(), "004", self.nickname + " " + self.server.name + " " + self.server.version + " o o")
        self.queue_command(cmd)

    def run251(self): #RPL_LUSERCLIENT
        cmd = self.command_format(self.server.prefix(), "251", self.nickname + " :There are " + str(len(self.server.clients)) + " users and 0 services on 1 servers")
        self.queue_command(cmd)

    def run422(self): #RPL_NOMOTD
        cmd = self.command_format(self.server.prefix(), "422", self.nickname + " :MOTD file is missing")
        self.queue_command(cmd)

    def run375(self): #RPL_MOTDSTART
        cmd = self.command_format(self.server.prefix(), "375", self.nickname + " :- " + self.server.name + " Message of the day -")
        self.queue_command(cmd)

    def run372(self): #RPL_MOTD
        cmd = self.command_format(self.server.prefix(), "372", self.nickname + " :- " + self.server.motd) 
        self.queue_command(cmd)

    def run376(self): #RPL_ENDOFMOTD
        cmd = self.command_format(self.server.prefix(), "376", self.nickname + " :End of MOTD command") 
        self.queue_command(cmd)

    def run331(self, name): #RPL_NOTOPIC
        cmd = self.command_format(self.server.prefix(), "331", self.nickname + " #" + name + ":No topic is set")
        self.queue_command(cmd)

    def run332(self, name): #RPL_TOPIC
        cmd = self.command_format(self.server.prefix(), "332", self.nickname + " #" + name + " :" + self.channels[name].topic)
        self.queue_command(cmd)
    
    def run353(self, name): #RPL_NAMREPLY
        cmd = self.command_format(self.server.prefix(),"353", self.nickname + " = " + "#" + name + " : " + " ".join(self.channels[name].users))
        self.queue_command(cmd)

    def run366(self, name): #RPL_ENDOFNAMES
        cmd = self.command_format(self.server.prefix(),"366", self.nickname + " #" + name + " :End of NAMES list") 
        self.queue_command(cmd)

    def runJOIN(self, channel): #JOIN
        cmd = self.command_format(self.prefix(), "JOIN", "#" + channel)

        # Send join command to all clients in the channel
        for client in self.channels[channel].users:
            self.server.nicks[client].queue_command(cmd) 

    def run315(self): #RPL_ENDOFWHO
        cmd = self.command_format(self.server.prefix(), "315", self.nickname + " :End of WHO list")
        self.queue_command(cmd)

    def run352(self, nick, channel): #RPL_WHOREPLY
        client = self.server.nicks[nick]
        cmd = self.command_format(self.server.prefix(), "352", self.nickname + " #" + channel + " " + client.username + " " + client.host + " " +  self.server.hostname + " " + client.nickname + " H :0 " + client.realname)
        self.queue_command(cmd)

    def run421(self, command): #RPL_UNKNOWNCOMMAND
        cmd = self.command_format(self.server.prefix(), "421", command + " :Unknown command")
        self.queue_command(cmd)

    def runPONG(self, params):
        cmd = self.command_format(self.server.prefix(), "PONG", params)
        self.queue_command(cmd)


    # COMMAND HANDLERS
    def on_nick(self, params):
        self.nickname = params
        self.server.nicks[self.nickname] = self

    def on_user(self, params):
        tokens = params.split(" ", 3)
        self.username = tokens[0]
        self.realname = tokens[3][1:]

        self.run001()
        self.run002()
        self.run003()
        self.run003()
        self.run251()

        # If there is no motd, run error commands, otherwise display motd
        if self.server.motd != "":
            self.run375()
            self.run372()
            self.run376()
        else:
            self.run422()

    def on_join(self, params):
        channel = params.split(" ")[0][1:]

        # Add client to channel object
        self.server.add_client_to_channel(self.nickname, channel)
        
        # Get channel object and send join message
        self.channels[channel] = self.server.channels[channel]
        self.runJOIN(channel)

        # Run subsequent messages
        if self.channels[channel].topic != "":
            self.run332(channel)
        else:
            self.run331(channel)

        self.run353(channel)
        self.run366(channel)

    def on_who(self, params):
        channel = params[1:]
        for i in self.server.channels[channel].users:
            self.run352(i, channel)
        self.run315()

    def on_ping(self, params):
        self.runPONG(params)


class Server:
    """ Server class handles the socket instantiation and select loop for the IRC server

    Attributes:
        name: The name of the server
        port: The port on which the server should listen
        motd: A short message of the day for the server
    """

    def __init__(self, name, port, motd):
        self.name = name
        self.port = port
        self.motd = motd
        self.channels = {} # name -> channel
        self.clients = {} # socket -> client
        self.nicks = {} # nick -> client
        self.socket = None
        self.hostname = ""
        self.version = "LudServer1.0"

    def init_socket(self):
        """ Initialises the socket for the server """

        try:
            self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            self.socket.setblocking(0)
            self.socket.bind(("::", self.port))
            self.socket.listen(5)
            self.hostname = self.socket.getsockname()[0]
        except:
            print("Oopsee woopsee, something went wrong. The server couldn't be connected to the socket.")
            quit()

    def run(self):
        """ Runs the server's select loop to check for activity """

        while True:
            r_list = [client.socket for client in self.clients.values()]
            r_list.append(self.socket)
            w_list = [client.socket for client in self.clients.values() if len(client.write_queue) > 0]

            readable, writable, _ = select.select(
                r_list, 
                w_list, 
                []
            )

            for sock in readable:
                if sock == self.socket:
                    # Accept new connection and set up ClientConnection object
                    client_sock, _ = sock.accept()
                    new_client = ClientConnection(client_sock, self)
                    self.clients[client_sock] = new_client

                else:
                    # Receive data from existing connection
                    data = sock.recv(1024)

                    if data:
                        # Handle incoming data
                        self.clients[sock].handle_incoming(data)

                    else:
                        # No incoming data -> client dead

                        # TODO: Ensure channels announce user leaving
                        connection = self.clients[sock]

                        for channel in connection.channels.values():
                            self.remove_client_from_channel(connection, channel)
                        
                        if connection.nickname in self.nicks:
                            del self.nicks[connection.nickname]
                        
                        del self.clients[sock]
                        sock.close()

            for sock in writable:
                # Tell writable clients to send all transmissions
                if sock in self.clients:
                    self.clients[sock].sendall()

    def prefix(self):
        """ Generates the server's prefix """

        return ":" + self.name

    def add_client_to_channel(self, client_name, channel_name):
        """ Adds a new client into the channel list 
        
        Args:
            client_name: The client's nickname
            channel_name: The channel's nickname
        """

        if channel_name in self.channels.keys():
            self.channels[channel_name].add_user(client_name)

        else:
            self.channels[channel_name] = Channel(channel_name)
            self.channels[channel_name].add_user(client_name)

    def remove_client_from_channel(self, client, channel):
        """ Removes a client from a channel list
        
        Args:
            client: The client to remove
            channel: The channel to remove the client from
        """

        # TODO: Check if channel is empty and del
        channel.remove_user(client.nickname)


if __name__ == "__main__":
    server = Server("LudServer", 6667, "This is a cool message")
    server.init_socket()
    server.run()