from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_interface_uses_brain_api_instead_of_direct_provider_or_github_writes():
    html = (ROOT / "brain-app.html").read_text(encoding="utf-8")
    assert "brainRequest('/chat'" in html
    assert "messages.slice(-16).map" in html
    assert "brainRequest('/missions'" in html
    assert "brainRequest('/company-workflows'" in html
    assert '<input type="text" id="settingsModel" placeholder="https://your-brain-api.example" value="http://localhost:8000">' in html
    assert "gemini-flash-latest" not in html
    assert "normalizeApiBaseUrl(localStorage.getItem('brain_api_base_url'))" in html
    assert "Enter a valid HTTP(S) Brain API base URL." in html
    assert "generativelanguage.googleapis.com" not in html
    assert "api.github.com" not in html
    assert "method: 'PUT'" not in html
    assert "sessionStorage.setItem('brain_control_api_key'" in html
    assert "normalizeApiBaseUrl(localStorage.getItem('brain_api_base_url'))" in html
    assert "Enter a valid HTTP(S) Brain API URL." in html
    test_handler = html[html.index("document.getElementById('testConnection').addEventListener"):]
    assert "document.getElementById('modelInput').value.trim() || State.model" in test_handler
    assert "State.apiKey = key;" in test_handler
    assert "State.model = baseUrl.replace" in test_handler
    assert "finally {" in test_handler


def test_mobile_interface_uses_backend_for_missions_and_approvals_and_disables_github_writes():
    html = (ROOT / "brain-ui-mobile.html").read_text(encoding="utf-8")
    assert "BrainAPI.request('/missions?limit=100'" in html
    assert "BrainAPI.request('/approvals?status_filter=PENDING&limit=100'" in html
    assert "BrainAPI.request('/approvals/' + encodeURIComponent(id)" in html
    assert "Authorization': `token ${this._token}`" not in html
    assert "method: 'PUT'" not in html
    assert "Direct GitHub writes are disabled" in html
    assert "sessionStorage.setItem('brain_control_api_key'" in html
