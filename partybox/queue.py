import random

class BaseQueue(object):

    def __init__(self):

        self._queue = []
        if self.__class__.__name__ is "BaseQueue":
            raise NotImplementedError("BaseQueue must be subclassed")

    def __len__(self):
        raise NotImplementedError()

    @property
    def next(self):
        """
        The next item in the queue
        'Up Next'
        """
        raise NotImplementedError()

    def add(self, media):
        """
        Adds a track to the end of Queue.
        """
        raise NotImplementedError()

    def add_next(self, media):
        """
        Adds a track to be played next.
        """
        raise NotImplementedError()

    def clear(self):
        """
        Empty the queue.
        """
        self._queue = []

    @property
    def shuffle(self):
        raise NotImplementedError()

    @shuffle.setter
    def shuffle(self, value):
        raise NotImplementedError()

    def toggle_shuffle(self):
        """
        Switches shuffle on or off.
        """
        raise NotImplementedError()

    def load_playlist(self, playlist):
        """
        Loads a playist object.
        """
        raise NotImplementedError()

    def remove(self, item):
        """
        Removes track at index or matching track.
        """
        try:
            del self._queue[item]
        except TypeError:
            index = self._queue.index(item)
            del self._queue[index]



class StandardQueue(BaseQueue):

    @property
    def next(self):
        try:
            return self._queue[1]
        except IndexError:
            return None

    def add(self, media):
        self._queue.append(media)

    def add_next(self, media):
        self._queue.insert(1, media)


    def toggle_shuffle(self):
        random.shuffle(self._queue)

    def __len__(self):
        return len(self._queue)








