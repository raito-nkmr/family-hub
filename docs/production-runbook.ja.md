# 本番構築・リリースRunbook

English version: [production-runbook.md](./production-runbook.md)

## 目的

Family Hubの本番環境を、リポジトリ内のレビュー済み設定から再現するための手順を定める。目標設計は
[`deployment.md`](./deployment.md)、現在の公開テスト環境は[`production-state.md`](./production-state.md)を参照する。

本書の本番構成は、ホスト上で動くCaddyとFastAPI、Docker Composeで動く専用PostgreSQL、および外付けHDDを使用する。
開発用`compose.yaml`とそのDB volumeは本番構成へ含めない。

## 秘密情報の境界

次のファイルはホスト上で管理し、リポジトリへコピー、表示、diff、またはcommitしない。

- `/etc/family-hub/backend.env`: FastAPI設定と本番`DATABASE_URL`
- `/etc/family-hub/database.env`: PostgreSQLコンテナ初期化設定
- Cloudflare Tunnelトークン
- Web Push秘密鍵

`database.env`の項目名は`deploy/database.env.example`を参照する。DBパスワードは開発環境と共有せず、
`backend.env`内の`DATABASE_URL`と同じ認証情報を手動で設定する。本番DBのホスト側ポートは`5433`とする。

エージェントは`.env`と上記の秘密ファイルを操作しない。作成と変更は運用管理者が直接行う。

## 本番DBの境界

| 項目 | 開発 | 本番 |
| --- | --- | --- |
| Compose file | `/path/to/repository/compose.yaml` | `/opt/family-hub/current/deploy/compose.production.yaml` |
| Compose project | `fastapi-react-playground` | `family-hub-production` |
| Host port | `127.0.0.1:5432` | `127.0.0.1:5433` |
| Volume | `fastapi-react-playground_postgres-data` | `family-hub-production-postgres-data` |
| DB environment | `backend/.env` | `/etc/family-hub/database.env` |
| Lifecycle | 開発者が`docker compose`で操作 | `family-hub-database.service`が操作 |

本番volumeはCompose外部volumeとして事前作成する。これにより、`docker compose down --volumes`は本番volumeを
削除しない。意図的な本番DB初期化では、サービス停止後にvolumeを明示的に削除する必要がある。

## リリースに含めるもの

`/opt/family-hub/releases/<timestamp>/`は少なくとも次の構成とする。

```text
<release>/
├── backend/
│   ├── .venv/
│   ├── alembic/
│   ├── alembic.ini
│   ├── app/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── requirements.lock
├── frontend/
│   └── dist/
└── deploy/
    └── compose.production.yaml
```

`.env`、テストデータ、Pythonキャッシュ、`frontend/node_modules`、および開発用Compose volumeをreleaseへ含めない。
Frontendはrelease作成前に`npm ci`、検証、`npm run build`を完了させ、`dist/`だけを配置する。Backendのvenvは
releaseごとにコミット済みの`requirements.lock`から作成する。互換範囲の入力は`requirements.txt`と
`requirements-dev.txt`に保持し、変更時は開発環境で`make backend-lock`を実行する。

releaseルートでの作成例は次のとおり。

```bash
python3.13 -m venv backend/.venv
make backend-sync
```

## 初回構築前の検証

Caddyfileの検証ではアクセスログ出力先も開かれるため、先にCaddy専用ユーザーで書き込める状態にする。

```bash
sudo install -d -o caddy -g caddy -m 0750 /var/log/family-hub
sudo touch /var/log/family-hub/access.log
sudo chown caddy:caddy /var/log/family-hub/access.log
sudo chmod 0640 /var/log/family-hub/access.log
```

その後、リポジトリで次を実行する。

```bash
FAMILY_HUB_DATABASE_ENV_FILE="$PWD/deploy/database.env.example" \
  docker compose --file deploy/compose.production.yaml config --quiet

sudo caddy validate --config deploy/Caddyfile --adapter caddyfile

systemd-analyze verify deploy/systemd/*.service deploy/systemd/*.timer
```

さらに、BackendとFrontendの通常のチェックを完了させる。Caddyとsystemdの検証結果は、インストール先ホストの
バージョンでも再確認する。

## 初回構築

以下は運用管理者がUbuntuホスト上で実施する。秘密ファイルを先に手動作成し、所有者と権限を確認する。

