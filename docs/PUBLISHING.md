# Publishing MediaCraft on PyPI

MediaCraft's Python distribution is named **mediacraft-cli**. Its command is **mediacraft**. PyPI publishing is handled through GitHub Actions Trusted Publishing; no long-lived API tokens or passwords should be stored in GitHub.

## One-time account setup

1. Create/sign in to a verified [PyPI](https://pypi.org/) account with two-factor authentication.
2. Confirm that https://pypi.org/project/mediacraft-cli/ does not belong to a different publisher. Do not attempt to upload under a name you do not own.
3. If the project is not yet published, visit https://pypi.org/manage/account/publishing/ and register a **pending GitHub publisher**. If the project exists under your account, open its **Manage → Publishing** page instead.
4. Enter the following exact settings:

   | Field | Value |
   | --- | --- |
   | PyPI project name (pending publisher) | mediacraft-cli |
   | GitHub repository owner | Helloworld9099 |
   | GitHub repository name | mediacraft |
   | Workflow filename | publish.yml |
   | GitHub environment | pypi |

5. In GitHub go to **Settings → Environments** for this repository and create/select the **pypi** environment. Configure deployment protections, ideally a required reviewer and a restriction to matching release tags (`v*`). Ensure a reviewer can actually approve the deployment. The workflow will not itself create these protections.
6. Do not create PyPI API tokens or add PyPI secrets to GitHub. The workflow uses a short-lived GitHub OIDC token.

A pending publisher does not reserve the package name; it becomes active only after the first successful publication.

## First release (v0.6.0)

1. Merge and verify the packaging changes on `main`.
2. Confirm `.github/workflows/test.yml` passes on Linux, Windows and macOS, and the **package** job builds both an sdist and wheel.
3. Ensure `version` in `pyproject.toml` matches `__version__` in `mediacraft/__init__.py` (both currently `0.6.0`).
4. On GitHub, open **Releases → Draft a new release**. Create a *new* tag named **v0.6.0**, targeting the tested `main` commit. Do not rename or overwrite the historical `utility` tag.
5. Give the release a useful title (for example, `MediaCraft v0.6.0`) and describe the primary commands and cross-platform support. Publish the release (not as a prerelease).
6. The `.github/workflows/publish.yml` workflow will validate the version tag, build and check wheel/source distributions, smoke-test the CLI entry point, and then request permission to publish from the `pypi` GitHub environment. Approve the deployment if prompted.
7. Open the workflow's Actions run. Confirm that the **Upload distribution to PyPI** job succeeds. Then verify the project exists at https://pypi.org/project/mediacraft-cli/.

If PyPI reports a missing or mismatched publisher, verify the four publisher fields and `pypi` environment name above. If the project name has become unavailable, stop and select a new distribution name before attempting any publication.

## Validate installation after publishing

On a machine with Python 3.11–3.13 and pipx installed:

```bash
pipx install mediacraft-cli
mediacraft --version
mediacraft doctor
mediacraft --help
```

Try a small SVG with `mediacraft splitdesign` to verify actual processing. The first use of image background removal or audio separation may download large optional dependencies. pipx needs to stay available on `PATH` so MediaCraft can use `pipx inject` for those optional engines.

To upgrade: `pipx upgrade mediacraft-cli`.

To uninstall: `pipx uninstall mediacraft-cli`. This removes the pipx environment but not necessarily caches created by third-party AI engines.

## Future releases

1. Update both version values and changelog/release notes.
2. Run tests, build and package checks; merge only after all checks pass.
3. Create a matching `vMAJOR.MINOR.PATCH` GitHub release tag for the tested commit.
4. Publish the GitHub Release, approve the protected PyPI deployment, and verify the new version on PyPI.
5. Do not reuse a PyPI release version after uploading: PyPI release artifacts are immutable.

## Troubleshooting

- **Trusted publisher mismatch:** Check owner, repository, workflow filename **publish.yml**, and environment **pypi**, including exact casing.
- **Build fails:** Run `python -m pip install build twine`, `python -m build`, and `python -m twine check --strict dist/*` locally before releasing.
- **Version mismatch:** Match `v0.6.0` to both `pyproject.toml` and `mediacraft/__init__.py`.
- **Upload rejected because version exists:** Increment the version; do not overwrite a previously published artifact.
- **pipx can't find the Python version:** Use `pipx install --python python3.12 mediacraft-cli` with a supported interpreter.
- **Optional engines won't install:** Check `pipx` is on `PATH`, available disk space and internet access. pipx normally handles its own isolated environment; avoid `sudo pip install` into system Python.
- **Using the repository installer instead of pipx:** Use `mediacraft uninstall`, not `pipx uninstall`.

References: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/), [Python Packaging Guide for GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
