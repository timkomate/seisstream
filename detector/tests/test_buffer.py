import unittest

import numpy as np

from detector.buffer import RollingTraceBuffer


class TestRollingTraceBuffer(unittest.TestCase):
    def test_get_segment_lenght_and_samplerate(self):
        buf = RollingTraceBuffer(max_seconds=20.0)
        samples = np.arange(21, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)
        self.assertEqual(buf.get_segment_length("XX.STA..HHZ"), 21)
        self.assertEqual(buf.get_samplerate("XX.STA..HHZ"), 1.0)

    def test_add_segment_initial(self):
        buf = RollingTraceBuffer(max_seconds=20.0)
        samples = np.arange(21, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)
        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 0.0)
        self.assertEqual(segment["end"], 20.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(segment["samples"], samples)

    def test_add_segment_computes_end_from_sample_count(self):
        buf = RollingTraceBuffer(max_seconds=20.0)
        samples = np.arange(4, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=10.0, samprate=2.0, samples=samples)

        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["end"], 11.5)

    def test_add_segment_multiple_times(self):
        buf = RollingTraceBuffer(max_seconds=50.0)
        samples = np.arange(21, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)
        buf.add_segment("XX.STA..HHZ", start=21.0, samprate=1.0, samples=samples)
        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 0.0)
        self.assertEqual(segment["end"], 41.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(
            segment["samples"], np.concatenate((samples, samples), axis=None)
        )

    def test_add_segment_for_multiple_sid(self):
        buf = RollingTraceBuffer(max_seconds=20.0)
        samples = np.arange(21, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)
        buf.add_segment("XX.STA2..HHZ", start=10.0, samprate=1.0, samples=samples)
        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 0.0)
        self.assertEqual(segment["end"], 20.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(segment["samples"], samples)
        segment2 = buf.get("XX.STA2..HHZ")
        self.assertEqual(segment2["start"], 10.0)
        self.assertEqual(segment2["end"], 30.0)
        self.assertEqual(segment2["samprate"], 1.0)
        assert segment2 != {}

    def test_add_segment_cutoff(self):
        buf = RollingTraceBuffer(max_seconds=10.0)
        samples = np.arange(11, dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)
        buf.add_segment("XX.STA..HHZ", start=11.0, samprate=1.0, samples=samples)
        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 11.0)
        self.assertEqual(segment["end"], 21.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(segment["samples"], samples)

    def test_trim_to_max_seconds(self):
        buf = RollingTraceBuffer(max_seconds=10.0)
        samples = np.arange(21, dtype=float)  # 0..20 at 1 Hz
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=1.0, samples=samples)

        segment = buf.get("XX.STA..HHZ")
        self.assertEqual(segment["start"], 10.0)
        self.assertEqual(segment["end"], 20.0)
        self.assertEqual(segment["samprate"], 1.0)
        np.testing.assert_array_equal(segment["samples"], samples[10:])

    def test_get_station_buffers_filters_invalid_and_mismatched(self):
        buf = RollingTraceBuffer(max_seconds=10.0)
        samples = np.array([1.0, 2.0], dtype=float)
        buf.add_segment("XX.STA..HHZ", start=0.0, samprate=2.0, samples=samples)
        buf.add_segment("XX.STA..HHN", start=0.0, samprate=2.0, samples=samples)
        buf.add_segment("YY.STA..HHZ", start=0.0, samprate=2.0, samples=samples)
        buf.add_segment("BAD", start=0.0, samprate=2.0, samples=samples)

        matches = buf.get_station_buffers("XX", "STA", "")
        sids = {sid for sid, _seg in matches}
        self.assertEqual(sids, {"XX.STA..HHZ", "XX.STA..HHN"})


if __name__ == "__main__":
    unittest.main()