1. `/etc/family-hub/database.env`を`root:family-hub`、`0640`で作成する
2. `/etc/family-hub/backend.env`の`DATABASE_URL`を本番DBの`127.0.0.1:5433`へ向ける
3. `family-hub-production-postgres-data` volumeを作成する
4. 新しいreleaseを配置し、`/opt/family-hub/current`を切り替える
5. Caddyfileとsystemd unitをインストールする
6. systemdをreloadし、本番DBを起動する
7. Alembicを適用する
8. 初期システム管理者を作成する
9. Backend、Caddy、cloudflaredを起動またはreloadする

本番volume作成とDBサービス起動の例は次のとおり。

```bash
sudo docker volume create family-hub-production-postgres-data
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-database.service \
  /etc/systemd/system/family-hub-database.service
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-backend.service \
  /etc/systemd/system/family-hub-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now family-hub-database.service
```

Alembicは本番環境ファイルを読み込む一時unitとして実行する。

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/alembic upgrade head
```

初期管理者の作成はパスワード入力用PTYを付ける。

```bash
sudo systemd-run --wait --pty --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.create_user --username owner --system-role admin
```

ユーザー名は運用時の値へ置き換える。パスワードをコマンド引数、環境変数、ログへ含めない。

## 公開テスト環境からの切り替え

現在の`fastapi-react-playground-db-1`はリセット可能な公開テストDBである。本番相当構成の初回リハーサルでは、
このDBを移行せず、新しい本番専用volumeへ空のスキーマを作る。

切り替え時は次の順序を守る。

1. `family-hub-backend.service`を停止する
2. 新しい本番DB volumeと秘密ファイルを準備する
3. 新releaseとsystemd unitを配置する
4. `family-hub-database.service`を起動し、Compose healthcheckの成功を確認する
5. Alembicを適用し、初期管理者を作成する
6. Backendを起動し、loopbackのhealthとreadinessを確認する
7. Caddyを検証してreloadする
8. 独自ドメインからhealth、ログイン、招待、主要機能を確認し、readinessが`404`になることを確認する
9. 問題がなければ旧開発DBコンテナを停止する

旧開発DBの削除は、新しい本番相当DBで必要な確認が完了してから行う。

## Cloudflareとブラウザキャッシュ

Cloudflare DashboardのCaching設定では、Browser Cache TTLを`Respect Existing Headers`にする。Cloudflareの既定4時間を
選ぶと、Caddyが返す短いTTLや再検証指示より長い`max-age`へ上書きされる場合がある。

公開hostnameを対象に、少なくとも次のCache Ruleを設定する。

| 条件 | Cache eligibility | 目的 |
| --- | --- | --- |
| URI Path starts with `/api/` | Bypass cache | 認証・認可付きAPIをEdgeへ保存しない |
| URI Path equals `/sw.js` | Bypass cache | Service Workerの更新確認をEdge cacheで遅延させない |

HTMLをCache Everythingの対象にしない。設定後、外部経路で次を確認する。

```bash
curl -sSI https://<public-host>/
curl -sSI https://<public-host>/invitations
curl -sSI https://<public-host>/sw.js
curl -sSI https://<public-host>/assets/<current-hash>.js
curl -sSI https://<public-host>/api/v1/health
```

期待する結果は次のとおり。

- `/`とSPA URL: `Cache-Control: no-cache, must-revalidate`
- `/sw.js`: `Cache-Control: no-store`、Cloudflareで`DYNAMIC`または`BYPASS`
- `/assets/*`: `public, max-age=31536000, immutable`、2回目以降にCloudflareで`HIT`
- `/api/*`: `private, no-store`、Cloudflareで`DYNAMIC`または`BYPASS`

Cloudflareのcache purgeだけでは、すでにブラウザへ保存された4時間キャッシュは消えない。設定変更直後の確認では、
SafariのWebサイトデータ削除または別ブラウザも併用する。

## 運用timerの導入

本番運用開始前に、DB backup、写真integrity、trash purgeの順で1つずつ導入する。unitを配置しただけではtimerを
有効化せず、各serviceを手動実行して成功条件を確認してからtimerを有効にする。

任意のdead-man監視を使う場合は、unitを起動する前に`/etc/family-hub/backend.env`へ対応するping URLを設定する。

| Job | Environment variable |
| --- | --- |
| DB backup | `MONITORING_PING_URL_DB_BACKUP` |
| 写真integrity | `MONITORING_PING_URL_INTEGRITY` |
| Trash purge | `MONITORING_PING_URL_TRASH_PURGE` |
| Web Push配送 | `MONITORING_PING_URL_NOTIFICATIONS` |
| 掃除期限通知 | `MONITORING_PING_URL_CLEANING_NOTIFICATIONS` |
| 2台目ストレージbackup | `MONITORING_PING_URL_SECONDARY_BACKUP` |

各URLにはHealthchecks互換の基底ping URLを指定する。unitは開始時に`/start`、成功時に基底URL、失敗時に`/fail`へ
POSTする。未設定時はno-opであり、監視URLの実値はリポジトリやRunbookへ記録しない。

### 前提ツール

DB backupコマンドはホスト上の`pg_dump`を使用する。PostgreSQL 18サーバーをdumpできる互換バージョンをインストールし、
次を確認する。2026年7月19日に`pg_dump`と`pg_restore` 18.4の導入を確認済みであり、クライアントバージョンの前提は
満たしている。同日にbackup serviceの手動実行と一時DBへの初回復元試験も完了した。PostgreSQLまたはクライアントを
更新した場合は、互換性と復元試験を再確認する。

```bash
command -v pg_dump
pg_dump --version
command -v pg_restore
pg_restore --version
command -v rsync
```

`rsync`は2台目HDDへのsnapshotを有効にする場合だけ必要である。2台目HDDがない間は
`family-hub-secondary-backup.timer`を有効にしない。

### unitのインストール

```bash
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-db-backup.service \
  deploy/systemd/family-hub-db-backup.timer \
  deploy/systemd/family-hub-integrity.service \
  deploy/systemd/family-hub-integrity.timer \
  deploy/systemd/family-hub-trash-purge.service \
  deploy/systemd/family-hub-trash-purge.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
```

### DB backup

```bash
sudo systemctl start family-hub-db-backup.service
sudo systemctl status family-hub-db-backup.service --no-pager
sudo journalctl -u family-hub-db-backup.service -n 50 --no-pager
```

次を確認するまでtimerを有効にしない。

- serviceが成功終了する
- HDDの`database-backups/YYYY/MM/`へ`.dump`と`.json`が作成される
- ファイルが一般ユーザーから読めない
- 管理画面のmaintenance履歴が`succeeded`になる
- 作成したdumpを一時DBへ復元できる

確認後に有効化する。

```bash
sudo systemctl enable --now family-hub-db-backup.timer
```

#### 一時DBへの復元試験

実際に作成されたdumpを指定し、loopbackだけで待ち受ける使い捨てPostgreSQLへ復元する。次の例の
`BACKUP`は検証対象の実ファイルへ置き換える。

```bash
BACKUP=/mnt/family-hub-storage/database-backups/YYYY/MM/family-hub-YYYYMMDDTHHMMSSZ.dump

docker run --detach --rm \
  --name family-hub-restore-drill \
  --env POSTGRES_HOST_AUTH_METHOD=trust \
  --env POSTGRES_DB=restore_drill \
  --publish 127.0.0.1:5434:5432 \
  postgres:18

docker exec family-hub-restore-drill \
  pg_isready -U postgres -d restore_drill

sudo -u family-hub pg_restore \
  --host 127.0.0.1 \
  --port 5434 \
  --username postgres \
  --dbname restore_drill \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  "$BACKUP"

docker exec family-hub-restore-drill \
  psql -U postgres -d restore_drill -v ON_ERROR_STOP=1 -c \
  "SELECT version_num FROM alembic_version;
   SELECT count(*) AS users FROM users;
   SELECT count(*) AS admins FROM users WHERE system_role = 'admin';"

docker stop family-hub-restore-drill
```

`pg_isready`が`accepting connections`を返すまで待ってから`pg_restore`へ進む。
`POSTGRES_HOST_AUTH_METHOD=trust`はloopback限定の一時コンテナだけで使用し、本番DBには使用しない。復元や確認が失敗した
場合も一時コンテナを停止する。この試験では本番DBを変更しない。

custom-format dumpには、スナップショット取得時点の`maintenance_runs`も含まれる。バックアップ自身や同時実行中の
保守ジョブは、復元先で`running`のまま見える場合がある。復元後に実行中のプロセスは引き継がれないため、Backendを
起動する前に該当行を中断扱いへ変更する。

```bash
sudo docker exec family-hub-production-db-1 \
  psql -U family_hub -d family_hub -v ON_ERROR_STOP=1 -c \
  "UPDATE maintenance_runs
   SET status = 'failed',
       finished_at = CURRENT_TIMESTAMP,
       error_code = 'interrupted_by_restore',
       error_message = 'Marked interrupted after database restore'
   WHERE status = 'running';"
```

2026年7月19日の初回試験では、PostgreSQL 18の一時DBへ`pg_restore --exit-on-error`で復元し、Alembic revision、
26テーブル、ユーザー件数、およびsystem role `admin`の保持を確認した。一時DBは検証後に削除した。

### 写真integrity

最初は原本全体のSHA-256再計算を行わない通常検査を実行する。

```bash
sudo systemctl start family-hub-integrity.service
sudo systemctl status family-hub-integrity.service --no-pager
sudo journalctl -u family-hub-integrity.service -n 100 --no-pager
```

欠損、不一致、孤立ファイルを検出した場合は終了コード1となる。原因を確認し、誤検出または既知の問題として整理するまで
timerを有効にしない。成功確認後に有効化する。

```bash
sudo systemctl enable --now family-hub-integrity.timer
```

### Trash purge

Trash purgeは保持期限を過ぎた写真を完全削除する。DB backupと写真integrityが成功し、保持期間とゴミ箱の内容を確認してから
初回実行する。

```bash
sudo systemctl start family-hub-trash-purge.service
sudo systemctl status family-hub-trash-purge.service --no-pager
sudo journalctl -u family-hub-trash-purge.service -n 100 --no-pager
```

意図した対象だけが削除され、maintenance履歴が成功したことを確認してから有効化する。

```bash
sudo systemctl enable --now family-hub-trash-purge.timer
sudo systemctl list-timers 'family-hub-*' --all --no-pager
```

Web PushのVAPID設定と実機確認が完了するまでは、通知関連timerを有効にしない。
有効化前に`/etc/family-hub/backend.env`の`PUSH_ALLOWED_ENDPOINT_HOSTS`が実機の正規providerだけを含み、
`PUSH_MAX_SUBSCRIPTIONS_PER_USER`が意図した上限であることを確認する。任意hostやLAN内hostは追加しない。

VAPID設定後は、iPhoneのstandalone版Family Hubから通知を有効にし、別ユーザーによる写真共有などでOutboxを作成する。
最初の配信はserviceを手動実行し、端末への表示とクリック遷移、および秘密情報を含まないjournalを確認する。

```bash
sudo systemctl start family-hub-notifications.service
sudo systemctl status family-hub-notifications.service --no-pager
sudo journalctl -u family-hub-notifications.service -n 100 --no-pager
```

通常通知の実機配信に成功し、掃除期限通知も手動実行で確認した後にtimerを有効化する。

```bash
sudo systemctl start family-hub-cleaning-notifications.service
sudo systemctl start family-hub-notifications.service
sudo systemctl enable --now family-hub-notifications.timer family-hub-cleaning-notifications.timer
sudo systemctl list-timers 'family-hub-*notifications*' --all --no-pager
```

## 意図的な本番相当DBリセット

本番運用開始前のリハーサル中に限り、テストデータを全消去できる。対象volume名を必ず確認し、開発volumeと
取り違えない。

```bash
sudo systemctl stop family-hub-backend.service
sudo systemctl stop family-hub-database.service
sudo docker volume inspect family-hub-production-postgres-data
sudo docker volume rm family-hub-production-postgres-data
sudo docker volume create family-hub-production-postgres-data
sudo systemctl start family-hub-database.service
```

その後、Alembic適用と初期管理者作成をやり直す。本番運用開始後はこの手順を通常運用で使用せず、バックアップからの
復元手順へ切り替える。

## リリース更新

DB構成を変えない通常releaseでは次の順序とする。

1. BackendとFrontendの全チェックを通す
2. 新しいtimestamp releaseを作成する
3. Alembicのupgrade内容と戻せない変更を確認する
4. Backendを停止する
5. `current`を新releaseへ切り替える
6. Alembicを適用する
7. Backendを起動する
8. Caddy設定に変更がある場合だけ検証してreloadする
9. loopbackと独自ドメインのhealth、ログイン、主要画面を確認する
10. 問題発生時はアプリreleaseを戻す。ただしDB downgradeは自動で行わない

## 本番運用開始条件

- 本番専用DBが開発DBから分離されている
- PC再起動後にDB health、Backend、Caddy、cloudflaredが自動復旧する
- DBバックアップが別の保存先へ作成される
- バックアップを一時DBへ復元できる
- 写真整合性検査が成功する
- 認証済み主要機能の外部スモークテストが成功する
- Cloudflare、Caddy、Service Workerのキャッシュ方針が期待どおりである
- iPhone SafariでPWA、アップロード、原本表示を確認している
- [`deployment.md`](./deployment.md#本番受入チェック)の受入条件を満たす
