# Skills

[![Validate skills](https://github.com/trmaphi/skills/actions/workflows/validate.yml/badge.svg)](https://github.com/trmaphi/skills/actions/workflows/validate.yml)

Practical skills by [Truong Ma Phi](https://trmaphi.work) for Codex and agents that support the `SKILL.md` format. Each skill includes focused instructions and the tools needed to carry out its workflow.

## Catalog

| Skill | Use it for | Platforms |
|---|---|---|
| [dji-export](dji-export/SKILL.md) | Export DJI Action DNG timelapse sequences to verified H.264 MP4 videos | macOS, Windows |

`dji-export` replaces the earlier `creating-dji-action-timelapses` skill with one shared Python exporter. Remove the old skill folder from your agent's skills directory when switching to avoid duplicate discovery.

## Install

In Codex, ask the skill installer:

> Install dji-export from https://github.com/trmaphi/skills/tree/main/dji-export

Or copy the skill folder manually. These examples use Codex's default `~/.codex/skills` directory; use `$CODEX_HOME/skills` if you configured a different Codex home. Other agents may use `~/.agents/skills`; choose one location for each skill.

macOS:

```sh
git clone https://github.com/trmaphi/skills.git
mkdir -p "$HOME/.codex/skills"
cp -R skills/dji-export "$HOME/.codex/skills/dji-export"
```

Windows PowerShell:

```powershell
git clone https://github.com/trmaphi/skills.git
New-Item -ItemType Directory -Force "$HOME\.codex\skills" | Out-Null
Copy-Item -Recurse skills\dji-export "$HOME\.codex\skills\dji-export"
```

These commands assume `dji-export` is not already installed. For updates, replace the existing skill folder with the new copy. Restart Codex after installing or updating skills. Then follow [DJI platform setup](dji-export/references/setup.md) to install its runtime dependencies.

## Use

```text
Use $dji-export to export my DJI Action DNG timelapse folder to MP4.
```

Provide the media folder, or let the skill select the next valid unrendered sequence under Pictures/TIMELAPSE. The same bundled exporter works on both platforms and can also be run directly; see [setup and commands](dji-export/references/setup.md).

## Contribute and validate

See [CONTRIBUTING.md](CONTRIBUTING.md) for structure, checks and contribution guidance. CI validates metadata and runs safety tests plus a generated DNG-to-MP4 integration test on macOS and Windows. Synthetic fixtures exercise the pipeline; they do not certify every DJI camera model or subjective image quality.

## License

Repository code and instructions are [MIT licensed](LICENSE). Dependencies retain their own licenses, including rawpy/LibRaw and the FFmpeg build you install. This is an independent project, unaffiliated with DJI.
