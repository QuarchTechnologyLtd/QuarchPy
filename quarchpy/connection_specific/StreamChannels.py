
class StreamGroups:
    def __init__(self):
        self.groups = []

    def add_group(self, group_id):
        self.groups.append(group(group_id))

class group:
    def __init__(self, group_id):
        self.group_id = group_id
        self.channels = []

    def add_channel(self, name, isDigital, channel_order_id):
        self.channels.append(channels(name,isDigital,channel_order_id))

class channels:
    def __init__(self, name, isDigital, channel_order_id):
        self.name = name
        self.isDigital = isDigital
        self.channel_order_id = channel_order_id

