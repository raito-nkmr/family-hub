# Provisional Person Detection Proposal

## Status and purpose

Person detection is not implemented and is not part of the current roadmap, API contract, or database contract. Work
should begin only if the number of photos and search problems demonstrate a clear need, and after reassessing accuracy,
processing cost, licensing, and maintenance cost.

If adopted, the goal would be to let users filter their personal photo collection for photos containing people. The
feature would detect presence only. Face recognition, personal identification, age or gender estimation, and scene
classification are out of scope. Analysis would run on the home PC; photos would not be sent to an external AI service.

## Proposed feature boundary

- Use a lightweight object-detection DNN and detect only the person class.
- Store whether a person was detected, the detected count, and the maximum confidence per photo.
- Add a “contains people” filter to the React photo library.
- Store only analysis results in PostgreSQL and never modify the original photo.
- Run analysis as a separate post-upload process so upload completion does not wait for inference.
- Store the model name and version so photos can be reprocessed after a model change.
- Distinguish “no person detected” from “not analyzed” and “analysis failed”; do not treat the former as an automatically verified landscape photo.

## Proposed backend structure

```text
app/features/photos/
└── person_detection/
    ├── detector.py
    ├── models.py
    ├── service.py
    └── worker.py
```

- `detector.py`: model loading, preprocessing, and person-class detection
- `models.py`: person-detection results and analysis state
- `service.py`: target selection, inference, result persistence, and failure handling
- `worker.py`: an analysis entry point separate from FastAPI requests

Model-specific APIs should be isolated in `detector.py`. Start with a command that analyzes one photo manually to measure
accuracy and processing time. Only develop a continuous worker after the need is confirmed.

## Processing flow

```text
Finalize the original, JSON sidecar, and thumbnail
  ↓
Register the Photo and a pending analysis in one database transaction
  ↓
Return success from the upload API
  ↓
Worker claims the pending analysis
  ↓
Detect only the person class
  ↓
Store the result, model information, and analysis timestamp in PostgreSQL
```

Do not hold a database row lock during DNN inference. Load the model once when the worker starts rather than once per
photo. Begin with one-photo-at-a-time CPU processing; do not introduce GPU or distributed processing until measurements
show that it is necessary.

## Provisional data model

`photo_person_analyses` uses `photo_id` as both its primary key and foreign key and stores at most one current analysis
state and result per photo. Analysis history is out of scope for the initial proposal.

| Column | PostgreSQL type | Nullable | Purpose |
| --- | --- | --- | --- |
| `photo_id` | `UUID` | No | Primary key and foreign key to `photos.id` |
| `status` | `VARCHAR(16)` | No | `pending`, `processing`, `succeeded`, or `failed` |
| `has_person` | `BOOLEAN` | Yes | Whether at least one person was detected |
| `person_count` | `INTEGER` | Yes | Number of detected people |
| `max_confidence` | `DOUBLE PRECISION` | Yes | Highest confidence score |
| `model_name` | `TEXT` | Yes | Model name used |
| `model_version` | `TEXT` | Yes | Model or weights version |
| `attempt_count` | `SMALLINT` | No | Number of attempted analyses |
| `error_message` | `TEXT` | Yes | Last failure reason |
| `queued_at` | `TIMESTAMPTZ` | No | Time the analysis was queued |
| `started_at` | `TIMESTAMPTZ` | Yes | Time the latest analysis started |
| `analyzed_at` | `TIMESTAMPTZ` | Yes | Time the analysis succeeded |

Proposed constraints:

- `attempt_count` and `person_count` are non-negative; `max_confidence` is between 0 and 1.
- When both `has_person` and `person_count` are set, `has_person = (person_count > 0)`.
- Only `succeeded` rows retain the result, model information, and `analyzed_at`.
- `failed` rows must contain `error_message`.
- Returning an analysis to `pending` for reprocessing clears the old result, model information, completion timestamp, and error.
- If photos are deleted in the future, analysis rows are deleted with `ON DELETE CASCADE`.

If multiple workers are allowed, claim the oldest `queued_at` row in a short transaction using `FOR UPDATE SKIP LOCKED`,
update it to `processing`, and then run inference. Use `started_at` and `attempt_count` to retry analyses interrupted by
an abnormal worker exit. Retry intervals and the maximum number of attempts are to be decided during implementation.

## Model and data management

- Compare candidate-model processing time and accuracy on the home PC's CPU.
- Review model and library licenses before adoption.
- If Ultralytics YOLO is selected, document the approach for complying with AGPL-3.0.
- Store weights on the internal SSD and never commit them to Git.
- Record the source, version, and, when possible, checksum of downloaded models.
- Treat resized inference images as temporary data and never modify originals on the external HDD.
- Never add real personal photos to the repository for tests or accuracy evaluation.

## Testing proposal

- Replace the real model with a test detector in ordinary unit tests.
- Cover people detected, no people detected, inference failure, retry, and reprocessing.
- Use a PostgreSQL integration test to verify that workers cannot claim the same photo concurrently.
- Keep real-model accuracy evaluation separate from the normal test suite.
- Do not require model downloads or external network access during normal test execution.

## Decisions required before implementation

- The photo volume and search problems that would justify a people filter
- The model, confidence threshold, license, and weights location
- Worker startup, retry, shutdown, and monitoring behavior
- Reprocessing load and progress reporting
- Backup scope and the boundary for reproducible derived data

日本語版: [person-detection.ja.md](./person-detection.ja.md)
