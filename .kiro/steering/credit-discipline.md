---
inclusion: always
---
# Working efficiently (the team has a limited Kiro credit budget)

- Make the **smallest change** that completes the task. Edit files in place. Never regenerate a whole file to change a few lines.
- Before writing code, read only the files you need. Prefer targeted reads over scanning the whole repo.
- Run the **narrowest test** that proves the change (a single test file or `-k` filter), not the full suite, unless the task says so.
- Don't create extra documentation, summaries or example files unless a task asks for them.
- If a command fails twice for the same reason, stop and report the error with a proposed fix instead of retrying variations.
- When a spec task is complete, stop. Don't start the next task unprompted.
- Keep chat responses short: what changed, which files, how it was verified.
