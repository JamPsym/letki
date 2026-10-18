# Documentation map

Read [the project overview](../README.md) first, then [current state](current-state.md)
for accepted revisions, orders, substitutions and next work. This project is still
in development. The media host is the last planned system component, not an end
point for development.

## Architecture and next work

| Document | Purpose |
| --- | --- |
| [Attachment architecture](attachments-study-20261017.txt) | Independent V007 converter and ESP8266/SPI/X035 host; later media-host candidates |
| [X035 bring-up plan](x035-bringup-plan-20261018.txt) | Staged USB/UART, logging/gyro, SPI/Wi-Fi and PD development |
| [General firmware design](general-firmware-design.txt) | Loaded and real-time show modes, memory and host responsibilities |
| [Protocol](general-firmware-protocol.txt) | Current general-firmware binary transport |
| [v3.2 maintenance proposal](v3_2-network-update.txt) | Proposed loader; distinct from implemented firmware |

## Software and operation

- [Toolchain setup](arch-setup.md), [contributor rules](../AGENTS.md) and
  [repository/data policy](repository.md).
- [Studio and service](../host/control/README.md), [local application API](../host/control/API.md),
  [native player](../host/player/README.txt) and [music demos](music-demos.md).
- [General firmware](../firmware/general/README.txt), [UART chain](uart-chain.md),
  [separate interface demo](interface-demo.md), [I2C test](i2c-v3-test.md).
- [Earlier TUI](tui.md), [native speech demo](tts-demo.md) and
  [word/caption tools](player-word-tools.txt).

## Hardware, assembly and sourcing

- [Hardware index](../hw/README.md): active projects and their individual READMEs.
- [v3.2 study](v3_2-study.txt), [routing](v3_2-routing.txt),
  [fabrication](v3_2-fabrication-20261017.txt), [orders/bring-up](v3_2-order-and-bringup.txt).
- [v3.1 handoff](v3_1-handoff.txt), [completion](v3_1-completion-20261015.txt),
  [assembly test](v3_1-assembly-test.txt) and [qualification](v3_1-qualification.csv).
- [v4 design](v4-design.md), [v4.1 design](v4_1-design.md),
  [v4.1 orders/bring-up](v4_1-order-and-bringup.txt).
- [KiCad routing tools](kicad-routing.md), [supplier workflow](jlcone-shipping.md),
  [purchase records](../config/purchase/README.md), [external inventory setup](../config/README.md).

## Evidence and history

The [R3 firmware milestone](milestones/v3-general-r3-20261017.txt) and
[v3.2 main CAD milestone](milestones/v3_2-main-20261017.txt) identify frozen
baselines and validation limits. Additional dated files stay beside these records
so existing links, scripts and source manifests remain valid.

The previous root README is retained as [development history](development-history.md).
[Archive navigation](../archive/README.md) separates superseded sources from active
work. Raw readbacks, logs, local recordings and large evidence bundles live in
ignored `build/` and require a separate backup; their paths in dated records are
local evidence references, not promises that every artifact ships in Git.
