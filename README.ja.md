# 生産技術エージェント

`prodeng` は、承認済みの製品要求と兄弟エージェントの設計成果物から製造計画を作成する、決定論的な生産技術コアおよび OpenHands プラグインです。QC工程表、検査・抜取計画、タクトに対するラインバランス、PFMEA、作業指示書、工場検査モード仕様、兄弟エージェント向けの構造化変更要求を生成します。

## 基本原則

- `*.prodeng.json` が唯一の正本です。`out/<product>/` の生成物と
  `*.prodeng-request.json` は正本から作る投影です。
- 合否・不明の判定を出すのは決定論的なゲートだけです。不明は合格にせず、
  LLM や画像レビューの所見でゲート判定を上書きしません。
- 兄弟エージェントとの連携は、SHA-256 の来歴情報を持つワークスペース JSON と
  `task` 委譲で行い、兄弟パッケージを直接 import しません。
- 製品安全試験の限度値・試験条件は、適用規格と製品認証手順に従います。
  エージェントが独自に値を作ることはありません。
- プラグインは Docker のツールイメージ内だけで実行します。イメージの
  digest lock が公開されるまでは `prodeng tools image not yet published/locked`
  と表示し、ホスト実行へ切り替えません。

## クイックスタート

```bash
uv sync --all-groups
uv run python -m prodeng doctor
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng requests examples/smart-kettle/smart-kettle.prodeng.json
```

Python 3.12 以降が必要です。アーキテクチャ、運用、設計判断、参考規格は
[docs/README.md](docs/README.md) を参照してください。プラグインのファイルは
[`plugins/prodeng/`](plugins/prodeng/README.md) にあります。

## 開発時の確認

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_docs.py
uv run --group sdk-check python scripts/check_plugin_load.py
```

## ライセンス

BSD-3-Clause。詳細は [LICENSE](LICENSE) を参照してください。
