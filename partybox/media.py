import random
import collections
import abc

class MediaType(object):
    LOCAL = 1
    STREAM = 2
    RADIO = 3

class AbstractMedia(object):
    """
    Abstract base class for Media objects.
    """

    __metaclass__ = abc.ABCMeta


    @abc.abstractproperty
    def length(self):
        """
        Duration of media in seconds.
        """
        pass

    @abc.abstractproperty
    def artist(self):
        """
        Artist/Producer of media.
        """
        pass

    @abc.abstractproperty
    def title(self):
        """
        Title or name of media.
        """
        pass

    @abc.abstractproperty
    def album(self):
        """
        Album the media belongs to.
        """
        pass

    @abc.abstractproperty
    def artwork(self):
        """
        URI to track artwork.
        """
        pass

    @abc.abstractmethod
    def get_uri(self):
        """
        Returns the URI for the media, this can be a one time URI.
        """
        pass


class TestMedia(AbstractMedia):
    """
    Simple subclass of AbstractMedia for testing purposes
    """

    def __init__(self, uri):
        self._uri = uri

    @property
    def length(self):
        return 0

    @property
    def artist(self):
        return "Test Artist"

    @property
    def title(self):
        return "Test Title"

    @property
    def album(self):
        return "Test Album"

    @property
    def artwork(self):
        return "https://discussions.apple.com/servlet/JiveServlet/showImage/2-20511310-185873/black.png"

    def get_uri(self):
        return self._uri


    def __str__(self):
        return self._uri


class BaseList(collections.MutableSequence):
    """
    Base wrapper class for list, subclass to create
    sequence like objects.
    """
    def __init__(self):
        self._container = list()

    def __getitem__(self, item):
        return self._container.__getitem__(item)

    def __setitem__(self, key, value):
        return self._container.__setitem__(key, value)

    def __delitem__(self, key):
        return self._container.__delitem__(key)

    def __len__(self):
        return self._container.__len__()

    def __str__(self):
        return self._container.__str__()

    def insert(self, index, value):
        return self._container.insert(index, value)


class PlayList(BaseList):
    """
    An ordered collection of persisted Media objects.
    """

    def shuffle(self):
        """
        Shuffle the order of the playlist
        """
        random.shuffle(self._container)

    @property
    def duration(self):
        """
        The sum of media duration.
        """
        #TODO: This should possibly be a method.
        i = 0
        for media in self._container:
            i += media.length
        return i

    @property
    def play_count(self):
        """
        How many times the playlist has been played
        """
        raise NotImplementedError()

    @property
    def date_created(self):
        """
        Date of creation.
        """
        raise NotImplementedError()

    @property
    def date_edited(self):
        """
        Date of last edit.
        """
        raise NotImplementedError()


class Queue(BaseList):
    """
    A queue of Media objects, used to manage 'Now Playing'
    items.
    """

    @property
    def up_next(self):
        """
        The next item in the queue.
        """
        return self._container[0]

    def get(self):
        """
        Remove and return the next item from the queue.
        """
        return self._container.pop(0)

    def clear(self):
        """
        Clear/empty the queue
        """
        self._container = list()

    def shuffle(self):
        """
        Shuffles the order of the queue
        """
        random.shuffle(self._container)

    def load_playlist(self, playlist):
        """
        Clear the queue and load the contents of a playlist.
        """
        self.clear()
        self.extend(playlist)


class CollaborativeQueue(Queue):
    """
    Queue to collaboratively control the server.
    """

    def __init__(self):
        raise NotImplementedError()

