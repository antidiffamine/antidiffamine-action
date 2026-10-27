# Releasing

1. Merge changes to `main`.
2. In GitHub, draft a release with a new tag `vX.Y.Z` targeting `main`, tick **Publish this release to the GitHub Marketplace**, and publish it.
3. The **Release** workflow then:
   - moves the major tag (`vX`) to the new release, so users on `@vX` get it;
   - triggers the scenario PRs in [`antidiffamine-test`](https://github.com/antidiffamine/antidiffamine-test). Results are in that repo's **Release test** workflow run.
4. Check the four scenario PRs by eye against their descriptions and record the results in `antidiffamine-test/FINDINGS.md`. If a scenario fails, move `vX` back to the previous release:
   ```bash
   git tag -f vX vX.Y.(Z-1) && git push -f origin vX
   ```

The Release workflow needs the secret `TEST_REPO_TOKEN`; see the antidiffamine-test README for how to create it.
