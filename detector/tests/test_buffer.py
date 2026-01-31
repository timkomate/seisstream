import unittest

import numpy as np

from detector.buffer import RollingTraceBuffer


class TestRollingTraceBuffer(unittest.TestCase):
    def test_add_segment_initial(self):
        buf = RollingTraceBuffer(max_seconds=10.0)
        samples = np.array([1.0, 2.0], dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, end=1.0, samprate=2.0, samples=samples)

        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 0.0)
        self.assertEqual(segment["end"], 1.0)
        self.assertEqual(segment["samprate"], 2.0)
        np.testing.assert_array_equal(segment["samples"], samples)

    def test_trim_to_max_seconds(self):
        buf = RollingTraceBuffer(max_seconds=10.0)
        samples = np.arange(21, dtype=float)  # 0..20 at 1 Hz
        buf.add_segment("XX.STA..HHZ", start=0.0, end=20.0, samprate=1.0, samples=samples)

        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 10.0)
        self.assertEqual(segment["end"], 20.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(segment["samples"], samples[10:])


if __name__ == "__main__":
    unittest.main()
