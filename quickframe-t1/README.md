# QuickFrame

**QuickFrame is a one-person AI video company.**

A business submits a brief — business, topic, brand colours and style — and QwenWork agents turn it into a brand-locked 30-second reel plus a full campaign kit in about 15 minutes.

## What you get

- A **30-second hero reel** in 9:16, generated from the brief
- A **15-second cutdown**
- **Stills / posters** in native formats
- **Captions and hashtags**, ready to post
- All downloadable from the campaign page — customers post the videos themselves

## How it works

QuickFrame runs on two platforms:

- **Hashmeta** hosts it: the website, the campaign store, and the brand profiles.
- **QwenWork** provides the workforce: Cloud agents pick up each campaign, generate the reel with QwenWork image and video models, check it against the customer's **Brand Lock** profile (a per-business style bible enforced on every scene), and publish the reel and kit back to the site. A live progress bar shows each campaign moving from Submitted to Ready to download.

## Live site

https://quickframe.geo.hashmeta.tech

## Demo

A real campaign for **Ya Kun Kaya Toast** (Singapore, since 1944) — the signature Kaya Toast Set: kaya toast with kaya and butter, soft-boiled eggs, and a cup of kopi. Watch the demo video to see a campaign go from form submission to finished reel and kit.

Demo video: https://youtu.be/8NNYIeSn_rE

## Built

17–23 November 2026, for the QwenWork x Hashmeta AI One-Person Company Hackathon (Track 1: Business Operations & Automation). Everything — the site, the campaign loop, Brand Lock, the Campaign Kit, and the demo video — was built with QwenWork Cloud agents and deployed on Hashmeta.

## Repository contents

This repo also contains the earlier T1 job-service prototype (`qf/`, `acceptance.py`, `Dockerfile`) — a Prompt → MP4 service (edge-tts voice + FFmpeg render) built from the same spec before the project moved to QwenWork Cloud agents and Hashmeta. It is kept here for reference; the live product is the Hashmeta site above.
