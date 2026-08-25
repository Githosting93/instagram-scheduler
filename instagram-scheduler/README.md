# Instagram Reel Auto-Poster (Free, GitHub Actions)

Publishes one video from `videos/queue/` to `sunoyaadein` as an Instagram Reel
every day, automatically, at zero cost — using GitHub Actions as the
scheduler and GitHub as the video host.

**Repo:** `https://github.com/Githosting93/instagram-scheduler` (already
created, public, empty — push this folder's contents there. See
`PUSH_INSTRUCTIONS.txt` for the exact git commands.)

---

## How it works

1. You drop an `.mp4` video into `videos/queue/`, plus a matching caption
   file in `captions/` (same filename, `.txt` extension).
2. Every day, a GitHub Actions workflow runs `scripts/publish_video.py`,
   which:
   - Picks the oldest video in the queue
   - Builds a public raw GitHub URL for it
   - Asks Instagram's Graph API to create a Reel container from that URL
   - Waits for Instagram to finish processing it
   - Publishes it
   - Moves the video + caption into `videos/posted/` and commits that change
     so it won't be posted twice
3. A second weekly workflow refreshes your access token automatically, so
   you never hit the 60-day expiry.

**Video requirements (Instagram's rules, not this script's):** MP4 or MOV,
H.264 video / AAC audio, 9:16 vertical recommended, under ~1GB. This covers
essentially all vertical Reels-style video content you'd upload manually —
any standard export from CapCut, Premiere, phone camera, etc. will work.

---

## One-time setup

### 1. Push this folder to Githosting93/instagram-scheduler

It's already public and empty. From inside this unzipped folder, run the
commands in `PUSH_INSTRUCTIONS.txt` (or copy them below):

```bash
git init
git branch -M main
git remote add origin https://github.com/Githosting93/instagram-scheduler.git
git add .
git commit -m "Initial commit: Instagram Reel auto-poster pipeline"
git push -u origin main
```

If you're prompted for credentials, GitHub no longer accepts your account
password over git — use a [Personal Access Token](https://github.com/settings/tokens)
as the password instead (username stays your GitHub username).

### 2. Create a Meta Developer App

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → choose the **Business** use case.
2. Note down your **App ID** and **App Secret** (Settings → Basic).
3. In the app dashboard, add the **Instagram** product.
4. Under Instagram → **API setup with Instagram login**, connect your
   `sunoyaadein` Instagram account. It must be a **Business or Creator**
   account (personal accounts don't work with this API) and should already
   be linked to a Facebook Page.

### 3. Generate a long-lived access token

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Select your app from the dropdown → **Get Token → Get User Access Token**.
3. Check these permissions: `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`, `pages_read_engagement`, `business_management`.
4. Generate and authorize — you'll get a **short-lived token** (~1 hour).
5. Exchange it for a **long-lived token** (60 days) by hitting:
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={APP_ID}
     &client_secret={APP_SECRET}
     &fb_exchange_token={SHORT_LIVED_TOKEN}
   ```
   (You can run this via the Graph API Explorer's URL bar, curl, or Postman.)

### 4. Get your Instagram Business Account ID

In Graph API Explorer, run:
```
GET /me/accounts?fields=id,name,instagram_business_account
```
Find your connected Page in the response — `instagram_business_account.id`
is the number you need.

### 5. Add repo secrets

In your GitHub repo → **Settings → Secrets and variables → Actions**, add:

| Secret name | Value |
|---|---|
| `IG_ACCESS_TOKEN` | The long-lived token from step 3 |
| `IG_BUSINESS_ID` | The Instagram Business Account ID from step 4 |
| `IG_APP_ID` | Your Meta App ID |
| `IG_APP_SECRET` | Your Meta App Secret |
| `GH_ADMIN_TOKEN` | A [GitHub Personal Access Token](https://github.com/settings/tokens) (classic, `repo` scope) — used only so the weekly refresh job can update `IG_ACCESS_TOKEN` automatically |

### 6. Push this folder to your public repo

Commit and push everything in this folder as-is. The two workflows in
`.github/workflows/` will pick up automatically once secrets are set.

---

## Daily usage

Just add files — no need to touch code:

```
videos/queue/003_song_teaser.mp4
captions/003_song_teaser.txt
```

Keep the numeric prefix (`001_`, `002_`, ...) so videos post in the order
you intend — the script always picks the oldest filename first.

The workflow runs daily at **13:00 UTC (6:30 PM IST)** — edit the `cron`
line in `.github/workflows/daily-post.yml` to change that.

You can also trigger a post immediately: go to **Actions → Daily Instagram
Reel Post → Run workflow**.

---

## Notes specific to your Bollywood content page

- This pipeline publishes via the official Graph API, which **cannot**
  attach Instagram's licensed trending-audio catalog to a Reel — that's
  only available through the in-app Music picker. If a video needs
  Instagram-licensed music, post it manually through the app instead.
- If your videos already have audio baked into the file (your own
  voiceover, licensed tracks, royalty-free background music), this
  pipeline handles that fine — Instagram just processes whatever audio is
  in the MP4/MOV.
