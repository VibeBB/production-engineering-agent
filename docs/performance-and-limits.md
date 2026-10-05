# Performance and limits

## Smart-kettle measurements

Measured on 2026-10-05 with the locked local `uv` environment and the
`examples/smart-kettle/smart-kettle.prodeng.json` contract. Each duration is
one wall-clock invocation including `uv run` startup; these are observations,
not a benchmark median.

| Operation | Command/output | Elapsed |
| --- | --- | ---: |
| Author (CLI rendering disabled by default) | `uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json --out /tmp/prodeng-perf-author` | 0.213 s |
| Render from contract | `uv run python -m prodeng render examples/smart-kettle/smart-kettle.prodeng.json --out /tmp/prodeng-renders` | 0.998 s |

The render used `DejaVuSans.ttf`, recorded in `renders/index.json`, and
produced ten 1600-pixel-wide PNGs. Sizes are unoptimized file bytes:

| PNG | Dimensions | Bytes |
| --- | ---: | ---: |
| `control-plan.png` | 1600 × 722 | 84,352 |
| `factory-test-spec.png` | 1600 × 1200 | 111,296 |
| `line-balance.png` | 1600 × 744 | 67,421 |
| `pfmea.png` | 1600 × 402 | 38,469 |
| `work-instruction-OP01.png` | 1600 × 468 | 44,686 |
| `work-instruction-OP02.png` | 1600 × 396 | 35,388 |
| `work-instruction-OP03.png` | 1600 × 376 | 36,862 |
| `work-instruction-OP04.png` | 1600 × 396 | 37,469 |
| `work-instruction-OP05.png` | 1600 × 514 | 50,999 |
| `work-instruction-OP06.png` | 1600 × 304 | 26,696 |
| **Total** |  | **533,638** |

## Pagination and MCP payload

The renderer enforces a 6,000-pixel maximum image height. Smart-kettle's
tallest sheet was 1,200 pixels and needed no pagination. A synthetic
work-instruction render with 190 repeated work elements produced three
pages at 5,920, 5,920, and 2,628 pixels; each remained at or below the cap.

For `prodeng_render` on the same contract, the serialized MCP
`CallToolResult` was **713,547 bytes**: 1,032 bytes of JSON text content and
711,532 base64 image-data characters across ten `image/png` blocks. The
measurement serializes the tool result model with compact JSON separators;
it does not include outer JSON-RPC or transport framing.

## Limits

- The 6,000-pixel cap limits each image, not the total number of pages or
  total response size. Long contracts can produce multiple PNGs and large
  inline MCP responses.
- Font selection tries `PRODENG_RENDER_FONT`, then the configured system
  font candidates, then Pillow's default. The bundled/default font may lack
  non-Latin glyphs; use a suitable font override when multilingual image
  output is required.
- A digest-locked tools image published before Pillow was added can still run
  authoring with rendering enabled: renders are skipped with a diagnostic
  reason, while explicit render commands fail clearly. Rendering requires a
  newly published image containing Pillow and an updated
  `docker/image-digests.json` lock.
- Pillow version is part of byte determinism. Identical inputs and the same
  Pillow version produce deterministic PNG bytes; different renderer/font
  environments are not claimed to produce identical pixels.
- Timings and payload sizes vary with hardware, font, Pillow version, and
  contract content. These measurements are one local run, not capacity or
  latency guarantees.
