# バックエンド設計

English version: [backend-design.md](./backend-design.md)

## 目的

写真、掃除管理、および買い物リストを含むFamily Hubのバックエンドを、FastAPIとPostgreSQLを使って段階的に構築する。本書ではMVPの
バックエンド構成、責務、依存方向、API、データモデル、ファイル保存処理、安全性、およびテスト方針を定める。

プロダクト全体の目的とスコープは[`product-brief.md`](./product-brief.md)を参照する。
PostgreSQLの詳細なスキーマ、制約、およびマイグレーション方針は
[`database-design.md`](./database-design.md)を参照する。

## 設計原則

- 機能単位でコードをまとめるFeature-based構成を採用する
- ルーター、モデル、サービスなどの責務は各feature内で分離する
- 複数featureで必要になるまで、機能固有のコードを共通領域へ移動しない
- importによる暗黙的な初期化や登録を行わない
- FastAPIのルーターは`app.include_router(...)`で明示的に登録する
- アプリケーションの起動・終了処理にはlifespanを使用する
- ファイルシステムとPostgreSQLの不整合が発生し得ることを前提に、検出・復旧可能な設計にする
- 受信はファイルごとに並行化し、原本・サイドカー・DBの確定処理だけを直列化する
- 学習とMVP完成を優先し、必要になる前に抽象化を追加しない

## ディレクトリ構成

```text
backend/
├── alembic/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── backup_database.py
│   │   ├── backup_secondary_storage.py
│   │   ├── check_photo_integrity.py
│   │   ├── create_dummy_users.py
│   │   ├── create_user.py
│   │   ├── enqueue_due_cleaning_notifications.py
│   │   ├── export_openapi.py
│   │   ├── purge_trashed_photos.py
│   │   ├── report_monitoring.py
│   │   ├── reset_user_password.py
│   │   ├── send_notifications.py
│   │   ├── sync_photo_sidecars.py
│   │   └── set_user_role.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── lifespan.py
│   │   └── middleware.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── session.py
│   └── features/
│       ├── __init__.py
│       ├── albums/
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   ├── public.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── auth/
│       │   ├── dependencies.py
│       │   ├── invitation_dependencies.py
│       │   ├── invitation_router.py
│       │   ├── invitations.py
│       │   ├── models.py
│       │   ├── passwords.py
│       │   ├── public.py
│       │   ├── rate_limit.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── cleaning/
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── health/
│       │   ├── __init__.py
│       │   └── router.py
│       ├── groups/
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   ├── public.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── maintenance/
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── notifications/
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   ├── public.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   ├── service.py
│       │   └── worker.py
│       ├── photos/
│       │   ├── __init__.py
│       │   ├── access.py
│       │   ├── activity.py
│       │   ├── dependencies.py
│       │   ├── export_router.py
│       │   ├── export.py
│       │   ├── image_validation.py
│       │   ├── models.py
│       │   ├── public.py
│       │   ├── queries.py
│       │   ├── registration.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   ├── service.py
│       │   ├── storage.py
│       │   ├── thumbnails.py
│       │   ├── trash_router.py
│       │   ├── upload_router.py
│       │   └── uploads.py
│       └── shopping/
│           ├── dependencies.py
│           ├── models.py
│           ├── router.py
│           ├── schemas.py
│           └── service.py
└── tests/
    ├── commands/
    ├── core/
    ├── database/
    └── features/
        ├── albums/
        ├── auth/
        ├── cleaning/
        ├── groups/
        ├── health/
        ├── maintenance/
        ├── notifications/
        ├── photos/
        └── shopping/
```

`alembic/`は導入時に生成される構成に従う。実際に必要になるまでは空のパッケージやプレースホルダーの
テストを作成しない。

## 各領域の責務

### `core`

アプリケーション全体で利用する設定と例外を管理する。feature固有の処理を置く汎用置き場にはしない。

- `config.py`: 環境変数の読み込みと型付き設定
- `lifespan.py`: アプリケーション設定とプロセス内リソースの起動・終了処理
- `middleware.py`: featureのHTTP入力より前に適用するアプリケーション共通の制約

### `database`

PostgreSQLとSQLAlchemyに関する共通基盤を管理する。

- `base.py`: SQLAlchemyのDeclarative BaseとAlembic向けmetadata
- `session.py`: Engine、Session factory、リクエスト単位のSession依存関係

モデルの読み込みをimport副作用に依存させない。Alembicへmetadataを渡す際は、対象モデルを明示的に
読み込む関数またはレジストリを用意する。

### `features.health`

公開livenessはアプリケーションプロセスの稼働状態だけを返す。loopback専用readinessはPostgreSQLと写真ストレージの
読み取り可否を確認し、どちらかが利用できなければ`503`を返す。Caddyはreadinessの正確なパスを`404`で遮断し、
公開URLから内部依存関係の状態を取得できないようにする。認証後に表示する詳細なストレージ状態はphoto featureの
専用APIとして提供する。

### `features.auth`

家族ユーザーのログイン、サーバー側セッション、システム権限、招待制アカウント作成、CSRF検証、および
ログイン試行制限を担当する。

- `router.py`: ログイン、パスワード変更、セッション一覧・失効、およびログアウト
- `service.py`: 資格情報の検証、パスワード更新、セッション生成・検証・一覧・失効
- `models.py`: `User`、`UserSession`、および`UserInvitation`
- `passwords.py`: Argon2idによるパスワードハッシュと検証
- `rate_limit.py`: 単一プロセス向けの、追跡キー数に上限を持つログイン試行制限
- `dependencies.py`: 認証、CSRF、および信頼済みOriginを検証する公開依存関係
- `public.py`: 別featureへ公開する最小限のユーザー情報と読み取り専用ディレクトリ
- `invitations.py`: 招待発行・一覧・取消・受諾と通常ユーザー作成
- `invitation_router.py`: システム管理者向け招待APIと公開の招待受諾API

写真featureは公開依存関係`require_authenticated_user`と`require_csrf_token`だけを利用し、auth featureの
サービスやモデルへ直接依存しない。

ログインとパスワード変更は対象の`User`行を`FOR UPDATE`でロックしてから最新のパスワードハッシュを検証する。
これにより、旧パスワードの検証中にパスワード変更が完了し、変更後に旧資格情報から新しいセッションが作られる競合を防ぐ。

### `features.groups`

家族グループの作成、所属、およびグループ内権限を担当する。

- `router.py`: 所属グループの一覧、作成、改名、参加依頼、管理概要、監査、およびメンバー管理
- `service.py`: グループ作成、管理者認可、参加依頼と承認、影響確認、権限変更・解除、最後の管理者保護
- `models.py`: `FamilyGroup`、`FamilyGroupMember`、および参加依頼
- `public.py`: 別featureへ公開するグループ権限と所属モデル
- `schemas.py`: グループとメンバーのリクエスト・レスポンス型
- `dependencies.py`: Sessionと公開されたユーザーディレクトリからServiceを構築

groups featureはauth featureの内部モデルへ直接依存せず、`features.auth.public`だけを利用する。非メンバーが
グループIDを指定した場合は、存在を開示せず`404`を返す。メンバー追加候補はグループ管理者にだけ返し、有効かつ
対象グループへ未所属のユーザーに限定する。グループ名はDBの一意制約でシステム全体の重複を防ぎ、作成時の
事前確認と一意制約違反の両方を`409 Conflict`へ変換する。

