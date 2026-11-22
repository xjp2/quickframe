# QuickFrame

**QuickFrame is a one-person AI video company.**

A business submits a brief — business, topic, brand colours and style — and gets back a brand-locked 30-second reel plus a full campaign kit in about 15 minutes.

## How it works

1. A business submits a campaign brief through the website: business name, email, topic, a product image, brand colours, a style description, and a caption style.
2. The brief is stored and queued. A live progress bar shows the campaign moving from Submitted to Ready.
3. Cloud agents pick up the campaign, generate the reel, check it against the customer's Brand Lock, and publish the finished reel and kit back to the site.
4. The customer downloads the reel, the 15-second cutdown, the stills, and the captions with hashtags — and posts them themselves.

## What you get

- A **30-second hero reel** in 9:16, generated from the brief
- A **15-second cutdown**
- **Stills / posters** in native formats
- **Captions and hashtags**, ready to post

## How Cloud agents are used

QuickFrame has no fixed backend server doing the work. The workforce is QwenWork Cloud agents.

- When a campaign is submitted, a scheduled Cloud agent picks it up.
- The agent generates the reel with QwenWork image and video models, following the brief's brand colours, style, and caption style.
- The agent checks every scene against the customer's Brand Lock — a per-business style bible (palette, typography, tone) enforced on every shot — and regenerates any scene that drifts.
- The agent assembles the cutdown, stills, and captions, then publishes the reel and kit back to the site and marks the campaign Ready.
- Campaigns run in parallel: independent generation jobs fan out in one batch, so a campaign takes about 10–15 minutes from submit to ready.

## How Hashmeta is used

Hashmeta hosts the whole product.

- The website (quickframe.geo.hashmeta.tech) runs on Hashmeta.
- The campaign store lives on Hashmeta: every submission, its status, its reel, and its kit.
- Brand profiles live on Hashmeta: each business's colours, style, and caption preferences, which the agents read when they generate.
- Media is stored on Hashmeta: product images, generated reels, cutdowns, and stills.

## Live site

https://quickframe.geo.hashmeta.tech

## Demo

A real campaign for **CHAGEE** — refreshing drinks: ice-cold fresh-brewed tea over real milk and chewy pearls. Watch the demo video to see a campaign go from form submission to finished reel and kit.

Demo video: https://youtu.be/XKNc9fG_4jQ
