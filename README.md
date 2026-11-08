# owith-podcast

Inbox for the daily OWITH.ai episode. Claude produces each episode in Anthropic's cloud and stages it here. A separate private repo, which Claude cannot access, validates and publishes it to Buzzsprout.

```
21:40 Zurich  Claude scheduled task (cloud, no secrets)
              reads public news → writes script → renders voice (Kokoro, offline) → MP3
              pushes text to branch `episodes`, audio to branch `audio-inbox`
05:20 Zurich  private publisher (holds the Buzzsprout token, no Claude access)
              downloads audio-inbox as data → validates → uploads to Buzzsprout for 07:00
07:00 Zurich  Buzzsprout releases the episode to Apple, Spotify, YouTube and the rest
```

## Layout
| Path | Purpose |
|---|---|
| `render/tts_render.py` | Offline text to speech used by the cloud job |
| `prompts/daily_task_prompt.md` | The scheduled task's instructions |
| branch `episodes` | Every script, sources list and metadata, one folder per day |
| branch `audio-inbox` | Only the next episode's files, force pushed daily |

## Security model
* No secrets live in this repo, and no workflow runs here.
* The publishing token sits in a separate private repo that the Claude GitHub app is not installed on, so the cloud job can neither read it nor change the publishing code.
* The publisher treats staged files as untrusted data: schema, sizes, MP3 header, duration and hashes are validated before upload. Nothing from this repo is executed there.
* The voice model download is pinned by SHA256.
