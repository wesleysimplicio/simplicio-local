# Distribution and clean install

`LocalInstaller` installs validated packages outside the source checkout into
versioned directories and activates them atomically. Package manifests include
target platform/architecture, protocol range, per-file SHA-256 checksums,
license, NOTICE, SBOM and provenance references. A target mismatch, missing
metadata, protocol skew or checksum failure blocks installation before
activation.

Updates are side-by-side and rollback selects a previous managed version. The
model/config root is supplied separately and is never deleted by uninstall.
The default service plan is a Runtime-owned child process; standalone service
mode is explicit. Clean-install validation must run against the published
artifact, not a build directory.
