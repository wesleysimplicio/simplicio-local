import hashlib
import time
import unittest

from local_data_plane.binary import ERROR, EVENT, RESPONSE
from local_data_plane.daemon import InferenceDaemon
from local_data_plane.runtime_bridge import RUNTIME_BACKEND_SCHEMA


def runtime_request(prompt="hello", **overrides):
    payload = {
        "schema": RUNTIME_BACKEND_SCHEMA,
        "request_id": "runtime-request-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "idem-1",
        "owner": "agent-1",
        "lease_id": "lease-1",
        "fence": 1,
        "prompt": {"locator": "memory://prompt-1", "sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                   "byte_len": len(prompt.encode())},
        "prompt_text": prompt,
        "limits": {"max_output_tokens": 2, "temperature": 0, "top_p": 1, "stop_sequences": []},
        "intents": {"weights_profile": "compatibility", "cache_profile": "compatibility",
                    "storage_profile": "resident", "device_profile": "cpu", "quality_floor": None,
                    "max_memory_bytes": None, "max_swap_bytes": None, "max_context": 128,
                    "workload_class": "interactive", "allow_fallback": False},
        "deadline_unix_ms": int(time.time() * 1000) + 30_000,
        "cancellation_token": "cancel-1",
    }
    payload.update(overrides)
    return payload


class RuntimeBridgeTests(unittest.TestCase):
    def test_runtime_request_wraps_local_receipt_and_event(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        payload = runtime_request(handle_id=handle, backend="fixture")
        events = daemon.handle({"method": "runtime_generate", "request": payload}, 9)
        self.assertEqual([kind for kind, _ in events], [EVENT, RESPONSE])
        response = events[-1][1]
        self.assertTrue(response["ok"])
        self.assertEqual(response["runtime_event"]["schema"], RUNTIME_BACKEND_SCHEMA)
        self.assertEqual(response["runtime_receipt"]["schema"], "simplicio.inference-receipt/v2")
        self.assertEqual(response["runtime_receipt"]["runtime"]["lease_id"], "lease-1")
        self.assertEqual(response["runtime_receipt"]["status"], "completed")
        self.assertEqual(response["local_physical_receipt"]["effect_authority"], "none")
        self.assertEqual(response["runtime_receipt"]["profile_resolution"]["effective"], "compatibility")

    def test_prompt_reference_is_verified_before_execution(self):
        payload = runtime_request(prompt="hello", handle_id="missing", backend="fixture")
        payload["prompt_text"] = "tampered"
        response = InferenceDaemon().handle({"method": "runtime_generate", "request": payload}, 10)[-1][1]
        self.assertEqual(response["error"]["code"], "prompt_integrity_failure")

    def test_expired_or_unfenced_runtime_request_is_rejected(self):
        expired = runtime_request(deadline_unix_ms=1)
        response = InferenceDaemon().handle({"method": "runtime_generate", "request": expired}, 11)[-1][1]
        self.assertEqual(response["error"]["code"], "deadline_expired")
        unfenced = runtime_request(fence=0)
        response = InferenceDaemon().handle({"method": "runtime_generate", "request": unfenced}, 12)[-1][1]
        self.assertEqual(response["error"]["code"], "invalid_request")

    def test_idempotency_replays_without_a_second_generation(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        payload = runtime_request(handle_id=handle, backend="fixture")
        first = daemon.handle({"method": "runtime_generate", "request": payload}, 13)[-1][1]
        second = daemon.handle({"method": "runtime_generate", "request": payload}, 14)[-1][1]
        self.assertFalse(first.get("replayed", False))
        self.assertTrue(second["replayed"])
        self.assertEqual(first["runtime_receipt"]["receipt_hash"], second["runtime_receipt"]["receipt_hash"])

    def test_idempotency_conflict_is_rejected(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        payload = runtime_request(handle_id=handle, backend="fixture")
        daemon.handle({"method": "runtime_generate", "request": payload}, 15)
        conflicting = dict(payload, prompt_text="different")
        response = daemon.handle({"method": "runtime_generate", "request": conflicting}, 16)[-1][1]
        self.assertEqual(response["error"]["code"], "idempotency_conflict")
        conflicting["prompt_text"] = payload["prompt_text"]
        conflicting["request_id"] = "runtime-request-2"
        response = daemon.handle({"method": "runtime_generate", "request": conflicting}, 17)[-1][1]
        self.assertEqual(response["error"]["code"], "idempotency_conflict")

    def test_turboquant_is_explicitly_rejected_or_downgraded(self):
        daemon = InferenceDaemon()
        handle = daemon.handle({"method": "load", "model_id": "tiny"})[0][1]["handle_id"]
        rejected = runtime_request(handle_id=handle, backend="fixture", turboquant_profile="safe-compressed")
        response = daemon.handle({"method": "runtime_generate", "request": rejected}, 18)[-1][1]
        self.assertEqual(response["error"]["code"], "profile_unavailable")
        downgraded = runtime_request(handle_id=handle, backend="fixture", idempotency_key="idem-fallback",
                                     turboquant_profile="safe-compressed")
        downgraded["intents"] = dict(downgraded["intents"], allow_fallback=True)
        response = daemon.handle({"method": "runtime_generate", "request": downgraded}, 19)[-1][1]
        self.assertTrue(response["ok"])
        self.assertTrue(response["runtime_receipt"]["profile_resolution"]["degraded"])


if __name__ == "__main__":
    unittest.main()