グループ削除のHTTP APIは提供しない。`python -m app.commands.delete_group --group-id <UUID>`を運用管理者向けの
唯一の物理削除経路とし、メンバーを除く関連データが存在する場合は`--include-related-data`を必須とする。コマンドは
削除前の関連件数表示、グループ名の完全一致確認、および確認後の再ロック・再集計を行い、表示後に状態が変わっていれば
削除を中止する。DBの外部キーCASCADEでメンバー、参加依頼、アルバムと写真関連、掃除箇所と完了履歴、買い物項目、写真共有、
写真新着イベントとのグループ関連、およびアップロードバッチ共有先を単一トランザクションで削除する。写真本体は保持し、
削除前に取得した共有写真IDを使って、コミット後にJSONサイドカーを残存する共有設定へ同期する。同期に失敗した場合は
DB削除済みであることと`sync_photo_sidecars`による再同期手順を明示して異常終了する。

所属解除と、所属を根拠にした写真共有・アップロード・アルバム・掃除・買い物の変更を直列化するため、変更系ユースケースは
対象の`FamilyGroup`行をUUID順でロックしてから所属を再確認する。複数種類の行をロックする場合は、
`FamilyGroup`、写真、アルバム、掃除箇所、または買い物品目の順に取得する。

### `features.cleaning`

家族グループ単位の掃除箇所、日数単位の頻度、および完了履歴を担当する。

- `router.py`: 掃除箇所の一覧・取得・作成・更新と完了記録のHTTP境界
- `service.py`: グループ認可、期限計算、掃除箇所管理、および完了記録
- `models.py`: `CleaningTask`と`CleaningCompletion`
- `schemas.py`: 掃除APIのリクエスト・レスポンス型
- `dependencies.py`: Sessionと公開されたユーザーディレクトリからServiceを構築

一覧と完了操作はグループメンバーへ許可し、作成、編集、停止、および再開はグループ管理者だけへ許可する。
変更系操作はグループ行をロックして所属を再確認した後に掃除箇所をロックし、所属解除および同じ掃除箇所への
同時更新を直列化する。完了時刻はクライアントから受け取らず、
サーバーのUTC現在時刻を記録する。一覧ではPostgreSQLの`DISTINCT ON`を使用して掃除箇所ごとの最新完了だけを取得し、
履歴全件をアプリケーションへ読み込まない。非メンバーには掃除箇所の存在を開示せず`404`を返す。

### `features.shopping`

家族グループ単位の買うもの、購入状態、購入者、および購入時刻を担当する。

- `router.py`: 品目一覧・作成、購入済み、および未購入へ戻す操作のHTTP境界
- `service.py`: グループ認可、一覧順、購入状態の行ロック、および直近購入済み件数の制御
- `models.py`: `ShoppingItem`
- `schemas.py`: 買い物APIのリクエスト・レスポンス型
- `dependencies.py`: Sessionと公開されたユーザーディレクトリからServiceを構築

すべての操作をグループメンバーへ許可する。変更系操作はグループ行をロックして所属を再確認した後に品目をロックし、
所属解除および同じ品目への同時更新を直列化する。購入時刻はクライアントから受け取らず、サーバーのUTC現在時刻を記録する。非メンバーには
品目の存在を開示せず`404`を返す。

### `features.photos`

写真のアップロード、保存、メタデータ管理、および取得を担当する。

- `router.py`: 写真一覧、詳細、メタデータ、共有、お気に入りのHTTP境界
- `trash_router.py`: ゴミ箱一覧、復元、および完全削除のHTTP境界
- `export_router.py`: 所有写真のZIP書き出しのHTTP境界
- `upload_router.py`: 一括・分割アップロードのHTTP境界
- `schemas.py`: Pydanticによるリクエスト・レスポンス型
- `models.py`: 写真、メタデータ、共有先、派生画像、およびアップロード状態のSQLAlchemyモデル
- `access.py`: 所有者およびグループ共有による写真閲覧条件
- `activity.py`: 共有写真の新着一覧、カーソルページネーション、およびユーザーごとの既読位置
- `queries.py`: 写真一覧の検索、カーソルページネーション、および月別集計
- `registration.py`: 単体・バッチで共有する写真モデル、サイドカー、および確定済みファイルの準備
- `service.py`: ファイル保存、DB登録、所有写真への共有先一括追加、およびサイドカー復元を含むユースケース全体の進行
- `uploads.py`: バッチ作成、受信位置、完了、期限切れ、キャンセルの状態管理
- `storage.py`: HDD状態確認、分割書き込み、ハッシュ計算、JSONサイドカー作成、ファイル確定
- `thumbnails.py`: 検証済み画像からのWebPサムネイル生成
- `dependencies.py`: SessionとStorageからServiceを構築するFastAPI依存関係
- `export.py`: 原本を一時ZIPへ複製せずに順次書き出すZIPストリーム
- `public.py`: アルバムなど別featureへ公開する読み取り専用の写真カタログとレスポンス型

### `features.albums`

アルバムの作成、編集、削除、および写真との関連付けを担当する。アルバム操作は写真原本やJSONサイドカーを
変更しない。

- `router.py`: HTTP入力、レスポンス、認証、およびCSRF検証
- `service.py`: アルバムと写真関連のDB操作を含むユースケース
- `models.py`: `Album`と`AlbumPhoto`モデル
- `schemas.py`: アルバムAPIのリクエスト・レスポンス型
- `dependencies.py`: Sessionと公開された写真カタログからServiceを構築する依存関係
- `public.py`: feature間で必要になるアルバムの公開境界

albums featureはphotos featureの内部モジュールへ直接依存せず、`features.photos.public`だけを利用する。
アルバムへ追加できる写真はアルバムのグループへ直接共有済みのものに限定し、アルバム所属を写真閲覧権限としては
扱わない。

Repository層はMVP開始時点では設けない。DB操作が増え、サービスの意図が読み取りにくくなった場合に、
`features/photos/repository.py`の追加を検討する。

## 依存方向

```text
router
  ↓
service
  ├── SQLAlchemy Session
  ├── registration
  │     ├── SQLAlchemy Session（読み取りのみ）
  │     └── storage
  └── storage
```

- `router`はファイル保存やSQLAlchemyクエリを直接実行しない
- `service`はHTTPレスポンスやステータスコードへ依存しない
- `storage`はFastAPIやSQLAlchemyへ依存しない
- `models`はrouter、service、schemasへ依存しない
- 公開serviceメソッドがユースケースのcommit、rollback、および確定済みファイルの補償削除を担当する
- 複数ユースケースから共有する`registration`処理はcommitとrollbackを行わない
- featureから別featureの内部モジュールを直接importしない
- feature間連携が必要になった場合は、`public.py`または認証用の明示的な公開依存関係を経由する
- アーキテクチャテストで、featureをまたぐ内部モジュールのimportを検出する

## アプリケーション生成

`main.py`はアプリケーション生成とルーター登録に責務を限定する。

```python
from fastapi import FastAPI

from app.features.health.router import router as health_router
from app.features.photos.router import router as photos_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(photos_router, prefix="/api/v1/photos")
    return app


app = create_app()
```

lifespanを`FastAPI`へ明示的に渡し、プロセス内で共有するリソースを初期化する。設定値の組み合わせは
`Settings`の生成時に検証する。DB接続とHDDの状態は起動条件にせず、使用するリクエストで確認することで、HDDが
利用できない場合もAPI自体は起動して状態確認を可能にする。写真のアップロードと原本取得は`503`で拒否し、
空き容量が安全基準を下回る場合のアップロードは`507`で拒否する。

## 本番配信境界

本番ではCloudflareをインターネット上の公開入口、Caddyをオリジンサーバー側の唯一のHTTP入口とする。
FastAPIはloopbackだけで待ち受け、Caddy以外から到達できないようにする。PostgreSQLと外付けHDDはクライアントへ
公開せず、写真原本は認証・認可付きAPIから返す。

