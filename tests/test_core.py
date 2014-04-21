import unittest
from partybox import media


class QueueTest(unittest.TestCase):

    def setUp(self):
        self.queue = media.Queue()

    def test_core(self):
        self.queue.append("track1.mp3")
        self.assertIn("track1.mp3", self.queue)

        self.queue.remove("track1.mp3")
        self.assertNotIn("track1.mp3", self.queue)
        print(len(self.queue))
        self.assertEqual(0, len(self.queue))

        for i in range(0, 10):
            self.queue.append("track{}.mp3".format(i))

        self.assertEqual(10, len(self.queue))
        self.assertEqual(self.queue.up_next, "track0.mp3")

        self.queue.insert(0, "oddball.mp3")
        self.assertEqual(self.queue.up_next, "oddball.mp3")

    def test_shuffle(self):
        for i in range(0, 10):
            self.queue.append("track{}.mp3".format(i))
        unshuffled = list(self.queue) #Make a copy
        self.queue.shuffle()
        self.assertNotEqual(unshuffled, self.queue)

