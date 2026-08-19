# バックエンド設計

English version: [backend-design.md](./backend-design.md)

## 目的

この文書では、Family Hubの写真、掃除、買い物機能を支えるFastAPIとPostgreSQLの段階的なバックエンドを定義する。
MVPのアーキテクチャ、責務、依存方向、API境界、データモデル、ファイル保存、安全性、およびテスト方針を扱う。
製品の範囲は[`product-brief.md`](./product-brief.md)、詳細なスキーマとマイグレーション方針は
[`database-design.md`](./database-design.md)を参照する。

## 設計原則

- 機能単位でコードを整理する
- 各機能内でrouter、model、schema、serviceを分離する
- 複数機能から必要になるまでは、機能固有のコードをその機能内に置く
- 暗黙の初期化や登録のためにimportを使用しない
- FastAPI routerは`app.include_router(...)`で明示的に登録する
- 起動と終了にはFastAPIのlifespanを使用する
- ファイルシステムとPostgreSQLは不整合になり得るものとして、検出と復旧を可能にする
- ファイル単位の受信は並列化し、原本・サイドカー・DBレコードの確定だけを直列化する
- 早すぎる抽象化より、学習と動くMVPを優先する

## ディレクトリ構成

```text
backend/
├── alembic/
├── app/
│   ├── main.py
│   ├── commands/
│   ├── core/
│   ├── database/
│   └── features/
│       ├── albums/
│       ├── auth/
│       ├── cleaning/
│       ├── groups/
│       ├── health/
│       ├── maintenance/
│       ├── notifications/
│       ├── photos/
│       └── shopping/
└── tests/
    ├── commands/
    ├── core/
    ├── database/
    └── features/
```

コマンドには、ユーザー・ダミーユーザー作成、パスワードリセット、DBおよび二次ストレージのバックアップ、
写真整合性検査、サイドカー同期、ゴミ箱の完全削除、OpenAPI出力、通知のキュー投入・配信、監視通知、権限管理を含める。
ユーザー作成では、有効なシステム管理者が存在する場合に限り通常ユーザーを作成できる。初期構築では管理者を明示的に作成する。
権限管理はWeb管理と同じトランザクションアドバイザリロックを使用する。必要になる前に空のパッケージやプレースホルダーのテストを作成しない。

## 各領域の責務

### `core`

`config.py`は型付き環境設定、`lifespan.py`はアプリケーションとプロセス資源の起動・終了、`middleware.py`は機能入力より前に実行する
アプリケーション全体のHTTP制約を担当する。`core`を機能ロジックの一般的な置き場にしない。

### `database`

`base.py`はSQLAlchemy Declarative BaseとAlembicメタデータを定義する。`session.py`はengine、session factory、リクエスト単位の
session依存関係を定義する。モデル検出はimportの副作用に依存させず、Alembic用の明示的なモデル読み込み関数またはregistryを用意する。

### `features.health`

公開livenessはアプリケーションプロセスが稼働中であることだけを返す。ループバック限定のreadinessはPostgreSQLと写真ストレージの
読み取り可否を確認し、どちらかが利用できない場合はプロセスの起動を妨げずに`503`を返す。Caddyは公開経路上の正確なreadinessパスを
`404`で遮断する。詳細な認証付きストレージ状態は写真機能が担当する。

### `features.auth`

家族ログイン、サーバー側セッション、システム権限、招待によるアカウント作成、CSRF検証、ログインレート制限を担当する。
router、serviceロジック、`User`、`UserSession`、`UserInvitation`モデル、Argon2idパスワードヘルパー、レート制限、認証依存関係、
招待処理、および意図的に小さくした`public.py`境界を含む。

ログインとパスワード変更では、現在のハッシュを検証する前に対象の`User`行を`FOR UPDATE`でロックする。これにより、パスワード変更と
同時に古いパスワードでログインして新しいセッションを作成することを防ぐ。

運用管理者によるパスワードリセットでは、ユーザーにパスワード変更を要求するフラグを立てる。このフラグが立っている間、ユーザーが
認証後に行えるのは現在のセッション取得、パスワード変更、ログアウトだけであり、その他の認証付き機能APIは`403`を返す。
招待の受諾は運用管理者によるリセットとは別であり、招待されたユーザーは一度だけの招待受諾時に自分のパスワードを選択し、
強制変更フラグは付与されない。

