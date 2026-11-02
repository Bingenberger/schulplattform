"""Strict manifests; acceptance artifacts are content addressed and mandatory."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / 'schemas/app-v1.schema.json'


def validate_manifest(manifest, evidence_directory: Path):
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator(schema).validate(manifest)
    if manifest['image'].split('@')[0].rsplit(':', 1)[1].lower() == 'latest':
        raise ValueError('latest images are forbidden')
    if manifest['id'] in ('schulwissen', 'fahrradausbildung', 'kompetenz-manager'):
        if manifest['resources']['workers'] < 2:
            raise ValueError('Synchronous export apps require at least two workers')
    for digest in manifest['acceptance'].values():
        artifact = evidence_directory / digest
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError('Missing acceptance artifact: ' + digest)
        with artifact.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Acceptance artifact checksum mismatch')
    return manifest


def validate_release(manifests, evidence_directory):
    ids, databases, accounts = set(), set(), set()
    for manifest in manifests:
        validate_manifest(manifest, evidence_directory)
        if manifest['id'] in ids:
            raise ValueError('Duplicate app ID')
        ids.add(manifest['id'])
        if manifest['database']['engine'].startswith('postgres'):
            for value, seen in [(manifest['database']['name'], databases),
                                (manifest['database']['account'], accounts)]:
                if value in seen:
                    raise ValueError('Postgres databases and accounts must be separate')
                seen.add(value)
    if not ids:
        raise ValueError('Release must contain at least one accepted application')
