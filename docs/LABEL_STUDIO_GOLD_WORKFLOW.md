# Insight Desk — Local Label Studio Gold Workflow

This workflow is intentionally human-only and offline from the production runtime. Use **Label Studio OSS 1.23.0 locally**. Do not create a Starter Cloud or Enterprise project for Insight Desk.

## 0. What this is for

Two independent projects are created:

1. `Insight Desk — Material Event Gold V1`
   - Decide only whether the displayed evidence establishes a concrete material event.
   - Choices: `MATERIAL`, `NOT_MATERIAL`, `UNCERTAIN`.
   - Old Run96 selection true-negatives are deliberately NOT pre-labeled as non-events.

2. `Insight Desk — Fact Span Gold V1`
   - Mark exact source spans for subject/action/object/date/location/cause/participant/number/attribution.
   - Never infer a missing span.

Do not combine the two projects. Event truth and fact extraction need independent human judgments.

## 1. Get the repository branch

In a terminal:

```bash
git clone -b phase4-core-contracts --single-branch https://github.com/kjkwon981229-prog/insight-desk.git
cd insight-desk
```

If the repository is already cloned:

```bash
git fetch origin
git switch phase4-core-contracts
git pull --ff-only origin phase4-core-contracts
```

## 2. Generate blind annotation tasks

This uses only Python's standard library and existing clean-room benchmarks.

```bash
python scripts/build_annotation_seed.py
```

Expected output begins with:

```text
ANNOTATION_SEED_READY
```

Generated local files:

- `annotation/material_event/tasks_seed.json`
- `annotation/material_event/seed_provenance.json`
- `annotation/fact_extraction/tasks_seed.json`
- `annotation/fact_extraction/seed_provenance.json`

The `tasks_seed.json` files contain no pre-populated gold labels. Provenance is kept in a separate file and is not shown by the provided Label Studio UI config.

## 3. Create an isolated Label Studio environment

### Windows PowerShell

```powershell
py -m venv .venv-labelstudio
.\.venv-labelstudio\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install label-studio==1.23.0
```

If PowerShell blocks activation, open Command Prompt instead and run:

```cmd
py -m venv .venv-labelstudio
.venv-labelstudio\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install label-studio==1.23.0
```

### macOS / Linux

```bash
python3 -m venv .venv-labelstudio
source .venv-labelstudio/bin/activate
python -m pip install --upgrade pip
python -m pip install label-studio==1.23.0
```

## 4. Start local Label Studio

```bash
label-studio
```

Open `http://localhost:8080` if the browser does not open automatically.

Create the local login requested by the self-hosted UI. This account belongs to the local Label Studio instance. Do not switch to Starter Cloud and do not enter payment information.

## 5. Material Event project

1. Click **Create Project**.
2. Project name: `Insight Desk — Material Event Gold V1`.
3. In **Data Import**, upload:
   - `annotation/material_event/tasks_seed.json`
4. Open **Labeling Setup**.
5. Choose custom/code configuration.
6. Replace the configuration with the complete contents of:
   - `annotation/material_event/label_config.xml`
7. Save the project.
8. Label every task using only the displayed title/evidence.
9. If evidence is insufficient, choose **UNCERTAIN**. Never guess based on outside knowledge.
10. Do not treat a familiar headline as an event unless the displayed evidence establishes the action/change/result.

When complete, export the project as JSON from Label Studio and keep the downloaded file unchanged.

## 6. Fact Span project

Create a separate project:

1. Click **Create Project**.
2. Project name: `Insight Desk — Fact Span Gold V1`.
3. In **Data Import**, upload:
   - `annotation/fact_extraction/tasks_seed.json`
4. Open **Labeling Setup** and use the complete contents of:
   - `annotation/fact_extraction/label_config.xml`
5. Save.
6. Highlight only literal source spans.
7. Use:
   - `SUBJECT` — actor/owner of the asserted action or state
   - `ACTION` — asserted action/state/change
   - `OBJECT` — material object/target of the action
   - `DATE_TIME` — explicit temporal expression
   - `LOCATION` — explicit location
   - `CAUSE` — explicit causal expression
   - `PARTICIPANT` — other named participant materially involved
   - `NUMBER_AMOUNT` — material number, amount, percentage, score, rank, count
   - `ATTRIBUTION_SOURCE` — explicit source/attribution such as an agency/company/person being quoted or cited
8. Do not manufacture a span when the source does not state it.
9. `FACT_STRUCTURE_PARTIAL` is valid. Do not force `FACT_STRUCTURE_CLEAR`.
10. Export as JSON when finished.

## 7. Return the gold data

Upload the two untouched exported JSON files back to the Insight Desk working conversation:

- Material Event export
- Fact Span export

Do not manually edit the export. The integration step will validate task IDs against the separate provenance maps, reject duplicate/incomplete annotations, and create a clean benchmark artifact.

## 8. Stop Label Studio

Return to the terminal running Label Studio and press `Ctrl+C`.

Deactivate the environment if desired:

```bash
deactivate
```

The `.venv-labelstudio` directory is local tooling only and must not become a project runtime dependency.

## Annotation rules that override convenience

- Evidence only; no outside knowledge.
- Missing means missing.
- `UNCERTAIN` is preferable to a forced label.
- Do not use Run96's old selection labels as material-event truth.
- Do not infer subject/object from a familiar story when the displayed text does not state them.
- Do not normalize dates or names during span annotation; mark the original source string.
