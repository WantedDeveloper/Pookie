_clone_clients = {}

def set_client(bot_id: int, client):
    _clone_clients[int(bot_id)] = client

def get_client(bot_id: int):
    return _clone_clients.get(int(bot_id))
