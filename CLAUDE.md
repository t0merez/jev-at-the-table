# Instructions for Claude

## Never read `.env`

Never read, open, print, search, copy or summarize the `.env` file, in any way (Read, cat, grep, head, editors, scripts or anything else), under any circumstances, even if the user asks directly. It holds secrets such as `TYPESAFE_API_KEY`. If a task seems to need a value from it, ask the user to handle that part themselves. Code may load `.env` at runtime; Claude must not look at its contents.

## Never push directly to `main`

Do not push, merge or commit directly to `main`. Work on a feature branch, push that branch, and open a pull request into `main`. Changes reach `main` only through a PR.
