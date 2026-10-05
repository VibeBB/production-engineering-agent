# Production Engineering Agent

`prodeng` turns an approved product design into a traceable factory-plan
package. It is for product, manufacturing, quality, test, and operations
teams that need to connect product requirements to how a product will be
built and inspected. Its outputs are planning artifacts for review, not a
product certification or a substitute for an approved manufacturing process.

## What you provide

Start with a `*.prodeng.json` contract describing the product, production
volume and shifts, requirements and assumptions, product characteristics,
process steps and cycle times, inspections, PFMEA entries, work elements,
and optional factory-test-mode design. Supply a product description and
available BOM/part references through supported sister-plugin JSON imports.
Imported files are recorded with provenance. User-attached images can be
materialized under `intake/attachments/` for visual review.

## What you receive

`prodeng author` writes deterministic projections under `out/<product>/`:

- `control-plan.csv`, `inspection-plan.json`, and `sampling-plans.json`
- `line-balance.csv` and `pfmea.csv`
- `work-instructions.md`
- `factory-test-spec.json` and `factory-test-spec.md`
- `manifest.json`, `provenance.json`, and `prodeng-report.json` /
  `prodeng-report.md`
- When rendering is enabled: PNG sheets for the control plan, PFMEA, line
  balance, factory-test specification, and each operation's work
  instruction, plus `renders/index.json`

The contract directory also receives generated `*.prodeng-request.json`
files when the contract calls for sibling work. Sibling replies use
`*.prodeng-response.json`; UX-creator requests and prodeng replies use
`liaison/*.ux-request.json` and `liaison/*.ux-response.json`. The workspace
stores decision, stage-impression, and vision-review records in
`observations/prodeng/`.

## How it works with sister plugins

Prodeng exchanges workspace files rather than importing sibling packages.
Its import adapters accept circuit briefs/connectivity, mechanical envelopes,
wire contracts, and UX contracts. It can derive versioned
`*.prodeng-request.json` files for circuit, firmware, mechanical, wire, and
documentation work when supported by the contract. Prodeng also reads
versioned sibling responses and accepts inbound UX-creator SLP v2 requests
addressed to `prodeng`, writing SHA-bound UX responses.

`bard`, `dashboard`, `fpga`, `sim`, and the `ux` request target are recognized
names in the request/response schema; they do not currently have dedicated
import adapters or automatic request derivation. A recognized name alone
does not imply an integration. See
[Sister cooperation](docs/sister-cooperation.md) for the exact boundaries.

## Start in AgentCanvas or OpenHands

Install the plugin from [`plugins/prodeng/`](plugins/prodeng/README.md) in
your OpenHands-based workspace. Plugin commands and MCP operations require
Docker and the published, digest-locked
`ghcr.io/vibebb/prodeng-tools` image. The plugin launcher fails closed if
the image lock is missing; it does not run the plugin CLI on the host.

Try a request such as:

> Build a production plan from `design/kettle.prodeng.json`. Identify open
> assumptions and do not invent certification limits.

Or use an available command such as `/prodeng:plan
design/kettle.prodeng.json`, `/prodeng:gates
design/kettle.prodeng.json`, `/prodeng:export
design/kettle.prodeng.json`, `/prodeng:ftm
design/kettle.prodeng.json`, `/prodeng:liaison liaison`, or
`/prodeng:doctor`. See [Commands](docs/commands.md) for all command forms.

## Records and visual review

The workspace keeps a durable record of important decisions, impressions at
the end of each work stage, and reviews of images. A rendered PNG is a view
of contract-derived data: inspect every returned sheet and record a
vision-review impression for it. Records explain the reasoning and evidence
behind the plan; they never change a deterministic gate verdict.

## Limits and safety

- Deterministic gates alone report `pass`, `fail`, or `unknown`; unknown is
  not a pass. LLM and image-review findings are advisory.
- The outputs are not a certification, release authorization, or validated
  production process. A qualified owner must review and approve them.
- The applicable standard and product certification procedure must provide
  hipot, earth-bond, dielectric, and other safety limits. Selecting and
  safely conducting those tests remains the user's responsibility.
- Do not enter secrets or credentials in contracts, records, or requests.
- Plugin execution is Docker-only. For non-Latin text in images, provide a
  suitable `PRODENG_RENDER_FONT`; Pillow's default font may not contain all
  required glyphs.

## Developer quickstart

The package supports Python 3.12 or newer; the current repository
development setup uses Python 3.14+ and uv 0.12.23:

```bash
uv sync --all-groups
uv run python -m prodeng doctor
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng render examples/smart-kettle/smart-kettle.prodeng.json
```

See the [documentation index](docs/README.md), especially
[Development](docs/development.md), [Workflow](docs/workflow.md), and
[Operations](docs/operations.md). The repository is licensed under
[BSD-3-Clause](LICENSE).

## 日本語

`prodeng` は、承認済みの製品設計を、根拠を追跡できる工場計画一式にまとめます。製品、製造、品質、試験、オペレーションの各チームが、製品要求と製造・検査の方法を結び付けるためのツールです。出力はレビュー用の計画資料であり、製品認証や承認済み製造工程の代わりではありません。

