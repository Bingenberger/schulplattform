"""PostgreSQL custom archives and empty-target restore.

The command prefix comes from trusted deployment code, never HTTP/UI input.
The caller must coordinate database/file writers and isolate the restore target.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
from .storage import exclusive


class Postgres:
    def __init__(self, prefix, database, account):
        if any(not isinstance(v, str) or not re.fullmatch("[a-z][a-z0-9_]{0,62}", v)
               for v in (database, account)):
            raise ValueError("Invalid PostgreSQL identifier")
        self.prefix, self.database, self.account = list(prefix), database, account

    def query(self, sql):
        result = subprocess.run(self.prefix + ["psql", "-X", "--no-password", "-v", "ON_ERROR_STOP=1",
            "-U", self.account, "-d", self.database, "-At", "-c", sql],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            raise ValueError("PostgreSQL query failed")
        return result.stdout.decode().strip()

    def snapshot(self, destination):
        destination = Path(destination)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                result = subprocess.run(self.prefix + ["pg_dump", "--no-password", "-U", self.account,
                    "-Fc", "-d", self.database], stdout=stream, stderr=subprocess.PIPE, timeout=600)
                stream.flush()
                os.fsync(stream.fileno())
            if result.returncode:
                raise ValueError("PostgreSQL snapshot failed")
            with destination.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            return {"engine": "postgres", "database": self.database, "account": self.account,
                    "sha256": digest, "bytes": destination.stat().st_size}
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

    def restore_into_empty(self, source, expected, lock_directory):
        source = Path(source)
        with exclusive(Path(lock_directory) / (self.database + ".restore.lock")):
            with source.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected["sha256"]:
                    raise ValueError("PostgreSQL archive checksum mismatch")
            objects = self.query("""
SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema')
     + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema')
""")
            if objects != "0":
                raise ValueError("Restore target is not empty")
            with source.open("rb") as stream:
                result = subprocess.run(self.prefix + ["pg_restore", "--no-password", "--exit-on-error",
                    "--single-transaction", "-U", self.account, "-d", self.database],
                    stdin=stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
            if result.returncode:
                raise ValueError("PostgreSQL restore failed; transaction rolled back")
            return True
