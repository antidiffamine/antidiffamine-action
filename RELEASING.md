# Releasing

1. Merge changes to `main`.
2. In GitHub, draft a release with a new tag `vX.Y.Z` targeting `main`, tick **Set as a pre-release**, and publish it.
   The **Release** workflow triggers the scenario PRs in [`antidiffamine-test`](https://github.com/antidiffamine/antidiffamine-test) against exactly `@vX.Y.Z`. Users on `@vX` are not affected yet.
3. Check the results: the **Release test** run in antidiffamine-test ends with a pass/fail table. Then compare the four PRs' comments and run summaries with their descriptions, and record the results in `antidiffamine-test/FINDINGS.md`.
4. If everything passes, edit the release: untick **Set as a pre-release** and tick **Publish this release to the GitHub Marketplace**. The Release workflow then moves the major tag `vX` to `vX.Y.Z`.
   If something fails, fix it on `main` and publish a new pre-release `vX.Y.(Z+1)`.

Publishing a full release directly also works: it runs the tests and moves `vX` at the same time, so users get it before the tests finish.

The Release workflow needs the secret `TEST_REPO_TOKEN`; see the antidiffamine-test README for how to create it.
