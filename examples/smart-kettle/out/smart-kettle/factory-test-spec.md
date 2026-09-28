# Factory test specification — smart-kettle

## Entry

Method: gpio_strap
A fixture-held strap on FTM_STRAP is sampled only during reset.

| Guard condition |
| --- |
| FTM_STRAP asserted by the keyed fixture before reset. |
| UART magic token PRODENG-FTM-v1 received before the 2-second boot timeout. |

## Field lockout

nvm_flag: Provisioning sets a write-once production-complete NVM flag that disables factory entry.

## Interface

Transport: uart; settings: 115200 baud, 8 data bits, no parity, 1 stop bit; UTF-8 newline-delimited frames.
Nets: FTM_STRAP, UART_RX, UART_TX

## Commands

| ID | Command | Request | Response | Timeout (ms) | Measures |
| --- | --- | --- | --- | --- | --- |
| TC-01 | board-and-heater-sensor-check | TEST SENSORS | SENSORS PASS | 2000 | UART_RX, UART_TX |
| TC-02 | provision-serial-and-calibration | PROVISION <serial> <calibration> | PROVISIONED <serial> | 1500 | FTM_STRAP |

## Provisioning

| Item | Source | Write once |
| --- | --- | --- |
| serial_number | MES-issued unit serial | true |
| calibration | Factory calibration fixture | true |

## Exit

Issue EXIT, restore the strap, and power-cycle; confirm normal firmware boot.

## Duration budget

Command timeout total: 3.5 s; maximum: 6 s.
