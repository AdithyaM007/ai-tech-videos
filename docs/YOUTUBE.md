# Uploading to YouTube

The pipeline can upload each finished episode to your channel, with a title,
description (including chapter timestamps), tags and a custom thumbnail. It also
adds the episode to a playlist named after the series (created on first upload).
Uploads are **private by default** so you can check every video before it goes live.

## One-time setup (about 10 minutes)

If you already have a working `youtube_credentials.json` from your earlier setup,
skip to step 6.

1. Open <https://console.cloud.google.com/> and create a project (or pick your existing one).
2. **APIs & Services → Library** → search for **YouTube Data API v3** → **Enable**.
3. **APIs & Services → OAuth consent screen**: choose **External**, fill in the app
   name and your email, and under **Test users** add the Google account that owns
   your channel.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**, with
   application type **Desktop app**.
5. Download the JSON file and save it in the project folder as
   `youtube_credentials.json` (it is already in `.gitignore`, so never commit it).
6. Sign in once. The first upload opens your browser: choose the account that
   owns the channel and allow access. The login is saved to `youtube_token.json`
   (also git-ignored), so later uploads don't ask again.

> **Important: unverified projects can only upload private videos.** YouTube locks
> videos uploaded through an API project that hasn't passed Google's API audit as
> private, and you can't make them public from YouTube Studio. To publish
> automatically, apply for the audit with the *YouTube API Services Audit and Quota
> Extension* form in the Google Cloud console. Until it is approved, keep
> `--privacy private` (the default).

> While the consent screen is in **Testing** mode, Google expires the saved login
> after 7 days and the browser sign-in runs again. Publishing the consent screen
> (no verification needed for personal use) stops that.

## Usage

```powershell
# Generate episode 1 and upload it (private)
python src\generate_episode.py --episode 1 --upload

# Upload an episode you already generated (no API credits spent)
python src\generate_episode.py --episode 1 --upload-only

# Unlisted: anyone with the link can watch it
python src\generate_episode.py --episode 1 --upload-only --privacy unlisted

# Schedule: uploads as private and YouTube publishes it at this time
python src\generate_episode.py --episode 2 --upload --publish-at 2026-10-01T18:30:00+05:30

# Whole series; episodes that are already uploaded are skipped
python src\generate_episode.py --all --upload

# See which episodes are on YouTube
python src\generate_episode.py --list
```

Each upload writes a record to `output/uploads/python_basics_epNN.json` with the video
URL. That record stops the same episode from being uploaded twice. Use `--reupload`
to upload it again anyway.

## What gets uploaded

| Field | Value |
|---|---|
| Title | `Python Basics #1: What is Python? \| Python for Beginners` |
| Description | Hook, series description, "In this episode you'll learn", chapter timestamps, next episode, subscribe link |
| Tags | `YOUTUBE_TAGS` in `config.py`, plus the series and episode title |
| Category | Education (`YOUTUBE_CATEGORY_ID=27`) |
| Made for kids | No |
| Altered or synthetic content | Yes, because the narration is an AI voice (`YOUTUBE_CONTAINS_SYNTHETIC_MEDIA`) |
| Thumbnail | The episode's title slide. Custom thumbnails need a [phone-verified channel](https://www.youtube.com/verify); if yours isn't verified, the upload still succeeds with an automatic thumbnail |
| Playlist | "Python Basics", created if missing (`YOUTUBE_PLAYLIST_PRIVACY`) |

## Quota

The YouTube Data API gives each project a daily quota of 10,000 units by default,
and an upload costs about 1,600 units. That means roughly **6 uploads per day**.
If `--all --upload` stops because of quota, run the same command again the next
day: episodes that are already uploaded are skipped.

## Troubleshooting

| Message | Fix |
|---|---|
| `YouTube OAuth client file not found` | Complete steps 1–5, or set `YOUTUBE_CREDENTIALS_FILE` |
| `access_denied` / "app has not completed verification" in the browser | Add your channel's Google account as a **Test user** (step 3) |
| `YouTube rejected the upload: ... quotaExceeded` | Daily quota used up; try again tomorrow |
| `... uploadLimitExceeded` | YouTube's per-channel daily upload limit; try again later |
| `invalid_grant` | Delete `youtube_token.json` and sign in again |
| Video stuck as private / "locked" | Unaudited API project; see the note above |
| "Could not set thumbnail" warning | Verify your channel at <https://www.youtube.com/verify> |
