import ssl as ssl
import socket
import weechat

weechat.register("waterpoint", "pj@place.org", "2.0", "GPL3", "connect to waterpoint", "CONNECTION_close", "")

SERVER = ('waterpoint.moo.mud.org', 8302)

class Connection(object):

    def __init__(self, connect_args, ssl=True):
        self.connect_args = connect_args
        self.ssl = ssl
        self.connect()

    def connect(self):
        sock = socket.socket()
        if self.ssl:
            self.s = ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLS)
        else:
            self.s = sock
        self.s.connect(self.connect_args)
        self.s.setblocking(False) # set non-blocking
        self.leftovers = ''

    def send(self, line):
        self.s.sendall(line + "\r\n")

    def _recv_nb(self):
        """Immediately return a list of strings - may be empty"""
        try:
            lines = self.s.recv(8192).split('\r\n')
            if lines:
                self.leftovers += lines[0]
            if len(lines) > 1:
                lines[0] = self.leftovers
                self.leftovers = lines.pop()
                return lines
        except ssl.SSLWantReadError:
            pass
        except socket.error as e:
            if e.errno == 9: # Bad FD: disconnected
                pass
            raise
        return []

    def readlines_nb(self):
        """empty recv() buffer b/c SSLSocket does it poorly"""
        lines, newlines = [], self._recv_nb()
        while newlines:
            lines += newlines
            newlines = self._recv_nb()
        return lines

    def close(self, *ignored):
        self.s.close()
        return weechat.WEECHAT_RC_OK

    close_cb = close

    def output(self, buffer):
        for line in self.readlines_nb():
            weechat.prnt(buffer, line.strip())

    def output_cb(self, data, remaining_calls):
        self.output(data)
        return weechat.WEECHAT_RC_OK

    def buffer_in_cb(self, data, buffer, input_data):
        self.send(input_data)
        weechat.prnt(buffer, "> " + input_data)
        self.output(buffer)
        return weechat.WEECHAT_RC_OK


CONNECTION = Connection(SERVER)

CONNECTION_close_cb = CONNECTION.close_cb

buffer_in_cb = CONNECTION.buffer_in_cb

# create buffer
buffer = weechat.buffer_new("waterpoint", "buffer_in_cb", "", "CONNECTION_close_cb", "")

# set title
weechat.buffer_set(buffer, "waterpoint", "Waterpoint")

output_cb = CONNECTION.output_cb

# call output every 500ms
weechat.hook_timer(500, 0, 0, "output_cb", buffer)

