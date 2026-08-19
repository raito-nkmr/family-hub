# 本番配信設計

English version: [deployment.md](./deployment.md)

## 目的と状態

Family Hubを自宅内外のiPhoneから同じHTTPS URLで利用するための配信方法を定義する。本書は目標アーキテクチャと受入条件の正本である。
Named Tunnel、Caddy、Uvicorn、releaseは実ホストへ公開テスト用に配置済みで、独自ドメインからのアクセスを確認している。本番運用は開始していない。
本番DBの分離、主要な運用timer、初回復元試験は完了し、次回のtimer自動実行、再起動時の挙動、光回線開通後の実機受入が未確認である。
ホスト固有の本番状態はリポジトリに含めない。運用者は本設計と本番runbookを使い、リポジトリ外で状態を記録・検証する。

Family Hubの認証を主認証として維持し、初期構成ではCloudflare Accessを追加しない。公開ホスト名はインターネットから到達可能なため、
health、ログイン、招待受諾を除くすべてのデータAPIをFamily Hubのセッション認証・認可で保護する。

## 目標構成

Cloudflareを公開入口、Caddyをオリジンホストの唯一のHTTP入口とする。

```text
自宅または外出先のiPhone
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
                            └── 内蔵の写真ストレージHDD
```

- 本番は固定ホスト名を持つNamed Tunnelを使用し、Quick Tunnelは一時的な開発確認に限定する
- ルーターで80、443、8080、8000番ポートを転送しない
- Caddy、FastAPI、PostgreSQL、写真ストレージをインターネットやLANへ直接公開しない
- 写真原本をCaddyの静的ファイルルートへ置かず、認証・認可済みFastAPI endpointから配信する
- ブラウザから見た静的コンテンツとAPIは同一originにする

Cloudflare Tunnel Published Applicationsは、公開ホスト名をローカルサービスへ接続できる。Quick Tunnelは公式にもテスト用とされるため、本番経路には含めない。

## 待ち受けとプロセス境界

| プロセス | 待ち受け・接続 | 方針 |
| --- | --- | --- |
| `cloudflared` | Cloudflareへの外向き接続 | インターネットからの着信ポートを作らない |
| Caddy | `127.0.0.1:8080` | `cloudflared`からだけ到達可能 |
| Uvicorn | `127.0.0.1:8000` | Caddyからだけ到達可能 |
| PostgreSQL | `127.0.0.1:5433` | 本番専用Composeで管理し、クライアントから到達不能 |

本番DBは`deploy/compose.production.yaml`で管理し、開発用`compose.yaml`から分離する。本番Compose projectは`family-hub-production`、
volumeは`family-hub-production-postgres-data`とする。volumeはexternalとして事前作成し、`compose down --volumes`で削除できないようにする。
開発PostgreSQLは`127.0.0.1:15432`、開発FastAPIは`127.0.0.1:18000`、Viteは`127.0.0.1:15173`で待ち受け、Viteの`/api`プロキシは開発Backendポートを使う。
開発フロントエンドが本番FastAPIの`127.0.0.1:8000`へ誤接続しないよう、Backendのポートを分離する。

実機のLANテストでは、開発FastAPIを`0.0.0.0`へbindし、ViteのLAN originを`CORS_ORIGINS`と`AUTH_TRUSTED_ORIGINS`へ追加し、端末では開発フロントエンドURLを使う。
開発React clientは再開可能なアップロードチャンクをポート`18000`へ直接送信し、それ以外のAPIリクエストはVite proxyを使う。

`family-hub-database.service`はDocker起動とCompose healthcheck成功を待つ。BackendとDB関連の保守unitはこのserviceを`Requires`と`After`へ宣言し、
存在しない可能性があるOS提供の`postgresql.service`に依存しない。構築・切り替え手順の正本は[`production-runbook.md`](./production-runbook.md)である。

Uvicornは`deploy/systemd/`のservice定義で管理する。本番DB serviceだけをBackend起動の必須条件とする。写真HDDが利用できない場合も、Backendは認証、掃除、
買い物、グループなどDBを使う機能を継続して提供し、HDDを必要とする写真操作だけが`503`または同等の利用不可状態を返す。

