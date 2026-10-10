from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_interface_uses_brain_api_instead_of_direct_provider_or_github_writes():
    html = (ROOT / "brain-app.html").read_text(encoding="utf-8")
    assert "brainRequest('/chat'" in html
    assert "brainRequest('/missions'" in html
    assert "brainRequest('/company-workflows'" in html
    assert "generativelanguage.googleapis.com" not in html
    assert "api.github.com" not in html
    assert "method: 'PUT'" not in html
    assert "sessionStorage.setItem('brain_control_api_key'" in html


def test_mobile_interface_uses_backend_for_missions_and_approvals_and_disables_github_writes():
    html = (ROOT / "brain-ui-mobile.html").read_text(encoding="utf-8")
    assert "BrainAPI.request('/missions?limit=100'" in html
    assert "BrainAPI.request('/approvals?status_filter=PENDING&limit=100'" in html
    assert "BrainAPI.request('/approvals/' + encodeURIComponent(id)" in html
    assert "Authorization': `token ${this._token}`" not in html
    assert "method: 'PUT'" not in html
    assert "Direct GitHub writes are disabled" in html
    assert "sessionStorage.setItem('brain_control_api_key'" in html
