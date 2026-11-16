# Wet test, stage 1: the StudioPilot website, opened for real

- Date: 2026-11-13
- Live version: Live 12 Suite per stage 0 (exact build not checked; Live not used in this stage)
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`)
- Bridge version: not checked (stage 0 stopped at pip, the doctor did not run)

This replaces the earlier INCOMPLETE version of this file (no browser at the time).

## How it was read

Claude in Chrome, real browser, all pages opened on 2026-11-13. No account, trial, purchase, download, install or
form. No CAPTCHA met. Quotes below are the pages' exact words.

| Page | Result |
|---|---|
| https://www.studiopilotmusic.com/ | read in full |
| https://www.studiopilotmusic.com/app | read in full (first load took over 45 s, second try fine) |
| https://www.studiopilotmusic.com/terms | read in full, "Last updated: 27 July 2026" |
| https://www.studiopilotmusic.com/privacy | read in full, "Last updated: 27 July 2026" (footer link) |
| https://www.studiopilotmusic.com/stemsplitter | read in full; the upload box was not used |
| https://www.studiopilotmusic.com/fl | read in full |
| https://www.studiopilotmusic.com/free-presets | read in full (menu link); the email form was not filled |
| https://www.studiopilotmusic.com/login | **not opened** (menu link "Log in"; a login page) |
| `/pricing`, `/download`, `/changelog` | 404. Not linked from the site; pricing is a section of `/` and `/app` |
| `/refunds`, `/docs`, `/faq`, `/support` | not linked from menu or footer; not opened. Refunds are in `/terms`, FAQ is a section, support is a mailto |
| https://github.com/emilyjoshua333-cyber/studiopilot-releases/releases (pages 1 and 2) | read in full: 0.1.18 down to 0.1.2 |

Menu of `/`: Demo, Features, Integrations, Pricing, FAQ (anchors), One-click app (`/app`), Free presets
(`/free-presets`), Help (mailto), Log in (`/login`). Footer: Free presets, Terms, Privacy, the support email.

## 1. Facts

### What is sold, and for how much

| Product | Price as shown | Exact words | URL |
|---|---|---|---|
| Setup Kit (Ableton) | $33.99 one-time | "Buy The Setup Kit · $33.99", "One-time payment · instant access", "$33.99 founder price" | `/` |
| FL Kit | $33.99 one-time | "Buy The FL Kit · $33.99", "One payment, no subscription." | `/fl` |
| App, Starter | $27.99/mo | "2,000 AI credits · never cuts off mid-track", "~5–10 tracks / month" | `/app` |
| App, Pro ("Most popular") | $54.99/mo | "8,000 AI credits", "~20–40 tracks / month" | `/app` |
| App, Studio | $87.99/mo | "20,000 AI credits", "50+ tracks / month" | `/app` |
| Stem splitter | free | "mp3, wav, m4a or flac · up to 150 MB · free" | `/stemsplitter` |
| Presets | free, for an email address | "Over 100 Operator presets plus 30 Diva presets" | `/free-presets` |

- Currency: `/terms` says "prices are shown at checkout in your local currency." The pages showed USD in this
  browser. Checkout was not opened, so the price charged in Israel: not checked.
- No free trial is mentioned on any page.
- Payment: "Secure checkout with Stripe." (`/app`)

### What each edition includes

- **App, all three plans identical except credits**: "Founders offer, every plan gets every feature." Listed on
  every plan: "Builds & arranges, drums, bass, MIDI, full sections", "Mixes & masters to a reference track", "All 33
  Nexevon plugins, Mac & Windows", "36+ sample packs included, and growing", "Sample packs from any track, 20
  included", "Reads your audio, LUFS, spectrogram, key & BPM", "Drives your 3rd-party plugins (Serum, FabFilter…)",
  "Uses your own sample library", "Sits pinned in front of Ableton", "AI built in, no Claude or Codex needed",
  "Lifetime updates included". (`/app`)
- **Plugins**: "13 instruments, 20 effects", "VST3 and Audio Unit on Mac, VST3 on Windows.", "Your StudioPilot
  email, no password. Use them on as many computers as you like." (`/app`)
- **Sample packs**: "Around 250 sounds a pack", "24-bit WAV, tagged properly, and cleared for you to use in your own
  music.", includes "The actual [Serum] presets used to make each pack". Browsing or downloading "never touches
  your credits." (`/app`)
- **Setup Kit**: "Full feature masterclass, Ableton setup walkthrough, Claude & Codex (ChatGPT) guides, Standalone
  app, Premium template file, Producer command library, Free MIDI packs & presets, Community & full support,
  Troubleshooting vault, Future workflow updates". Needs the buyer's own agent: "the setup version requires Claude
  or Codex (ChatGPT) to work." (`/`)
- **What the kit lacks**: "You bring the agent, and it doesn't include the app's sample pack generator or
  reference-match mastering." (`/app` FAQ)
- **The site contradicts itself on the kit**: `/` lists "Standalone app" and "app access" inside the kit, and its
  MASTER card says "match the loudness of a reference track", while `/app` sells the app only by subscription and
  says the kit has no reference-match mastering. What "Standalone app" in the kit means: not stated.
- **FL Kit**: "60+ FL Studio actions"; "FL's API doesn't allow placing clips on the playlist, so you arrange the
  timeline yourself."; "the API can't load new plugins or samples by itself". The app does not support FL: "FL
  support is on the roadmap." (`/fl`)

### Platforms and Live versions

- "The StudioPilot app runs on macOS (Intel and Apple Silicon) and Windows." (`/app` FAQ)
- Kit: "anywhere Ableton Live and Claude or Codex (ChatGPT) run." (`/` FAQ)
- **Live versions and editions (11/12, Intro/Standard/Suite): not stated on any page.**
- Inside Ableton: "a small bridge", "you may need to enable the control surface inside Ableton once." (`/app` FAQ)

### Limits

- Credits: 2,000 / 8,000 / 20,000 a month. "Credits reset at the start of each billing period and do not roll
  over." (`/terms`). What one credit buys: not stated; only "A full track ... typically uses only a small slice of a
  plan's monthly pot". "You're never cut off mid-track." (`/app` FAQ)
- Own sample packs: "Every plan comes with 20 packs of your own." (`/app`). Per month or in total: not stated.
- Files: free splitter "up to 150 MB", mp3/wav/m4a/flac (`/stemsplitter`). App: "big 24-bit files (up to 200MB) now
  work" (release 0.1.7). Maximum track length in minutes: not stated.
- JAM mode: "Stack up to 32 layers" (release 0.1.11).

### Refunds and cancelling (`/terms`)

- "Because both products give you immediate access to digital files and software, we are not able to offer refunds
  as standard."
- "If something genuinely does not work for you, or you have been charged in error, email us and we will look at it
  properly and sort you out."
- "If you cancel, you keep access until the end of the period you have already paid for." "Changes to your plan are
  pro-rated automatically."

### Terms: benchmarking, reverse engineering, commercial use (`/terms`)

- **Benchmarking: not mentioned. Reverse engineering: not mentioned.** The only restrictions: "You may not resell
  it, share it publicly, or redistribute the files." and "Do not attempt to break, abuse or resell access to the
  service." Also "Use StudioPilot lawfully and for your own music."
- Commercial use of output: "Anything you create using StudioPilot belongs entirely to you. We claim no ownership,
  no royalties and no rights over your music. You are free to release it commercially."
- Other people's tracks: "the rights in that original track still belong to whoever owns it ... that part is your
  responsibility".
- Liability: "our liability is limited to the amount you have paid us."
- No company name, address, country or governing law appears in the terms. Contact: one email address.

### Privacy (`/privacy`)

- "We do not collect, upload or store your audio, samples or projects, and we never use anything you make with
  StudioPilot to train any AI."
- **The stated exception**: "If you use that feature [track to sample pack], the audio file you choose is uploaded
  to the specialist service that performs the stem split".
- "Our AI provider processes the instructions you type in the app".
- Collected: email, purchase records, "the number and size of AI requests", website analytics.
- Ads: "we send a scrambled version of your email address (a hash ...)" to Meta, TikTok, Snapchat and Google when
  you buy. Also Vercel Analytics and Rewardful (affiliates).

### Release notes: bugs the product really had

Latest is **0.1.18**, "released this 3 days ago" as seen on 2026-11-13. Dates of older releases: not checked.
Every release shows the same commit `613b926`; assets: 9 per release (names and sizes not read, except
`latest-mac.yml` seen in 0.1.18).

| Version | Exact words |
|---|---|
| 0.1.18 | "Mix & Master works with your own master Limiter"; "Listening to a section starts at that section"; "Sample packs survive a short internet drop"; "Timeline automation keeps your clips intact"; "Fixed a cause of \"Bridge failed\" at startup"; "Windows: a new way of installing the listener" |
| 0.1.17 | "Fixed: in 0.1.16 Mix & Master could fail to listen to your song or read a reference track."; "Windows: if the listener doesn't install, StudioPilot now shows you how to add it by hand"; "If Ableton is busy for a moment ... StudioPilot now waits for it instead of asking you to set it up again" |
| 0.1.13 | "wakes up cleanly after your Mac sleeps"; "building a whole song from your loops now lands every track first time"; Eco "follows the plan and stops second-guessing itself" |
| 0.1.12 | pack building "takes a minute or two instead of twenty"; "long WAV uploads no longer time out part-way"; "the credits display now shows plainly what you have left" |
| 0.1.11 | "arrangement deletes are strictly scoped (the assistant can only remove exactly what you ask)"; "pack purchasing fixed" |
| 0.1.9 | "jump to the drop and hit play actually plays the drop, not the top of the track"; "your plan appears right after paying instead of showing zero"; "Long sessions cost much less" |
| 0.1.8 | "Safer edits: it asks before removing anything you did not explicitly ask for"; "unusual file names fixed" |
| 0.1.7 | "Sample packs are back: failures fixed"; "kicks keep their tails ... claps land on the hit"; "Exact levels: ask for -6dB and get -6.0dB"; "Track numbers match what you see"; "Device knobs land first try"; "Windows build to follow." |

Recurring themes: the bridge connection (startup, sleep, busy Live), the assistant deleting or damaging things it
was not asked to touch (0.1.8, 0.1.11, 0.1.18), playback not starting where asked (0.1.9, again 0.1.18), and the
Windows install of the "listener" (0.1.17, 0.1.18).

Features in the notes that `docs/MARKET.md` does not have: Mix & Master mode with "A small listener sits on your
tracks and hears the song as it plays" (0.1.16), Learn mode (0.1.15), "Hum it" mic to MIDI and "Remake a track"
(0.1.13), JAM mode (0.1.11), Eco/Pro engine switch (0.1.9).

## 2. `docs/MARKET.md`, claim by claim

| Claim in MARKET.md | Verdict | Evidence |
|---|---|---|
| AI assistant controlling Live in free language, two forms (app, Setup Kit) | Confirmed | `/`, `/app`, `/terms` "The two products" |
| App for macOS and Windows with AI built in | Confirmed | `/app` |
| App: monthly subscription with credits, from $27.99 | Confirmed | "From $27.99/mo · cancel anytime"; plans $27.99 / $54.99 / $87.99 |
| Setup Kit: one-time, **£24.99** "per the site" | **Contradicted as shown here** | "$33.99 founder price". Could be local-currency display; checkout not opened |
| Kit needs your own Claude/Codex plan | Confirmed | "You need your own paid AI plan to use it" (`/terms`) |
| App includes 33 plugins, 36+ packs, pack maker, reference mastering | Confirmed | `/app` |
| Kit includes videos, templates, command packs, troubleshooting | Confirmed | `/` "INSIDE THE KIT" |
| Kit lacks the pack maker and reference mastering | Confirmed on `/app`, but `/` muddies it | see "The site contradicts itself" above |
| Control: playback, tempo, arming, loading sounds, devices, clips, MIDI, arrangement, mix | Confirmed | "200+ ACTIONS" (`/`) |
| "AI can't hear", analyser makes waveform and spectrogram | Confirmed | "AI can't hear. So StudioPilot lets it see your sound." |
| Clash detection and ranking layers that fill gaps | Confirmed | "Anti-clash scoring" |
| Stem split, audio to MIDI, arrangement, mix, master | Confirmed | `/stemsplitter`: "It splits stems, turns them into MIDI, builds arrangements, mixes and masters." |
| Reference mastering (EQ, Glue, Limiter, LUFS) only in the app | Confirmed | `/app` FAQ |
| Free stem splitter page, free presets, FL page | Confirmed | all three opened |
| Privacy: does not collect, upload or store audio, no training | **Partly contradicted** | `/privacy` exception: pack-from-track uploads the audio file to a stem service; typed instructions go to "Our AI provider" |
| Version found: 0.1.17 | Out of date | latest 0.1.18 |
| No independent user reviews found | Still true | section 4 |
| Table: "no mention" of a journal of AI changes | **Contradicted** | 0.1.16: "Every change is listed, and Undo all of that takes it all back out" (in Mix & Master mode) |
| Table: "no mention" of a look-only mode | **Contradicted** | 0.1.15 Learn mode: "answers your questions and explains the why, without changing a single thing in your set" |
| Table: "no mention" of AI tracks with non-round tempo | Not found on the site | only "detects the BPM, key and structure" and "inspect warp markers"; nothing on drifting tempo |
| Table: "no mention" of singing from MIDI | Not found on the site | the reverse exists: hum to MIDI (0.1.13) |
| Table: install help is "videos and email support" | Confirmed, plus more | app "sets up the Ableton bridge for you and runs a connection test"; 0.1.18 "says when Ableton needs a restart" |
| Table: FL Studio "has a page" | Confirmed | a separate $33.99 kit, 60+ actions, no playlist placement |
| Category weakness 2: the AI gets a picture, "no number that can be checked" | Does not hold for StudioPilot's own claims | "at 66% mid, 27% low-mid"; "Reads your audio, LUFS"; 0.1.8 "the assistant can read real output levels"; 0.1.16 listener on the tracks |
| Category weakness 3: one big request times out | StudioPilot claims otherwise | 0.1.8 "ask for a whole track and watch it build it"; 0.1.13 fix shows it used to fail |
| Category weakness 4: third-party plugins barely reachable | StudioPilot claims otherwise | "Drives your 3rd-party plugins (Serum, FabFilter…)"; 0.1.7 "on stock devices and plugins" |
| Category weakness 5: technical install, 30 to 60 minutes | StudioPilot claims otherwise | testimonial "Setup took ten minutes with Claude."; app "one click" |

All of these are the seller's words. None was tested.

## 3. What the site does not say

- Which AI model or provider (only "Our AI provider", "music-tuned AI"), and what Eco and Pro engines are.
- Which stem separation service receives the uploaded audio, and where it is stored and for how long. The free
  splitter page says only "uploads straight to secure storage".
- What exactly leaves the computer with a chat request: the typed text only, or also session data, analyser
  numbers and spectrogram images. "it reads what it needs from your session" is the whole statement.
- What happens offline. 0.1.18 implies packs need internet; only JAM is said to run "entirely on your machine".
- Supported Live versions and editions, minimum OS, hardware needs ("a fairly new computer" is all).
- What a credit is, what an action costs, and what happens when the credits run out before the month ends.
- What the "listener" is technically (a Max for Live device, a plugin?) and whether it needs Suite or Max for Live.
- Whether the kit's bridge is open or closed code, and whether it can coexist with another control surface.
- Company name, legal entity, country, address, governing law. Who the testimonials are (first names and an
  initial only; "Loved by pro producers" with no names).
- Benchmarking, reverse engineering, competitor use: the terms are silent.
- Any free trial, any money-back period, any documentation or changelog page on the site itself.
- Accuracy numbers for anything: key detection, BPM, stem quality, loudness matching.

## 4. Independent voices

Three WebSearch queries on 2026-11-13 (name with "review", with reddit/forum/trustpilot/product hunt, with
youtube/tiktok/scam/legit). **None found**: no user review, forum thread, video comment, Trustpilot or Product Hunt
page about StudioPilot of studiopilotmusic.com.

The only hits carrying the name, both opened by nobody here (search summaries only):

- https://saasbrowser.com/en/saas/1542850/studiopilot : a directory entry, "$19.99/mo", zero reviews. Not confirmed
  to be the same product; the price matches nothing on the site.
- https://lobehub.com/mcp/consigcody94-studio-pilot : an open-source "studio-pilot" MCP server for Claude Desktop
  over OSC. Looks like a different project.

The site's own menu points to TikTok-style marketing (ads on Meta, TikTok, Snapchat, Google per `/privacy`);
comments on those ads were not searched inside the platforms: not checked.

## What a hands-on test would cost and need

Not obtained. For the user's decision:

| Option | Cost | Needs | Tests what |
|---|---|---|---|
| A. Setup Kit | $33.99 once (price at checkout in local currency: not checked) | an account by email, a download, their bridge installed as a control surface in Live, your existing Claude | The part built like our tool: the 200+ actions, the analyser, clash scoring. Not the pack maker or reference mastering |
| B. App, Starter, one month | $27.99, then cancel | an account, installing the app and its "listener" on Windows, their bridge in Live | Everything, including pack maker, reference mastering, Mix & Master. 2,000 credits; how far that goes is unknown |
| C. Free stem splitter | free | uploading a track to their storage (up to 150 MB) | Only pack cutting: are loops really bar-aligned on a track whose tempo drifts. Compare with our `sample_pack` |

Things to know before choosing:

- Refunds are "not ... as standard", so A or B is money spent.
- Both A and B install a second control surface next to `T2A_Bridge`. Whether they coexist is unknown; test in an
  empty Set, with a backup of the Remote Scripts folder.
- B and C send audio off the computer (their privacy page says so for packs). Use a track you are allowed to upload.
- The terms do not forbid comparing or benchmarking. They do forbid sharing or redistributing the files.
- Account creation, payment, download and install are the user's to do; this session did none of them.

STOP: waiting for the user's decision on A, B, C or none.

**User's decision, 2026-11-13: A (Setup Kit).** The purchase, the account and the download are done by the user.
Nothing bought, downloaded or installed yet at the time of writing.
