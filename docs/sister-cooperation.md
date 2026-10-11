# Sister cooperation

Prodeng communicates through workspace JSON files and SHA-256 provenance.
It does not import sibling Python packages or directly edit sibling-owned
files. Requests are proposals for the sibling owner, not automatic design
changes.

## Supported imports

| Sister artifact | Import kind | Imported data |
| --- | --- | --- |
| Circuit design | `circuit-brief` | Part references, net names, and connector references. |
| Circuit connectivity | `circuit-connectivity` | Net references and connector references used by test-access checks. |
| Circuit assembly | `circuit-assembly` | Populated (non-DNP) part references; the strict `CircuitAssemblySource` mirror is re-validated by the gate. |
| Circuit part handling | `circuit-handling` | Handled part references; the strict `CircuitHandlingSource` mirror is re-validated by the gate. |
| Wire crimp table | `wire-crimp` | No extracted lists; the strict `WireCrimpSource` mirror is re-validated by the gate. |
| Wire formboard | `wire-formboard` | No extracted lists; the strict `WireFormboardSource` mirror is re-validated by the gate. |
| Mechanical design | `mech-envelope` | Named mechanical anchors. |
| Mechanical brief | `mech-brief` | No extracted lists; the enclosure `width_mm`/`depth_mm`/`height_mm` are re-read by `packaging.fit`. |
| Mechanical appearance | `mech-appearance` | Limit sample IDs; the strict `MechAppearanceSource` mirror is re-validated by the gate. |
| Wire design | `wire-contract` | Wire IDs and connector IDs. |
| UX design | `ux-contract` | Product surface IDs. |
| FPGA production programming | `fpga-production` | The FPGA device reference; the strict `FpgaProductionSource` mirror is re-validated by the gate. |
| Firmware production image | `firmware-production` | The MCU reference; the strict `FirmwareProductionSource` mirror is re-validated by the gate. |

Each import records the workspace-relative source path and SHA-256 in the
contract. `imports.fresh` fails when a source changes and is unknown if its
source is missing.

circuit-agent writes `<name>.circuit-assembly.json` from the KiCad board
(`python -m circuit assembly`): every placed footprint with its side, mount
attribute (`smd`/`tht`), DNP flag and position. List the board sides each
`smt`, `tht` or `selective_solder` operation assembles in
`operations[].sides`. `circuit.assembly` emits one check per populated
mount/side group (for example `smd:bottom`) and fails when no operation of a
matching kind covers that side; with a `circuit-brief` import it also fails
when the board does not place a brief part. A changed or malformed artifact
fails; a missing artifact, an incomplete circuit export (a part without a
mount attribute) or a board with no populated parts is unknown.

circuit-agent writes `<name>.circuit-handling.json` from the brief part
`handling` facts (`python -m circuit handling`): MSL, peak reflow temperature,
ESD sensitivity and the datasheet source. `circuit.handling` emits `esd`
(every `smt`/`tht`/`selective_solder` operation is `esd_sensitive` when any part
is), one `reflow:<OP>` check per `smt` operation (`reflow_peak_c` at or below
the coolest part rating, because every part rides through each reflow pass;
missing is unknown) and `msl` (every `smt` operation has `floor_life_control`
when any part is above MSL 1). A changed or malformed artifact fails; a missing
artifact or an export with parts lacking handling facts is unknown.

fpga-agent writes `<design>.fpga-production.json` only after a passing full
gate run. Bind its device to the `programming` operation that loads it with
`operations[].programs` (for example `["U1"]`). `fpga.programming` fails when
no programming operation lists the device, when the artifact is malformed or
changed since import, when the target is volatile `sram` instead of `flash`,
or when the bitstream next to the artifact no longer has the gated sha256 or
size; an unreadable artifact or bitstream is unknown. The pass detail carries
the openFPGALoader command for the station. prodeng never programs hardware.

