import ssl
import errno
import socket
import string
import weechat

weechat.register("mud.py", "pj@place.org", "2.1", "GPL3", "connect to muds", "shutdown_cb", "")

WEE_OK = weechat.WEECHAT_RC_OK
WEE_ERROR = weechat.WEECHAT_RC_ERROR


class Connection(object):

    def __init__(self, name):
        self.name = mudname(name)
        self.buffer = weechat.buffer_new(name, "buffer_in_cb", name, "close_cb", name)
        weechat.buffer_set(self.buffer, "title", name)

    @property
    def connect_args(self):
        return (self.mudcfg('host'), self.mudcfg('port'))

    @property
    def ssl(self):
        return self.mudcfg('ssl')

    def mudcfg(self, part):
        part_type = {'host': weechat.config_string,
                     'port': lambda x: int(weechat.config_string(x)),
                     'cmd': weechat.config_string,
                     'ssl': lambda x: weechat.config_string(x) == "on"
                     }
        val = mudcfg_get("muds.%s.%s" % (self.name, part))
        casted = part_type[part](val)
        if DEBUG: weechat.prnt('', "Loaded muds.%s.%s and got %r" % (self.name, part, casted))
        return casted

    def connect(self):
        ca = self.connect_args
        weechat.prnt(self.buffer, "Connecting to %s at %s:%s%s" % (self.name, ca[0], ca[1], ' with ssl' if self.ssl else ''))
        sock = socket.socket()
        if self.ssl:
            self.s = ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLS)
        else:
            self.s = sock
        self.s.connect(self.connect_args)
        self.s.setblocking(False) # set non-blocking
        self.leftovers = ''
        cmd = self.mudcfg('cmd')
        if cmd:
            self.send(cmd)

    def send(self, line):
        try:
            self.s.sendall(line + "\r\n")
        except IOError:
            if not self.is_closed():
                raise

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
            if e.errno == 11: # Resource temporarily unavail
                return []
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
        return WEE_OK

    disconnect = close

    def is_closed(self):
        try:
            return self.s.fileno() == -1
        except socket.error as e:
            if e.errno == errno.EBADF: # Bad FD
                return True
            raise

    def is_connected(self):
        return not self.is_closed()

    def output(self, prefix=''):
        try:
            if prefix.strip():
                weechat.prnt(self.buffer, prefix.strip())
            for line in self.readlines_nb():
                weechat.prnt(self.buffer, line.strip())
        except IOError:
            if not self.is_closed():
                raise

    def first_connect(self):
        # connect before calling output_cb
        self.connect()
        # call output every 500ms
        weechat.hook_timer(500, 0, 0, "output_cb", self.name)

    def reconnect(self, buffer):
        if not self.is_closed():
            weechat.prnt(buffer, "%s is still connected." % self.name)
        else:
            self.connect()
        return WEE_OK



def mudname(name):
    return ''.join([c for c in name if c in string.letters + string.digits ])


def mud_exists(name):
    name = mudname(name)
    return mudcfg_is_set("muds.%s.host" % name)

MUDCFG_PREFIX = "plugins.var.python.mud.py."
mudcfg_is_set = lambda *a: weechat.config_is_set_plugin(*a)
mudcfg_get = lambda name: weechat.config_get(MUDCFG_PREFIX + name)
mudcfg_set = lambda *a: weechat.config_set_plugin(*a)
mudcfg_unset = lambda *a: weechat.config_unset_plugin(*a)

DEBUG = weechat.config_string(mudcfg_get("debug")) == "on"

MUDS = {}


def shutdown_cb(*unknownargs, **unknownkwargs):
    weechat.prnt("", "mud.py shutting down.")
    for m in MUDS.values():
        m.close()
    return WEE_OK


def buffer_in_cb(mudname, buffer, input_data):
    if not mudname in MUDS:
        return WEE_ERROR
    mud = MUDS[mudname]
    mud.send(input_data)
    mud.output("> " + input_data)
    return WEE_OK