他の機能は`features.auth.public`、`require_authenticated_user`、`require_password_change_complete`、
`require_csrf_token`だけを使用でき、authの内部実装を直接importしてはならない。

### `features.groups`

グループ作成、メンバーシップ、グループ内権限、招待、管理画面向け集計、監査情報へのアクセス、メンバー変更を担当する。
非メンバーにはグループの存在を開示せず`404`を返す。候補ユーザーはグループ管理者にだけ返し、有効かつ未所属でなければならない。
DBの一意制約と事前確認の両方で、重複名を`409 Conflict`へ変換する。

HTTPによるグループ削除APIは提供しない。物理削除の経路は運用管理者向けの
`python -m app.commands.delete_group --group-id <UUID>`だけとする。関連データがある場合は`--include-related-data`が必要である。
コマンドは件数を表示し、グループ名の完全一致確認を要求し、削除直前に再ロックして再集計し、状態が変わっていれば中止する。
カスケードによりメンバーシップ、招待、アルバムとその関連、掃除履歴、買い物項目、写真共有、活動グループ関連、アップロードバッチ共有を削除する。
写真は残し、影響を受けたサイドカーはコミット後に同期する。

メンバーシップ削除、およびメンバーシップに依存する写真・アップロード・アルバム・掃除・買い物の操作は、対象の`FamilyGroup`を先に
ロックしてからメンバーシップを再確認することで直列化する。複数種類の行が必要な場合は、グループ、写真、アルバム、掃除タスク、買い物項目の順でロックする。

最後の有効なシステム管理者またはグループ管理者を変更し得るミューテーションでは、PostgreSQLのトランザクションアドバイザリロックを1つ使用する。
認可確認の前にロックを取得し、判断からコミットまで保持することで、システム管理者の状態変更とグループ管理者のメンバー変更が同時実行されても
管理者不変条件が壊れないようにする。

### `features.cleaning`

グループ単位の掃除タスク、日数間隔、追記専用の完了履歴を担当する。メンバーは有効なタスクの一覧と完了登録を行い、グループ管理者は作成、編集、
停止、再開を行える。ミューテーションではグループをロックし、メンバーシップを再確認してからタスクをロックする。完了時刻は常にサーバーの現在UTC時刻を使う。
全履歴を読み込まず最新の完了をタスクごとに返すため、PostgreSQLの`DISTINCT ON`を使用する。非メンバーには`404`を返す。

### `features.shopping`

グループ内の品目、購入状態、購入者、購入時刻を担当する。全メンバーが操作できる。ミューテーションではグループをロックし、メンバーシップを再確認してから
品目をロックし、メンバー削除と同時の状態変更を直列化する。購入時刻はサーバーが生成するUTC時刻とする。非メンバーには`404`を返す。

### `features.photos`

アップロード、保存、メタデータ、認可、共有、お気に入り、活動、ゴミ箱、書き出し、取得を担当する。routerは写真、ゴミ箱、書き出し、チャンクアップロードの
HTTP境界を提供する。serviceはストレージとDBの処理を調整する。`access.py`は所有者とグループ共有の可視性、`activity.py`は新着と既読位置、
`queries.py`は検索、カーソル、月別集計、`registration.py`は確定済み写真・サイドカー・共有の準備、`uploads.py`はバッチ状態、
`storage.py`はHDD状態の検証、チャンクのストリーム処理、ハッシュ、サイドカー書き込み、ファイル確定、`thumbnails.py`は画像または動画先頭フレームからの
WebPサムネイル生成、`video_validation.py`は`ffprobe`による対応動画コンテナの検証を担当する。
`export.py`は全体を一時ZIPにしてから返すのではなく、ZIPをストリーム配信する。`public.py`は他機能が必要とする読み取り専用の写真カタログだけを公開する。
ユースケースserviceは責務ごとに分割し、`access_service.py`は読み取り、コンテンツ、お気に入り、`metadata_service.py`はメモ、撮影時刻の上書き、共有、
`upload_service.py`は単一写真の登録、`trash_service.py`はゴミ箱遷移と完全削除、`export_service.py`はZIP書き出し選択の検証を担当する。
バッチアップロードは引き続き`uploads.py`に置く。