mechanical-agent writes `<name>.mech-appearance.json` from its brief's
`appearance` block: the viewing condition (distance, illuminance, time,
angle, source), each face's cosmetic class A/B/C with defect limits, and
the limit samples — one `accept` (worst part still shipped) and one `reject`
(mildest part refused) per class A/B defect limit. List both sample IDs in a
`visual` inspection's `limit_samples`. `appearance.limit_samples` emits one
check per class A/B face defect and fails when no visual inspection holds
the pair, when the holding inspection's characteristic is `variable`, or
when the artifact is malformed or changed since import; an unreadable
artifact is unknown. The pass detail carries the inspections, the defect
bound, and the viewing condition. Class C limits without samples need no
inspection. prodeng owns the physical samples; mech owns their criteria.

firmware-agent writes `<name>.fw-production.json` only after a passing full
gate run: the ELF path, sha256 and size, the MCU part/package, and — when its
`ftm` block pins this contract's `factory-test-spec.json` — that spec's
sha256 and command ids. Bind the MCU reference with `operations[].programs`
as for FPGA devices; one device may come from only one programming import.
`firmware.programming` fails when no programming operation lists the MCU,
when the artifact is malformed or changed since import, when the ELF next to
it no longer has the gated sha256 or size, when the contract declares a
`factory_test_mode` but the firmware was gated without it or against a
different `factory-test-spec.json` (the sha256 of the bytes `prodeng project`
writes) or a different command set, and when the firmware still serves a
spec this contract no longer declares. An unreadable artifact or ELF is
unknown. Flashing stays a host-only, human-confirmed station step.

Intake photos are materialized by the attachment hook
for review; they are not contract import kinds.

## UX out-of-box packaging handoff

UX-creator lists the box contents in its contract `oobe.in_box`, top first
in the order the user needs them during the out-of-box experience.
Import the UX contract (`ux-contract`, sha256-pinned) and declare where
each item sits in the carton under `packaging.contents`. `packaging.oobe`
re-reads the pinned UX contract and fails when an item is not packed, an
unlisted item is packed, a packing step is not a `packing` operation, or
an item UX needs earlier sits in a lower layer than a later one.

## Mechanical packaging handoff

Import mechanical-agent's design brief (`<name>.brief.json`) as
`mech-brief`; its enclosure outer size is the product envelope packed into
the carton declared in `packaging`. `packaging.fit` re-reads the pinned
brief and fails when it changed, is malformed, or the packed block
(`arrangement` × envelope + cushion on both sides) exceeds the carton on any
axis; `packaging.mass` and `packaging.stack` check gross mass and pallet
compression against cited limits. Transport drop or vibration testing
(ISTA) and shipping labels stay outside the contract.

## Wire crimp handoff

wire-agent writes `<contract_id>.wire-formboard.json` (`python -m wire
formboard`): every route flattened 1:1 with segment stations and the wires
laid on it. `wire.formboard` fails when the artifact changed since import,
is malformed, lists wires shorter than their route, or no `harness`
operation lists the fixture `formboard:<contract_id>`; it is `unknown` when
the file is missing or wire declared no route. A pass reports the longest
route in mm (the board length) and the holding operations.

wire-agent writes `<contract_id>.wire-crimp.json` (`python -m wire crimp`):
each crimp condition (terminal, wire gauge, crimp height and tolerance,
minimum pull force, applicator, cited application specification) with the
wire ends it crimps. Bind a variable characteristic to a condition with
`crimp: {condition, quantity}` — `crimp_height` in mm or `pull_force` in N.
`wire.crimp` emits one check per condition and quantity
(`CC1:crimp_height`, `CC1:pull_force`) and fails when no characteristic
controls it, when its limits are looser than the table (height outside
nominal ± tolerance, pull-force LSL below the minimum) or when it is not
inspected on a `harness` operation; a characteristic bound to a condition
the table does not hold fails. A changed or malformed artifact fails; a
missing artifact or an incomplete wire table (`verdict: fail`) is
`unknown`.

## Simulation predictions

