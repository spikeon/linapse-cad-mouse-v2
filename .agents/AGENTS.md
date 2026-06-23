# Agent Rules for Linapse CAD Mouse

All AI agents working on this project MUST follow these guidelines without exception.

## Versioning System

The current version of this project is stored in the `VERSION` file at the repository root (using `MAJOR.MINOR.PATCH` Semantic Versioning).
You MUST only increment the version number and sync it when the user explicitly requests a push or a release. Do not update the version for minor intermediate changes during a session unless requested.
When doing a release/push-time version increment:
1. **Read the current version** from the [VERSION](file:///home/spikeon/Dev/linapse-cad-mouse-v2/VERSION) file.
2. **Increment the version number** based on your changes:
   - **PATCH** (`x.y.Z`): Increment for backwards-compatible bug fixes, minor documentation updates, test additions, or internal refactoring.
   - **MINOR** (`x.Y.z`): Increment for backwards-compatible new features or functional additions.
   - **MAJOR** (`X.y.z`): Increment for breaking API changes, hardware protocol updates, or massive structural refactors.
3. **Write the new version** back to the [VERSION](file:///home/spikeon/Dev/linapse-cad-mouse-v2/VERSION) file.
4. **Run `python3 scripts/sync_version.py`** from the repo root. This single command propagates the version in `VERSION` to all embedded version strings across the codebase. Do NOT manually edit the following files — the script handles them:
   - `firmware/src/main.cpp` — `Serial.println("version=X.Y.Z")`
   - `service/linapse/state.py` — `service_version = "X.Y.Z"`
   - `installer.iss` — `AppVersion=X.Y.Z`
   - `configurator/package.json` — `"version": "X.Y.Z"`
   - `service/linapse-browser-connector.user.js` — `// @version X.Y.Z`
   - `CHANGELOG.md` is intentionally NOT touched by the script — update it manually with release notes.

## Changelog Updates

When performing a push/release version increment, you MUST update [CHANGELOG.md](file:///home/spikeon/Dev/linapse-cad-mouse-v2/CHANGELOG.md) to record the new version's release notes:
1. Create a section for the new version you are releasing/incrementing to.
2. List your changes clearly under the standard "Keep a Changelog" headings:
   - `Added` for new features.
   - `Changed` for changes in existing functionality.
   - `Deprecated` for soon-to-be-removed features.
   - `Removed` for now-removed features.
   - `Fixed` for any bug fixes.
   - `Security` in case of vulnerabilities addressed.
3. Ensure the date of the change is recorded next to the version header (e.g., `[2.0.1] - 2026-06-18`).

## Git Token Environment Variable

You MUST ignore the `git_token` (or any environment variables containing git/github auth tokens) when executing git commands. Do NOT try to read them, use them, or prompt the user for them. Assume git authentication is handled by the user/system credential helper.

If git commands (like `git push`) fail with authentication/token errors, it is likely because `GITHUB_TOKEN` or `GH_TOKEN` environment variables are present and invalid, overriding the valid credentials stored in the system's keyring. To bypass this, run git push with these invalid environment variables explicitly unset:
```bash
env -u GITHUB_TOKEN -u GH_TOKEN git push
```


## Documentation Requirement

Whenever a new feature is added to the codebase, you MUST:
1. **Write or update documentation** under the `docs/` folder explaining the new feature, its architecture, integration details, and usage.
2. **Update the main README.md** (and other relevant readmes, e.g. `service/README.md`) to call out the new capability and link to the detailed documentation.

## Firmware Build and Test (PlatformIO)

PlatformIO (`pio`) is installed but NOT on `$PATH`. Always invoke it with the full path:
```bash
~/.platformio/penv/bin/pio
```

To run native firmware unit tests (no hardware required):
```bash
~/.platformio/penv/bin/pio test -e native
```

To build for the device:
```bash
~/.platformio/penv/bin/pio run
```

## CI Workflow Step Name Constraint

`service/test_installer_config.py::TestInstallerConfig::test_workflow_yaml_valid` asserts that specific step names exist in `.github/workflows/multi-distro-test.yml`. If you add, rename, or remove CI steps, you MUST update this test or it will fail. Read the test before touching the workflow file.

## Playwright Integration Testing

Do NOT recommend disabling Playwright tests or marking them as slow to skip by default. They are the most important tests for ensuring correct behavior across all distributions.

## CI/CD Failure Fixing Loop

When fixing CI/CD errors or failures:
1. **Commit and Push**: After implementing your proposed fix, stage and commit the changes, then push them to trigger the CI/CD pipeline.
2. **Wait and Verify**: Wait for the CI/CD run to complete and verify the results.
3. **Retry on Failure**: If the run fails, analyze the new failures, adjust your implementation, and repeat the commit-push-wait loop.
4. **Iterate to Success**: Continue this process until the CI/CD pipeline succeeds. If appropriate, recommend or utilize the `/goal` command to ensure thorough, multi-turn tracking.

## Lighting Mode Modification Requirement

When making any changes to the lighting modes (such as adding, removing, or modifying an effect or its behavior), you MUST update:
1. **LED Preview**: The corresponding LED Preview rendering logic inside the configurator's `index.html`.
2. **Lighting Page Render Simulation**: The render simulation/animation loop for that effect inside the configurator's `index.html`.
3. **LIGHTING.md Documentation**: The [LIGHTING.md](file:///home/spikeon/Dev/linapse-cad-mouse-v2/docs/LIGHTING.md) file describing the effect's behavior, parameters, and layout.
4. **LIGHTING.md GIF**: The corresponding visualizer preview GIF in the `docs/images/` directory (e.g., using the playwright-driven generator script) to match the changes.
