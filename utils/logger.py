COLOUR_BLUE = "\033[94m"
COLOUR_CYAN = "\033[96m"
COLOUR_RESET = "\033[0m"

def log_incoming(addr, port, message):
    print(COLOUR_BLUE + "[" + addr + ":" + str(port) + "]" + COLOUR_CYAN + " -> " + COLOUR_RESET + message.strip())

def log_outgoing(addr, port, message):
    print(COLOUR_BLUE + "[" + addr + ":" + str(port) + "]" + COLOUR_CYAN + " <- " + COLOUR_RESET + message.strip())

def log_msg(message):
     print(COLOUR_BLUE + "[SERVER LOG] " + COLOUR_RESET + message)