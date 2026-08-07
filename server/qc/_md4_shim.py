"""Makes hashlib.new('md4', ...) work again for pywinrm's NTLM auth.

OpenSSL 3.x's default provider disables MD4 (a legacy/broken hash) —
`hashlib.new('md4', ...)` raises `ValueError: unsupported hash type md4` on
any Linux distro built against it (confirmed on this box: OpenSSL 3.0.13).
pywinrm's NTLM transport (ntlm_auth/compute_hash.py) calls exactly that, with
no fallback, to derive the NTLM hash from the WinRM password — so without
this, every WinRM connection from this server fails before it even reaches
the network (verified live: raised inside winrm.Session.run_ps before any
socket I/O).

Fix: redirect *only* the 'md4' algorithm name to pycryptodome's pure-Python
MD4 (unaffected by OpenSSL's provider config, since it doesn't go through
OpenSSL at all). Every other hashlib.new(...) call is untouched and still
goes through OpenSSL as normal. This only patches this process's hashlib
module — no system-wide OpenSSL config change, no `/etc/ssl/openssl.cnf`
edit, nothing that could affect any other service on this host.

Must be imported before `import winrm` (see dashboard.py) so the patch is in
place before ntlm_auth ever runs.
"""
import hashlib

from Crypto.Hash import MD4 as _MD4

_orig_new = hashlib.new


class _MD4Wrapper:
    """Just enough of hashlib's hash-object interface for ntlm_auth's usage
    (construct-with-data then .digest()), backed by pycryptodome's MD4."""

    def __init__(self, data=b""):
        self._h = _MD4.new(data)

    def update(self, data):
        self._h.update(data)

    def digest(self):
        return self._h.digest()

    def hexdigest(self):
        return self._h.hexdigest()

    def copy(self):
        clone = _MD4Wrapper()
        clone._h = self._h.copy()
        return clone


def _patched_new(name, data=b"", **kwargs):
    if name.lower() == "md4":
        return _MD4Wrapper(data)
    return _orig_new(name, data, **kwargs)


hashlib.new = _patched_new
