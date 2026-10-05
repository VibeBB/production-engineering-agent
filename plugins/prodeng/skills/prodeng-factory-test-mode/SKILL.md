---
name: prodeng-factory-test-mode
description: Specify a guarded, time-bounded, field-locked factory-test-mode protocol and its firmware/circuit ownership.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - factory test mode
  - FTM
  - production test firmware
  - fixture protocol
---

# Factory-test-mode design

Read and author the `factory_test_mode` object in the production-engineering
contract; the deterministic projection is `factory-test-spec.json` and
`factory-test-spec.md`. Derive sibling requests with the `requests` CLI
command through the installed plugin launcher. Do not insert unspecified
safety limits or edit generated files.

## Required safeguards

1. **Guard entry with independent conditions.** Require at least two
   independent conditions, such as a physical strap/test pad plus a
   one-time magic token received during a short boot window. Define the
   window, allowed retries, token lifetime, and invalid-entry behavior.
   Avoid a single software command that can accidentally enter production
   test mode.
2. **Lock out in the field.** After production provisioning, make the
   entry route unavailable using an approved OTP fuse, irreversible NVM
   flag, signed lock token, or physical removal. `none` is not acceptable.
   Define manufacturing authorization and how lockout is verified.
3. **Use a fixed protocol.** Define transport settings, framing, command
   IDs, request fields, response fields, encoding, checksum/error behavior,
   and deterministic machine-parseable responses. Avoid free-form text as
   the only machine result.
4. **Bound time.** Set a positive timeout for every command and a total
   command-timeout budget no larger than the station's cycle-time budget.
   Include boot, fixture handshake, retries, and power-cycle time in the
   production station plan; the gate compares declared command timeouts
   with FTM duration and linked operation cycle time.
5. **Make provisioning write-once.** Specify approved sources and one-time
   writes for serial number, MAC address, calibration, license key, or
   device certificate. Return readback/status and reject a second write.
6. **Guard destructive actions.** Reset-to-default, erase, fuse changes,
   calibration overwrite, and similar commands must be marked destructive
   and require an explicit command flag/authorization. Omit them if the
   station does not need them.
7. **Exit cleanly.** Define a clear exit command, invalidate the session
   token, return to normal boot, and power-cycle before release from the
   fixture. Specify recovery for timeout, malformed response, and power
   interruption.
8. **Close debug access.** Do not leave JTAG/SWD enabled after field
   lockout. Document the safe fixture-side debug/test access, authorization,
   and the production verification that the access is disabled.

## Ownership

- **Firmware** owns entry-state logic, token/boot-window checks, protocol,
  deterministic responses, timeouts, command behavior, provisioning,
  destructive guards, lockout, and normal-boot exit.
- **Circuit** owns physical test points/strap resistor, safe fixture access
  to UART/SWD/JTAG signals, interface protection, labeling, and test-net
  connectivity.
- **Production engineering** owns the station command sequence, fixture
  interface, measurement coverage, time budget, traceability, and the
  test/lockout verification steps.

Keep the `TC-##` command definitions linked to inspected characteristics
and FTM inspection operations. Every command needs covered characteristics
and an inspection use; missing test access is a gate failure or unknown,
not an advisory pass.

## Vision review points

After every `prodeng_author` that renders or `prodeng_render`, inspect every
returned PNG and record one `prodeng_record_vision_review` per image. Use
`factory-test-spec` for the FTM sheet and the matching checklist for each
other sheet. Judge accuracy against the contract, ambiguity, design intent,
and whether an operator or inspector can act on the content. Review intake
photos in `intake/attachments/` with `intake-photo` and sibling
circuit/PCB/schematic or mechanical drawings with `sister-render`.
