import io
import unittest

from local_data_plane.binary import (
    ERROR,
    REQUEST,
    decode_frame,
    decode_value,
    encode_frame,
    encode_value,
    golden_vector,
)


class BinaryCodecTests(unittest.TestCase):
    def test_nested_values_round_trip(self):
        value = {"a": [1, True, None, b"x"], "z": -4.5}
        self.assertEqual(decode_value(encode_value(value)), value)

    def test_golden_vector_is_stable(self):
        vector = golden_vector()
        self.assertEqual(
            vector,
            "534c563202010000000000000000000700000051ed4d18e44d0000000353000000066c696d6974734c0000000349000000000000000149000000000000000249000000000000000353000000066d6574686f64530000000968616e647368616b6553000000026f6b54",
        )

    def test_frame_round_trip(self):
        frame = encode_frame(REQUEST, 12, {"method": "status"})
        self.assertEqual(decode_frame(frame), (REQUEST, 12, {"method": "status"}))

    def test_checksum_failure_is_rejected(self):
        frame = bytearray(encode_frame(REQUEST, 1, {"method": "status"}))
        frame[-1] ^= 1
        with self.assertRaises(ValueError):
            decode_frame(bytes(frame))


if __name__ == "__main__":
    unittest.main()