### `features.albums`

アルバムの作成、編集、削除、写真関連を担当する。アルバム操作は原本やJSONサイドカーを変更しない。アルバムのグループへすでに共有されている写真だけを
追加でき、アルバム所属自体は写真の可視性を与えない。この機能は写真の内部実装ではなく`features.photos.public`だけを使用する。
service/DBロジックが読みにくくなるまではrepository層を意図的に導入しない。

### `features.maintenance`と`features.notifications`

maintenanceは管理者向けのストレージ集計と保守履歴を公開する。整合性検査、DBバックアップ、二次HDDスナップショット、ゴミ箱の完全削除は、
HTTPではなく管理コマンドとsystemd timerだけで実行する。

notificationsはセッションに結び付いたWeb Push購読、設定、outboxを担当する。DBの複合外部キーにより、保存した購読のユーザーとセッション所有者を一致させる。
写真共有と買い物項目追加は業務変更と同じトランザクションでoutbox行を作成し、掃除期限通知は定期的にキューへ入れる。
workerは期限切れセッションを除外し、時刻とトークンでclaimし、古いclaimを再キュー化し、失敗した端末だけを再試行する。
エンドポイントはHTTPSで、設定済みのproviderホストに限定する。VAPID秘密鍵はリポジトリの外に置く。

## 依存方向

```text
router
  ↓
service
  ├── SQLAlchemy Session
  ├── registration（読み取り専用session + storage）
  └── storage
```

- routerはファイルを書き込まず、SQLAlchemyのクエリを直接実行しない
- serviceはHTTPレスポンスやステータスコードに依存しない
- storageはFastAPIやSQLAlchemyに依存しない
- modelはrouter、service、schemaに依存しない
- 公開serviceメソッドがユースケースのcommit、rollback、確定済みファイルの補償削除を所有する
- 共通のregistrationロジックはcommitもrollbackもしない
- 機能間で他機能の内部モジュールをimportせず、`public.py`または明示的な公開依存関係を使用する
- アーキテクチャテストで機能間の内部importを検出する

## アプリケーション生成

`main.py`はアプリケーション生成とrouterの明示的な登録に限定する。

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

lifespanは`FastAPI`へ明示的に渡し、`Settings`生成時に設定の組み合わせを検証する。プロセス起動時にDBやHDDの利用可能性を必須にせず、
使用時に確認して状態エンドポイントが障害を説明できるようにする。ストレージが利用できない場合はアップロードと原本取得を`503`で拒否し、
空き容量の安全しきい値を下回るアップロードは`507`で拒否する。

## 本番配信境界

Cloudflareを公開入口、Caddyをオリジンの唯一のHTTP入口とし、FastAPIはloopbackで待ち受ける。PostgreSQL、内蔵の写真ストレージHDD、
接続を解除した外付けバックアップHDDはクライアントへ公開しない。原本は認証・認可済みのAPIエンドポイントだけから配信する。
Tunnel、Caddy、転送ヘッダー、キャッシュ、アップロード、ZIP、受入条件は[`deployment.md`](./deployment.md)を参照する。

## API契約

MVPのAPIは`/api/v1`を使用する。このprefix外の情報用routeはOpenAPI契約から除外する。FastAPIのOpenAPIスキーマを正本とし、
フロントエンド型、fetch client、SDKは`frontend/src/shared/api/generated/`へ生成する。生成ファイルを直接編集してはならず、routerやPydantic schemaを変更したら再生成する。

すべてのミューテーションで認証とCSRFの要件を宣言する。認証・認可はrouter境界だけでなくservice境界でも確認する。存在を開示してはならないリソースには`404`を返す。

セッションはランダムなHttpOnly Cookieトークンを使用し、保存するのはSHA-256ハッシュだけとする。ミューテーションにはセッションに結び付いたCSRFトークンを要求する。
認証付きAPIとバイナリには`Cache-Control: private, no-store`を使用する。

写真検索は、パスワード変更を完了した認証済みユーザー向けに`GET /api/v1/photos/search-options`を提供する。
レスポンスには、名前・ID順で安定ソートしたアップロード者候補と現在のグループ候補を含める。アップロード者は呼び出し元から見える有効写真の作者に限定する。
写真詳細レスポンスには呼び出し元が現在所属している共有グループだけを出し、共有写真でも`group_ids`が空になる場合がある。
所有者によるメタデータ更新では、所有者が現在見られない既存共有を保持する。

