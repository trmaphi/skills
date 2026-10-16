# Contributing

Open an issue for bugs, reproducible failures or new skill ideas. For DJI export bugs, include OS, Python/rawpy/FFmpeg versions, the command and sanitized error output. Do not upload private footage or credentials.

## Skill structure

Each top-level skill folder contains:

```text
skill-name/
  SKILL.md            # YAML name/description, then concise instructions
  agents/openai.yaml  # Display name, short description and $skill-name prompt
  scripts/            # Reusable tools, when needed
  references/         # Setup or detailed guidance, when needed
```

Use a lowercase, hyphenated name matching the folder. Describe when the skill applies in its frontmatter. Keep instructions portable, use relative asset paths, invoke scripts through an interpreter and document platform dependencies. Add the skill to the README catalog.

## Checks

Use Python 3.13 in a virtual environment. From the repository root:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python dji-export/scripts/export_timelapse.py --check
python -m unittest discover -s tests -v
```

`python` must refer to your virtual environment on either platform. Install FFmpeg/ffprobe using [platform setup](dji-export/references/setup.md) before running integration tests. CI requires both tools and tests the real RAW decoder and encoder on macOS and Windows. A local test run without FFmpeg skips the integration test, so it is not full export verification.

Test changed scripts against meaningful success and failure cases. For export changes, preserve originals, output naming, frame ordering, no-overwrite publication, cleanup and verification. Use generated fixtures; include third-party files only with redistribution permission and attribution. Review real footage locally when changing image development settings.

Keep pull requests focused. Describe the user-visible change and validation performed. Contributions are made under the repository's MIT license.