A variable characteristic can pin one check of a simulation-agent
`sim-report.json` (`simulation.report_path`, `sha256`, `check_id`). The
`sim.prediction` gate passes only when the report is unchanged, simulation
passes that check, and its predicted value lies inside the characteristic's
`[lsl, usl]` window; the detail reports the headroom to the nearest limit.
A changed report or a simulation fail fails; a missing report, check, or
finite prediction is unknown. Factory measurements are not imported; the
link only proves the design is predicted to fall inside the production
test window.

## Outbound requests and inbound sibling replies

`prodeng_author` and `prodeng_requests` generate
`*.prodeng-request.json` schema-v2 proposals. Authoring places requests
beside the contract; `prodeng_requests` defaults there and accepts an
explicit output directory. Every request binds the contract and its
imported artifacts by path and SHA-256. The current derivation rules are:

| Target | Topic | Derivation |
| --- | --- | --- |
| `firmware` | `factory-test-mode` | An FTM is present. |
| `circuit` | `test-access` | FTM nets or measurements, a failed access check, or GPIO-strap entry calls for circuit-side test access. |
| `mech` | `fixtures` | One or more contract operations declare fixtures. |
| `wire` | `harness-test` | One or more operations have kind `harness`. |
| `doc` | `work-instructions` | Always derived for controlled instructions and inspection/control-plan typesetting. |

The schema also recognizes `fpga`, `ux`, `dashboard`, `sim`, and `bard` as
target names, but no automatic request derivation currently emits those
targets. Prodeng reads sibling `*.prodeng-response.json` v2 files and
reports their status and hash freshness with `prodeng_liaison`; a stale,
malformed, mismatched, or missing reply is not a gate verdict.

## UX-creator SLP v2

Prodeng accepts `liaison/<id>.ux-request.json` files when they validate as
strict SLP v2, target `prodeng`, and use an ID matching the filename stem.
An inbox entry reports stage, risk, purpose, dependencies, state, and detail.
Input hash changes or changed prodeng-response input hashes take precedence
and yield `stale`. Otherwise a valid prodeng response is `answered`; a
request whose dependencies lack valid `done` responses is `blocked`; the
remaining request is `new`. Malformed files are listed separately. The
inbox verdict itself is informational and returns pass.

The liaison agent answers every new or stale request with
`prodeng_ux_respond`. It can acknowledge accepted/in-progress work, complete
it, or use needs-info/deferred/rejected with a substantive reason. A `done`
reply requires at least one existing artifact, at least one gate verdict
with no fail/unknown results, and event IDs for real decision and impression
records.
When a contract path is supplied, prodeng runs the deterministic gates and
rejects caller-supplied gate results that disagree.

High-risk request rationale must cite a recognized UX job ID and declared
job source. The current accepted text patterns are intentionally limited;
their cross-check heuristics remain an improvement item. See
[Contracts](contracts.md) for the schemas and [Commands](commands.md) for
CLI entry points.

## Change control (ECR/ECO)

A change to a file that another agent pins by sha256 goes through
UX-creator's change records, never a silent re-pin. There is no human
approval step.

1. Raise `<id>.ecr.json` with the reason, the proposal and each file to
   change with its current sha256.
2. After regenerating, write `<id>.eco.json` with each file's `before` and
   `after` sha256, the gate report that passed it (verdict `pass`, citing
   the `after` sha256) and the AI review findings with their dispositions.
   A `blocker` closes only as `fixed`, and the author cannot review its own
   change.
3. `ux change <eco>` (MCP `ux_change_check`) finds every consumer that pins
   a changed file. It fails if one still pins the old sha256, or re-pinned
   without being listed in the ECO.

AI review findings can only stop a change. This plugin's deterministic
gates and the change check decide. The record formats are in
[UX-creator-agent `docs/sister-cooperation.md`](https://github.com/VibeBB/UX-creator-agent/blob/main/docs/sister-cooperation.md#change-control-ecreco-and-design-review).