管理者向けユーザー一覧には`group_names`と`group_admin_group_names`の両方を含める。後者により、管理画面はそのユーザーがグループの最後の有効な管理者である場合に
利用停止操作を無効化できる。ただし、古いクライアントデータや同時実行に対してはサーバー側の不変条件チェックが最終的な権威となる。

## ファイル保存とサムネイル

```text
photo-storage/                       # 内蔵HDD; PHOTO_STORAGE_ROOT
├── originals/YYYY/MM/<UUID>.<ext>
│   └── <UUID>.json
└── incoming/<UUID>.part

backend/var/photo-derivatives/       # 再生成可能な内蔵SSDデータ
├── thumbnails/YYYY/MM/<UUID>.webp
└── incoming/<UUID>.thumbnail.part

snapshots/<timestamp>/                # 接続を解除した外付けHDD; BACKUP_STORAGE_ROOT
├── originals/
└── database-backups/
```

原本と`incoming`は同一ファイルシステムに置き、確定時にatomic renameを使えるようにする。`PHOTO_STORAGE_ROOT`はHDDのマウントポイント自体を指す。
ルートの`.photo-storage-marker`は`PHOTO_STORAGE_MARKER`と一致しなければならず、ルートとマーカーはシンボリックリンクにしない。
Linuxのマウント情報を利用できる場合は確認し、利用できなければ通常のマウントポイント判定へフォールバックする。
内蔵SSDの開発テストではbind mountを有効とするが、本番では内蔵写真ストレージHDDのマウントを指定する。
`BACKUP_STORAGE_ROOT`は別にマウントされた外付けHDDを指し、保守コマンドだけが使用する。

パスの組み立てにクライアントのファイル名や拡張子を使用しない。コンテンツ検証後の拡張子はサーバーが決める。
JPEG、MPOの主画像、PNG、HEIF/HEICは再圧縮せず受け付ける。MP4、QuickTime MOV、M4Vも受け付け、`ffprobe`で対応コンテナと利用可能な動画ストリームを確認する。
検証とサムネイルにはMPOの先頭画像または動画の先頭フレームを使うが、原本ファイルは保持する。

確定時には、内蔵SSD上に長辺480px以下、quality 80、method 4のWebPサムネイルを作成する。小さい画像を拡大せず、アルファを保持する。
一覧とアルバムはサムネイルAPIを使用し、拡大モーダルは原本APIを使用する。原本、ダウンロード、サムネイル、ZIP書き出しは`private, no-store`を返す。

サイドカーはスキーマバージョン7を使用し、原本の復旧情報、派生ファイルの場所、編集可能なメモのメタデータ、所有者が入力した撮影時刻の上書き、共有を含める。
元のEXIF撮影時刻は、写真クエリで使用する実効撮影時刻とは別に保持する。共有のマイグレーション後は
`python -m app.commands.sync_photo_sidecars`を実行して、DBからすべてのサイドカーを再生成する。

## アップロード処理

バッチ、共有グループ、項目を登録する。バッチの有効期間は24時間とする。バッチ作成をトランザクション単位のアドバイザリロックで直列化し、
空き容量の確認では既存の有効バッチに含まれる未受信バイトも加算する。ブラウザは8MiBのチャンクを送信し、サーバーは最大8MiBを受け付けて
`Upload-Offset`を検証する。各ブラウザリクエストにはタイムアウトがあり、一時的な失敗後はサーバーのoffsetと照合してチャンクを最大3回再試行する。
中断後はDBの位置と`.part`サイズを照合し、同じページが開いている間だけ再開する。期限切れバッチはアクセス時または新しいバッチ作成時にキャンセルし、一時ファイルを削除する。

現在の5秒リクエストタイムアウトは、LAN上の開発診断用に意図的に短くしている。停止したリクエストと再試行をすぐ観測するためのもので、
本番の目標値ではない。値を大きくしてもSafariが応答を保持する問題は解決しない。本番受入前には、実際のiPhoneのWi-Fiとモバイル回線の測定に基づく環境別タイムアウトを使用し、
開発用の値を本番ビルドへ含めない。

