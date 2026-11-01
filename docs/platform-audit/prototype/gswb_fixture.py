"""Real app factory; synthetic data only. Run with gunicorn, no external AI calls."""
import os,sqlite3
from pathlib import Path
from grundschul_woerterbuch import create_app
root=Path(os.environ['AUDIT_FIXTURE_DIR']).resolve();root.mkdir(parents=True,exist_ok=True)
app=create_app({'DATABASE':str(root/'words.db'),'IMPORT_DIR':str(root/'imports'),
 'MEDIA_IMAGE_DIR':str(root/'images'),'MEDIA_AUDIO_DIR':str(root/'audio'),
 'HANDWRITING_UPLOAD_DIR':str(root/'uploads'),'HANDWRITING_MODE':'mock',
 'SECRET_KEY':'synthetic-local-fixture-only'})
with sqlite3.connect(root/'words.db') as c:
 c.executemany('INSERT OR IGNORE INTO words(lemma,normalized_lemma,part_of_speech,definition) VALUES(?,?,?,?)',
 [(f'Auditwort{i:04}',f'auditwort{i:04}','Nomen','Synthetischer Testeintrag.') for i in range(1000)])
