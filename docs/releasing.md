# Releasing BlendMCP

Publishing a GitHub release triggers [publish.yml](../.github/workflows/publish.yml).
The workflow builds a wheel and source distribution, passes them between jobs
as the `dist` artifact, and uploads them to PyPI using Trusted Publishing in the
`pypi` environment. Pushing a commit or tag alone does not trigger publication.

## Prepare the version

1. Update `version` in [pyproject.toml](../pyproject.toml) and `bl_info["version"]`
   in [addon.py](../src/blendmcp/addon.py). The installer tests check that they match.
2. Run `uv lock` to update the package version in `uv.lock`.
3. Update [CHANGELOG.md](../CHANGELOG.md) and the release links, upgrade examples,
   and validation notes in [README.md](../README.md).
4. Validate the changes and build the distributions:

   ```bash
   uv sync --locked --group dev
   uv run --locked pytest -q
   uv build
   ```

   Check the wheel's version, dependency bounds, and bundled
   `blendmcp/addon.py`. Add-on changes also need a smoke test in the affected
   Blender versions; the unit tests use fakes for `bpy`.
5. Merge the changes and wait for the `tests` workflow on that `main` commit to
   pass on Python 3.10, 3.11, and 3.12.

## Publish the release

Use an authenticated GitHub CLI with release permissions. Start from a clean,
up-to-date `main` checkout. Set `release_version` to the version being released,
without a leading `v`, and confirm that its tag, GitHub release, and PyPI version
are all unused.

Write the version's changelog entry and validation results to a release-notes
file, then create the release at the exact tested commit:

```bash
release_version=X.Y.Z
release_commit="$(git rev-parse HEAD)"
gh release create "v${release_version}" \
  --repo owenpkent/blendmcp \
  --target "$release_commit" \
  --title "v${release_version}" \
  --notes-file /tmp/blendmcp-release-notes.md \
  --latest
```

This creates the tag if needed and publishes the release immediately. Find the
resulting workflow run and confirm its `headSha` matches `release_commit`:

```bash
gh run list --repo owenpkent/blendmcp --workflow publish.yml \
  --event release --branch "v${release_version}" \
  --json databaseId,headSha,status,conclusion,url
gh run watch RUN_ID --repo owenpkent/blendmcp --exit-status
```

Replace `RUN_ID` with the matching run's `databaseId`. Both `build` and `publish`
must finish successfully. Then verify the version page on
[PyPI](https://pypi.org/project/blendmcp/#history): it should offer both a wheel
and a source distribution with the intended version and dependency metadata.
Fetch the release tag locally with `git fetch origin tag "v${release_version}"`.

## Publishing configuration

The PyPI Trusted Publisher must match owner `owenpkent`, repository `blendmcp`,
workflow `publish.yml`, and environment `pypi`. Repository renames require
updating that configuration.

The `tests` workflow does not exercise the artifact upload/download or PyPI
publishing steps. Check those steps when action versions change. The
[v1.4.4 publication](https://github.com/owenpkent/blendmcp/actions/runs/35048115387)
successfully exercised the build, artifact transfer, and PyPI upload.

If publication fails, inspect the failed job's logs and check whether any files
already reached PyPI before retrying. Fix the underlying problem before running
the publishing workflow again.
