# Letki interface demo

Independent UART and two-board I2C test firmware for the v3/v3.1 board. See [wiring, commands and verification limits](../../docs/interface-demo.md).

```sh
make interface-demos -j4
make test
make compdb VARIANT=interface-demo
```

The SDK and board scan driver were copied from active v3; vendor notices are preserved. IDE project name: `letki_interfaces`. Application sources are in `User/`. Default mode is UART; controller and target roles use separate native build outputs. No flashing occurs during a build.
