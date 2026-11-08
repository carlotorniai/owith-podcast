# owith-podcast

Daily OWITH.ai episode, produced in Anthropic's cloud and published to Buzzsprout by GitHub Actions. No server, no Mac, no AWS.

```
21:40 Zurich  Claude scheduled task (cloud, no secrets)
              reads public news → writes script → renders voice (Kokoro, offline) → MP3
              pushes text to branch `episodes`, audio to branch `audio-inbox`
05:20 Zurich  GitHub Actions on main (holds the Buzzsprout secret)
              validates staged files → uploads to Buzzsprout for 07:00 → archives as Release ep-YYYY-MM-DD
07:00 Zurich  Buzzsprout releases the episode to Apple, Spotify, YouTube and the rest
```

## Layout
| Path | Purpose |
|---|---|
| `.github/workflows/publish.yml` | Morning publisher (schedule or manual run only) |
| `publisher/publish.py` | Validation and Buzzsprout upload |
| `render/tts_render.py` | Offline text to speech used by the cloud job |
| `prompts/daily_task_prompt.md` | The scheduled task's instructions |
| branch `episodes` | Every script, sources list and metadata, one folder per day |
| branch `audio-inbox` | Only the next episode's files, force pushed daily |
| Releases `ep-YYYY-MM-DD` | Permanent archive: MP3, WAV, script, sources |

## One time setup (Carlo)
1. Create this repo on github.com, empty. Rulesets and environment branch limits are only enforced on public repos or paid plans.
2. Settings → Environments → New environment `buzzsprout` → Deployment branches: **Selected branches** → add `main`.
3. In that environment add secret `BUZZSPROUT_TOKEN` (the newly regenerated token). Add repository variable `BUZZSPROUT_PODCAST_ID` with the podcast's Buzzsprout ID.
4. Settings → Rules → Rulesets → New branch ruleset on `main`: restrict updates, require a pull request, bypass list = you only.
5. Settings → Actions → General → Workflow permissions: read and write (needed for Releases).
6. In Buzzsprout, Directories: submit the RSS feed in YouTube Studio if not already linked.
7. Run the workflow once by hand with `check_only` on (the default for manual runs): it validates the staged episode and tests the token with a read only call, uploading nothing. `dry_run` uploads a private episode; leave it off unless you want that.

## Security model
* The cloud job holds no credentials. It reads public pages, writes the script, renders audio offline and pushes to `episodes` and `audio-inbox`.
* The Buzzsprout token is an environment secret on `buzzsprout`, limited to `main`. The workflow runs only on schedule or manual dispatch, so its code always comes from `main`.
* Staged files are treated as data: schema, sizes, MP3 header, duration and hashes are validated before upload. Nothing from `audio-inbox` is executed.
* The voice model download is pinned by SHA256.
