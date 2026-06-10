from datetime import datetime

def _timestamp():
    return datetime.now().strftime('%d.%m.%Y_%H.%M.%S')
