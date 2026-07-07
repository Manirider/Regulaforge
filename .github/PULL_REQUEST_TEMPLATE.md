---
name: Pull Request
about: Submit changes to RegulaForge
title: ""
labels: ""
assignees: ""
---

## Description

Please provide a summary of the changes and the problem they solve. Include relevant motivation and context.

Fixes #(issue-number)

---

## Type of Change

Check all that apply:

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that causes existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] ♻️ Refactor (code restructuring without functional changes)
- [ ] ⚡ Performance improvement
- [ ] 🔧 CI / Chore / Tooling

---

## Checklist

- [ ] My code follows the project's code style guidelines (Black, Ruff, mypy, Prettier, ESLint)
- [ ] I have performed a self-review of my own code
- [ ] I have commented on complex code sections where necessary
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally (`pytest` and `npm run test:run`)
- [ ] I have run the linter and type checker (`ruff check .`, `mypy src/regulaforge`, `npm run lint`, `npm run typecheck`)
- [ ] I have updated the documentation accordingly (if applicable)
- [ ] I have added an entry to the changelog or release notes (if applicable)
- [ ] My branch is up to date with `main` and rebased (not merged)

---

## Related Issues

List any related issues, pull requests, or discussions:

- Closes #(issue)
- Related to #(issue)
- Depends on #(PR)

---

## Screenshots (if applicable)

| Before | After |
|--------|-------|
| (screenshot) | (screenshot) |

---

## Additional Context

Add any other context about the pull request here:

- Performance implications
- Security considerations
- Migration steps required
- Rollout strategy (feature flag, gradual rollout, etc.)
- Any manual testing performed