Cloudflare Tunnel、Caddy、転送ヘッダー、キャッシュ、アップロード制限、ZIP書き出し、および受入確認の詳細は
[`deployment.md`](./deployment.md)を正本とする。本節ではバックエンドが守る境界だけを定義する。

## API

MVPでは`/api/v1`をAPIプレフィックスとする。案内用のルートだけはAPIバージョンの対象外とし、OpenAPI
スキーマへ含めない。

FastAPIのOpenAPIスキーマをAPI契約の正本とし、フロントエンドの型、fetch client、およびSDKはOpenAPIから生成する。
生成物は`frontend/src/shared/api/generated/`へコミットするが直接編集せず、routerまたはPydantic schemaの変更時に
`npm --prefix frontend run api:generate`で更新する。通常の検証では生成し直した結果との差分を確認し、APIと
TypeScript型と通信契約のずれを検出する。標準的なJSON CRUDは生成SDKを使用し、分割アップロードや直接ダウンロードなど
ブラウザ通信を細かく制御する処理と画面固有の状態だけを手書きで維持する。

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/` | API名とhealth、Swagger UIへのパスを返す案内 |
| `GET` | `/api/v1/health` | APIプロセスの稼働確認 |
| `GET` | `/api/v1/readiness` | loopbackからDBと写真ストレージの準備状態を確認。OpenAPIとCaddy公開経路には含めない |
| `POST` | `/api/v1/auth/login` | ログインしてセッションCookieを発行 |
| `GET` | `/api/v1/auth/me` | 現在のユーザーとCSRFトークンを取得 |
| `POST` | `/api/v1/auth/logout` | 現在のセッションを失効 |
| `POST` | `/api/v1/auth/logout-all` | ユーザーの全セッションを失効 |
| `GET` | `/api/v1/auth/sessions` | 現在のユーザーのアクティブセッション一覧を取得 |
| `DELETE` | `/api/v1/auth/sessions/{session_id}` | 現在のユーザーが指定したセッションを失効 |
| `PUT` | `/api/v1/auth/password` | 現在のパスワードを確認して変更し、全セッションを失効 |
| `POST` | `/api/v1/auth/invitations/accept` | 招待トークンを受諾して通常ユーザーを作成 |
| `GET` | `/api/v1/admin/invitations` | システム管理者が招待一覧を取得 |
| `POST` | `/api/v1/admin/invitations` | システム管理者が招待を発行 |
| `DELETE` | `/api/v1/admin/invitations/{invitation_id}` | システム管理者が招待を取り消す |
| `DELETE` | `/api/v1/admin/invitations/history/{invitation_id}` | 招待を無効化して履歴一覧から削除し、監査ログを残す |
| `GET/PATCH` | `/api/v1/admin/users...` | ユーザー一覧、利用状態・システム権限変更 |
| `GET` | `/api/v1/admin/groups` | 全グループのメンバー数と有効管理者数 |
| `PATCH` | `/api/v1/admin/groups/{group_id}/administrator` | 有効な所属ユーザーをグループ管理者へ設定 |
| `GET` | `/api/v1/admin/audit-events` | 管理監査ログ |
| `GET` | `/api/v1/admin/maintenance/history` | 保守実行履歴 |
| `GET` | `/api/v1/groups` | 自分が所属する家族グループの一覧取得 |
| `POST` | `/api/v1/groups` | グループを作成し、作成者を管理者として登録 |
| `GET` | `/api/v1/groups/{group_id}` | 所属グループとメンバーの取得 |
| `PATCH` | `/api/v1/groups/{group_id}` | 管理者がグループ名を変更 |
| `GET` | `/api/v1/groups/{group_id}/administration` | グループ管理概要 |
| `GET` | `/api/v1/groups/{group_id}/audit-events` | グループ管理監査ログ |
| `POST` | `/api/v1/groups/{group_id}/membership-invitations` | 未所属ユーザーへ参加依頼 |
| `POST` | `/api/v1/groups/membership-invitations/{invitation_id}/decision` | 本人が参加依頼を承認・辞退 |
| `GET` | `/api/v1/groups/{group_id}/member-candidates` | 管理者が追加可能な有効ユーザーを取得 |
| `POST` | `/api/v1/groups/{group_id}/members` | 管理者が既存ユーザーをグループへ追加 |
| `PATCH` | `/api/v1/groups/{group_id}/members/{user_id}` | 管理者がグループ内権限を変更 |
| `DELETE` | `/api/v1/groups/{group_id}/members/{user_id}` | 管理者がグループ所属を解除 |
| `DELETE` | `/api/v1/photos/{photo_id}/groups/{group_id}` | 管理者が当該グループの写真共有を解除 |
| `GET` | `/api/v1/cleaning/groups/{group_id}/tasks` | メンバーがグループの掃除箇所一覧を取得 |
| `POST` | `/api/v1/cleaning/groups/{group_id}/tasks` | グループ管理者が掃除箇所を作成 |
| `GET` | `/api/v1/cleaning/tasks/{task_id}` | メンバーが掃除箇所と最新完了を取得 |
| `PATCH` | `/api/v1/cleaning/tasks/{task_id}` | グループ管理者が名前、頻度、または状態を更新 |
| `POST` | `/api/v1/cleaning/tasks/{task_id}/completions` | メンバーが掃除完了を記録 |
| `GET` | `/api/v1/shopping/groups/{group_id}/items` | メンバーが未購入品と直近20件の購入済み品を取得 |
| `POST` | `/api/v1/shopping/groups/{group_id}/items` | メンバーが買うものを追加 |
| `POST` | `/api/v1/shopping/items/{item_id}/purchase` | メンバーが購入者と購入時刻を記録 |
| `DELETE` | `/api/v1/shopping/items/{item_id}/purchase` | メンバーが購入済み品を未購入へ戻す |
| `GET` | `/api/v1/photos/storage-status` | HDDの接続、書き込み、空き容量の確認 |
| `GET` | `/api/v1/photos/trash` | 所有者がゴミ箱内の写真をカーソルページ単位で取得 |
| `GET` | `/api/v1/photos/trash/{photo_id}/thumbnail` | 所有者がゴミ箱内写真のサムネイルを取得 |
| `POST` | `/api/v1/photos` | 写真を1枚アップロード |
| `GET` | `/api/v1/photos` | 写真メタデータの一覧取得 |
| `GET` | `/api/v1/photos/timeline` | JST基準の月別写真数を取得 |
| `GET` | `/api/v1/photos/activity` | 閲覧可能な共有写真の新着一覧と未読件数を取得 |
| `POST` | `/api/v1/photos/activity/seen` | 指定した新着イベントまでを既読として記録 |
| `POST` | `/api/v1/photos/bulk-sharing` | 所有する最大100枚の写真へ、既存設定を維持して共有グループを一括追加 |
| `GET` | `/api/v1/photos/export` | 所有する最大100枚の原本をZIPストリームとして書き出し |
| `GET` | `/api/v1/photos/{photo_id}` | 写真メタデータの取得 |
| `GET` | `/api/v1/photos/{photo_id}/content` | 写真原本の取得 |
| `GET` | `/api/v1/photos/{photo_id}/download` | 閲覧可能な写真原本を元ファイル名の添付として取得 |
| `GET` | `/api/v1/photos/{photo_id}/thumbnail` | 一覧用WebPサムネイルの取得 |
| `PATCH` | `/api/v1/photos/{photo_id}` | 閲覧者が共有メモ、所有者が公開範囲をバージョン付きで更新 |
| `DELETE` | `/api/v1/photos/{photo_id}` | 所有者が写真をゴミ箱へ移動 |
| `POST` | `/api/v1/photos/{photo_id}/restore` | 所有者がゴミ箱内の写真を復元 |
| `DELETE` | `/api/v1/photos/{photo_id}/permanent` | 所有者がゴミ箱内の写真の完全削除を要求 |
| `PUT` | `/api/v1/photos/{photo_id}/favorite` | 閲覧可能な写真を現在のユーザーのお気に入りへ追加 |
| `DELETE` | `/api/v1/photos/{photo_id}/favorite` | 現在のユーザーのお気に入りから解除 |
| `POST` | `/api/v1/upload-batches` | 最大100枚の受信予定と共通公開範囲を登録し容量を予約 |
| `GET` | `/api/v1/upload-batches/{batch_id}` | バッチとファイル別の進捗を取得 |
| `DELETE` | `/api/v1/upload-batches/{batch_id}` | バッチを中止し一時ファイルを破棄 |
| `HEAD` | `/api/v1/upload-batches/items/{item_id}/content` | サーバーが受信済みのオフセットを取得 |
| `PATCH` | `/api/v1/upload-batches/items/{item_id}/content` | オフセット付きで分割データを追記 |
| `POST` | `/api/v1/upload-batches/items/{item_id}/complete` | 1ファイルの検証と原本登録を確定 |
| `GET` | `/api/v1/albums` | アルバム一覧の取得 |
| `POST` | `/api/v1/albums` | アルバムの作成 |
| `GET` | `/api/v1/albums/{album_id}` | アルバムと写真のカーソルページを取得 |
| `PATCH` | `/api/v1/albums/{album_id}` | アルバム名、説明、または表紙写真の更新 |
| `DELETE` | `/api/v1/albums/{album_id}` | 写真を残してアルバムを削除 |
| `POST` | `/api/v1/albums/{album_id}/photos` | 最大200枚の写真をアルバムへ追加 |
| `DELETE` | `/api/v1/albums/{album_id}/photos/{photo_id}` | 写真を削除せずアルバムから外す |
| `GET` | `/api/v1/admin/maintenance/status` | システム管理者がストレージ集計と保守実行履歴を取得 |
| `GET` | `/api/v1/notifications/config` | Web Push設定、現在の端末の購読、および通知設定を取得 |
| `POST` | `/api/v1/notifications/subscriptions` | 現在のログインセッションへPush購読を登録 |
| `DELETE` | `/api/v1/notifications/subscriptions/{subscription_id}` | 現在のログインセッションのPush購読を解除 |
| `PUT` | `/api/v1/notifications/preferences` | ユーザー単位の通知種別設定を更新 |

写真の削除は、所有者によるゴミ箱への論理削除、復元、およびゴミ箱内からの完全削除要求として提供する。
完全削除はDBを`purge_pending`へ遷移させてからファイルを冪等に削除し、途中で失敗した場合は保守コマンドから再試行する。
`POST /photos`は既存クライアント向けの単一ファイルAPIとして維持し、ReactはバッチAPIを使用する。

原本ダウンロードは既存の写真閲覧権限をそのまま適用する。ZIP書き出しは手動バックアップ用途として本人所有の
写真だけを1件以上100件以下で受け付ける。元ファイル名が重複する場合はZIP内だけ連番を付け、パス区切りと制御文字は
安全な文字へ置換する。サーバー上にZIP全体の一時ファイルを作らず、原本を格納形式で順次ストリーミングする。
Reactもレスポンスを`Blob`へ蓄積せず、認証Cookieを伴うブラウザの直接ダウンロードを開始する。
Cloudflare Tunnel経由のバッファリングとタイムアウトは未検証であるため、数GB級のZIPを本番保証済みとは扱わない。
実機確認と問題発生時の制限方針は[`deployment.md`](./deployment.md#zip書き出し)に定める。

### 認証とセッション

写真APIはすべて認証必須とし、セッションCookieを自動送信できる同一オリジンのReactクライアントから利用する。
アップロードは共有先なしの`private`を既定値とし、Reactでは一括選択した写真へ同じグループID集合を適用する。
共有グループが1件以上あるAPI上の状態は`shared`と表現し、旧global-family audienceは使用しない。
一括共有は指定された写真がすべて本人所有で、追加先がすべて本人の所属グループである場合だけ実行する。共有解除は行わず、
既存の共有行は変更なしとして数える。変更した全写真の新着イベントには同じ操作IDを付け、閲覧側で1件に集約する。
DB更新に失敗した場合は、先に更新したJSONサイドカーを操作前の内容へ戻す。
本人の写真と、現在所属するグループへ共有された写真だけを一覧・単体・原本APIから返す。公開範囲の変更はアップロードした
本人だけに許可し、指定可能な共有先は本人が所属するグループに限定する。共有メモは写真を閲覧できる
ユーザー全員が編集できる。どちらも`metadata_version`による楽観的ロックで別画面からの上書きを拒否する。
共有メモには最終更新者のユーザーID、ユーザー名、および更新日時を記録する。
お気に入りはユーザーと写真の組み合わせで保持し、共有やアルバムの状態を変更しない。写真の閲覧権限を失った場合、
お気に入り行が残っていても一覧や単体APIには表示しない。
セッショントークンは32バイトの暗号学的乱数から生成し、Cookieにだけ原値を保存する。DBにはSHA-256ハッシュ、
有効期限、最終利用日時、失効日時、およびCSRFトークンを保存する。

開発時のCookie名は`photo_session`、HTTPS運用時は`__Host-photo_session`とする。Cookieには`HttpOnly`、
`SameSite=Lax`、`Path=/`を設定し、本番では`Secure`を必須とする。JavaScriptはセッションCookieを読み取らず、
`GET /api/v1/auth/me`とログインレスポンスからCSRFトークンだけをメモリへ保持する。

セッションのアイドル期限は7日、絶対期限は30日を既定値とする。DBの更新頻度を抑えるため、最終利用日時は
1時間以上経過した場合だけ更新する。ログアウト、全端末ログアウト、ユーザー無効化、パスワード変更、および
期限切れは認証失敗として扱う。

セッション一覧は、失効済み、絶対期限切れ、アイドル期限切れ、および最後のパスワード変更より前に作成されたものを
除外し、最終利用日時の新しい順で返す。ユーザーは自分のセッションだけを個別失効できる。パスワード変更では現在の
パスワードをArgon2idで確認して新しいハッシュへ置き換え、現在を含む全セッションを同時に失効してCookieを削除する。

ログインは設定された`AUTH_TRUSTED_ORIGINS`と`Origin`ヘッダーを照合する。失敗メッセージはユーザーの有無に
かかわらず同一とし、存在しないユーザーでもダミーハッシュを検証する。同じ接続元IPとユーザー名の組み合わせで
5分間に5回失敗した場合は`429 Too Many Requests`を返す。追跡する接続元とユーザー名の組み合わせは最大10,000件に
制限する。現在はUvicorn単一プロセス運用を前提としたメモリ内制限であり、複数プロセス化する場合はPostgreSQLなどの
TTL付き共有状態へ移行する。本番ではCloudflareの`CF-Connecting-IP`をCaddyで検証して`X-Forwarded-For`へ引き継ぎ、
Uvicornはloopback上のCaddyから受け取る転送ヘッダーだけを信頼する。詳細は
[`deployment.md`](./deployment.md#クライアントipの伝搬)に定める。

写真アップロード、パスワード変更、セッション個別失効、ログアウト、および全端末ログアウトでは
`X-CSRF-Token`を必須とする。GETは状態を変更せず、
許可するCORS Originと認証用の信頼済みOriginを環境ごとに明示する。

アルバムAPIもすべて認証必須とし、1つの家族グループへ所属させる。グループメンバー全員へ閲覧・編集を許可し、
作成、更新、削除、写真追加、および写真解除では`X-CSRF-Token`を必須とする。アルバムへ追加できるのは、その
アルバムのグループへ直接共有済みの写真に限定する。アルバム所属は追加の写真閲覧権限を与えない。同じ写真を同じ
アルバムへ再度追加した場合は既存の関連を維持し、重複レコードを作成しない。表紙にはアルバム内の写真を指定でき、
未指定時は最初に追加された写真を返す。表紙写真をアルバムから外した場合は明示指定を解除してフォールバックへ戻す。

掃除APIもすべて認証必須とし、変更系では`X-CSRF-Token`を必須とする。掃除箇所は家族グループへ所属し、
一覧・取得・完了はグループメンバー、作成・更新はグループ管理者へ限定する。次回期限は最新完了日時、完了が
ない場合は作成日時へ`interval_days`を加算して返す。停止中の掃除箇所への完了記録は`409 Conflict`で拒否する。

買い物APIもすべて認証必須とし、変更系では`X-CSRF-Token`を必須とする。品目は家族グループへ所属し、一覧、
作成、購入済み、および未購入へ戻す操作はグループの全メンバーへ許可する。一覧では未購入品をすべて古い順、
購入済み品を直近20件だけ新しい順で返す。取得後に状態が変わった品目への更新は`409 Conflict`で拒否する。

初回セットアップではマイグレーション適用後、バックエンドディレクトリから次を実行して初期システム管理者を
作成する。パスワードは端末上で非表示入力し、コマンド引数、環境変数、シェル履歴へ残さない。
管理コマンドと招待受諾で新規設定するパスワードは8文字以上128文字以下とする。

```bash
alembic upgrade head
python -m app.commands.create_user --username owner --system-role admin
```

管理コマンドによる通常ユーザー作成も利用できる。既存ユーザーのシステム権限を変更または復旧する場合は
`python -m app.commands.set_user_role --username owner --system-role admin`を使用する。
パスワードを忘れたユーザーは、本人確認後にサーバー管理者が
`python -m app.commands.reset_user_password --username family-user`を実行して一時パスワードへ再設定する。
パスワードは端末上で2回非表示入力し、コマンド引数や実行結果へ含めない。ユーザー行をロックした同一トランザクションで
Argon2idハッシュと`password_changed_at`を更新し、対象ユーザーの未失効セッションすべてへ同じ失効時刻を設定する。
DBには次回変更を強制する状態を追加しないため、管理者は一時パスワードを安全な経路で本人へ伝え、本人へログイン直後の
変更を依頼する。コマンドを実行できるOSアカウントとDB接続情報は運用管理者だけに限定する。

招待APIでは、管理者向けの
一覧・発行・取消を`/api/v1/admin/invitations`、未認証の受諾を`/api/v1/auth/invitations/accept`で提供する。
管理操作はシステム管理者認可とCSRF検証、受諾は信頼済みOriginを必須とする。招待トークンはURLフラグメントから
Reactが読み取り、JSONリクエスト本文で送信する。
ユーザー名はNFKC正規化と大文字・小文字の正規化を行い、1文字以上64文字以下のUnicode文字・数字と
ピリオド、アンダースコア、ハイフンを許可する。招待URLはユーザー名に依存せず、ランダムトークンだけで構成する。

システム権限を追加するマイグレーションでは、既存環境の管理経路を失わないよう、作成日時が最も古い有効ユーザー
1人を初回システム管理者へ昇格する。必要に応じて適用後に`set_user_role`で明示的な管理者構成へ変更する。

Alembicと管理コマンドは`backend/.env`を明示的に読み込む。Uvicornを端末から直接起動する場合も、
`uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8001`のように環境ファイルと
開発専用ポートを指定する。
アプリケーション設定は`.env`を暗黙には読まず、Uvicornの`--env-file`またはプロセス環境から受け取る。この差は、
ASGIサーバーからの起動と管理コマンドの双方で設定元を明示するための意図した境界である。

手動確認用のアカウントをまとめて用意する場合は、開発専用の
`python -m app.commands.create_dummy_users`を使用する。既定ではシステム管理者1人と通常ユーザー5人を作成し、
共通パスワードは端末上で非表示入力する。`APP_ENV=development`以外では実行を拒否し、再実行時は既存の同名ユーザーを
変更せずスキップする。これにより、本番へのダミーデータ投入と、既存ユーザーのパスワードや権限の意図しない変更を防ぐ。

### 写真メタデータのAPI表現

一覧APIは既定50件、最大100件のカーソルページネーションを使用する。カード表示に不要なハッシュ、保存先、メモ全文、
メタデータバージョンなどは一覧へ含めず、写真を開いた際に詳細APIから取得する。レスポンスは総件数、次のカーソル、
軽量な一覧項目を返す。

Reactは一覧末尾がビューポートへ近づいたとき、`next_cursor`で次の50件を取得して既存の一覧へ追加する。
同時リクエストは1件に限定し、`next_cursor`が`null`になったら監視を終了する。追加取得に失敗した場合は自動再試行を
停止し、ユーザーが手動で再試行できる導線を表示する。アルバムの写真追加画面も同じ挙動とする。
`IntersectionObserver`の通知が不安定なモバイル環境に備え、ページ全体とダイアログ内のスクロールイベントでも
監視要素の位置を確認し、同一ページの二重取得はクライアント側で防止する。

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "uploaded_by_user_id": "65c6cc91-965a-46b0-b438-e70601be8d83",
      "uploaded_by_username": "owner",
      "visibility": "private",
      "original_filename": "IMG_0001.JPG",
      "content_type": "image/jpeg",
      "width": 4032,
      "height": 3024,
      "captured_at": "2026-07-14T03:00:00Z",
      "uploaded_at": "2026-07-14T03:05:00Z"
    }
  ],
  "next_cursor": "eyJzb3J0X2F0Ijoi...",
  "total_count": 1250
}
```

