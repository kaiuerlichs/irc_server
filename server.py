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
    def add_user(self):
        pass
        
    # remove user
    def remove_user(self):
        pass

    # get topic
    def get_topic(self):
        pass

    # set topic
    def set_topic(self):
        pass
        

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

    def sendall(self):
        # send all messages
        pass

    # command handlers & runners
    
    # calc_prefix
    def prefix_calc(self):
        pass


class Server:
    def __init__(self, name, port, motd):
        self.name = name
        self.port = port
        self.motd = motd
        self.channels = {} # name -> channel
        self.clients = {} # socket -> client
        self.nicks = {} # nick -> client
        self.socket = None

    def init_socket(self):
        self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.socket.setblocking(0)
        self.socket.bind(("::", self.port))
        self.socket.listen(5)

    def run(self):
        while True:
            r_list = [client.socket for client in self.clients.values()]
            r_list.append(self.socket)
            w_list = [client.socket for client in self.clients.values() if len(client.write_queue) > 0]

            readable, writable, exceptional = select.select(
                r_list, 
                w_list, 
                []
            )

            for sock in readable:
                if sock == self.socket:
                    # New connection
                    print("[LOG] Incoming connection")
                    client_sock, _ = sock.accept()
                    new_client = ClientConnection(client_sock, self)
                    self.clients[client_sock] = new_client

                else:
                    # Data received from active connection
                    print("[LOG] Data received")
                    data = sock.recv(1024)

                    if data:
                        # Connection active
                        pass

                    else:
                        # TODO: Ensure channels announce user leaving
                        connection = self.clients[sock]

                        for channel in connection.channels.values():
                            channel.remove_user(connection)
                        
                        if connection.nickname in self.nicks:
                            del self.nicks[connection.nickname]
                        
                        del self.clients[sock]
                        sock.close()

            for sock in writable:
                if sock in self.clients:
                    self.clients[sock].sendall()


    # add_client
    # add_nick
    # remove client
    # change nick
    # remove client from channel
    # remove channel
    # add client to channel


if __name__ == "__main__":
    server = Server("LudServer", 6667, "This is a cool message")
    server.init_socket()
    server.run()