各チャンク試行にはクライアント生成の試行ID、再試行回数、直接routeか同一オリジンrouteかのラベルを付ける。ブラウザの診断メッセージとバックエンドログには、
試行ID、項目ID、offset、バイト数、レスポンスのリクエストID、時刻を記録する。バックエンドはリクエストボディの受信、永続化した`.part`の同期、
offset競合からの復旧を分けて記録し、リクエスト中断と応答消失を区別できるようにする。アップロード診断にファイル名、ファイル内容、Cookie、CSRFトークン、その他の認証情報を記録しない。

成功した`PATCH`レスポンスは空の`204`ではなく、短く明示的なサイズのbodyを持つ`200 OK`を使用する。statusと`Upload-Offset`ヘッダーを受け取った後、
ブラウザはbodyを待たずにレスポンスストリームをabortする。これにより、iPhone Safariが開発LANのcross-originリクエストを保持して7個目を無期限にキューへ積むことを防ぐ。
ローリングデプロイ中は以前の`204`レスポンスも受け付ける。

レスポンスストリームのabortは、Vite originのポート`15173`からFastAPIのポート`18000`へ直接送る開発アップロード用の回避策である。
本番アップロードはCloudflare、Caddy、FastAPIを通る公開同一オリジンの`/api`を使用する。本番受入前にabortの挙動を開発用直接アップロードrouteに限定するか、
Cloudflare経由でclient-closed responseを発生させないことを明示的に検証する。

本番React clientは常にチャンクアップロードを使用する。Cloudflareのリクエスト制限とファイル全体の`PHOTO_MAX_UPLOAD_BYTES`は別の制約である。
フロントエンドは同時に最大2ファイルを送信し、成功、重複、失敗を個別に表示する。成功したファイルをロールバックせず、失敗したファイルだけを再試行する。

```text
利用可能ならContent-Lengthを確認
  ↓
HDDの識別、マウント、書き込み権限、空き容量を検証
  ↓
incoming/<UUID>.partへチャンクを書き込み、サイズとSHA-256を計算
  ↓
サイズと実際の画像またはMP4/MOV/M4V動画の内容を検証
  ↓
画像サイズとEXIFまたは動画の作成時刻を読み取る
  ↓
同じ所有者によるSHA-256重複を確認
  ↓
一時WebPサムネイルとJSONサイドカーを作成
  ↓
原本、サイドカー、サムネイルを最終場所へrename
  ↓
PostgreSQLへメタデータ、共有、活動を登録してcommit
  ↓
201 Createdを返す
```

`Content-Length`、ファイル名、拡張子、申告MIMEタイプだけを信用しない。実際の画像内容はPillowと`pillow-heif`、動画内容は`ffprobe`で検証する。
AVIFと対応外の動画コンテナは拒否する。実行環境には動画の検証とサムネイル生成のため`ffprobe`と`ffmpeg`コマンドが必要である。
確定処理のいずれかが失敗した場合は、可能な限り完成済みファイルを削除し、削除できないファイルを整合性復旧の対象として報告する。

## ファイルシステムとDBの整合性

原本、サイドカー、サムネイルのrenameとPostgreSQLのcommitを1つのトランザクションにはできない。原本 → サイドカー → サムネイル → DBの順で確定し、
失敗時は補償処理を行う。原本とサイドカーから写真メタデータを再構築できるよう、パス規則とサイドカースキーマを安定させる。
整合性コマンドは読み取り専用で、欠損ファイル、サイズ不一致、サイドカー不一致、孤立ファイル、対応しない`.part`ファイルを報告する。
`--verify-hashes`を付けると原本も読み込み、SHA-256を比較する。問題がなければ0、問題があれば1を返し、ファイルやDBを変更しない。
自動修復とサイドカーからDBを再構築する機能は未実装である。

## ストレージ利用可否

アップロード前に、設定ルートが想定したHDDのマウントであること、マーカーが存在して一致すること、`originals`と`incoming`へ書き込めること、
空き容量が安全しきい値を満たすこと、パス解決が許可ルートの外へ出ないことを検証する。ディレクトリが存在するだけでは不十分であり、
HDDを取り外した際に同名の内蔵SSDディレクトリへ書き込む事故を防ぐ。

