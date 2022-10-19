""" A simple IRC server

An IRC server module that is capable of instantiating a simple server and correctly
answer the most common IRC commands. It can handle multiple clients and channels.
"""

import select
import socket
import time
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
        self.alive = time.time()
        self.ping = time.time()
        self.ping_ack = True


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
        self.alive = time.time()
        try:
            transmissions = data.decode(self.encoding).split("\r\n")
        except UnicodeError:
            logger.log_msg("Refusing connection to client with address " + self.host + " on port " + str(self.port) + ": Invalid encoding.")
            self.refuse_connection()
            return
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
                case "PRIVMSG":
                    self.on_privmsg(params)
                case "PONG":
                    self.on_pong()
                case "PART":
                    self.on_part(params)
                case "QUIT":
                    self.on_quit(params)
                case _:
                    self.run421(command)


    def remove_connection(self, message):
        # Announce leaving to users
        self.announce_quit(message)
        
        # Remove from channel lists
        for channel in self.channels.values():
            channel.remove_user(self.nickname)
            if len(channel.users) == 0:
                self.server.remove_channel(channel.name)
        
        # Remove from server nick and clients list
        if self.nickname in self.server.nicks:
            del self.server.nicks[self.nickname]
        if self.socket in self.server.clients:
            del self.server.clients[self.socket]

        # Shutdown and close socket
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


    def refuse_connection(self):
        self.run451()
        self.sendall()

        if self.nickname in self.server.nicks:
            del self.server.nicks[self.nickname]

        if self.socket in self.server.clients:
            del self.server.clients[self.socket]

        # Shutdown and close socket
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
            


    # COMMAND RUNNERS
    def run001(self): # RPL_WELCOME
        cmd = self.command_format(self.server.prefix(), "001", self.nickname + " :Welcome to the IRC!:" + self.nickname + "!" + self.username + "@" + self.host)
        self.queue_command(cmd)

    def run002(self): #RPL_YOURHOST
        cmd = self.command_format(self.server.prefix(),"002", self.nickname + " :Your host is " + self.server.name + " running version " + self.server.version)
        self.queue_command(cmd)

    def run003(self): #RPL_CREATED
        cmd = self.command_format(self.server.prefix(), "003", self.nickname + " :This server was created sometime.")
        self.queue_command(cmd)

    def run004(self): #RPL_MYINFO
        cmd = self.command_format(self.server.prefix(), "004", self.nickname + " " + self.server.name + " " + self.server.version + " o o")
        self.queue_command(cmd)

    def run251(self): #RPL_LUSERCLIENT
        cmd = self.command_format(self.server.prefix(), "251", self.nickname + " :There are " + str(len(self.server.clients)) + " users and 0 services on 1 servers")
        self.queue_command(cmd)
    
    def run315(self): #RPL_ENDOFWHO
        cmd = self.command_format(self.server.prefix(), "315", self.nickname + " :End of WHO list")
        self.queue_command(cmd)

    def run331(self, name): #RPL_NOTOPIC
        cmd = self.command_format(self.server.prefix(), "331", self.nickname + " #" + name + " :No topic is set")
        self.queue_command(cmd)

    def run332(self, name): #RPL_TOPIC
        cmd = self.command_format(self.server.prefix(), "332", self.nickname + " #" + name + " :" + self.channels[name].topic)
        self.queue_command(cmd)

    def run352(self, nick, channel): #RPL_WHOREPLY
        client = self.server.nicks[nick]
        cmd = self.command_format(self.server.prefix(), "352", self.nickname + " #" + channel + " " + client.username + " " + client.host + " " +  self.server.hostname + " " + client.nickname + " H :0 " + client.realname)
        self.queue_command(cmd)
    
    def run353(self, name): #RPL_NAMREPLY
        cmd = self.command_format(self.server.prefix(),"353", self.nickname + " = " + "#" + name + " :" + " ".join(self.channels[name].users))
        self.queue_command(cmd)

    def run366(self, name): #RPL_ENDOFNAMES
        cmd = self.command_format(self.server.prefix(),"366", self.nickname + " #" + name + " :End of NAMES list") 
        self.queue_command(cmd)
        
    def run372(self): #RPL_MOTD
        cmd = self.command_format(self.server.prefix(), "372", self.nickname + " :- " + self.server.motd) 
        self.queue_command(cmd)

    def run375(self): #RPL_MOTDSTART
        cmd = self.command_format(self.server.prefix(), "375", self.nickname + " :- " + self.server.name + " Message of the day -")
        self.queue_command(cmd)

    def run376(self): #RPL_ENDOFMOTD
        cmd = self.command_format(self.server.prefix(), "376", self.nickname + " :End of MOTD command") 
        self.queue_command(cmd)
    
    def run401(self, params): #ERR_NOSUCHNICK
        logger.log_msg("(401) No such nick.")
        cmd = self.command_format(self.server.prefix(), "401", params + " :No such nick/channel")
        self.queue_command(cmd)

    def run403(self, params): #ERR_NOSUCHCHANNEL
        logger.log_msg("(403) Client tried to join non-existent channel.")
        cmd = self.command_format(self.server.prefix(), "403", params + " :No such channel")
        self.queue_command(cmd)

    def run411(self): #ERR_NORECIPIENT
        logger.log_msg("(411) Client sent a message without recipient.")
        cmd = self.command_format(self.server.prefix(), "411", ":No recipient given")
        self.queue_command(cmd)

    def run412(self): #ERR_NOTEXTTOSEND
        logger.log_msg("(412) Client sent a message without text.")
        cmd = self.command_format(self.server.prefix(), "412", ":No text to send")
        self.queue_command(cmd)

    def run421(self, command): #RPL_UNKNOWNCOMMAND
        logger.log_msg("(421) Client sent unknown or unimplemented command.")
        cmd = self.command_format(self.server.prefix(), "421", command + " :Unknown command")
        self.queue_command(cmd)
    
    def run422(self): #RPL_NOMOTD
        cmd = self.command_format(self.server.prefix(), "422", self.nickname + " :MOTD file is missing")
        self.queue_command(cmd)
    
    def run431(self): #ERR_NONICKNAMEGIVEN
        logger.log_msg("(431) Client sent NICK command without nickname.")
        cmd = self.command_format(self.server.prefix(), "431", ":No nickname given")
        self.queue_command(cmd)

    def run432(self): #ERR_ERRONEUSNICKNAME
        logger.log_msg("(432) Client sent NICK command with erroneuous nickname.")
        cmd = self.command_format(self.server.prefix(), "432", self.nickname + ":Erroneus nickname")
        self.queue_command(cmd)

    def run433(self): #ERR_NICKNAMEINUSE
        cmd = self.command_format(self.server.prefix(), "433", self.nickname + ":Nickname is already in use")
        self.queue_command(cmd)
    
    def run442(self, params): #ERR_NOTONCHANNEL
        logger.log_msg("(442) Client tried to perform action on a channel they are not on.")
        cmd = self.command_format(self.server.prefix(), "442", params + " :You're not on that channel")
        self.queue_command(cmd)
    
    def run451(self): #ERR_NOTREGISTERED
        cmd = self.command_format(self.server.prefix(), "451", self.nickname + " :Not registered")
        self.queue_command(cmd)

    def run461(self): #ERR_NEEDMOREPARAMS
        logger.log_msg("(461) Client command is missing parameters.")
        cmd = self.command_format(self.server.prefix(),"461", ":Not enough parameters")
        self.queue_command(cmd)
        
    def run462(self): #ERR ALREADYREGISTERED
        logger.log_msg("(462) Registered client attempted registration.")
        cmd = self.command_format(self.server.prefix(), "462", ":Unauthorized command (already registered)")
        self.queue_command(cmd)

    def runJOIN(self, channel): #JOIN
        cmd = self.command_format(self.prefix(), "JOIN", "#" + channel)
        # Send join command to all clients in the channel
        for client in self.channels[channel].users:
            self.server.nicks[client].queue_command(cmd) 

    def runPING(self):
        self.ping = time.time()
        self.ping_ack = False
        cmd = self.command_format(self.server.prefix(), "PING", "Aliveness check")
        self.queue_command(cmd)

    def runPONG(self, params):
        cmd = self.command_format(self.server.prefix(), "PONG", params)
        self.queue_command(cmd)

    def announce_quit(self, message):
        cmd = self.command_format(self.prefix(), "QUIT", ":" + message)
        for channel in self.channels.values():
            for nick in channel.users:
                if nick != self.nickname and nick in self.server.nicks:
                    self.server.nicks[nick].queue_command(cmd)
                    
    def announce_part(self, channel):
        cmd = self.command_format(self.prefix(), "PART", channel)

        for nick in self.channels[channel[1:]].users:
            self.server.nicks[nick].queue_command(cmd)



    # COMMAND HANDLERS
    def on_nick(self, params):
        params = params.strip()
        invalid = [" ", ",", "!", "?", "@", "*", "."]
        starting = ["$", ":", "#", "&"]

        if params == "":
            self.run431()
            return

        if params.lower() in [x.lower() for x in self.server.nicks]:
            self.run433()
            return

        # check nick format
        if len(params) > 9:
            self.run432()
            return

        for i in starting:
            if params[0] == i:
                self.run432()
                return
            else:
                continue

        for i in invalid:
            if i in params:
                self.run432()
                return
            else:
                continue

        self.nickname = params
        self.server.nicks[self.nickname] = self


    def on_user(self, params):
        tokens = params.split(" ", 3)
        
        if len(tokens) < 3:
            self.run461()
            return
            
        if self.username != "":
            self.run462() 
            return
            
        self.username = tokens[0]
        self.realname = tokens[3][1:]
        self.run001()
        self.run002()
        self.run003()
        self.run004()
        self.run251()

        # If there is no motd, run error commands, otherwise display motd
        if self.server.motd != "":
            self.run375()
            self.run372()
            self.run376()
        else:
            self.run422()


    def on_join(self, params):
        if params == "":
            self.run461()
            return

        if params.split(" ")[0][0]=="#":
            channel = params.split(" ")[0][1:]
        else:
            channel = params.split(" ")[0]

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
        if params == "" or params == " ":
            self.run461()
            return 
        self.runPONG(params)

    def on_pong(self):
        self.ping_ack = True

    def on_privmsg(self, params):
        if (params.strip() == " ")<1:
            self.run461() #NOTENOUGHPARAMS
            return
        try:
            contents = params.split(' ',1)
            message = contents[1][1:]
        except:
            self.run412() #NOTEXTTOSEND
            return

        target = contents[0]
        if target == "":
            self.run411() #NORECIPIENT
            return
        elif target[0]=='#':
            self.sendChannelMsg(target, message)
        elif target in self.server.nicks:
            self.sendUserMsg(target, message)
        else:
            self.run411() #NORECIPIENT
        
    def on_quit(self, params):
        self.remove_connection(params[1:])

    def on_part(self, params):
        if params == "":
            self.run461()
            return

        channels_to_part = params.split(":")[0].strip().split(",")
        
        for channel in channels_to_part:
            if channel[1:] not in self.server.channels:
                self.run403(channel)
                return

            if channel[1:] not in self.channels:
                self.run442(channel)
                continue

            self.announce_part(channel)
            self.channels[channel[1:]].remove_user(self.nickname)
            del self.channels[channel[1:]]
    
    def sendChannelMsg(self, target, msg):
        cmd = self.command_format(self.prefix(), "PRIVMSG", target + " :" + msg)
        
        for nick in self.channels[target[1:]].users:
            if nick == self.nickname:
                continue
            client = self.server.nicks[nick]
            client.queue_command(cmd)   

    def sendUserMsg(self, target, msg):
        if target not in self.server.nicks:
            self.run401(target)
            return
        cmd = self.command_format(self.prefix() , "PRIVMSG ", target + " :" + msg)
        self.server.nicks[target].queue_command(cmd)


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
            logger.log_msg("Oopsie woopsie, something went wrong. The server couldn't be connected to the socket.")
            quit()

    def run(self):
        """ Runs the server's select loop to check for activity """
        
        logger.log_msg("Listening on port " + str(self.port) + ".")
        while True:
            r_list = [client.socket for client in self.clients.values()]
            r_list.append(self.socket)
            w_list = [client.socket for client in self.clients.values() if len(client.write_queue) > 0]

            readable, writable, _ = select.select(
                r_list, 
                w_list, 
                [],
                20
            )

            for sock in readable:
                if sock == self.socket:
                    # Accept new connection and set up ClientConnection object
                    client_sock, _ = sock.accept()
                    new_client = ClientConnection(client_sock, self)
                    self.clients[client_sock] = new_client

                    logger.log_msg("Accepted new connection from " + new_client.host + " at port " + str(new_client.port) + ".")

                else:
                    # Receive data from existing connection
                    data = sock.recv(1024)

                    if data:
                        # Handle incoming data
                        self.clients[sock].handle_incoming(data)

                    else:
                        # No incoming data -> client dead
                        logger.log_msg("Connection to " + self.host + " at port " + str(self.port) + " has been removed.")
                        self.clients[sock].remove_connection("Client connection closed.")

            for sock in writable:
                # Tell writable clients to send all transmissions
                if sock in self.clients:
                    self.clients[sock].sendall()

            now = time.time()

            alive_check = [client for client in self.clients.values() if (now - client.alive) > 90 and client.ping_ack == True]
            dead_connection = [client for client in self.clients.values() if (now - client.ping) > 15 and client.ping_ack == False]

            for client in alive_check:
                client.runPING()

            for client in dead_connection:
                logger.log_msg("Connection to " + client.host + " at port " + str(client.port) + " has been removed due to inactivity.")
                client.remove_connection()

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

    def remove_channel(self, channel):
        del self.channels[channel]
        return


if __name__ == "__main__":
    try:
        server = Server("LudServer", 6667, "This is a cool message")
        server.init_socket()
        server.run()
    except KeyboardInterrupt:
        server.socket.shutdown(socket.SHUT_RDWR)
        server.socket.close()