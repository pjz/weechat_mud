# weechat_mud
A multi-mud script for weechat

#  Installation

  * put `mud.py` in your .weechat/python dir

# commands

  * /mud connect _mud_name_ - connect to a specified mud
  * /mud <disconnect|dc> [_mud_name_] - disconnect from the specified mud (current buffer if unspecified)
  * /mud add _mud_name_ _hostname_ _port_ [_cmd_] - add the specified mud
    * _mud_name_ - name of the mud (and buffer to create)
    * _hostname_ - the mud's hostname
    * _port_ - the muds' port
    * _cmd_ - a command to run after connecting to the mud
  * /mud <del|rm> _mud_name_ - remove the specified mud


