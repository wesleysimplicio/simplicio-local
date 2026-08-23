import unittest

from local_data_plane.hardware_topology import HARDWARE_TOPOLOGY_SCHEMA_V1, detect_hardware_topology, topology_from_payload


class HardwareTopologyTests(unittest.TestCase):
    def _payload(self):
        payload = {
            "schema": HARDWARE_TOPOLOGY_SCHEMA_V1, "platform": "linux", "architecture": "x64",
            "logical_cpus": 8, "physical_cpus": 4,
            "caches": [{"level": 1, "kind": "Data", "size_bytes": 32768, "shared_cpu_list": "0"},
                       {"level": 3, "kind": "Unified", "size_bytes": 8388608, "shared_cpu_list": "0-7"}],
            "cache_line_bytes": 64, "isa_features": ["avx2", "sse4_2"], "numa_nodes": 1,
            "system_memory_bytes": 16 * 1024 ** 3, "available_memory_bytes": 12 * 1024 ** 3,
            "core_classes": [], "gpu": {}, "unavailable": {},
        }
        import hashlib, json
        fingerprint_payload = {key: value for key, value in payload.items() if key != "unavailable"}
        encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        payload["fingerprint"] = hashlib.sha256(encoded).hexdigest()
        return payload

    def test_synthetic_topology_is_versioned_and_stable(self):
        first = topology_from_payload(self._payload())
        second = topology_from_payload(self._payload())
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.caches[0].size_bytes, 32768)
        self.assertEqual(first.isa_features, ("avx2", "sse4_2"))

    def test_fingerprint_mismatch_fails_closed(self):
        payload = self._payload()
        payload["fingerprint"] = "0" * 64
        with self.assertRaises(ValueError):
            topology_from_payload(payload)

    def test_missing_probe_sources_are_explicit(self):
        topology = detect_hardware_topology(sys_root="/path/that/does/not/exist", proc_root="/path/that/does/not/exist")
        self.assertEqual(topology.schema, HARDWARE_TOPOLOGY_SCHEMA_V1)
        self.assertIn("caches", topology.unavailable)
        self.assertIn("gpu", topology.unavailable)

    def test_no_cache_claim_is_inferred_from_cpu_name(self):
        topology = detect_hardware_topology(sys_root="/path/that/does/not/exist", proc_root="/path/that/does/not/exist")
        self.assertEqual(topology.caches, ())


if __name__ == "__main__":
    unittest.main()
