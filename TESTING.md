# Verification — free production workspace

Validated locally with Python 3.12, Streamlit 1.67.0, google-genai 3.6.1 and FFmpeg.

```sh
python -m pip install -r requirements.txt pytest
python -m pytest -q
python -m compileall -q app.py task_inbox.py free_policy.py free_media.py free_render.py free_studio.py tests
```

Result: **36 tests passed**. Syntax checks and diff whitespace checks passed.

Coverage includes the existing task queue and WAV conversion, login gate,
cloud generation blocked before creating a client, production speech blocked
before any provider request, project validation, variable-duration common
briefs, source metadata and attribution, duplicate catalog widgets, source
selection, malformed durations/path traversal, timed Turkish SRT, three aspect
ratios with real FFmpeg subtitles and mixed audio, narration duration mismatch,
and full-resolution 1080x1920 rendering from a looped video clip without audio.

Retained legacy Gemini routing tests explicitly replace the policy with mocks
and use mocked provider clients. They do not prove that those models are free,
available, or suitable; production policy remains fail-closed.

Live read-only catalog checks: NASA and Wikimedia Commons each returned 12
results for `moon`. No catalog media was automatically downloaded.

No paid generation was requested, no billing changed, no YouTube credential
was used, no video was published, and the live Streamlit deployment was not
changed during verification. Subjective voice quality, historical/scientific
accuracy, visual motion consistency and production-scale cloud capacity still
require review; passing tests do not certify professional video quality.