`limit`、`cursor`、`q`、`date_from`、`date_to`、`uploader_id`、`mine_only`、`visibility`、
`sharing_group_id`、`favorite`、`captured_at_known`、`album_id`、および`exclude_album_id`を検索条件として受け取る。
条件は組み合わせ可能とし、
キーワードは元ファイル名とメモを部分一致で検索する。`mine_only`と`uploader_id`、`album_id`と
`exclude_album_id`はそれぞれ同時に指定しない。不正なカーソルは`400 Bad Request`とする。アルバム追加画面では
`exclude_album_id`を使い、登録済み写真をDBで除外してからページを作る。

日付範囲はJSTの日付として受け取り、`COALESCE(captured_at, uploaded_at)`を対象に開始日以上、終了日の翌日未満で
検索する。一覧は同じ日時式の降順、続いてUUIDの降順で並べる。カーソルは最後の日時とUUIDを表す不透明な値とし、
フロントエンドは内容を解釈しない。

`GET /api/v1/photos/timeline?year=2026`はJST基準の月と写真枚数を返す。フロントエンドは年を前後に移動でき、月を
選択すると該当月の日付範囲で一覧を再検索する。詳細APIは完全な写真メタデータをエンベロープなしで返す。
指定されたUUIDが存在しない場合は`404 Not Found`を返す。

