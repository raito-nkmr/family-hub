# 2026-07-29 ホスト再起動後のサービス停止調査 引き継ぎ

## この文書の目的

2026-07-29 に確認された NFMRC Workspace の PostgreSQL 接続エラーと、
同じホスト上の Family Hub 停止について、別Agentが調査・復旧を継続するための
事実、実施済み操作、未解決事項をまとめる。

秘密情報および `.env` の内容は確認・記載していない。

## 2026-07-29 16:23 JST 時点の結論

* Docker上のPostgreSQLがすべて停止したままになっているわけではない。
* ホストは 08:10 に正常シャットダウンされ、08:11 に再起動している。
* 再起動時に稼働中のDockerコンテナはいったん正常停止した。
* Family Hubの開発用・本番用PostgreSQLは再起動後に自動復帰し、現在も
  `healthy`。
* NFMRCのPostgreSQLは、削除済みの旧作業ディレクトリを参照する
  bind mount が原因で自動復帰できなかった。コンテナだけ再作成して復旧済み。
* Family Hubが利用できない直接原因はPostgreSQLではなく、
  `family-hub-backend.service` が停止していること。
* Family Hubバックエンドの必須依存である
  `/mnt/family-hub-storage` のストレージ装置がOSから認識されていない。
* Family Hubの停止は、NFMRCコンテナを再作成する約8時間前から発生している。
  NFMRCへの復旧操作がFamily Hubを停止させたものではない。

## 現在の状態

確認日時: `2026-07-29T16:23:27+09:00`

| 対象 | 状態 | 備考 |
|---|---|---|
| `nfmrc-workspace-db` | `healthy` | `127.0.0.1:5434` |
| `family-hub-db-1` | `healthy` | `127.0.0.1:15432` |
| `family-hub-production-db-1` | `healthy` | `127.0.0.1:5433` |
| `fastapi-react-playground-db-1` | `Exited (0)` | 2日前から停止。今回の操作対象外 |
| `docker.service` | `active (running)` | 08:11:17から稼働 |
| `caddy.service` | `active (running)` | 待受あり |
| `family-hub-database.service` | `active (exited)` | DB起動処理は成功 |
| `family-hub-backend.service` | `inactive (dead)` | 起動時の依存関係エラー |
| `/mnt/family-hub-storage` | 未マウント | 必要なブロックデバイスも未認識 |

Family Hubストレージの期待値:

```text
Mount point: /mnt/family-hub-storage
Device: /dev/disk/by-uuid/407299b9-f7a7-4600-9360-e474f9c234aa
```

2026-07-29 16:23 JST 時点では、上記UUIDのデバイスは存在せず、
`lsblk --fs` にも対象ストレージは表示されていない。

## 発生時系列

| 時刻（JST） | 事象 |
|---|---|
| 08:10:07 | `family-hub-backend.service` の正常停止開始 |
| 08:10:30 | Family Hubバックエンド停止完了。Docker DBコンテナも正常停止 |
| 08:10:36 | ホストの正常シャットダウン完了 |
| 08:11:01 | ホスト再起動 |
| 08:11:12 | Family Hubストレージマウントが依存関係エラー |
| 08:11:12 | `family-hub-backend.service` も依存関係エラー |
| 08:11:17 | Dockerデーモン起動 |
| 08:11:17 | Family HubのPostgreSQLコンテナ起動 |
| 08:11:22 | Family Hub本番PostgreSQLが `healthy` |
| 16:18頃 | NFMRC PostgreSQLの復旧作業開始 |
| 16:18:52 | NFMRC PostgreSQLコンテナ再作成・起動 |

## NFMRC PostgreSQLで発生していた問題

初期管理者作成CLIの実行時、次の接続エラーが発生した。

```text
connection to server at "127.0.0.1", port 5434 failed: Connection refused
```

`docker compose ps` ではNFMRCのサービスが起動していなかった。
既存の `nfmrc-workspace-db` コンテナは次の削除済みパスを参照していた。

```text
/home/raito/Projects/NFMRC-workspace-codex/docker/secrets/postgres_password.txt
```

現在のワークスペースにある秘密ファイルは、内容を読まず存在だけを確認した。

```text
/home/raito/Projects/NFMRC-workspace/docker/secrets/postgres_password.txt
```

## 実施済み操作