アプリケーションログはISO風タイムスタンプ、レベル、logger名、リクエストIDとともにstderrへ出力する。systemd Backend unitはjournalへ収集し、
アプリケーションとリクエストログは`journalctl -u family-hub-backend.service`で確認する。別のログレベルが必要な場合はホスト環境の`APP_LOG_LEVEL`を設定する。
リクエストパスからquery stringを除外し、検索文字列などのユーザー入力をアプリケーションログへコピーしない。

再開可能チャンクの診断では、ブラウザconsoleとBackendのリクエストボディ受信、永続`.part`同期、offset変更、レスポンスstatusをクライアント生成の試行IDで関連付ける。
ブラウザは`[photo-upload]` prefixで記録し、直接cross-originの開発アップロードではBackendの`X-Request-ID`を読める。
ブラウザの`attemptId`とBackendログの`attempt_id`を比較する。サーバーoffsetが進んだ後にclient timeoutと古いoffsetでの`409`再試行が起きれば、
サーバーはチャンクを保存したがレスポンスが届かなかったことを示す。これらの診断にはファイル名、メディア内容、Cookie、CSRFトークン、認証情報を含めない。

成功した再開可能チャンクのレスポンスは、短く明示的なbodyを持つ`200 OK`を使用する。statusと`Upload-Offset`ヘッダーを読み取った後、ブラウザはbodyを待たずにレスポンスストリームをabortする。
これにより、iPhone Safariが6つのcross-originレスポンスを保持した後に7つ目をキューへ積むことを防ぐ。開発・本番proxyを通して`Upload-Offset`を保持し、次の正しい位置として扱う。

この失敗はLAN開発中に50.5MiBのMOVで確認された。8MiBの`PATCH`を6回FastAPIへ到達・永続化できたが、7回目はBackendへ到達しなかった。
空または短いレスポンスbodyを待つと最初のリクエストが停止する可能性がある。レスポンスヘッダーを取得してからそのレスポンスストリームだけをabortすると、
7つ目のチャンク、項目完了、サムネイル取得が再試行なしで成功した。

開発フロントエンドは一時的な診断値として5秒のアップロードタイムアウトを使う。本番ビルドは`VITE_UPLOAD_REQUEST_TIMEOUT_MS`のbuild-time変数を受け付け、
未設定または不正な場合は30秒をfallbackにする。本番受入前に、fallbackへ頼らず、iPhoneのWi-Fiとモバイル回線の実測値を設定する。
レスポンスストリームのabortは開発用cross-origin直接routeのために追加したため、そのrouteだけに限定するか、Cloudflare経由でclient-closed responseを生まないことを確認する。

例えば、測定値をrelease buildへ渡す。

```bash
VITE_UPLOAD_REQUEST_TIMEOUT_MS=30000 npm run build
```

値は1,000〜300,000ミリ秒の整数でなければならない。本番値はホスト側のrelease build環境に置き、ホスト固有の値や秘密情報をリポジトリへ入れない。

```bash
uv run --locked python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
```

`--forwarded-allow-ips="*"`は使用しない。

## Caddyの責務

- `frontend/dist/`を静的配信する
- 対応する静的ファイルがないFrontend routeは`index.html`へfallbackする
- `/api/*`をパスから`/api`を除去せずFastAPIへ転送する
- loopback限定のreadiness path `/api/v1/readiness`を`404`で遮断し、公開routeから転送しない
- `frontend/dist/`以外のローカルファイルを配信しない
- 本番でViteの開発・preview serverを使用しない
- access logへCookie、認証情報、招待トークン、その他の秘密情報を書かない

ハッシュ付き`/assets/*`は`public, max-age=31536000, immutable`を返す。`sw.js`は`Cache-Control: no-store`と`Cloudflare-CDN-Cache-Control: no-store`を返す。
その他の静的ファイルとSPA fallbackの`index.html`は`no-cache, must-revalidate`とし、releaseごとに再検証できるようにする。具体的な設定は`deploy/Caddyfile`にある。

## クライアントIPの転送

ログイン試行を区別するため、元のクライアントIPを次の経路で転送する。