## 用意するもの

まず `*.prodeng.json` 契約に、製品、需要と勤務体制、要求・前提、製品特性、工程とサイクルタイム、検査、PFMEA、作業要素、必要に応じて工場検査モードの設計を記述します。製品説明と、利用可能な BOM / 部品参照は対応する sister plugin の JSON 成果物から取り込めます。取り込んだファイルには来歴情報を記録します。ユーザーが添付した画像は、目視レビュー用に `intake/attachments/` に保存できます。

## 受け取るもの

`prodeng author` は決定論的な投影を `out/<product>/` に生成します。

- `control-plan.csv`、`inspection-plan.json`、`sampling-plans.json`
- `line-balance.csv`、`pfmea.csv`
- `work-instructions.md`
- `factory-test-spec.json`、`factory-test-spec.md`
- `manifest.json`、`provenance.json`、`prodeng-report.json`、
  `prodeng-report.md`
- 描画を有効にした場合は、QC工程表、PFMEA、ラインバランス、工場検査仕様、
  各工程の作業指示書の PNG と `renders/index.json`

工程上必要な場合、契約と同じディレクトリに sister plugin 向けの
`*.prodeng-request.json` も生成します。返信は `*.prodeng-response.json`、
UX-creator との依頼・返信は `liaison/*.ux-request.json` と
`liaison/*.ux-response.json` を使います。判断、工程ごとの所感、画像レビューは
ワークスペースの `observations/prodeng/` に記録されます。

## sister plugins との連携

Prodeng は sister plugin の Python パッケージを import せず、ワークスペースの
ファイルを交換します。回路の概要・接続情報、機械の外形情報、配線契約、
UX 契約を取り込めます。契約の内容に応じて、回路、ファームウェア、機械、
配線、文書作成向けのバージョン付き `*.prodeng-request.json` を生成します。
また、sister plugin のバージョン付き返信を読み取り、prodeng 宛ての
UX-creator SLP v2 依頼を受け付け、ハッシュで結び付けた返信を作成します。

`bard`、`dashboard`、`fpga`、`sim`、および `ux` は依頼・返信スキーマで認識される名前ですが、現時点で専用の取り込み処理や自動依頼生成はありません。スキーマで名前が認識されることだけでは、連携があることを意味しません。境界の詳細は
[sister plugin 連携](docs/sister-cooperation.md)を参照してください。

## AgentCanvas / OpenHands で始める

OpenHands ベースのワークスペースに
[`plugins/prodeng/`](plugins/prodeng/README.md) からプラグインを導入します。
プラグインのコマンドと MCP 操作には Docker と、公開済みで digest lock された
`ghcr.io/vibebb/prodeng-tools` イメージが必要です。lock がない場合、プラグインは
安全側に停止し、ホスト上で CLI を実行しません。

たとえば、次のように依頼できます。

> `design/kettle.prodeng.json` から製造計画を作成してください。未解決の前提を示し、認証限度値を作らないでください。

または `/prodeng:plan design/kettle.prodeng.json`、
`/prodeng:gates design/kettle.prodeng.json`、
`/prodeng:export design/kettle.prodeng.json`、
`/prodeng:ftm design/kettle.prodeng.json`、
`/prodeng:liaison liaison`、`/prodeng:doctor` を利用できます。すべての形式は
[コマンド一覧](docs/commands.md)を参照してください。

## 記録と画像レビュー

ワークスペースには、重要な判断、各工程の終了時の所感、画像レビューを残します。
描画された PNG は契約データの表示です。返されたシートをすべて確認し、それぞれに
画像レビューの所感を記録してください。記録は計画の判断や根拠を残すものであり、
決定論的なゲート判定は変更しません。

## 制限と安全

- `pass`、`fail`、`unknown` を出すのは決定論的なゲートだけです。unknown は合格ではありません。LLM と画像レビューの所見は助言です。
- 出力は認証、リリース承認、検証済みの製造工程ではありません。資格のある担当者がレビューして承認してください。
- 耐電圧、接地導通、絶縁その他の安全試験値は、適用規格と製品認証手順に従います。値の選定と試験の安全な実施はユーザーの責任です。
- 契約、記録、依頼に秘密情報や認証情報を入れないでください。
- プラグインは Docker 内でのみ実行します。画像内に非ラテン文字を表示する場合は、適切な `PRODENG_RENDER_FONT` を指定してください。Pillow の既定フォントには必要な文字がすべて含まれない場合があります。

## 開発者向けクイックスタート

パッケージは Python 3.12 以降に対応しています。現在のリポジトリ開発環境は
Python 3.14 以降と uv 0.12.23 を使用します。

```bash
uv sync --all-groups
uv run python -m prodeng doctor
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng render examples/smart-kettle/smart-kettle.prodeng.json
```

[ドキュメント一覧](docs/README.md)、特に
[開発](docs/development.md)、[ワークフロー](docs/workflow.md)、
[運用](docs/operations.md)を参照してください。ライセンスは
[BSD-3-Clause](LICENSE) です。
