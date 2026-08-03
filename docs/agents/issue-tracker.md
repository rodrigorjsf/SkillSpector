# Issue Tracker

Issues for SkillSpector are tracked in GitHub Issues:
**[github.com/rodrigorjsf/SkillSpector-Polyglot/issues](https://github.com/rodrigorjsf/SkillSpector-Polyglot/issues)**

## Consumer rules

The engineering skills (`to-tickets`, `triage`, `to-spec`, `qa`) read from and write to this tracker. They use the `gh` CLI to:
- List issues with `gh issue list --search <query>`
- Read issue details and comments
- Create issues with `gh issue create --title <title> --body <body>`
- Update labels and state with `gh issue edit`

Ensure you are authenticated: `gh auth status` (or `gh auth login` if needed).

## PRs as requests

This tracker does **not** include pull requests in the triage queue by default. External PRs land in GitHub but are not automatically escalated to the triage workflow. (A maintainer can flip this setting in the skill config if desired.)
