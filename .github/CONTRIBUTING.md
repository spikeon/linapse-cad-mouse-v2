# Contributing to Linapse

Thanks for your interest in improving **Linapse — CAD Mouse MK2 (v2)**. This is
an independent, cross-platform software stack for a DIY 6-DOF space mouse.
Contributions of all kinds are welcome: bug reports, fixes, docs, and features.

> This project is **not** intended to be merged back upstream. Hardware design
> (enclosure, PCB, BOM) lives in the [original project](https://github.com/sb-ocr/cad-mouse-mk2).

## Ways to contribute

- **Report a bug** — open an [issue](https://github.com/spikeon/linapse-cad-mouse-v2/issues) using the Bug Report template.
- **Request a feature** — open an issue using the Feature Request template.
- **Ask / discuss** — join the [Discord](https://discord.gg/YABjjtuCMU).
- **Submit a fix or feature** — open a Pull Request (see below).

## Repository layout

| Path            | What lives here                                  |
| --------------- | ------------------------------------------------ |
| `firmware/`     | Device firmware (PlatformIO, see `platformio.ini`) |
| `service/`      | Host-side Python service                          |
| `configurator/` | Electron configuration GUI                        |
| `installer.iss` / `setup.sh` / `debian/` / `fedora/` / `aur/` | Packaging per platform |
| `docs/`         | Documentation and images                          |
| `scripts/`      | Build / CI helper scripts                         |

## Development setup

The stack spans three components. Build only what your change touches.

- **Firmware** — build/flash with [PlatformIO](https://platformio.org/): `pio run` (see `platformio.ini` for environments).
- **Service** — Python. Run the test suite with `pytest` from the repo root.
- **Configurator** — Electron app in `configurator/`. `npm install` then `npm start`.

See the [README](../README.md) for full platform-specific install and run instructions.

## Pull request process

1. **Fork** the repo and create a branch off `main` (`fix/...`, `feat/...`).
2. **Keep changes focused** — one logical change per PR. Smaller is easier to review.
3. **Test your change.** Run `pytest` for service changes; build firmware/configurator for those. CI (`.github/workflows/`) must pass.
4. **Use [Conventional Commits](https://www.conventionalcommits.org/)** for commit messages (e.g. `fix(service): ...`, `feat(configurator): ...`), matching the existing history.
5. **Open the PR** against `main`, fill out the PR template, and link any related issue.

> ⚠️ **Never commit secrets or real device VID/PID values** to this repository.

## Code style

Match the surrounding code — naming, comment density, and idioms. Don't
reformat unrelated lines. Keep diffs minimal.

## License

By contributing, you agree that your contributions will be licensed under the
project's [CC BY-NC-SA 4.0](../LICENSE) license.
