# Brain frontend/backend connection

The checked-in desktop and mobile HTML interfaces now call the Brain API for chat, missions, company workflows, and approvals. They no longer call Gemini directly or write mission JSON files to GitHub's `main` branch.

## Required backend configuration

Set these variables in the backend hosting environment:

- `BRAIN_CONTROL_API_KEY`: a randomly generated secret of at least 24 characters. Never commit it to the repository or put it in frontend source.
- `BRAIN_CORS_ORIGINS`: comma-separated exact origins allowed to call the API from a browser. For a GitHub Pages deployment, use the exact origin that serves the page (for example, `https://OWNER.github.io`). Do not use a wildcard.

The API must be deployed over HTTPS for remote use. The interfaces default to `http://localhost:8000` for local development; on a phone, localhost refers to the phone itself, not a remote server.

## Using the interfaces

1. Deploy Brain's FastAPI app with a persistent database/workspace and the environment variables above.
2. Open `brain-app.html` or `brain-ui-mobile.html`.
3. Enter the backend's base URL and the control key in the interface's session-only key field.
4. Use **Test Connection** (desktop) or **Connect** (mobile). A successful connection requires the authenticated `GET /missions` request to succeed.
5. In the desktop interface, send ordinary questions to chat, prefix mission creation with `/mission `, and prefix specialist workflow requests with `/run `. The mobile interface creates missions through the backend API and can approve/reject pending approvals through the backend API.

## Current deployment status

This repository change does not deploy a public API or create a production secret. A real, persistent HTTPS API URL and its CORS configuration must be verified before the GitHub Pages interfaces can work remotely. Browser automation is outside the scope of this change.