def close_cb(mudname, buffer):
    if not mudname in MUDS:
        return WEE_ERROR
    mud = MUDS[mudname]
    mud.s.close()
    weechat.prnt(mud.buffer, "*** Disconnected ***")
    del MUDS[mudname]
    return WEE_OK


def output_cb(mudname, remaining_calls):
    if not mudname in MUDS:
        return WEE_ERROR
    MUDS[mudname].output()
    return WEE_OK


def mud_command_cb(data, buffer, args):
    def prnt(*a, **kw):
        weechat.prnt(buffer, *a, **kw)

    args = args.strip().split()

    if not args:
        prnt("/mud connect <name>")
        prnt("/mud disconnect [name]")
        prnt("/mud add <name> <host> <port> [cmd]")
        prnt("/mud del [name]")

    elif args[0] in ('c', 'connect'):
        # connect to specified mud
        name = mudname(args[1]) if len(args) > 1 else ''
        if not name:
            prnt("/mud connect requires a mud name to connect to")
            return WEE_ERROR
        elif not mud_exists(name):
            prnt("%s is not a mud name I know about. Try /mud add <name> <host> <port> [cmd]" % name)
            return WEE_ERROR
        elif name in MUDS:
            MUDS[name].reconnect()
        else:
           # add to running muds
            MUDS[name] = mud = Connection(name)
            mud.first_connect()
        return WEE_OK

    elif args[0] in ('dc', 'disconnect'):
        # disconnect from specified mud, or current-buffer if unspecified
        if len(args) > 1:
            name = args[1]
        else:
            name = weechat.buffer_get(buffer, "name")
        mud = MUDS.get(name)
        if mud is None:
            prnt("No mud named '%s' was found." % name)
            return WEE_ERROR
        if not mud.is_connected():
            prnt("%s is already disconnected.")
            return WEE_ERROR
        mud.disconnect()

    elif args[0] in ('add',):
        # add <name> <host> <port> [cmd]
        # save the mud spec into the config area
        if len(args) < 4:
            prnt("/mud add command requires at least <name> <host> <port>")
            return WEE_ERROR
        name, host, port = args[1:4]
        ssl = args[4:5] == '-ssl'
        i = 5 if ssl else 4
        cmd = ' '.join(args[i:])

        mudcfg_set("muds.%s.host" % name, host)
        mudcfg_set("muds.%s.port" % name, port)
        mudcfg_set("muds.%s.ssl" % name, "on" if ssl else "off")
        success_msg = "Added %s at %s:%s" % (name, host, port)
        if ssl:
            success_msg += " (ssl)"
        if cmd:
            mudcfg_set("muds.%s.cmd" % name, cmd)
            success_msg += " with login command: '%s'" % cmd
        prnt(success_msg)

    elif args[0] in ('del', 'rm'):
        if len(args) < 2:
            prnt("/mud del command requires a mud name as arg.")
            return WEE_ERROR
        name = args[1]
        if not mud_exists(name):
            prnt("No mud named %s exists." % name)
            return WEE_ERROR
        # del the mud spec into the config area
        mudcfg_unset("muds.%s.host" % name)
        mudcfg_unset("muds.%s.port" % name)
        mudcfg_unset("muds.%s.cmd" % name)
        mudcfg_unset("muds.%s.ssl" % name)
        prnt("Removed mud named %s." % name)

    return WEE_OK

hook = weechat.hook_command("mud", "manage mud connections",
    "[connect name] | [disconnect|dc [name]] | [add name host port [-ssl] [cmd]] | [del|rm name]",
    "connect to a specified mud, disconnect from the specified mud (current buffer if unspecified)",
    "add %(mud_names) %(hosts) %(ports) %(cmds)"
    " || del %(mud_names)"
    " || rm %(mud_names)"
    " || connect %(mud_names)"
    " || disconnect %(filters_names)"
    " || dc %(mud_names)",
    "mud_command_cb", "")


