# Production engineering report — smart-kettle

Revision: 1.0
Verdict: **pass**
Takt: 72.000 s/unit

## Gate checks

| Check | Subject | Status | Measured | Limit | Detail |
| --- | --- | --- | --- | --- | --- |
| coverage.characteristic | CH-01 | pass | 1 | >=1 | inspection coverage present |
| coverage.characteristic | CH-02 | pass | 2 | >=1 | inspection coverage present |
| coverage.critical_full | CH-02 | pass | 2 | >=1 | full inspection present |
| coverage.characteristic | CH-03 | pass | 1 | >=1 | inspection coverage present |
| coverage.characteristic | CH-04 | pass | 1 | >=1 | inspection coverage present |
| sampling.plan | IN-01 | pass | 80 | 1000 | J, Ac 1, Re 2 |
| sampling.plan | IN-05 | pass | 80 | 1000 | J, Ac 3, Re 4 |
| takt.station | ASSEMBLY | pass | 32.0 | 72.0 | station total compared with takt |
| takt.station | PACK | pass | 15.0 | 72.0 | station total compared with takt |
| takt.station | PROGRAM-FCT | pass | 25.0 | 72.0 | station total compared with takt |
| takt.station | SAFETY-TEST | pass | 20.0 | 72.0 | station total compared with takt |
| takt.station | SMT | pass | 20.0 | 72.0 | station total compared with takt |
| takt.station | THT | pass | 18.0 | 72.0 | station total compared with takt |
| ftm.present | smart-kettle | pass | declared | factory_test_mode required | FCT inspection requires a declared factory-test mode |
| ftm.entry_guard | smart-kettle | pass | 2 | >=2 | entry conditions |
| ftm.lockout | smart-kettle | pass | nvm_flag | not none | Provisioning sets a write-once production-complete NVM flag that disables factory entry. |
| ftm.duration | smart-kettle | pass | 3.5 | 6.0 | sum of command timeouts |
| ftm.command_used | TC-01 | pass | covers=1, inspections=1 | covers >=1 CH and used >=1 IN | command coverage and inspection usage |
| ftm.command_used | TC-02 | pass | covers=1, inspections=1 | covers >=1 CH and used >=1 IN | command coverage and inspection usage |
| ftm.station_fit | OP03 | pass | 3.5 | 25.0 | timeout budget compared with operation cycle time |
| dft.test_access | FTM_STRAP | pass | present | present in circuit import | circuit test access net |
| dft.test_access | UART_RX | pass | present | present in circuit import | circuit test access net |
| dft.test_access | UART_TX | pass | present | present in circuit import | circuit test access net |
| pfmea.controls | FM-01 | pass | 1 | >=1 | inspection control linked |
| pfmea.high_severity | FM-01 | pass | 1 | >=1 full inspection control | high-severity risk control |
| pfmea.controls | FM-02 | pass | 1 | >=1 | inspection control linked |
| work_instruction.steps | OP01 | pass | 2 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP01 | pass | hazards=1, precautions=1 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| work_instruction.steps | OP02 | pass | 1 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP02 | pass | hazards=1, precautions=1 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| work_instruction.steps | OP03 | pass | 2 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP03 | pass | hazards=0, precautions=0 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| work_instruction.steps | OP04 | pass | 1 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP04 | pass | hazards=1, precautions=1 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| work_instruction.steps | OP05 | pass | 2 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP05 | pass | hazards=1, precautions=2 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| work_instruction.steps | OP06 | pass | 1 | >=1; every step has key points | work-instruction step coverage |
| work_instruction.safety | OP06 | pass | hazards=0, precautions=0 | hazard precautions; hazards for hipot/ground-bond | safety instruction coverage |
| imports.fresh | upstream/smart-kettle.circuit-brief.json | pass | 3e7d5d37099c58dc67ddc5c72896d3faea546e09bcbb70054e6b197d37caa8ed | 3e7d5d37099c58dc67ddc5c72896d3faea546e09bcbb70054e6b197d37caa8ed | sha256 matches |

## Liaison

Requests: 4; open: 4; answered: 0; mismatched: 0.
Orphans: 0; malformed files: 0.
