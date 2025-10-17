# Instagram Scraping – Non‑Technical Overview

This system helps us find restaurants’ Instagram accounts, gather recent videos, and decide which ones are good enough to show on their DoorDash store pages.

## What it does

1) Finds the restaurant’s Instagram account using web search.
2) Locates recent Instagram video posts (including Reels).
3) Downloads those videos.
4) Uses AI to judge video quality for marketing (looks tasty, well‑shot, brand‑safe).
5) Prepares a text message we can send to the restaurant to approve using their videos.

## Why we built it

- Save time: No manual searching or downloading
- Consistency: Apply the same quality criteria to all videos
- Scale: Process many restaurants quickly and safely

## Where the information comes from

- Public web pages (restaurant sites, Yelp, Google Maps, etc.)
- Instagram public profiles and posts
- We prefer safe, official methods and avoid anything that needs passwords

## How it stays safe and respectful

- Uses gentle pacing to avoid triggering platform limits
- Focuses on public information only
- Stores all sensitive keys (like OpenAI/Twilio) outside the codebase

## What teammates need to know

- Inputs: restaurant name and address (phone is optional)
- Outputs: a list of approved videos and a ready‑to‑send SMS preview
- For large lists, we can run in bulk from a CSV and get progress + results files

## Typical outcomes

- “Approved videos” with scores and short reasons (from the AI)
- If no good videos are found, the SMS explains that too

## When things fail

- The system logs why (couldn’t find the IG account, download failed, etc.)
- It moves on so one failure doesn’t block others

If you need more detail on the technical side, see the engineering guide: IG_SCRAPING_TECHNICAL.md.
