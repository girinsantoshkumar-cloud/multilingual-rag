from io import BytesIO
from pathlib import Path
import time

import pytest

from app.ingest import chunk_text
from app.router import query_views, retrieval_decision
from app.utils import compute_cmi, language_profile, safe_filename, transliterate_roman_hindi, transliterate_roman_tamil


def test_cmi_mixed_query_is_nonzero():
    assert compute_cmi('मेरा refund कब आएगा') > 0

def test_roman_hindi_transliteration():
    assert 'मेरा' in transliterate_roman_hindi('mera refund kab aayega')

def test_chunking_overlap_and_size():
    chunks = chunk_text('Sentence one. Sentence two. Sentence three. ' * 50, size=80, overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)

def test_safe_filename_blocks_paths():
    assert '/' not in safe_filename('../../secret.pdf')

def test_mixed_query_has_fanout_views():
    views = query_views('मेरा refund कब आएगा', 'hi', compute_cmi('मेरा refund कब आएगा'))
    assert len(views) >= 3

def test_tamil_script_is_detected_as_matrix_language():
    profile = language_profile('என் refund எப்போது வரும்?')
    assert profile['matrix_language'] == 'ta'
    assert compute_cmi('என் refund எப்போது வரும்?') > 0

def test_roman_tamil_gets_native_script_view():
    query = 'enakku refund eppo varum?'
    assert 'எனக்கு' in transliterate_roman_tamil(query)
    views = query_views(query, 'ta', compute_cmi(query))
    assert any(name == 'native-script' and 'எனக்கு' in text for name, text in views)

def test_retrieval_gate_skips_personal_and_casual_turns():
    assert retrieval_decision('My name is John, remember it')['retrieve'] is False
    assert retrieval_decision('What is my name?')['retrieve'] is False
    assert retrieval_decision('hello')['retrieve'] is False

def test_retrieval_gate_handles_documents_and_followups():
    assert retrieval_decision('What is the refund policy?')['retrieve'] is True
    history = [{'role': 'assistant', 'content': 'The policy says five days.', 'citations': [{'filename': 'policy.pdf', 'chunk_id': 1}]}]
    decision = retrieval_decision('What about international customers?', history)
    assert decision['retrieve'] is True
    assert decision['mode'] == 'document-follow-up'

def test_web_health_and_chat(tmp_path, monkeypatch):
    from app.web import app
    app.config['TESTING'] = True
    client = app.test_client()
    assert client.get('/health').status_code == 200
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    # Get upload page first to establish session token.
    page = client.get('/')
    with client.session_transaction() as sess:
        token = sess['csrf_token']
    response = client.post('/api/upload', data={'csrf_token': token, 'files': (BytesIO(b'Refunds take five business days.'), 'doc.txt')}, content_type='multipart/form-data')
    assert response.status_code == 202
    job_id = response.get_json()['job_id']
    for _ in range(50):
        job = client.get(f'/api/upload/status/{job_id}').get_json()
        if job['status'] == 'complete':
            break
        time.sleep(0.02)
    assert job['status'] == 'complete'
    assert job['indexed']
