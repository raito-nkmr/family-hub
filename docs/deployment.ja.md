# 本番配信設計

English version: [deployment.md](./deployment.md)

## 目的と状態

Family Hubを自宅内外のiPhoneから同じHTTPS URLで利用するための本番配信方針を定める。本書は目標構成と
受入条件の正本である。Named Tunnel、Caddy、Uvicorn、およびreleaseは公開テストとして実ホストへ導入済みで、
独自ドメインからのアクセスとアプリ利用を確認した。本番運用はまだ開始していない。本番専用DBへの分離、主要な運用timer、
および初回復元試験は完了し、timerの次回自動実行、再起動、光回線開通後の実機受入確認が残っている。
2026年7月19日時点の実環境と本書との差異は[`production-state.md`](./production-state.md)を参照する。

アプリケーション自身の認証を主認証として維持し、初期構成ではCloudflare Accessを追加しない。公開ホスト名には
インターネットから到達できるため、health、ログイン、および招待受諾を除くデータAPIは、引き続きFamily Hubの
セッション認証と認可で保護する。

## 目標構成

本番ではCloudflareをインターネット上の公開入口、Caddyをオリジンサーバー側の唯一のHTTP入口とする。

```text
外出先・自宅のiPhone
        ↓ HTTPS
Cloudflare Edge
        ↓ Cloudflare Tunnel
cloudflared
        ↓ http://127.0.0.1:8080
Caddy
  ├── /*     → frontend/dist
  └── /api/* → http://127.0.0.1:8000
                         FastAPI
                            ├── 127.0.0.1:5433
                            │     Docker PostgreSQL
                            └── 外付けHDD
```

- 本番は固定ホスト名を持つNamed Tunnelを使用し、Quick Tunnelは開発時の一時確認に限定する
- ルーターで80番、443番、8080番、および8000番をポート転送しない
- Caddy、FastAPI、PostgreSQL、および写真ストレージをインターネットやLANへ直接公開しない
- 写真原本はCaddyの静的ファイルルートへ含めず、認証・認可付きFastAPIエンドポイントから返す
- ブラウザから見た静的コンテンツとAPIは同一オリジンとする

Cloudflare TunnelのPublished Applicationは公開ホスト名をローカルサービスへ接続できる。Quick Tunnelは公式にも
テスト用とされているため、本番経路には含めない。

## 待ち受けとプロセス境界

| Process | Listen / connection | 方針 |
| --- | --- | --- |
| `cloudflared` | Cloudflareへ外向き接続 | 外部からの着信ポートを作らない |
| Caddy | `127.0.0.1:8080` | `cloudflared`からだけ到達可能にする |
| Uvicorn | `127.0.0.1:8000` | Caddyからだけ到達可能にする |
| PostgreSQL | `127.0.0.1:5433` | 本番専用Composeで管理し、クライアントから到達不能にする |

本番DBは`deploy/compose.production.yaml`で管理し、開発用`compose.yaml`から分離する。本番Compose projectは
`family-hub-production`、volumeは`family-hub-production-postgres-data`とする。volumeはexternalとして事前作成し、
Composeの`down --volumes`では削除されないようにする。開発DBは従来どおり`127.0.0.1:5432`を使用できる。
開発用FastAPIは`127.0.0.1:8001`で待ち受け、Viteの`/api`プロキシも同ポートへ接続する。本番用FastAPIの
`127.0.0.1:8000`へ開発フロントエンドが誤接続しないよう、Backendのポートも環境間で分離する。

`family-hub-database.service`はDocker起動後にCompose healthcheckの成功まで待つ。BackendとDBを利用する保守unitは
このserviceを`Requires`および`After`へ指定し、存在しないOS版`postgresql.service`には依存しない。構築と切り替えの
手順は[`production-runbook.md`](./production-runbook.md)を正本とする。

Uvicornの起動条件は次のとおりとする。サービス定義は`deploy/systemd/`で管理し、HDD mountと本番DB serviceを
起動条件に含める。

```bash
.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
```

`--forwarded-allow-ips="*"`は使用しない。

## Caddyの責務

- `frontend/dist/`を静的配信する
- 静的ファイルが存在しないフロントエンド経路は`index.html`へフォールバックする
- `/api/*`をパスから`/api`を取り除かずにFastAPIへ転送する
- loopback運用監視用の`/api/v1/readiness`は正確なパスを`404`で遮断し、公開経路へ転送しない
- `frontend/dist/`以外のローカルファイルを静的配信しない
- Viteの開発サーバーやpreviewサーバーを本番で使用しない
- アクセスログへCookie、認証情報、招待トークンなどの秘密情報を残さない

