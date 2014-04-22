import threading

def synchronized(func):
    """
    Decorator to make a function thread safe
    """

    func.__lock__ = threading.Lock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func