### ストレージ状態のAPI表現

`GET /api/v1/photos/storage-status`はストレージが利用できない場合も状態確認を可能にするため`200 OK`を返す。
`available`はマウント、マーカー、書き込み可否、および空き容量のすべての確認に成功した場合だけ`true`とする。

```json
{
  "status": "available",
  "available": true,
  "writable": true,
  "free_bytes": 1099511627776,
  "minimum_free_bytes": 10737418240
}
```

`status`には`available`、`not_configured`、`root_not_found`、`root_not_directory`、`symlink_not_allowed`、
`not_mount_point`、`marker_missing`、`marker_mismatch`、`read_only`、`not_writable`、`insufficient_space`、または
`io_error`を返す。安全に容量を取得できなかった場合の`free_bytes`は`null`とし、設定されていない場合の
`minimum_free_bytes`も`null`とする。

### 日時のAPI表現

PostgreSQLとの入出力およびFastAPI内部では、タイムゾーンを認識したUTCの`datetime`だけを扱う。APIレスポンスの
日時はUTCのISO 8601形式で返し、JSTへ変換しない。

```json
{
  "captured_at": "2026-07-14T03:00:00Z",
  "uploaded_at": "2026-07-14T03:05:00Z"
}
```

Reactは受け取ったUTC日時を`Asia/Tokyo`へ変換して表示する。日付による検索条件はJSTの開始時刻と終了時刻を
UTCへ変換してからDBを検索する。例えばJSTの1日を検索するときは、JSTの00:00以上、翌日の00:00未満に対応する
UTC範囲を使用する。