## DBアクセスと設定

psycopg 3を使用するSQLAlchemy 2の同期EngineとSessionを使う。リクエストごとにsessionを作成して閉じる。commitとrollbackの境界はserviceの
ユースケース単位で明示する。すべてのスキーマ変更はAlembicで管理し、本番スキーマを`create_all()`で暗黙に作成しない。
まずは同期のファイル・DB I/Oで開始し、非同期DBアクセスを導入する前に計測する。

型付き設定を使用し、環境パスや認証情報をハードコードしない。主な設定は`DATABASE_URL`、信頼するorigin、セッションのidle/absolute/touch制限、
Secure Cookieとログイン制限、24・72・168時間に固定した招待期限、`PHOTO_STORAGE_ROOT`、`PHOTO_DERIVATIVE_ROOT`、`BACKUP_STORAGE_ROOT`、
ストレージマーカー、アップロードと空き容量の制限、既定タイムゾーン、Push providerのallowlistと購読数上限、任意の`MONITORING_PING_URL_*`である。
開発時の既定値は最大ファイルサイズ100MiB、チャンク1MiB、最低空き容量10GiBとする。実際の`.env`値をコードや文書へ置かない。

## テスト方針

### Storage

実HDDではなくpytestの一時ディレクトリを使用する。チャンク書き込み、ハッシュ、原本/JSONのrename、サイズ制限、クリーンアップ、サイドカースキーマと対応関係、
孤立検出、ストレージ利用不可、外付けHDDがない・未マウント・マーカー不一致の場合のバックアップルート拒否をテストする。

### Authentication

Argon2id、ユーザー名正規化、トークンハッシュ、期限、失効、CSRF、信頼するorigin、ログイン制限、Cookie属性、一般化したログインエラー、
セッション無効化をテストする。パスワード変更とログインの直列化には実PostgreSQLの並行実行テストを使用する。

### Services

StorageとSessionの境界を制御し、重複、commit失敗、確定失敗後の成功とクリーンアップをテストする。掃除の認可、管理者権限、期限計算、停止、完了者、
買い物の並び、購入者、復元、同時競合を網羅する。グループロックの直列化、全Alembic revision、通知claimと古いclaimの復旧、重複排除、端末別再試行、
保守の終端状態には実PostgreSQLを使用する。

### Routerとマイグレーション

FastAPIの依存関係をテスト用SessionとStorage実装へ置き換える。multipartアップロード、レスポンススキーマ、ドメイン例外からHTTPへの変換をテストする。
CIでは空のPostgreSQLへ最新マイグレーションを適用し、統合テストと単体テストを別々に実行できるようにする。

## 今後の設計候補と未決定事項

候補は、既存の呼び出しが問題になった場合のホーム集約API、整合性検査結果の修復コマンド、派生画像のバックグラウンド再生成、iPhone以外やSafari以外の対応である。
未決定事項は、HDDの正確なマウント先とマーカー値、アップロードと空き容量の制限、派生画像キャッシュの方針、原本のrange requestとキャッシュ、
本番ホスト名とCloudflareプラン、Cloudflare停止時の独立したLAN HTTPSである。

人物検出は現在のバックエンド契約から除外する。詳細は[`proposals/person-detection.md`](./proposals/person-detection.md)を参照する。

## ゴミ箱と完全削除

写真は原本を移動せず、`active`、`trashed`、`purge_pending`の間を遷移する。ゴミ箱に入れた写真は通常の認可、一覧、新着、アルバム、書き出しから除外する。
閲覧・復元できるのは所有者だけとし、復元に備えて共有、アルバム関連、メモ、お気に入りは残す。アルバムの件数、ページ、表紙は有効な写真だけを対象とするが、
`AlbumPhoto`関連は残すため、復元すると既存のアルバム所属へ戻る。このライフサイクルもサイドカースキーマ7へ保存する。

完全削除ではまず`purge_pending`をcommitし、同じDBトランザクション内で写真のアルバム表紙を解除する。その後、原本、サイドカー、派生画像を冪等に削除し、
最後にDB行を削除する。中断した処理は`python -m app.commands.purge_trashed_photos`で再試行する。既定の保持期間は30日とする。

日本語版: [backend-design.ja.md](./backend-design.ja.md)