ハッシュ付きの`/assets/*`は`public, max-age=31536000, immutable`で長期キャッシュする。`sw.js`は
`Cache-Control: no-store`と`Cloudflare-CDN-Cache-Control: no-store`を返す。その他の静的ファイルと、任意のSPA URLから
フォールバックした`index.html`は`no-cache, must-revalidate`として、新しいreleaseを毎回再検証できるようにする。
具体的な設定は`deploy/Caddyfile`で管理する。

## クライアントIPの伝搬

ログイン試行制限で接続元を区別するため、次の経路で元のクライアントIPを伝える。

```text
Cloudflare Edge
  └── CF-Connecting-IP
        ↓
cloudflared（同一ホストのloopback接続）
        ↓
Caddy（信頼する直前プロキシはloopbackだけ）
  └── X-Forwarded-For
        ↓
Uvicorn（127.0.0.1からの転送ヘッダーだけを信頼）
```

Cloudflareは`CF-Connecting-IP`でオリジンへクライアントIPを通知する。Caddyでは`trusted_proxies`と
`client_ip_headers`を明示し、`cloudflared`が同じホストで動作する限り信頼範囲を`127.0.0.1/8`と`::1`へ限定する。
LAN全体や`private_ranges`を信頼しない。Caddy自体をLANへ公開するとヘッダーを偽装できる経路が増えるため、
初期構成ではloopback待ち受けを維持する。

設定後は、CaddyとFastAPIが記録するクライアントIP、ログイン試行制限のキー、および偽装ヘッダーを送った場合の
挙動を実機で確認する。

## 認証とOrigin

- Family Hubのサーバー側セッション、CSRF検証、グループ認可を主認証として使用する
- Cloudflare Accessは初期構成へ追加しない
- 本番Cookieは`__Host-photo_session`、`Secure`、`HttpOnly`、`SameSite=Lax`、`Path=/`とする
- `AUTH_TRUSTED_ORIGINS`と`CORS_ORIGINS`には本番公開Originだけを指定する
- 本番設定へ開発用の`http://localhost:5173`を混在させない

例として公開URLが`https://family.example.com`の場合、末尾スラッシュを付けずに次を設定する。

```dotenv
APP_ENV=production
AUTH_TRUSTED_ORIGINS=https://family.example.com
CORS_ORIGINS=https://family.example.com
AUTH_COOKIE_SECURE=true
```

実際のホスト名、認証情報、およびTunnelトークンはリポジトリへ記録しない。

## キャッシュ方針

認証・認可結果で内容が変わるAPIレスポンスをCloudflare Edgeへ保存しない。

- Cloudflare Cache Ruleで`URI Path starts with /api/`を`Bypass cache`にする
- CloudflareのBrowser Cache TTLを`Respect Existing Headers`にし、Caddyの用途別ヘッダーを上書きしない
- `/sw.js`はCache Ruleでも`Bypass cache`とし、Service Workerの更新確認を妨げない
- 写真原本、サムネイル、ZIPなど認証付きバイナリは`Cache-Control: private, no-store`を返す
- 認証、グループ、アルバム、掃除、買い物などの動的APIも、配信実装時に`private, no-store`を共通適用する
- `/assets/*`のハッシュ付き成果物は`public, max-age=31536000, immutable`を使用できる
- `index.html`は長期キャッシュしない

CloudflareのCache Ruleはオリジンのヘッダーより強い設定を行えるため、APIの明示的なBypassを本番受入条件とする。

## アップロード

Cloudflareのプロキシ対象リクエストにはプラン別の本文サイズ上限があり、FreeとProは100 MBである。100 MiBは
104,857,600バイトのため、単一リクエストの上限として同一視しない。

- 本番Reactクライアントは常にバッチの分割アップロードAPIを使用する
- 各チャンクはCloudflareのリクエスト上限を十分下回るサイズにする
- `POST /api/v1/photos`は互換用APIとして維持するが、Cloudflare経由で上限付近のファイルを送れるとは保証しない
- 本番プランやCloudflare設定を変更した場合は、公式の現在値と実際の`413`境界を再確認する

`PHOTO_MAX_UPLOAD_BYTES`はファイル全体のアプリケーション上限、`PHOTO_UPLOAD_CHUNK_BYTES`は1リクエストの
チャンクサイズとして別々に扱う。

## Web Pushの外向き通信

Push購読endpointはHTTPSに限定し、`PUSH_ALLOWED_ENDPOINT_HOSTS`へ列挙したprovider hostだけを登録できるようにする。
既定値はSafari、Chromium、およびFirefoxの主要provider hostとし、実機で新しいhostが必要になった場合は、運用者が
providerの正当性を確認してから本番`backend.env`へ追加する。任意host、IP address、loopback、LAN内endpointを許可しない。
1ユーザーの購読数は`PUSH_MAX_SUBSCRIPTIONS_PER_USER`で制限し、既定値を10とする。