### 主なHTTPレスポンス

| Status | 用途 |
| --- | --- |
| `201 Created` | 写真の保存とDB登録に成功 |
| `401 Unauthorized` | セッションが存在しない、無効、または期限切れ |
| `403 Forbidden` | CSRFトークンまたはOriginが不正 |
| `404 Not Found` | 指定された写真が存在しない |
| `409 Conflict` | 同一ハッシュのファイルが登録済み |
| `413 Content Too Large` | 最大ファイルサイズを超過 |
| `415 Unsupported Media Type` | 未対応のファイル形式 |
| `429 Too Many Requests` | ログイン試行回数の上限を超過 |
| `503 Service Unavailable` | HDDまたは派生画像ストレージが利用不可 |
| `507 Insufficient Storage` | HDDの空き容量が安全基準を下回る |

サービスはHTTP例外を送出せず、feature固有の例外を送出する。routerが例外をHTTPレスポンスへ変換する。

## データモデル

`Photo`の初期モデルは次のフィールドを持つ。

| Field | Type | 制約・用途 |
| --- | --- | --- |
| `id` | UUID | Primary key、サーバー側で生成 |
| `uploaded_by_user_id` | UUID | アップロードしたユーザーのID、`users.id`への外部キー |
| `uploaded_by_username` | string | アップロード時点のユーザー名スナップショット |
| `original_filename` | string | アップロード時の表示用ファイル名 |
| `storage_key` | string | ストレージルートからの相対パス、unique |
| `content_type` | string | 検証済みMIMEタイプ |
| `size_bytes` | integer | 原本のバイト数、0より大きい |
| `sha256` | string | 小文字16進数64文字、`uploaded_by_user_id`との組み合わせでunique |
| `width` | integer/null | 画像の幅 |
| `height` | integer/null | 画像の高さ |
| `captured_at` | datetime/null | EXIFなどから得た撮影日時 |
| `uploaded_at` | datetime | UTCで記録するアップロード日時 |

画像本体はPostgreSQLへ保存しない。`storage_key`には絶対パスではなく、次のような相対パスを保存する。

```text
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.jpg
```

これによりHDDのマウント先が変わった場合は、設定変更だけで対応できる。

ゴミ箱一覧は既定50件、最大100件のカーソルページネーションを使用し、レスポンスへ総件数と次のカーソルを含める。
お気に入り状態はページ内の写真IDをまとめて照会し、写真ごとの追加クエリを発行しない。アルバム詳細も既定50件、
最大100件だけを返し、`photo_count`はアルバム全体の件数、`next_cursor`は次ページがある場合の取得位置とする。
どちらも不正なカーソルには`400 Bad Request`を返す。

一覧APIは`COALESCE(captured_at, uploaded_at) DESC, id DESC`で取得する。写真としての並び順には撮影日時を
優先し、取得できない場合だけアップロード日時へフォールバックする。UUIDを第2ソートキーにして同じ日時の
レコードも順序を安定させる。制約とインデックスの詳細は
[`database-design.md`](./database-design.md)に定める。

## ストレージ構成

```text
<PHOTO_STORAGE_ROOT>/
├── .photo-storage-marker           # PHOTO_STORAGE_MARKERと一致する1行の識別値
├── originals/
│   └── YYYY/MM/                    # アップロード日時を基準に分類
│       ├── <UUID>.<extension>
│       └── <UUID>.json
├── incoming/
│   ├── <UUID>.part
│   └── <UUID>.json.part
└── database-backups/

<PHOTO_DERIVATIVE_ROOT>/             # 内蔵SSD上の再生成可能データ
├── thumbnails/YYYY/MM/<UUID>.webp
└── incoming/<UUID>.thumbnail.part
```

MVPでは`originals`と`incoming`を同じファイルシステム上に置く。アップロード完了時のrenameを同一
ファイルシステム内で行い、不完全なファイルを正式な原本として見せないためである。

`PHOTO_STORAGE_ROOT`は外付けHDDのマウントポイントそのものを指す絶対パスとする。ルート直下の
`.photo-storage-marker`には`PHOTO_STORAGE_MARKER`と同じ1行の識別値を保存する。アプリケーションはルートが
実際のマウントポイントであること、パスとマーカーファイルがシンボリックリンクでないこと、およびマーカー値が
一致することを確認する。これにより、HDDが外れた状態で内蔵SSD上の同名ディレクトリへ保存することを防ぐ。
Linuxでは`/proc/self/mountinfo`を確認してbind mountもマウントポイントとして認識し、情報を取得できない環境では
Pythonの標準マウントポイント判定へフォールバックする。bind mountは内蔵SSDでの開発試験に使用できるが、本番の
`PHOTO_STORAGE_ROOT`は外付けHDD自体のマウントポイントを指定する。

ストレージ操作では、クライアントから渡されたファイル名をパス生成に使用しない。拡張子も検証済みの
ファイル形式からサーバー側で決定する。MVPではJPEG、JPEGとして選択されるMPO、PNG、およびHEIF/HEICを受け付け、
原本は再圧縮や別形式への変換を行わず、受信したバイト列のまま保存する。MPOは先頭の主画像を表示用画像として
検証・サムネイル生成に使用し、複数画像を含む原本自体は変更しない。

