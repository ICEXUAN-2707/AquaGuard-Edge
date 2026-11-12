# B experiment results → C read-only API → existing experiment page

Status: proposal for B/C review, not a frozen contract or implemented API.
The frontend continues to use the existing experiment page and running-trial query.
No backend, public DTO or database changes are included in this frontend branch.

## Current capability and gap

`ExperimentResult` schema 1.1 provides trial_id, source, status, started_at,
ended_at and asset_refs. It has no metrics, method comparisons, sample counts or
model provenance. It is a strict backend DTO: do not silently append ad-hoc fields.
An asset path alone is not accessible evaluation data and the browser must not
fetch arbitrary local files or execute result files.

## Recommended minimal integration

1. B exports one versioned evaluation JSON, split manifest, per-window/trial
   predictions and labels, model card and reproducible evaluation command.
2. B and C agree on metric definitions, JSON schema and identifier mapping before
   implementation. C validates trusted output and serves it through a small read-only
   endpoint; a separate `GET /api/evaluations/{evaluation_id}` is a candidate,
   not an existing endpoint. Keep the old running-trial endpoint compatible.
3. C supplies an explicit association from trial/run to evaluation; no guessed
   filenames, path scanning or user-controlled filesystem access in the browser.
4. Frontend expands the existing experiment page with a report selector/association,
   method table, metric explanations and provenance. Raw report export remains.

## Required report information to agree

| Group | Information |
|---|---|
| Identity | report schema version, evaluation_id, creation time, evaluation code commit |
| Scope | task/label definitions, source (simulation or hardware), dataset version/hash |
| Data | independent trial count, window/sample count, class distribution, label provenance |
| Split | split manifest and grouping policy, train/validation/test trial references |
| Methods | C0–C3 method/version, configuration, feature version; model version for C3 |
| Metrics | value or null, units, denominators, applicable split, unavailable reason |
| Limits | unsupported scenarios, failure cases, sample limitations and conclusions |
| Evidence | trusted references to metrics, predictions, labels, manifest and model card |

Use null plus a reason for uncomputed/undefined metrics; never substitute zero.
Agree on fractions vs percentages and milliseconds vs seconds. Methods may be
compared only with the same task, evaluation split and compatible denominators.
Separate simulation and hardware reports rather than silently averaging them.

Prioritize false alarms per trial, abnormal recall, rejection rate and latency.
Macro-F1 and confidence intervals depend on data applicability; missing classes or
insufficient evidence must be disclosed. C3 may report unavailable or no demonstrated
improvement. A working shadow ML experiment need not replace the safety fast path.

## Existing page changes when results arrive

- Keep running state, trial source, checkpoints, evidence and exports.
- Replace the pending C0–C3 panel only when a validated report is available.
- Display method rows and comparable metrics, with sample counts/units visible.
- Add dataset/split/model provenance, limitations and failure examples.
- Use a small chart only if values are comparable and sufficiently supported;
  the table remains the primary presentation and exportable source of truth.
- Provide loading/not-found/failed/partial-report states; no placeholder accuracy.

## Acceptance

B reproduces the JSON from versioned inputs; C rejects malformed or unauthorized
reports; frontend displays values without re-estimating metrics. Verify fractions,
nulls, missing methods, simulation labels, slow response ordering and exports.
Until B/C handoff, the page remains metadata/evidence only. This does not complete G3.

## Reference design

The user's reference is AquaGuard Edge 全链路验证看板, Site version 1, inspected
2026-11-10. Its sidebar, breadcrumb, mint cards and chain explanation inform local
presentation only. Issue/Gate counts and management features are not copied into
the operational workbench. The hosted Site and its access configuration are unchanged.
