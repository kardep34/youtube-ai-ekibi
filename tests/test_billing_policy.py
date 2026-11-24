"""No Google traffic: billing verification must fail before generation on ambiguity."""
from unittest.mock import Mock

import pytest

from free_policy import FreeOnlyBlocked, verify_unbilled_key


def checker(info=None, lookup=None, status=200):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.side_effect = [
        Mock(status_code=200, json=lambda: lookup if lookup is not None else {
            'parent': 'projects/123/locations/global',
            'name': 'projects/123/locations/global/keys/key-id',
        }),
        Mock(status_code=status, json=lambda: info if info is not None else {
            'name': 'projects/test-project/billingInfo', 'projectId': 'test-project',
            'billingEnabled': False, 'billingAccountName': '',
        }),
    ]
    return session, Mock(return_value=session)


def test_unbilled_exact_key_can_generate():
    session, factory = checker()
    assert verify_unbilled_key('secret-key', object(), factory) == 'test-project'
    calls = session.get.call_args_list
    assert calls[0].kwargs['params'] == {'keyString': 'secret-key'}
    assert calls[1].args[0].endswith('/projects/123/billingInfo')
    assert all(c.kwargs['allow_redirects'] is False for c in calls)
    session.post.assert_not_called()
    session.put.assert_not_called()


@pytest.mark.parametrize('changes', [
    {'billingEnabled': True}, {'billingAccountName': 'billingAccounts/closed'},
    {'billingEnabled': 'false'}, {'billingEnabled': None},
    {'billingAccountName': None}, {'projectId': ''}, {'name': 'wrong'},
])
def test_paid_inactive_or_malformed_is_blocked(changes):
    info = {'name': 'projects/test-project/billingInfo', 'projectId': 'test-project',
            'billingEnabled': False, 'billingAccountName': ''}
    info.update(changes)
    _, factory = checker(info)
    with pytest.raises(FreeOnlyBlocked):
        verify_unbilled_key('secret-key', object(), factory)


def test_proto_omitted_false_and_empty_fields_are_supported():
    _, factory = checker({'name': 'projects/test-project/billingInfo', 'projectId': 'test-project'})
    assert verify_unbilled_key('secret-key', object(), factory) == 'test-project'


@pytest.mark.parametrize('lookup', [{}, {'parent': 'projects/123/locations/global'}, {
    'parent': 'projects/123/locations/global', 'name': 'projects/999/locations/global/keys/abc',
}, {'parent': 'https://evil.test', 'name': 'key'}])
def test_bad_key_identity_stops_before_billing(lookup):
    session, factory = checker(lookup=lookup)
    with pytest.raises(FreeOnlyBlocked):
        verify_unbilled_key('secret-key', object(), factory)
    assert session.get.call_count == 1


@pytest.mark.parametrize('status', [302, 401, 403, 429, 500])
def test_status_errors_are_closed(status):
    _, factory = checker(status=status)
    with pytest.raises(FreeOnlyBlocked):
        verify_unbilled_key('secret-key', object(), factory)


def test_missing_auth_does_not_make_any_request():
    factory = Mock()
    with pytest.raises(FreeOnlyBlocked):
        verify_unbilled_key('secret-key', None, factory)
    factory.assert_not_called()


def test_transport_errors_do_not_leak_key_or_provider_error():
    session, factory = checker()
    session.get.side_effect = RuntimeError('https://google.test?keyString=secret-key')
    with pytest.raises(FreeOnlyBlocked) as error:
        verify_unbilled_key('secret-key', object(), factory)
    assert 'secret-key' not in str(error.value)
    assert error.value.__cause__ is None


def test_fallback_stops_when_billing_verification_is_revoked():
    from unittest.mock import patch
    from task_inbox import create_narration
    client = Mock()
    client.interactions.create.side_effect = RuntimeError('first model unavailable')
    with patch('task_inbox.require_free_generation', side_effect=[None, None, FreeOnlyBlocked('closed')]):
        with pytest.raises(FreeOnlyBlocked):
            create_narration(client, 'Anlatım')
    assert client.interactions.create.call_count == 1
    client.models.generate_content.assert_not_called()


def test_oauth_purpose_is_signed_and_legacy_youtube_state_still_valid():
    import ast
    import base64
    import hashlib
    import hmac
    import secrets
    import time
    from pathlib import Path
    from types import SimpleNamespace
    tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {
        'oauth_signature', 'new_oauth_state', 'valid_oauth_state', 'oauth_purpose'}]
    context = dict(base64=base64, hashlib=hashlib, hmac=hmac, secrets=secrets, time=time,
                   st=SimpleNamespace(secrets={'YOUTUBE_CLIENT_SECRET': 'client', 'PANEL_PASSWORD': 'panel'}))
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<oauth>', 'exec'), context)
    for purpose in ('youtube', 'billing'):
        state = context['new_oauth_state'](purpose)
        assert context['oauth_purpose'](state) == purpose
        assert context['oauth_purpose'](state + 'tampered') is None
    encoded = base64.urlsafe_b64encode(f'{int(time.time())}.oldnonce'.encode()).decode().rstrip('=')
    assert context['oauth_purpose'](encoded + '.' + context['oauth_signature'](encoded)) == 'youtube'


def test_panel_audio_can_be_used_without_reupload():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py'), default_timeout=15)
    at.secrets['PANEL_PASSWORD'] = 'test'
    at.session_state['giris'] = True
    at.session_state['vortex_task_audio'] = (b'RIFFtest', 2.0)
    at.session_state['vortex_task_audio_voice'] = 'Algenib'
    at.run()
    assert not at.exception
    next(c for c in at.checkbox if c.label == 'Panelde üretilen son ses kaydını kullan').check().run()
    assert not at.exception
    assert any('Algenib' in c.value and 'İndirip yeniden yüklemeniz gerekmez' in c.value for c in at.caption)