サムネイルはアップロード確定時に長辺480px以下へ縮小し、品質80、method 4のWebPとして内蔵SSD上の
`PHOTO_DERIVATIVE_ROOT`へ保存する。小さい画像は拡大せず、透過画像のアルファチャンネルは維持する。
一覧とアルバムは
サムネイルAPIを使い、拡大モーダルは原本APIを使う。
原本表示、原本ダウンロード、サムネイル、およびZIP書き出しには`Cache-Control: private, no-store`を設定し、
同じブラウザで利用者が切り替わった場合や
公開範囲を狭めた後に、認証を迂回してキャッシュ済み画像が表示されないようにする。
Cloudflareでは`/api/*`をCache RuleでBypassする。動的API全体へ適用する本番方針は
[`deployment.md`](./deployment.md#キャッシュ方針)に定める。

JSONサイドカーは原本と同じディレクトリへ同じUUIDで保存し、DB復旧に必要な原本情報、派生画像の所在、共有メモと
その最終更新情報、および共有先を保持する。現在のスキーマバージョンは`6`とし、`metadata_version`でDB上の編集状態と照合する。
サムネイル本体は再生成可能なのでHDDへ複製しない。
共有先をバックフィルするマイグレーションの適用後は、`python -m app.commands.sync_photo_sidecars`を実行して
全写真のJSONサイドカーをDBの最新状態から再生成する。コマンドは途中で失敗しても再実行できる。

## アップロード処理

複数ファイルは共通の共有グループ集合とともに`UploadBatch`、`UploadBatchGroupShare`、`UploadItem`へ登録する。バッチは24時間有効とし、PostgreSQLのtransaction-level
advisory lockでバッチ作成を直列化してから、未受信バイト数を既存のactiveバッチと合算して空き容量を確認する。
ブラウザは4 MiBごと、サーバーは最大8 MiBの受信単位とし、
`Upload-Offset`で必ず先頭からの受信位置を照合する。通信中断後はDBと`.part`の実サイズを再照合し、未受信部分から
再開する。ReactがバッチIDと選択ファイルを保持するのは同じページを開いている間だけであり、ページ再読み込み後の
再開は対象外とする。期限切れは次回アクセスまたは新規バッチ作成時に検出し、一時ファイルを破棄する。

本番Reactは常にこの分割アップロードを使用する。Cloudflareのリクエスト本文上限とファイル全体の
`PHOTO_MAX_UPLOAD_BYTES`は別の制約として扱う。単一ファイル互換APIを含む本番上限の詳細は
[`deployment.md`](./deployment.md#アップロード)に定める。

フロントエンドは2ファイルまで並列送信し、成功、重複、失敗をファイルごとに表示する。一部の失敗で成功済みを
巻き戻さず、失敗分だけを再試行できる。`processing`は原本確定の状態であり、将来の画像解析Workerは写真登録後の別ジョブとする。

```text
リクエスト受信
  ↓
Content-Lengthの事前確認（存在する場合）
  ↓
HDDの識別、マウント、書き込み権限、空き容量を確認
  ↓
申告されたMIMEタイプの事前確認
  ↓
incoming/<UUID>.partへチャンク単位で書き込み
  ├── 実サイズを計測
  └── SHA-256を計算
  ↓
サイズ上限とJPEG/MPO、PNG、HEIF/HEICのファイル内容を最終検証
  ↓
画像の幅、高さ、およびEXIFの撮影日時を取得
  ↓
同じアップロードユーザーによる同一SHA-256の登録を確認
  ↓
PHOTO_DERIVATIVE_ROOT/incoming/<UUID>.thumbnail.partへWebPサムネイルを生成
  ↓
incoming/<UUID>.json.partへ復旧用メタデータを書き込み
  ↓
originals/YYYY/MM/<UUID>.<extension>へrename
  ↓
originals/YYYY/MM/<UUID>.jsonへrename
  ↓
PHOTO_DERIVATIVE_ROOT/thumbnails/YYYY/MM/<UUID>.webpへrename
  ↓
PostgreSQLへメタデータを登録してcommit
  ↓
201 Created
```

互換用の単一ファイルmultipart APIでは、Starletteがリクエスト本文を解析する前にmiddlewareで`Content-Length`を
確認する。multipart境界とヘッダーのため最大ファイルサイズに64 KiBを加えた値をリクエスト上限とし、ファイル自体の
正確な上限はHDDへのチャンク書き込み中にも検証する。バッチAPIでは各PATCHを最大8 MiBに制限する。

`Content-Length`は未指定または不正確な場合があるため、それだけを信用しない。書き込み中も実サイズを
計測し、上限を超えた時点で中断する。失敗時は可能な範囲で`.part`ファイルを削除する。

許可するMIMEタイプは`image/jpeg`、`image/png`、`image/heif`、および`image/heic`とする。ただし、クライアントが
送信するファイル名、拡張子、およびMIMEタイプだけでは形式を確定せず、PillowでJPEG、MPO、およびPNGを、
`pillow-heif`でHEIF/HEICをデコードし、実際の内容、画像サイズ、および破損の有無を検証する。MPOは
`image/jpeg`として受け付けて先頭の主画像を検証・表示に使用する。HEIF/HEICはlibheifがデコード可能な
コンテナだけを受け付け、AVIFはMVPの対象外として拒否する。

JSONスキーマバージョン6では、不変な原本情報と派生画像一覧を`asset`、ユーザー編集情報を`metadata`、
共有先を`sharing`へ分離する。
トップレベルには`schema_version`、`id`、`metadata_version`を保存し、共有メモ、その最終更新者・更新日時、および
共有先もDB復旧対象として保持する。
日時はAPIと同じUTCのISO 8601形式とし、JSONをDBクエリの代わりには使用しない。撮影日時などJSONに含まれる
復旧対象のメタデータを後から変更する場合は、DB更新とあわせてJSONも`.part`への書き込みとrenameで更新する。

撮影日時はEXIFの撮影日時を優先して取得する。EXIFにUTCオフセットが含まれる場合はその値を使用し、含まれない
場合は`PHOTO_DEFAULT_TIMEZONE`で指定するJST（`Asia/Tokyo`）として解釈してUTCへ変換する。EXIFが存在しない、
または値が不正な場合は`captured_at`をnullとし、写真のアップロード自体は失敗させない。

## ファイルとDBの整合性

原本、JSON、サムネイルの複数回のrename、およびPostgreSQLのcommitを単一トランザクションにはできない。
MVPでは原本、JSON、サムネイル、DBの順に確定し、次の復旧方針を採用する。

- JSONの確定に失敗した場合、確定済み原本の削除を試みる
- サムネイル確定に失敗した場合、確定済み原本とJSONの削除を試みる
- DB登録に失敗した場合、確定済み原本、JSON、サムネイルの削除を試みる
- 削除にも失敗した原本またはJSONは孤立ファイルとして残す
- 定期的または管理操作で孤立した`.part`、原本、JSON、サムネイル、およびDBレコードを検出できるようにする
- HDD上の原本とJSONを走査してメタデータを再構築できるよう、パス規則とJSONスキーマを安定させる
- DBレコードが存在して原本がない場合は、欠損状態として検出・報告する
- JSONがない原本は自動登録せず、再解析で復元可能な情報と復元不能な情報を報告する

`python -m app.commands.check_photo_integrity`は読み取り専用でDB上の全写真を走査し、原本、JSONサイドカー、
サムネイルの欠損、ファイルサイズの不一致、DBから構築した期待値とJSONの不一致、およびDBから参照されない
原本・JSON・サムネイルを報告する。原本側と派生画像側の`incoming`も走査し、DB上の進行中アップロードに
対応しない一時ファイルを`orphan_part`として報告する。`--verify-hashes`を指定した場合だけ原本全体を読み、SHA-256をDB値と照合する。
問題がなければ終了コード0、問題を検出した場合は1とし、ファイルやDBは変更しない。検出結果からの自動修復や、
JSONからDBを再構築する復旧コマンドは未実装とする。

## 将来提案

人物検出は現在のバックエンド契約に含めない。プロダクト境界、バックエンド構成、暫定スキーマ、およびテスト案は
[`proposals/person-detection.md`](./proposals/person-detection.md)へ分離する。

## ストレージ利用可否の判定

アップロード前に最低限、次の項目を確認する。

- 設定されたストレージルート自体が想定したHDDのマウントポイントである
- ルート直下の`.photo-storage-marker`が存在し、設定された識別値と一致する
- `originals`と`incoming`が書き込み可能である
- 利用可能容量が設定された安全基準以上である
- シンボリックリンクなどを経由して許可範囲外へ保存しない

単にディレクトリが存在するだけでは利用可能と判定しない。HDDが外れた状態で内蔵SSD上の同名ディレクトリへ
書き込む事故を防ぐ。

## DBアクセスとマイグレーション

- SQLAlchemy 2の同期EngineとSessionを使用する
- PostgreSQLドライバーにはpsycopg 3を使用する
- Sessionはリクエストごとに作成し、処理終了時に必ずcloseする
- commitとrollbackの境界はサービスのユースケース単位で明示する
- DBスキーマ変更はAlembicのマイグレーションとして管理する
- アプリケーション起動時に`create_all()`で本番スキーマを暗黙生成しない

ファイルI/OとDBアクセスはいずれも同期処理から開始する。必要性を計測する前に非同期DBを導入しない。

## 設定

設定値は型付き設定オブジェクトから参照し、アプリケーションコード内へ環境固有のパスや認証情報を
ハードコードしない。想定する主な環境変数は次のとおり。

| Variable | 用途 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL接続URL |
| `AUTH_TRUSTED_ORIGINS` | ログインを許可するOriginのカンマ区切り一覧 |
| `AUTH_SESSION_IDLE_SECONDS` | セッションのアイドル期限 |
| `AUTH_SESSION_ABSOLUTE_SECONDS` | セッションの絶対期限 |
| `AUTH_SESSION_TOUCH_SECONDS` | 最終利用日時を更新する最小間隔 |
| `AUTH_COOKIE_SECURE` | セッションCookieをHTTPSのみに制限。本番では`true`必須 |
| `AUTH_LOGIN_ATTEMPTS` | 制限期間内に許可するログイン失敗回数 |
| `AUTH_LOGIN_WINDOW_SECONDS` | ログイン試行制限の期間 |
| `AUTH_INVITATION_TTL_SECONDS` | 招待URLの有効期間。既定値は24時間 |
| `PHOTO_STORAGE_ROOT` | HDDのマウントポイントそのものを指す絶対パス |
| `PHOTO_DERIVATIVE_ROOT` | 内蔵SSD上の再生成可能な派生画像ディレクトリ。省略時は`backend/var/photo-derivatives` |
| `PHOTO_STORAGE_MARKER` | ルート直下の`.photo-storage-marker`と照合する識別値 |
| `PHOTO_MAX_UPLOAD_BYTES` | 1ファイルあたりの最大サイズ |
| `PHOTO_MIN_FREE_BYTES` | アップロードを許可する最低空き容量 |
| `PHOTO_UPLOAD_CHUNK_BYTES` | 分割書き込みのチャンクサイズ |
| `PHOTO_DEFAULT_TIMEZONE` | UTCオフセットがないEXIF撮影日時の解釈に使うタイムゾーン。`Asia/Tokyo` |
| `PUSH_ALLOWED_ENDPOINT_HOSTS` | 購読登録を許可するWeb Push providerのHTTPSホスト一覧 |
| `PUSH_MAX_SUBSCRIPTIONS_PER_USER` | 1ユーザーが登録できるPush購読数の上限 |
| `MONITORING_PING_URL_*` | systemd保守ジョブごとの任意Healthchecks互換ping URL。実値は本番環境ファイルだけへ保存 |

`PHOTO_DEFAULT_TIMEZONE`は`Asia/Tokyo`とする。開発用の例では最大アップロードサイズを100 MiB、書き込みチャンクを
1 MiB、最低空き容量を10 GiBとする。100 MiBはCloudflareの100 MBリクエスト上限とは異なるが、本番Reactは
分割アップロードを使用する。環境ごとの値とHDDのマウント先は`.env.example`をもとに設定する。`.env`は
ユーザー管理の秘密情報として扱い、アプリケーションコードやドキュメントへ実値を記録しない。

## テスト方針

### Storageテスト

- pytestの一時ディレクトリをストレージルートとして使用する
- 実際の外付けHDDへ書き込まない
- チャンク書き込み、ハッシュ、原本とJSONのrename、サイズ上限、後始末を検証する
- JSONのスキーマ、原本との対応、および途中のrenameに失敗した場合の孤立検出を検証する
- HDD利用不可に相当する状態を依存関係またはテスト用実装で再現する

### Authテスト

- Argon2idハッシュ、ユーザー名正規化、セッショントークンのハッシュ化を検証する
- 期限切れ、失効、CSRF不一致、信頼されないOrigin、およびログイン試行制限を検証する
- Cookie属性、汎用ログインエラー、およびセッション失効を検証する
- 実PostgreSQLを使い、パスワード変更と旧パスワードによるログインが直列化されることを並行テストで検証する

### Serviceテスト

- StorageとSessionの境界を制御して正常系と失敗時の後始末を検証する
- 重複、DB commit失敗、ファイル確定失敗を検証する
- 掃除のグループ認可、管理者権限、期限計算、停止状態、および完了者記録を検証する
- 買い物のグループ認可、一覧順、購入者記録、状態復元、および同時更新競合を検証する
- 実PostgreSQLを使い、所属解除と掃除・買い物の変更操作がグループ行ロックで直列化されることを検証する
- Alembicの全revisionをPostgreSQL向けoffline SQLへ展開し、DDL生成と単一headを検証する
- 通知Outboxのclaim、stale復旧、重複防止、および購読端末単位の再試行を実PostgreSQLで検証する
- 保守runが成功、警告、および例外終了で必ず終端状態へ遷移することを検証する

### Routerテスト

- FastAPIの依存関係をテスト用SessionとStorageへ差し替える
- multipart uploadとレスポンススキーマを検証する
- ドメイン例外が適切なHTTPステータスへ変換されることを検証する

### マイグレーションテスト

- CIで空のPostgreSQLに対して最新マイグレーションを適用できることを確認する
- DB統合テストと単体テストを分離し、必要なテストだけを個別実行できるようにする

## 今後の設計候補（優先順ではない）

- ホーム画面の既存API呼び出し数が問題になった場合の集約API
- 整合性検査で検出した孤立ファイルと欠損ファイルの修復コマンド
- 既存写真の派生画像再生成とバックグラウンド処理
- 動画の取り扱い
- iPhone以外の端末とSafari以外のブラウザへの対応

## 未決定事項

- HDDの正確なマウント先と環境ごとのマーカー値
- 最大アップロードサイズと最低空き容量
- 派生画像キャッシュの使用量上限と削除・再生成ポリシー
- 原本配信時のキャッシュとRange request対応
- 本番用の公開ホスト名とCloudflareプラン
- Cloudflare停止時にも独立したLAN内HTTPS経路を将来用意するか

人物検出に関する未決定事項とテスト案は[`proposals/person-detection.md`](./proposals/person-detection.md)に、
本番配信の未決定事項と受入条件は[`deployment.md`](./deployment.md)に分離する。

## 写真のゴミ箱と完全削除

写真は`active`、`trashed`、`purge_pending`の状態を持つ。論理削除時は原本を移動せず、通常の写真認可・一覧・
新着・アルバム・書き出しから除外する。所有者だけが閲覧・復元でき、共有先、アルバム所属、メモ、お気に入りは
復元のため保持する。ライフサイクル状態はJSONサイドカースキーマ7にも保存する。

完全削除ではDBを先に`purge_pending`へ確定してから原本、サイドカー、派生画像を冪等に削除し、最後にDBレコードを
削除する。途中失敗は`python -m app.commands.purge_trashed_photos`から再試行できる。既定保持期間は30日とする。

## 保守状態と通知

`features.maintenance`は管理者向けストレージ集計と保守実行履歴を提供する。整合性検査、DBバックアップ、2台目HDD
スナップショット、およびゴミ箱削除はHTTPから起動せず、管理コマンドとsystemd timerで実行する。

`features.notifications`はログインセッションに結び付くWeb Push購読、ユーザー設定、およびOutboxを管理する。
写真共有と買い物追加は本体変更と同じDBトランザクションでOutboxへ追加し、掃除期限は定期コマンドで追加する。
配信Workerは失効・期限切れセッションを除外する。Outboxのclaim時刻とtokenを記録し、停止したclaimだけを
再キューへ戻す。端末ごとの配信状態を保持し、成功済み端末へ再送せず一時失敗した端末だけを再試行する。
購読endpointはHTTPSかつ設定したprovider hostに限定し、ユーザー単位の登録上限を設ける。
VAPID秘密鍵はリポジトリ外のファイルから読み込む。
通知種別、初期設定、配信・再試行、およびフロントエンドを含む現在の実装状況は
[`web-push.md`](./web-push.md)を参照する。
