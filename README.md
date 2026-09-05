# Energy Market Live

A simple public page for:

- WTI crude
- Brent crude
- Natural Gas
- Baker Hughes U.S. rig count
- Baker Hughes Canada rig count
- North America total
- Baker Hughes International rig count

## How the automatic updates work

### Market charts
TradingView widgets load market data directly in the visitor's browser when the website opens.

### Rig count
`/scripts/update_rigcount.py` reads the public summary table at:

https://rigcount.bakerhughes.com/

GitHub Actions runs the updater every weekday at 1:20 PM America/Chicago. If Baker Hughes has published a new number, the workflow updates `site/rigcount.json`, commits the change, and redeploys the website automatically.

If Baker Hughes is temporarily unavailable, the site keeps the last successfully saved rig-count values.

## One-time GitHub setup

1. Create a new **public** GitHub repository.
2. Upload this project's files and folders.
3. Open repository **Settings → Pages**.
4. Under **Build and deployment → Source**, select **GitHub Actions**.
5. Open the **Actions** tab and run **Update rig count and deploy website** once with **Run workflow**.
6. Wait for the green check.
7. Return to **Settings → Pages** to see the public URL.

Your public page will normally be:

`https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/`

## Instagram

Instagram feed posts cannot execute live HTML or JavaScript.

Use the public GitHub Pages URL in:
- Instagram bio
- Story link sticker
- DM
- QR code

Then post a screenshot/Reel that says something like:
**Live WTI, Brent, Natural Gas & Rig Count — link in bio.**

## Notes

- TradingView says widget market data can be real-time, delayed, or end-of-day depending on the market/data source.
- Baker Hughes publishes North America weekly and International monthly.
- Keep Baker Hughes attribution visible if you display its rig-count information.
