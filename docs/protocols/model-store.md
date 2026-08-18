# Local Model Store

The Model Store is offline-first and content-addressed. Every object is stored
under `objects/sha256/<digest>` and every logical model reference is an atomic
manifest under `refs/<model-id>.json`. The filename, logical ID and revision
never determine content identity.

Ingestion hashes before publishing, copies through a resumable `.part` file,
fsyncs, and atomically renames the completed object. Existing objects are
verified before reuse. Updates retain the previous digest in history and
rollback only selects an already verified local object. A corrupt or missing
object blocks resolution; the store never silently fetches from the network.

The store records revision, source filename, format and license metadata. It
does not overwrite files outside its root, and model IDs reject path traversal.
