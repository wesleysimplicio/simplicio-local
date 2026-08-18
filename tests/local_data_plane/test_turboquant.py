import unittest

from local_data_plane.daemon import InferenceDaemon
from local_data_plane.turboquant import TurboQuantExecutor, TurboQuantPacket


def vectors(rows=32, dimension=128):
    return [[((row * 17 + column * 3) % 101 - 50) / 50.0
             for column in range(dimension)] for row in range(rows)]


class TurboQuantTests(unittest.TestCase):
    def test_cpu_executor_round_trip_is_real_and_bounded(self):
        executor = TurboQuantExecutor()
        self.assertTrue(executor.available())
        packet = executor.compress(vectors(), bits=4, seed=7)
        decoded = executor.decompress(packet)
        metrics = executor.measure(vectors(), bits=4, seed=7)
        self.assertEqual(packet.shape, (32, 128))
        self.assertEqual(packet.rotation_mode, "hadamard")
        self.assertTrue(metrics["finite"])
        self.assertGreater(metrics["compression_ratio"], 4.0)
        self.assertLess(metrics["relative_l2_error"], 0.35)
        self.assertEqual(decoded.shape, (32, 128))

    def test_packet_serialization_preserves_decode(self):
        executor = TurboQuantExecutor()
        packet = executor.compress(vectors(4, 7), bits=3, seed=11)
        restored = TurboQuantPacket.from_dict(packet.as_dict())
        first = executor.decompress(packet)
        second = executor.decompress(restored)
        self.assertEqual(restored, packet)
        self.assertEqual(first.tolist(), second.tolist())

    def test_daemon_exposes_compress_and_decompress_methods(self):
        daemon = InferenceDaemon()
        capabilities = daemon.handle({"method": "capabilities"})[0][1]
        self.assertTrue(capabilities["turboquant"]["executor_available"])
        self.assertIn("safe-compressed", capabilities["turboquant"]["profiles"])
        compressed = daemon.handle({"method": "turboquant_compress", "vectors": vectors(2, 8),
                                    "bits": 4, "seed": 3}, 21)[0][1]
        self.assertTrue(compressed["ok"])
        self.assertEqual(compressed["backend"], "turboquant-kv-numpy")
        decompressed = daemon.handle({"method": "turboquant_decompress",
                                      "packet": compressed["packet"]}, 22)[0][1]
        self.assertTrue(decompressed["ok"])
        self.assertEqual(decompressed["shape"], [2, 8])


if __name__ == "__main__":
    unittest.main()
