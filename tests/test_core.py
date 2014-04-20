import unittest
from partybox import queue
import warnings

class StandardQueueTest(unittest.TestCase):

    def setUp(self):
        self.queue = queue.StandardQueue()

    def test_core(self):
        self.queue.add("track1.mp3")
        self.assertIn("track1.mp3", self.queue._queue)
        warnings.warn("StandardQueue does not implement container methods")

        self.queue.remove("track1.mp3")
        self.assertNotIn("track1.mp3", self.queue._queue)
        self.assertEqual(0, len(self.queue))

        for i in range(0, 10):
            self.queue.add("track{}.mp3".format(i))

        self.assertEqual(10, len(self.queue))
        self.assertEqual(self.queue.next, "track1.mp3")

        self.queue.add_next("oddball.mp3")
        self.assertEqual(self.queue.next, "oddball.mp3")

    def test_shuffle(self):
        for i in range(0, 10):
            self.queue.add("track{}.mp3".format(i))
        unshuffled = list(self.queue._queue) #Make a copy
        self.queue.toggle_shuffle()
        self.assertNotEqual(unshuffled, self.queue._queue)