```text
Cloudflare Edge
  └── CF-Connecting-IP
        ↓
cloudflared（同じホストのloopback接続）
        ↓
Caddy（直前のloopback proxyだけを信頼）
  └── X-Forwarded-For
        ↓
Uvicorn（127.0.0.1からの転送ヘッダーだけを信頼）
```

Cloudflareは`CF-Connecting-IP`でクライアントIPをオリジンへ渡す。Caddyでは`trusted_proxies`と`client_ip_headers`を明示し、
同じホストで`cloudflared`が動く場合に限り`127.0.0.1/8`と`::1`を信頼する。LAN全体や`private_ranges`を信頼しない。
Caddyをloopbackで待ち受けることでヘッダー偽装経路を限定する。

設定後は、CaddyとFastAPIに記録されるクライアントIP、ログインレート制限のキー、実機から偽装転送ヘッダーを送ったときの挙動を確認する。

## 認証とOrigin

- Family Hubのサーバー側セッション、CSRF検証、グループ認可を主認証として使う
- 初期構成でCloudflare Accessを追加しない
- 本番Cookieは`__Host-photo_session`、`Secure`、`HttpOnly`、`SameSite=Lax`、`Path=/`とする
- `AUTH_TRUSTED_ORIGINS`と`CORS_ORIGINS`は本番公開originだけにする
- 本番設定へ開発用`http://localhost:15173`を混在させない

公開URLが`https://family.example.com`の場合、末尾スラッシュなしで次を設定する。

```dotenv
APP_ENV=production
AUTH_TRUSTED_ORIGINS=https://family.example.com
CORS_ORIGINS=https://family.example.com
AUTH_COOKIE_SECURE=true
```

実際のホスト名、認証情報、Tunnel tokenをリポジトリへ記録しない。

## キャッシュ方針

認証・認可に依存する内容のAPIレスポンスをCloudflare Edgeへ保存しない。

- `URI Path starts with /api/`のCloudflare Cache Ruleを`Bypass cache`にする
- Browser Cache TTLを`Respect Existing Headers`にし、Caddyの用途別ヘッダーを上書きさせない
- Cache Ruleでも`/sw.js`をBypassし、Service Worker更新確認を遅らせない
- 原本、サムネイル、ZIPなど認証付きバイナリは`Cache-Control: private, no-store`を返す
- 認証、グループ、アルバム、掃除、買い物の動的APIも`private, no-store`を適用する
- ハッシュ付き`/assets/*`は`public, max-age=31536000, immutable`を使える
- `index.html`を長期キャッシュしない

Cloudflare Cache Ruleはオリジンヘッダーを上書きできるため、APIの明示的なBypassを本番受入条件とする。

## アップロード

Cloudflare経由のリクエストにはプラン別の本文サイズ制限があり、FreeとProは100MBである。100MiBは104,857,600バイトなので、値を同一視しない。

- 本番React clientは常にバッチ・チャンクアップロードAPIを使用する
- 各チャンクをCloudflareのリクエスト上限より十分小さくする
- `POST /api/v1/photos`は互換用に残すが、Cloudflare経由で上限付近のファイルを保証しない
- 本番プランやCloudflare設定を変更したら、公式の現在の上限と実際の`413`境界を再確認する

`PHOTO_MAX_UPLOAD_BYTES`をファイル全体のアプリケーション上限、`PHOTO_UPLOAD_CHUNK_BYTES`を1リクエストのチャンク上限として別々に扱う。

Backendホストの`PATH`には、MP4、QuickTime MOV、M4Vの検証とサムネイル生成用に`ffprobe`と`ffmpeg`を用意する。動画原本は変換せず保存し、
再生は返したMIMEタイプに対するブラウザのネイティブ対応を使う。

## Web Pushの外向き通信

HTTPSの購読endpointだけを受け付け、provider hostは`PUSH_ALLOWED_ENDPOINT_HOSTS`に列挙されたものに限定する。
実機に新しいhostが必要な場合は、運用者がproviderを確認してから本番`backend.env`へ追加する。任意host、IP、loopback、LAN endpointを許可しない。
ユーザーあたりの購読数を`PUSH_MAX_SUBSCRIPTIONS_PER_USER`で制限し、既定値は10とする。

