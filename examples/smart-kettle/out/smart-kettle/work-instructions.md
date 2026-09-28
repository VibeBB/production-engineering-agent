# Work instructions — smart-kettle

Revision: 1.0

## OP01 — SMT assembly

Station: SMT
Cycle time: 20.0 s
Operators: 1
Tools: reflow oven, stencil printer
Fixtures: PCB carrier
ESD: sensitive; use grounded ESD controls
Safety hazards: hot reflow surfaces
Safety precautions: Use thermal gloves for oven service.
Linked inspections: IN-01 (aoi, CH-01)

| Major step | Key points | Reasons |
| --- | --- | --- |
| Load the PCB and apply solder paste. | Verify board revision and stencil alignment. | Prevents wrong-revision builds and solder bridging. |
| Place components and reflow. | Use the released placement file and qualified thermal profile. | Maintains component position and solder-joint integrity. |

## OP02 — THT component soldering

Station: THT
Cycle time: 18.0 s
Operators: 1
Tools: selective soldering system
Fixtures: THT board nest
ESD: sensitive; use grounded ESD controls
Safety hazards: hot solder and flux fumes
Safety precautions: Keep extraction running and use heat-resistant tools.
Linked inspections: None

| Major step | Key points | Reasons |
| --- | --- | --- |
| Insert through-hole components. | Check polarity and component height before soldering. | Ensures correct function and mechanical fit. |

## OP03 — Programming and factory functional test

Station: PROGRAM-FCT
Cycle time: 25.0 s
Operators: 1
Tools: UART fixture, programming station
Fixtures: keyed programming nest
ESD: sensitive; use grounded ESD controls
Safety hazards: None specified
Safety precautions: None specified
Linked inspections: IN-02 (fct, CH-03)

| Major step | Key points | Reasons |
| --- | --- | --- |
| Load the released firmware and enter guarded test mode. | Assert the strap and present the production UART token. | Prevents accidental entry into factory mode in the field. |
| Run test commands and provision the unit. | Verify responses, write the serial, and confirm lockout. | Ensures traceability and prevents field re-entry. |

## OP04 — Mechanical assembly

Station: ASSEMBLY
Cycle time: 32.0 s
Operators: 1
Tools: torque driver
Fixtures: kettle-body assembly fixture
ESD: not designated
Safety hazards: pinch points at the handle joint
Safety precautions: Keep fingers clear of the closing joint.
Linked inspections: None

| Major step | Key points | Reasons |
| --- | --- | --- |
| Join the body, handle, base, and control board. | Route wiring away from hot surfaces and moving joints. | Avoids insulation damage and pinched conductors. |

## OP05 — Hipot and earth-bond safety tests

Station: SAFETY-TEST
Cycle time: 20.0 s
Operators: 1
Tools: earth-bond tester, hipot tester
Fixtures: interlocked safety-test enclosure
ESD: not designated
Safety hazards: hazardous test voltage and high test current
Safety precautions: Keep the enclosure interlock closed during test., Discharge the unit before removal.
Linked inspections: IN-03 (hipot, CH-05); IN-04 (ground_bond, CH-02)

| Major step | Key points | Reasons |
| --- | --- | --- |
| Connect the unit and run hipot and earth-bond tests. | Confirm the interlock and approved test limits before start. | Protects the operator and verifies electrical safety. |
| Record results and quarantine failures. | Do not release a failed or incomplete safety test. | Maintains traceability and prevents unsafe shipment. |

## OP06 — Final inspection and packing

Station: PACK
Cycle time: 15.0 s
Operators: 1
Tools: carton scale, label printer
Fixtures: None specified
ESD: not designated
Safety hazards: None specified
Safety precautions: None specified
Linked inspections: IN-05 (visual, CH-04)

| Major step | Key points | Reasons |
| --- | --- | --- |
| Inspect the finished unit and pack accessories. | Match the serial label to the production record. | Preserves traceability and prevents missing-content escapes. |