通知Workerだけがproviderへ外向きHTTPS接続する。購読APIから任意URLへ同期接続せず、Caddy、Uvicorn、PostgreSQL、
写真ストレージの受信公開範囲も変更しない。

通知の契機、購読とログインセッションの関係、および再試行は[`web-push.md`](./web-push.md)を参照する。
VAPID設定とiPhone実機確認が完了するまでは、通知関連timerを有効にしない。
現在の公開テスト環境では2026年7月20日に両方を確認し、通知関連timerを有効化済みである。

## 保守ジョブのdead-man監視

DB backup、写真integrity、trash purge、通知配送、掃除期限通知、および2台目ストレージbackupのsystemd unitは、
任意のHealthchecks互換ping URLへ開始、成功、失敗を通知できる。ジョブごとの`MONITORING_PING_URL_*`を本番の
`backend.env`へ設定し、実値やcheck identifierはリポジトリへ保存しない。URLはHTTPSを必須とし、同一ホストの
自己ホスト監視へ接続する場合だけloopback HTTPを許可する。未設定のジョブはpingを行わず、保守処理自体は継続する。
監視先の一時障害によって本体ジョブを失敗させないため、ping失敗はjournalへ型名だけを記録して終了コード0とする。

## ZIP書き出し

FastAPIはZIP全体を一時ファイルへ作らず、原本を順次読み出す。ただしCloudflare Tunnelは
`Content-Type: text/event-stream`以外のレスポンスを既定でバッファリングするため、Cloudflare経由で同じ逐次性や
メモリ特性が維持されるとはまだ確認できていない。また、オリジンが一定時間応答を返さない場合は`524`の対象になり得る。

本番化前に、100枚・数GB程度の書き出しで次を実測する。

- ダウンロード開始までの時間
- iPhone Safariでの完了可否
- `cloudflared`、Caddy、およびFastAPIのメモリ使用量
- Cloudflareの`524`や途中切断の有無
- 失敗後にサーバーやブラウザへ不要な一時ファイルが残らないこと

問題がある場合は、外部経由の書き出し上限を下げるか、大規模バックアップをLAN内の管理経路または管理コマンドへ
分離する。実測が完了するまで、数GB級ZIPのCloudflare経由動作を保証済みとは扱わない。

## 自宅LANからの利用

初期運用では、自宅Wi-Fiからも外出先と同じ`https://family.example.com`形式の公開URLを使用する。これにより
Secure CookieとOrigin設定を1系統に保つ。

この方式はインターネットまたはCloudflareの停止中に利用できない。独立したLAN内アクセスが必要になった場合は、
ローカルHTTPS、証明書、名前解決、Cookie、Origin、およびCaddyの信頼境界を別途設計する。平文HTTPの
`http://192.168.x.x:8080`を本番Cookieの代替経路にはしない。

## 本番受入チェック

- Named Tunnelが再起動後も自動接続し、Quick Tunnelへ依存していない
- ルーターに受信用ポート転送がなく、CaddyとUvicornがloopbackだけで待ち受けている
- 未認証状態で保護対象APIと写真原本を取得できない
- loopbackの`/api/v1/readiness`がDBと写真ストレージを確認し、Caddy経由では`404`になる
- `AUTH_TRUSTED_ORIGINS`、CORS、Cookie属性が本番Originと一致する
- 偽装した転送ヘッダーを直接送ってもクライアントIPとして採用されない
- `/api/*`がCloudflareキャッシュをBypassし、認証付きバイナリが`private, no-store`を返す
- 上限付近の写真をReactの分割アップロードで保存できる
- ZIP書き出しの実測項目を満たすか、運用上の制限を決定している
- PostgreSQLと外付けHDDへCloudflare、LAN、またはクライアントから直接到達できない
- バックアップと復元手順を別媒体で確認している
- 有効化した保守timerのdead-man監視が開始、成功、および意図的な失敗を検知する

## 参考資料

- [Cloudflare Tunnel: Set up](https://developers.cloudflare.com/tunnel/setup/)
- [Cloudflare Tunnel: Routing](https://developers.cloudflare.com/tunnel/routing/)
- [Cloudflare HTTP headers](https://developers.cloudflare.com/fundamentals/reference/http-headers/)
- [Cloudflare Cache Rules settings](https://developers.cloudflare.com/cache/how-to/cache-rules/settings/)
- [Cloudflare Edge and Browser Cache TTL](https://developers.cloudflare.com/cache/how-to/edge-browser-cache-ttl/)
- [Cloudflare default cache behavior and upload limits](https://developers.cloudflare.com/cache/concepts/default-cache-behavior/)
- [Cloudflare Tunnel troubleshooting](https://developers.cloudflare.com/cloudflare-one/troubleshooting/tunnel/)
- [Cloudflare error 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/)
- [Caddy global server options](https://caddyserver.com/docs/caddyfile/options)
- [FastAPI: Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