providerへの外向きHTTPS接続は通知workerだけが行う。購読APIは任意URLへ同期接続せず、Caddy、Uvicorn、PostgreSQL、写真ストレージの受信公開範囲を変更しない。
通知トリガー、購読とログインセッションの関係、再試行は[`web-push.md`](./web-push.md)を参照する。VAPID設定とiPhone検証が完了するまで通知timerを無効にする。
現在の公開テスト環境では2026年7月20日に両方を確認し、通知timerを有効化済みである。

## 保守ジョブのdead-man監視

DBバックアップ、写真整合性、ゴミ箱完全削除、通知配信、掃除期限通知、二次ストレージバックアップのsystemd unitは、Healthchecks互換URLへ開始・成功・失敗を送れる。
各ジョブの`MONITORING_PING_URL_*`を本番`backend.env`へ設定し、実際のURLやcheck IDをリポジトリへ保存しない。HTTPSを必須とし、同一ホストの自己ホスト監視だけloopback HTTPを許可する。
未設定ならpingせず保守処理を続ける。ping失敗で本体ジョブを失敗させず、journalにはping種別だけを記録して終了コード0とする。

## ZIP書き出し

FastAPIは完全な一時ZIPを作らず、原本を順次読み込む。Cloudflare Tunnelは`Content-Type: text/event-stream`以外をバッファする可能性があり、
Cloudflare経由で同じストリーミング特性とメモリ特性が維持されるかは未確認である。originが一定時間応答しないと`524`になる可能性もある。

本番前に約100枚・数GBの書き出しで次を測定する。

- ダウンロード開始までの時間
- iPhone Safariで完了するか
- `cloudflared`、Caddy、FastAPIのメモリ使用量
- Cloudflareの`524`や接続中断
- 失敗した書き出しがサーバーやブラウザへ不要な一時ファイルを残さないか

問題があれば外部書き出し上限を下げるか、大きなバックアップをLAN限定の管理経路または管理コマンドへ移す。測定が終わるまで、Cloudflare経由の数GB ZIP対応を保証しない。

## 自宅LANからの利用

初期運用では、自宅Wi-Fiでも外出先でも`https://family.example.com`のような同じ公開URLを使う。Secure Cookieとorigin設定を1経路に保つためである。

この経路はインターネットまたはCloudflareが停止すると使えない。独立したLANアクセスが必要になった場合は、LAN用HTTPS、証明書、名前解決、Cookie、origin、
Caddyの信頼境界を別に設計する。本番Cookieの代替として平文の`http://192.168.x.x:8080`を使わない。

## 本番受入チェック

- Named Tunnelが再起動後に自動再接続し、Quick Tunnelへ依存しない
- ルーターに受信ポート転送がなく、CaddyとUvicornがloopbackだけで待ち受ける
- 未認証で保護APIと写真原本を取得できない
- loopbackの`/api/v1/readiness`がDBと写真ストレージの状態を返し、Caddy経由では`404`になる。写真ストレージが利用できなくてもBackendや非写真APIは動く
- `AUTH_TRUSTED_ORIGINS`、CORS、Cookie属性が本番originと一致する
- 直接送った偽装転送ヘッダーがクライアントIPとして受け入れられない
- `/api/*`がCloudflare cacheをBypassし、認証付きバイナリが`private, no-store`を返す
- 上限に近い写真と対応動画をReactのチャンクアップロードで保存できる
- ZIP書き出しの測定が完了するか、運用上の上限を決定している
- PostgreSQL、内蔵の写真ストレージHDD、接続を解除した外付けバックアップHDDへCloudflare、LAN、クライアントから直接到達できない
- 別媒体を使ってバックアップと復元を検証している
- 有効化したすべての保守timerでdead-man監視が開始、成功、意図的失敗を検知する

デプロイ後は、信頼できる運用マシンから公開originに対してリポジトリのsmoke checkを実行できる。

```bash
PUBLIC_BASE_URL=https://family.example.com make production-smoke
```

これは公開health、外部から遮断されたreadiness route、未認証APIレスポンス、SPAとService Workerの利用可能性、想定したcache-control headerを確認する。
認証付きlive E2Eや実機でのアップロード・ZIP測定の代わりにはならない。

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

日本語版: [deployment.ja.md](./deployment.ja.md)
