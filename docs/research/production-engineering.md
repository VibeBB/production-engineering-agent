# Production engineering research note

Production engineering (生産技術) converts an approved product design into
a repeatable, capable, safe, and auditable production system. It connects
product requirements, process design, equipment/fixtures, inspection,
operator instructions, quality-risk control, and manufacturing feedback.
This note identifies reference frameworks for the agent; it does not
reproduce copyrighted standards or replace customer/certification
requirements.

## Practice areas and references

- **APQP, PPAP, and Control Plan — AIAG.** Advanced Product Quality
  Planning structures readiness planning across product/process
  development. Production Part Approval Process provides evidence that the
  defined process can repeatedly produce conforming product. A Control Plan
  connects process steps, product/process characteristics, measurement,
  sample frequency, reaction, and ownership. Use the current customer-
  required editions and customer-specific requirements.
- **FMEA — AIAG & VDA FMEA Handbook (2019) and IEC 60812.** Identify
  failure modes, effects, causes, prevention/detection controls, and
  action priorities. Prodeng's S/O/D and RPN projection are informative
  screening records, not a replacement for the full AIAG-VDA FMEA method
  or an automatic risk-acceptance decision.
- **Acceptance sampling — ISO 2859-1 and JIS Z 9015-1.** Attribute
  sampling by AQL depends on lot size, inspection level, and plan type.
  The prodeng core resolves only its explicitly supported single-sampling
  tables and preferred AQLs. Under prodeng's rules, critical
  safety/regulatory characteristics always use 100% inspection.
- **Electronic assembly workmanship — IPC-A-610, IPC/WHMA-A-620, and
  J-STD-001.** These provide acceptance/workmanship requirements for
  electronic assemblies, cable/harness assemblies, and soldered electrical
  assemblies respectively. Apply the contractually required revision and
  product class.
- **Boundary scan — IEEE 1149.1.** Test access architecture can improve
  board-level interconnect coverage when device/board support exists.
  Define chain access and fixture strategy in the circuit design; do not
  assume boundary scan replaces functional or safety tests.
- **Mains-product routine tests — IEC 60335-1 and IEC 62368-1.** The
  applicable product standard and certification procedure determine whether
  and how electric-strength, earth-bond, leakage, and other safety tests
  apply. **Exact voltage, duration, leakage limit, bond limit, and
  acceptance criteria must come from the applicable standard and product
  certification; the agent must not invent them.**
- **Operator training — Toyota Training Within Industry Job Instruction
  (TWI JI).** Break work into Major steps, Key points, and Reasons so
  trainers can teach a standardized method, critical points, and the
  reason each point matters. Link instruction rows to hazards and
  inspections.

## Process design and takt

The theoretical takt time is the available production time divided by
customer demand for the same period:

```text
takt_s =
  working_days_per_year
  * shifts_per_day
  * available_minutes_per_shift
  * 60
  / annual_demand_units
```

This is a demand pacing target, not a cycle-time measurement or an
unconditional promise of line capacity. Compare each station's summed
operation cycle time with takt. Include realistic breaks, planned downtime,
changeovers, yield, staffing, bottlenecks, and production mix in the
underlying approved capacity analysis. A null cycle time stays unknown.

## Inspection and reaction planning

Choose inspection method and location based on the feature and process:
SPI/AOI/AXI for assembly process checks; ICT/flying probe/boundary scan for
electrical access; FCT for product behavior; hipot for dielectric withstand;
ground bond for protective-earth continuity; burn-in only when defined by
the approved reliability/customer plan. A method name alone is not a
complete plan: specify approved equipment, acceptance source, sampling,
record, containment, escalation, and disposition reaction.

## Japanese ↔ English terminology

| Japanese | English terminology |
| --- | --- |
| 生産技術 | Production engineering; manufacturing engineering |
| 工作性／製造性 | Workability / manufacturability |
| QC工程表 | QC process chart / control plan |
| 作業指示書／作業標準書 | Work instruction / standard work |
| 出荷検査 | Outgoing inspection / final inspection |
| 工場検査モード | Factory-test mode |
| ポカヨケ | Poka-yoke / mistake-proofing |
| 治具 | Fixture / jig |
| 4M | Man, Machine, Material, Method |

## References

1. Automotive Industry Action Group (AIAG), *Advanced Product Quality
   Planning (APQP)*, *Production Part Approval Process (PPAP)*, and
   *Control Plan* manuals; use the customer-required editions.
2. AIAG and VDA, *FMEA Handbook*, 1st edition, 2019.
3. IEC 60812, *Failure modes and effects analysis (FMEA and FMECA)*.
4. ISO 2859-1, *Sampling procedures for inspection by attributes — Part 1:
   Sampling schemes indexed by acceptance quality limit (AQL) for
   lot-by-lot inspection*; JIS Z 9015-1, corresponding Japanese standard.
5. IPC-A-610, *Acceptability of Electronic Assemblies*.
6. IPC/WHMA-A-620, *Requirements and Acceptance for Cable and Wire Harness
   Assemblies*.
7. IPC J-STD-001, *Requirements for Soldered Electrical and Electronic
   Assemblies*.
8. IEEE 1149.1, *Standard for Test Access Port and Boundary-Scan
   Architecture*.
9. IEC 60335-1, *Household and similar electrical appliances — Safety —
   Part 1: General requirements*, including applicable routine-test
   provisions in Annex A.
10. IEC 62368-1, *Audio/video, information and communication technology
    equipment — Part 1: Safety requirements*.
11. Toyota Training Within Industry (TWI), *Job Instruction* training
    method and standard job breakdown (Major steps, Key points, Reasons).

Consult controlled, current editions and certification-body interpretations
for the product, market, and customer. Reference titles are for
orientation, not substituted text or a complete applicability assessment.
