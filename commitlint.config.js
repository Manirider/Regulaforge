module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "chore",
        "docs",
        "test",
        "refactor",
        "perf",
        "ci",
        "build",
        "style",
        "revert",
      ],
    ],
    "subject-case": [2, "always", "sentence-case"],
    "header-max-length": [2, "always", 72],
  },
  defaultIgnores: true,
  helpUrl:
    "https://github.com/conventional-commits/commitlint/#what-is-commitlint",
};