以下の操作だけを実施した。

1. Docker、systemd、待受ポート、ジャーナルを読み取り確認。
2. `nfmrc-workspace-db` を現在のCompose定義で強制再作成。
3. NFMRCの既存named volumeは保持。
4. NFMRC PostgreSQLのhealth check成功を確認。
5. NFMRCのAlembicリビジョンが `202606260001 (head)` であることを確認。

NFMRCコンテナの再作成コマンド:

```bash
cd /home/raito/Projects/NFMRC-workspace
docker compose up -d --force-recreate db
```

実施していない操作:

* PostgreSQLデータベースのリセット
* Docker volumeの削除
* Family Hubバックエンドの起動
* Family Hubストレージのマウント
* Family Hubまたは他プロジェクトのコンテナ再作成
* `.env` や秘密ファイルの読み取り・変更
* NFMRC初期管理者の作成

## Family Hubバックエンドが復帰しなかった理由

`family-hub-backend.service` は次のユニットを必須依存にしている。

* `family-hub-database.service`
* `mnt-family\x2dhub\x2dstorage.mount`

データベースユニットは再起動後に成功している。一方、ストレージマウントは
必要なデバイスが存在せず、08:11:12に依存関係エラーとなった。
その結果、バックエンドも起動できなかった。

バックエンドには `Restart=on-failure` が設定されているが、今回はプロセスの
異常終了ではなくsystemdの依存関係エラーであり、自動再試行されていない。

## 次に行うこと

### 1. 物理ストレージを確認

Family Hub用ストレージの電源、USB接続、ケーブル、ハブを確認する。
デバイスが認識されるまではマウントやバックエンド起動を試みない。

認識確認:

```bash
lsblk --fs
test -e /dev/disk/by-uuid/407299b9-f7a7-4600-9360-e474f9c234aa
```

### 2. デバイス認識後にマウント

UUIDとマウント先が期待値どおりであることを確認してから実行する。

```bash
sudo systemctl start 'mnt-family\x2dhub\x2dstorage.mount'
findmnt --target /mnt/family-hub-storage
```

期待するUUID以外のデバイスを代用しない。マウント失敗時は、
`journalctl -u 'mnt-family\x2dhub\x2dstorage.mount'` を確認する。

### 3. Family Hubバックエンドを起動

ストレージのマウントと本番DBのhealth check成功を確認してから実行する。

```bash
sudo systemctl start family-hub-backend.service
systemctl status family-hub-backend.service --no-pager
```

起動後は、ローカル待受、Caddy経由の公開URL、主要API、画像読み出しを確認する。
公開URLや認証情報はこの文書には記載していない。

### 4. NFMRC初期管理者作成を再実行

NFMRC PostgreSQLは復旧済み。ユーザー自身が実際の管理者情報とパスワードを
使って実行する。

```bash
cd /home/raito/Projects/NFMRC-workspace/backend
uv run python -m app.cli.create_initial_admin \
  --email <実際の管理者メールアドレス> \
  --display-name "管理者"
```

調査時に提示された `admin@exammple.com` は `m` が1つ多いため、実際の
メールアドレスを再確認する。

## 恒久対策の検討事項

復旧後、Family Hub側の管理対象として次を検討する。

* 再起動時に外部ストレージが認識されなかった原因の確認。
* 外部ストレージ認識後にバックエンド起動を再試行できるsystemd構成。
* マウント失敗とバックエンド停止の監視・通知。
* ホスト再起動後のDB、マウント、バックエンド、Caddyの一括ヘルスチェック。
* NFMRCコンテナが削除済みワークツリーのbind mountを保持しない運用。

恒久対策を実装する前に、Family Hubリポジトリの運用・バックアップ・
ストレージ関連ドキュメントとユニット定義を確認すること。

## NFMRCリポジトリのGit状態

引き継ぎ書作成前の確認時点:

```text
branch: dev
status: origin/dev より1コミット先行、作業ツリーはクリーン
local-only commit: ed99255 docs: add initial admin setup step
```

直前の関連コミット:

```text
bb536c1 feat: add equipment location bootstrap CLI
ed99255 docs: add initial admin setup step
```

プッシュは実施していない。

この引き継ぎ書 `docs/incident-handoff-2026-07-29.md` 自体は未コミットの
新規ファイルである。
