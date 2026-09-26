# The Push — NHL power rankings and playoff picture

A GitHub Pages site for the whole league. The home page is this week's power rankings and playoff picture: current standings, trending teams, the games on the slate, and last week's scores. Every club links to its own page, built the same way as the Maple Leafs dashboard: two routes into April, the cut line, the division, the schedule, and the points underneath the record.

Hockey does not use a wins-and-losses wild-card table. A win is 2 points. An overtime or shootout loss is 1. The top three in each division are in. Two wild cards join them in each conference.

Before opening night the standings are still last season's. The page says so, shows that finish, and runs the new schedule through the model. Once regular-season games count, the same pages switch to the live race.

## Pages

- `/` — this week's power rankings and playoff picture
- `/teams/tor/` — Toronto, and the same path for all 32 clubs (`bos`, `edm`, `fla`, …)

## Enable it on GitHub

1. Push this project to a public GitHub repo (default branch `main`).
2. In the repo: **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: `/ (root)`
3. In **Settings → Actions → General**, allow GitHub Actions and permit the workflow to read and write contents so it can commit the JSON under `data/`.
4. Open **Actions → Update playoff dashboard → Run workflow** once so the first refresh is confirmed.

The public URL will be:

`https://<your-github-username>.github.io/nhl-playoff-push/`

## What updates

A scheduled GitHub Action runs `scripts/fetch_playoff_data.py`. It writes `data/league.json` and `data/teams/<club>.json` from the [NHL API](https://api-web.nhle.com/). If nothing in the race changed, the workflow skips the commit.

Power rankings blend points percentage, shrunk toward a .500 club, with the goal margin over the last three games. The playoff percentage is a 2,500-season simulation from that same model plus home ice. It is not a betting line, and it is not an official NHL ranking.

## Local refresh

```bash
python3 scripts/fetch_playoff_data.py
python3 -m http.server 8080
```

Visit [http://localhost:8080](http://localhost:8080). Opening `index.html` as a file will block `fetch`.

## Notes

This is a fan dashboard, not an official NHL product.
