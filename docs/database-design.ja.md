# データベース設計

English version: [database-design.md](./database-design.md)

## 目的

Family Hubの写真、掃除管理、および買い物リストで使用するPostgreSQLのスキーマ、制約、インデックス、および
マイグレーション方針を定める。画像本体は外付けHDDへ保存し、PostgreSQLには検索と整合性確認に必要な
メタデータだけを保存する。DB復旧用として、原本と同じUUIDを持つJSONサイドカーも外付けHDDへ保存する。

開発初期のスキーマは単一ベースラインへ統合済みであり、その後の機能は独立したマイグレーションで追加する。
人物検出などの将来機能は必要性を再評価して実装を決定した段階でテーブルを追加し、未確定の機能に備えた
テーブルは先に作らない。

```text
family_groups 1 ───── 0..N albums 1 ───── 0..N album_photos N..0 ───── 1 photos
photos 1 ───── 1 photo_metadata
photos 1 ───── 0..N photo_derivatives
photos 1 ───── 0..N photo_shares N..1 ───── 1 family_groups
users 1 ───── 0..N photo_favorites N..1 ───── 1 photos
photos 1 ───── 0..N photo_activity_events 1 ───── 1..N photo_activity_event_groups N..1 ───── 1 family_groups
users 1 ───── 0..1 photo_activity_states
users 1 ───── 0..N family_group_members N..1 ───── 1 family_groups
family_groups 1 ───── 0..N cleaning_tasks 1 ───── 0..N cleaning_completions
users 1 ───── 0..N cleaning_completions
family_groups 1 ───── 0..N shopping_items
users 1 ───── 0..N shopping_items (created_by / purchased_by)
users 1 ───── 0..N upload_batches 1 ───── 1..N upload_items N..0 ───── 0..1 photos
upload_batches 1 ───── 0..N upload_batch_group_shares N..1 ───── 1 family_groups
users 1 ───── 0..N push_subscriptions N..1 ───── 1 user_sessions
users 1 ───── 0..N notification_preferences
users 1 ───── 0..N notification_outbox 1 ───── 0..N notification_deliveries
push_subscriptions 1 ───── 0..N notification_deliveries
maintenance_runs
administrative_audit_events
```

上図は現在のスキーマだけを示す。未実装機能の暫定スキーマは`proposals/`へ分離し、現行のリレーションには含めない。

## 共通方針

- 主キーにはPostgreSQLの`UUID`型を使用する
- UUIDはファイル書き込み前にPythonでUUID v4を生成し、一時ファイル、原本、およびDBレコードで
  共有する
- 日時にはタイムゾーン付きの`TIMESTAMPTZ`を使用し、UTCで記録する
- PostgreSQLのセッションタイムゾーンもUTCとし、DB接続元のOS設定に依存させない
- FastAPIは日時をUTCのISO 8601形式で返し、DBとAPIの境界ではJSTへ変換しない
- Reactは日時をJST（`Asia/Tokyo`）へ明示的に変換して表示する
- 日付別の検索とグループ化にはJSTの日付境界を使用する
- 写真の整理と表示には`captured_at`を優先し、取得できない場合だけ`uploaded_at`へフォールバックする
- DBには画像データ、HDDの絶対パス、および環境固有のマウント先を保存しない
- 制約とインデックスにはAlembicで安定して管理できる名前を付ける
- PostgreSQL固有のENUMは当面使用せず、変更しやすい文字列と`CHECK`制約を使用する

## 日時の取り扱い

DBに保存する値とAPIが返す値はUTC、ユーザーに見せる値はJSTとする。

```text
PostgreSQL  2026-07-14 03:00:00+00
FastAPI     2026-07-14T03:00:00Z
React       2026年7月14日 12:00 JST
```

`uploaded_at`はサーバー側で現在時刻をUTCとして生成する。`captured_at`はEXIFにUTCオフセットがあればその値を
尊重してUTCへ変換する。UTCオフセットがない場合はJST（`Asia/Tokyo`）として解釈し、UTCへ変換してから保存する。
EXIFが存在しない、または日時が不正な場合は`captured_at`をnullにする。

Reactでは実行環境のローカルタイムゾーンへ暗黙変換せず、`Intl.DateTimeFormat`などへ`Asia/Tokyo`を明示する。
日付別検索では、ユーザーが指定したJSTの開始時刻以上、翌日の開始時刻未満となる範囲をUTCへ変換してDBへ渡す。
これにより、UTCでは前日になるJSTの深夜帯も正しい日付へ含める。

## `users`テーブル

管理コマンドまたは管理者が発行した招待から作成する家族ユーザーを保持する。一般向けの登録画面は提供しない。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `username` | `VARCHAR(64)` | No | NFKCと大文字・小文字を正規化したUnicodeユーザー名、unique |
| `password_hash` | `TEXT` | No | Argon2idハッシュ。平文パスワードは保存しない |
| `is_active` | `BOOLEAN` | No | 無効ユーザーのログインと既存セッション利用を拒否 |
| `system_role` | `VARCHAR(16)` | No | システム全体の`admin`または通常の`user` |
| `created_at` | `TIMESTAMPTZ` | No | ユーザー作成日時 |
| `password_changed_at` | `TIMESTAMPTZ` | No | これより古いセッションを無効化 |

`username`には`ck_users_username_lowercase`を設定する。1文字以上64文字以下のUnicode文字・数字とピリオド、
アンダースコア、ハイフンを許可し、APIと管理コマンドでも検証する。
グループ内の`admin`と`member`は`system_role`とは独立して管理する。招待受諾で作成するユーザーの
`system_role`は必ず`user`とする。

## `user_invitations`テーブル

システム管理者が発行する1回限りのアカウント作成招待を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `username` | `VARCHAR(64)` | No | 招待時に予約する正規化済みユーザー名 |
| `token_hash` | `VARCHAR(64)` | No | 招待トークンのSHA-256ハッシュ、unique |
| `created_by_user_id` | `UUID` | No | 発行したシステム管理者、削除時はrestrict |
| `created_at` | `TIMESTAMPTZ` | No | 発行日時 |
| `expires_at` | `TIMESTAMPTZ` | No | 有効期限 |
| `used_at` | `TIMESTAMPTZ` | Yes | アカウント作成に使用した日時 |
| `revoked_at` | `TIMESTAMPTZ` | Yes | 管理者が取り消した日時 |

未使用かつ未取消の同一ユーザー名の招待は1件に限定する。再発行時は以前の招待を取り消す。受諾時は招待を
行ロックし、有効期限、使用日時、取消日時、およびユーザー名重複を検証してから、通常ユーザー作成と`used_at`更新を
同一トランザクションで確定する。トークン原値はDBへ保存せず、発行時に1回だけクライアントへ返す。

## `user_sessions`テーブル

ブラウザへ発行したサーバー側セッションを保持する。Cookieへ保存したランダムトークンの原値はDBへ保存せず、
SHA-256ハッシュだけを`token_hash`へ保存する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `user_id` | `UUID` | No | `users.id`への外部キー、ユーザー削除時にcascade |
| `token_hash` | `VARCHAR(64)` | No | セッショントークンの小文字SHA-256、unique |
| `csrf_token` | `VARCHAR(43)` | No | セッションへ結び付ける32バイトのURL-safeトークン |
| `created_at` | `TIMESTAMPTZ` | No | セッション作成日時 |
| `last_seen_at` | `TIMESTAMPTZ` | No | アイドル期限の判定に利用 |
| `expires_at` | `TIMESTAMPTZ` | No | 絶対期限 |
| `revoked_at` | `TIMESTAMPTZ` | Yes | ログアウトなどによる失効日時 |

認証時は`token_hash`の一意制約に伴うインデックスで検索する。全セッション失効を効率化するため、`user_id`に
`ix_user_sessions_user_id`を作成する。期限切れセッションの定期削除は運用量を確認してから追加する。

## `family_groups`テーブル

写真やアルバムの共有先として使用する家族のまとまりを保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `name` | `VARCHAR(120)` | No | 前後の空白を除いた1文字以上120文字以下の名前 |
| `created_by_user_id` | `UUID` | No | 作成した`users.id`への外部キー、削除時はrestrict |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時 |
| `updated_at` | `TIMESTAMPTZ` | No | グループ情報の更新日時 |

グループ名はシステム全体で一意とする。作成者からグループを検索できるよう、`created_by_user_id`へインデックスを作成する。

## `family_group_members`テーブル

ユーザーと家族グループの多対多関係、およびグループ内だけで有効な権限を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時はcascade |
| `user_id` | `UUID` | No | `users.id`への外部キー、削除時はrestrict |
| `role` | `VARCHAR(16)` | No | `admin`または`member` |
| `joined_at` | `TIMESTAMPTZ` | No | グループへ参加した日時 |

`(group_id, user_id)`を複合主キーとして同じ所属の重複を防ぐ。ユーザーの所属グループ一覧を効率的に取得するため、
`user_id`へインデックスを作成する。グループ作成時はグループと作成者の`admin`所属を同じトランザクションで
登録し、管理者のいないグループを作らない。メンバー追加、権限変更、および解除では対象グループを行ロックし、
同じグループへの管理操作を直列化する。最後の有効な`admin`を降格または解除する操作はcommit前に拒否する。

## `family_group_membership_invitations`テーブル

グループ管理者から既存の有効ユーザーへの参加依頼を保持する。`group_id`、`user_id`、依頼者、予定ロール、
`pending`・`accepted`・`rejected`の状態、作成・応答日時を持つ。同じグループとユーザーの未応答依頼は1件に限定し、
承認時に`family_group_members`を同じトランザクションで作成する。グループ削除時はcascadeする。

## `cleaning_tasks`テーブル

家族グループで共有する掃除箇所と頻度を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時はcascade |
| `name` | `VARCHAR(120)` | No | 前後の空白を除いた1文字以上120文字以下の掃除箇所名 |
| `interval_days` | `INTEGER` | No | 1以上3650以下の24時間単位の頻度 |
| `is_active` | `BOOLEAN` | No | 完了記録を受け付ける有効状態。既定値はtrue |
| `created_by_user_id` | `UUID` | No | 作成した`users.id`への外部キー、削除時はrestrict |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時。未完了時の期限計算基準 |
| `updated_at` | `TIMESTAMPTZ` | No | 名前、頻度、または状態の最終更新日時 |

グループの有効・停止タスクを取得するため、`(group_id, is_active)`へ
`ix_cleaning_tasks_group_id_is_active`を作成する。カウントダウンや`next_due_at`は保存せず、最新完了日時または
`created_at`へ`interval_days`を加算してAPIで算出する。停止は論理状態の変更とし、履歴を保持する。

## `cleaning_completions`テーブル

掃除完了を追記型の履歴として保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `task_id` | `UUID` | No | `cleaning_tasks.id`への外部キー、タスク削除時はcascade |
| `completed_by_user_id` | `UUID` | No | 完了を記録した`users.id`への外部キー、削除時はrestrict |
| `completed_at` | `TIMESTAMPTZ` | No | サーバーがUTCで設定する完了日時 |

最新完了を安定して取得するため、`(task_id, completed_at DESC, id DESC)`へ
`ix_cleaning_completions_task_id_completed_at`を作成する。同時に完了ボタンが押された場合も両方を履歴として保持し、
日時とUUIDの降順で先頭となる完了を次回期限の基準とする。完了履歴の編集・削除APIは初期実装へ含めない。

## `shopping_items`テーブル

家族グループで共有する買うものと現在の購入状態を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時はcascade |
| `name` | `VARCHAR(120)` | No | 前後の空白を除いた1文字以上120文字以下の品目名 |
| `created_by_user_id` | `UUID` | No | 追加した`users.id`への外部キー、削除時はrestrict |
| `purchased_by_user_id` | `UUID` | Yes | 購入済みにした`users.id`への外部キー、削除時はrestrict |
| `created_at` | `TIMESTAMPTZ` | No | 品目の追加日時 |
| `updated_at` | `TIMESTAMPTZ` | No | 購入状態を含む最終更新日時 |
| `purchased_at` | `TIMESTAMPTZ` | Yes | サーバーが設定する購入日時。未購入ではnull |

`purchased_by_user_id`と`purchased_at`は両方nullまたは両方設定済みの状態だけを許可する。グループ内の未購入品と
直近購入済み品を取得するため、`(group_id, purchased_at, created_at)`へ
`ix_shopping_items_group_id_purchase_state`を作成する。未購入品は`created_at ASC, id ASC`、購入済み品は
`purchased_at DESC, id DESC`で取得する。購入状態の変更時は行ロックを使用し、購入履歴用の別レコードは初期実装では
作成しない。未購入へ戻すと購入者と購入日時をnullへ戻す。

## `photos`テーブル

写真の原本と1対1で対応するメタデータを保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `uploaded_by_user_id` | `UUID` | No | `users.id`への外部キー、ユーザー削除時はrestrict |
| `uploaded_by_username` | `VARCHAR(64)` | No | アップロード時点のユーザー名スナップショット |
| `original_filename` | `TEXT` | No | アップロード時の表示用ファイル名 |
| `storage_key` | `TEXT` | No | ストレージルートからの相対パス、unique |
| `content_type` | `TEXT` | No | 検証済みMIMEタイプ |
| `size_bytes` | `BIGINT` | No | 原本のバイト数、0より大きい |
| `sha256` | `VARCHAR(64)` | No | 小文字16進数64文字、アップロードユーザーとの組み合わせでunique |
| `width` | `INTEGER` | Yes | 画像の幅 |
| `height` | `INTEGER` | Yes | 画像の高さ |
| `captured_at` | `TIMESTAMPTZ` | Yes | EXIFなどから得た撮影日時 |
| `uploaded_at` | `TIMESTAMPTZ` | No | アップロード日時、デフォルトは現在時刻 |
| `lifecycle_state` | `VARCHAR(16)` | No | `active`、`trashed`、`purge_pending` |
| `trashed_at` | `TIMESTAMPTZ` | Yes | ゴミ箱へ移動した日時 |
| `trashed_by_user_id` | `UUID` | Yes | ゴミ箱へ移動した所有者 |
| `purge_after` | `TIMESTAMPTZ` | Yes | 自動完全削除の期限 |
| `purge_requested_at` | `TIMESTAMPTZ` | Yes | 完全削除開始日時 |

### 制約

- `storage_key`は一意とし、複数レコードが同じ原本を指さないようにする
- `uploaded_by_user_id`は必須とし、対応するユーザーが存在しない写真を登録しない
- 通常の写真一覧と写真単体の認可は`photo_shares`を参照する
- 写真単体と原本の取得は、本人または共有先グループのメンバーだけに許可する
- 写真を保持したままユーザーを削除しない。利用停止には`users.is_active`を使用する
- `(uploaded_by_user_id, sha256)`を一意とし、同じユーザーによる同一内容の重複登録を防ぐ
- 別ユーザーの`private`写真の存在を重複エラーから推測できないよう、重複判定はユーザーをまたがない
- `size_bytes`は0より大きい値に限定する
- `sha256`は`^[0-9a-f]{64}$`に一致する値に限定する
- `width`と`height`は両方null、または両方が0より大きい状態だけを許可する
- ライフサイクル状態と削除関連日時の組み合わせをチェック制約で固定する

制約名は、例えば次のようにする。

```text
pk_photos
uq_photos_storage_key
uq_photos_uploaded_by_user_id_sha256
ck_photos_size_bytes_positive
ck_photos_sha256_lower_hex
ck_photos_dimensions
```

対応画像形式をDBの`CHECK`制約には含めない。MIMEタイプと実際のファイル内容はアップロード処理で
検証する。MVPではJPEG、JPEGとして選択されるMPO、PNG、およびHEIF/HEICを許可するが、将来ほかの形式や動画を
追加するときにDBマイグレーションを必須にしない。

## `photo_metadata`テーブル

ユーザーが後から編集できる写真情報を原本情報から分離して保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `photo_id` | `UUID` | No | `photos.id`への外部キー兼主キー、写真削除時にcascade |
| `memo` | `TEXT` | Yes | 閲覧者が共同編集するプレーンテキスト、2000文字以下 |
| `memo_updated_by_user_id` | `UUID` | No | 最後にメモを更新した`users.id`への外部キー、削除時はrestrict |
| `memo_updated_by_username` | `VARCHAR(64)` | No | 最終更新時点のユーザー名スナップショット |
| `memo_updated_at` | `TIMESTAMPTZ` | No | メモの最終更新日時 |
| `version` | `INTEGER` | No | 1以上の楽観的ロック用バージョン |
| `created_at` | `TIMESTAMPTZ` | No | メタデータ作成日時 |
| `updated_at` | `TIMESTAMPTZ` | No | 最終編集日時 |

更新APIはクライアントが取得した`version`を必須とし、不一致の場合は`409 Conflict`を返す。共有メモは写真を閲覧できる
全ユーザー、共有範囲は写真所有者だけが更新できる。メモまたは共有範囲が更新されるたびにバージョンを増やし、JSON
サイドカーの`metadata_version`と一致させる。メモ更新時だけ`memo_updated_by_*`と`memo_updated_at`を更新する。

## `photo_derivatives`テーブル

原本から再生成できる表示用画像を保持する。初期実装では全写真に一覧用サムネイルを1件作成する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key |
| `photo_id` | `UUID` | No | `photos.id`への外部キー、写真削除時にcascade |
| `kind` | `VARCHAR(16)` | No | 現在は`thumbnail` |
| `storage_key` | `TEXT` | No | `PHOTO_DERIVATIVE_ROOT`からの相対パス、unique |
| `content_type` | `VARCHAR(64)` | No | 現在は`image/webp` |
| `width` | `INTEGER` | No | 派生画像の幅、0より大きい |
| `height` | `INTEGER` | No | 派生画像の高さ、0より大きい |
| `size_bytes` | `BIGINT` | No | 派生画像のバイト数、0より大きい |
| `created_at` | `TIMESTAMPTZ` | No | 生成日時 |

`(photo_id, kind)`を一意として同じ用途の派生画像を重複させない。サムネイルは長辺480px以下、品質80、
エンコードmethod 4のWebPとして内蔵SSDへ保存し、原本と
サイドカーは従来どおり外付けHDDへ保存する。派生画像が欠損した場合は原本から再生成できるものとして扱う。

## `photo_shares`テーブル

写真の共有先を保持する。共有行がない写真は所有者だけが閲覧できる。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key |
| `photo_id` | `UUID` | No | `photos.id`への外部キー、写真削除時にcascade |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時にcascade |
| `created_at` | `TIMESTAMPTZ` | No | 共有設定日時 |

`(photo_id, group_id)`をuniqueとし、同じ写真を複数グループへ共有できる。共有行が0件なら個人のみ、1件以上なら
API上の`shared`として扱う。旧global-family audienceはグループ共有への移行後にスキーマから撤去する。

## `photo_favorites`テーブル

ユーザーごとに独立したお気に入りを保持する。共有設定やアルバムとは連動しない。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `user_id` | `UUID` | No | `users.id`への外部キー、ユーザー削除時にcascade |
| `photo_id` | `UUID` | No | `photos.id`への外部キー、写真削除時にcascade |
| `created_at` | `TIMESTAMPTZ` | No | お気に入りへ追加した日時 |

`(user_id, photo_id)`を複合主キーとして冪等な追加を可能にする。写真の閲覧認可は別途`photo_shares`で判定し、
お気に入り行そのものには閲覧権限を持たせない。

## `photo_activity_events`テーブル

自分以外の家族が閲覧可能にした写真を新着画面へ表示するため、アップロードまたは後からの共有追加を追記型で保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key |
| `photo_id` | `UUID` | No | `photos.id`への外部キー、写真削除時にcascade |
| `actor_user_id` | `UUID` | No | 操作した`users.id`への外部キー、削除時はrestrict |
| `actor_username` | `VARCHAR(64)` | No | 操作時点のユーザー名スナップショット |
| `event_type` | `VARCHAR(16)` | No | `uploaded`または`shared` |
| `operation_id` | `UUID` | No | 一括アップロードまたは一括共有を表示上で集約する操作ID |
| `occurred_at` | `TIMESTAMPTZ` | No | アップロード確定または共有追加のサーバー時刻 |

一覧は`(occurred_at DESC, id DESC)`でカーソルページングする。既存共有先を維持した更新と共有解除ではイベントを
追加せず、新しく追加された共有グループがある場合だけ`shared`イベントを追加する。同じアップロードバッチまたは
一括共有操作で作成したイベントには共通の`operation_id`を設定し、新着画面で1件にまとめる。単体操作にも固有の
操作IDを設定する。マイグレーション前の写真は
バックフィルせず、導入後に発生した操作だけを新着として扱う。

## `photo_activity_event_groups`テーブル

イベント発生時に写真を新しく閲覧可能にしたグループを保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `event_id` | `UUID` | No | `photo_activity_events.id`への外部キー、削除時にcascade |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、削除時にcascade |

`(event_id, group_id)`を複合主キーとする。取得時はイベントのグループに現在所属し、`joined_at`がイベント日時以前で、
同じグループへの`photo_shares`が現在も存在することを検証する。これにより参加前の履歴や共有解除後の写真を表示しない。

## `photo_activity_states`テーブル

ユーザーごとの新着既読位置を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `user_id` | `UUID` | No | Primary key兼`users.id`への外部キー、削除時にcascade |
| `seen_through_at` | `TIMESTAMPTZ` | No | 最後に確認したイベント日時 |
| `seen_through_event_id` | `UUID` | No | 同一日時の順序を確定するイベントID |

日時とUUIDの組を既読位置として使い、それより新しく、かつ現在閲覧可能なイベントを未読件数として数える。

### 一覧用インデックス

一覧APIは撮影日時を優先し、撮影日時を取得できない場合だけアップロード日時を使用する。アップロード日時は
撮影日時の代替値としてDBへ保存せず、`captured_at`はnullのまま維持する。APIや画面では撮影日時が不明で
あることを区別する。

```sql
SELECT *
FROM photos
ORDER BY COALESCE(captured_at, uploaded_at) DESC, id DESC;
```

同じ日時のレコードも順序が安定するよう、UUIDを第2ソートキーにする。この並び順を支援する式インデックスを
作成する。

```sql
CREATE INDEX ix_photos_sort_date_id
    ON photos (COALESCE(captured_at, uploaded_at) DESC, id DESC);
```

`storage_key`と`(uploaded_by_user_id, sha256)`には一意制約に伴うインデックスが作成されるため、同じカラムへ別の
インデックスを重複して作成しない。撮影日時が不明な写真だけを抽出するなど、別の検索要件が生じた場合に
追加のインデックスを検討する。

一覧は上記の日時とUUIDをカーソルへ格納し、最後に取得した組み合わせより小さい行を最大100件取得する。
キーワード検索は元ファイル名と`photo_metadata.memo`の部分一致を対象とする。写真枚数が増えても部分一致検索を
全件走査しないよう`pg_trgm`拡張を有効化し、次のGINインデックスを使用する。

```sql
CREATE INDEX ix_photos_original_filename_trgm
    ON photos USING gin (original_filename gin_trgm_ops);
CREATE INDEX ix_photo_metadata_memo_trgm
    ON photo_metadata USING gin (memo gin_trgm_ops);
```

月別タイムラインと日付検索では、`COALESCE(captured_at, uploaded_at)`を`Asia/Tokyo`へ変換してJSTの日付境界と
月境界を使用する。DBに保存する日時自体はUTCのまま変更しない。

## `upload_batches`テーブル

ブラウザがまとめて選択した写真の受信単位を保持する。写真原本の永続メタデータではなく、通信中断後の
再開、予約容量、および部分成功を管理する運用状態である。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key |
| `owner_user_id` | `UUID` | No | `users.id`への外部キー、ユーザー削除時はcascade |
| `status` | `VARCHAR(16)` | No | `active`、`completed`、`canceled` |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時 |
| `expires_at` | `TIMESTAMPTZ` | No | 再開可能期限 |
| `completed_at` | `TIMESTAMPTZ` | Yes | 完了または中止日時 |

`(owner_user_id, created_at DESC)`にインデックスを作成する。期限切れの`active`バッチは次回アクセスまたは
新規作成時に`canceled`へ移行し、未完了項目の`.part`を破棄する。
APIレスポンスの`visibility`は永続化せず、共有グループが0件なら`private`、1件以上なら`shared`として導出する。
ファイル完了時には所有者の現在のグループ所属を再検証し、作成後に共有権限を失ったバッチを中止する。

## `upload_batch_group_shares`テーブル

一括アップロード内の全写真へ適用する共有グループ集合を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `batch_id` | `UUID` | No | `upload_batches.id`への外部キー、バッチ削除時にcascade |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時にcascade |

`(batch_id, group_id)`を複合主キーとし、同じグループの重複指定を防ぐ。

## `upload_items`テーブル

1ファイルごとの受信位置と最終結果を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、成功時は写真IDと一致 |
| `batch_id` | `UUID` | No | `upload_batches.id`への外部キー、バッチ削除時はcascade |
| `client_id` | `VARCHAR(64)` | No | ブラウザ内のファイル識別子 |
| `original_filename` | `TEXT` | No | 表示用の元ファイル名 |
| `declared_content_type` | `VARCHAR(64)` | No | クライアント申告MIMEタイプ |
| `size_bytes` | `BIGINT` | No | 予定サイズ、0より大きい |
| `received_bytes` | `BIGINT` | No | `.part`と再照合する受信済み位置 |
| `status` | `VARCHAR(16)` | No | `queued`、`uploading`、`processing`、`succeeded`、`duplicate`、`failed` |
| `error_code` | `VARCHAR(32)` | Yes | 再試行判定と表示に用いる安定コード |
| `photo_id` | `UUID` | Yes | 成功時の`photos.id`、写真削除時はnull |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時 |
| `completed_at` | `TIMESTAMPTZ` | Yes | 終端状態へ移行した日時 |

`(batch_id, client_id)`をunique、`received_bytes`を0以上`size_bytes`以下とする。ファイル間は独立して完了し、
1項目の失敗で成功済みの写真を巻き戻さない。

## `albums`テーブル

写真を旅行などのまとまりで整理するためのアルバムを保持する。アルバムは写真原本の保存場所や所有権を変更しない。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Primary key、アプリケーションで生成 |
| `title` | `VARCHAR(120)` | No | 前後の空白を除いた1文字以上120文字以下の名前 |
| `description` | `TEXT` | Yes | 2000文字以下の任意説明 |
| `group_id` | `UUID` | No | `family_groups.id`への外部キー、グループ削除時にcascade |
| `cover_photo_id` | `UUID` | Yes | 明示指定した表紙。`(id, cover_photo_id)`で`album_photos`を参照 |
| `created_by_user_id` | `UUID` | No | `users.id`への外部キー、ユーザー削除時はrestrict |
| `created_by_username` | `VARCHAR(64)` | No | 作成時点のユーザー名スナップショット |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時 |
| `updated_at` | `TIMESTAMPTZ` | No | 名前、説明、または写真構成を最後に変更した日時 |

一覧は`updated_at DESC, id DESC`で並べ、写真枚数を`album_photos`から集計して返す。同じ名前のアルバムは許可する。
グループメンバー全員が閲覧・編集できる。グループに所属しない旧アルバム状態は現行スキーマで許可しない。

## `album_photos`テーブル

アルバムと写真の多対多の関連を保持する。

| Column | PostgreSQL type | Null | 制約・用途 |
| --- | --- | --- | --- |
| `album_id` | `UUID` | No | `albums.id`への外部キー、アルバム削除時にcascade |
| `photo_id` | `UUID` | No | `photos.id`への外部キー、写真削除時にcascade |
| `added_at` | `TIMESTAMPTZ` | No | アルバムへ追加した日時 |

`(album_id, photo_id)`を複合主キーとして同じ写真の二重登録を防ぐ。`photo_id`から所属アルバムを検索できるよう
`ix_album_photos_photo_id`を作成する。アルバム内の写真は
`COALESCE(captured_at, uploaded_at) ASC, photos.id ASC`で古い順に返す。明示表紙が未設定の場合は`added_at`が最も古い
写真を表紙として返す。明示表紙は同じアルバムに所属する写真だけを指定でき、対象写真を外した場合はnullへ戻す。
共有解除によって写真がアルバムのグループから閲覧不能になる場合も、同じトランザクションで関連と明示表紙を解除する。

アルバムと関連は編集可能な情報であるためJSONサイドカーには保存しない。DB喪失時の復元にはデータベース
バックアップを使用する。

## ファイル保存との対応

`storage_key`には次のような相対パスだけを保存する。

```text
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.jpg
```

`YYYY/MM`は撮影日時ではなくアップロード日時から決定する。撮影日時はEXIFが存在しない場合や、
アップロード時点で未解析の場合があるため、保存先の決定には使用しない。HDDのマウント先が変わった場合は、
`PHOTO_STORAGE_ROOT`の設定変更だけで対応する。

物理的な保存先と写真としての並び順は独立して扱う。撮影日時を後から取得または修正しても原本は移動せず、
DBとJSONサイドカーの`captured_at`を更新する。JSONがない、または`captured_at`が不正な場合は、画像内に
残っているEXIFから再取得を試みる。

`original_filename`は画面表示用のメタデータであり、パス生成には使用しない。

JPEG、JPEGとして選択されるMPO、PNG、およびHEIF/HEICの原本は再圧縮や形式変換を行わず、アップロードされた
バイト列のまま保存する。MPOの検証とサムネイル生成には先頭の主画像を使用する。
画像形式はDBの`content_type`だけを信用せず、アップロード時と復旧時に原本の内容を検証する。

### JSONサイドカー

各原本と同じディレクトリへ、同じUUIDを持つJSONを保存する。

```text
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.jpg
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.json
```

JSONはDBを失った場合の復旧情報であり、通常の一覧や検索には使用しない。スキーマバージョン`6`では原本と
派生画像一覧、編集可能メタデータ、および共有先を別オブジェクトとして保存する。

| JSON field | 用途 |
| --- | --- |
| `schema_version` | JSON形式のバージョン |
| `id` | `photos.id`と原本ファイル名で共有するUUID |
| `metadata_version` | `photo_metadata.version`と一致する編集バージョン |
| `asset` | アップロードユーザー、原本情報、画像サイズ、撮影・登録日時、および派生画像一覧 |
| `metadata` | 共有メモ、その最終更新者・更新日時などユーザーが編集する復旧対象情報 |
| `sharing` | 複数の家族グループIDを含む共有先配列 |

復旧時はJSONを無条件には信用せず、UUIDとパスの対応を確認し、原本からサイズ、ハッシュ、MIMEタイプ、および
画像サイズを再検証する。`captured_at`は後から修正される可能性があるためJSONの値を使用し、値がない、または
不正な場合だけEXIFから再取得する。JSONに含まれる復旧対象のメタデータを変更するときは、`.part`へ新しいJSONを
書き込んでからrenameし、DBとJSONの両方を更新する。サムネイルの所在は整合性確認用に含めるが、人物解析結果など
それ以外の再生成可能な派生情報は含めない。

## 将来スキーマ

人物検出など未実装機能のテーブルは現在のスキーマ契約へ含めない。人物検出の暫定データモデルは
[`proposals/person-detection.md`](./proposals/person-detection.md)へ分離し、着手決定時に再検証してから
本書とAlembicへ反映する。

## アップロード時のトランザクション

受信チャンクごとに`upload_items.received_bytes`をcommitし、通信中断後に`.part`の実サイズと再照合できるようにする。
受信完了後は項目を`processing`にcommitしてから、原本、JSONサイドカー、およびWebPサムネイルを確定し、
`photos`、`photo_metadata`、`photo_derivatives`、必要な`photo_shares`、および共有写真の
`photo_activity_events`と`photo_activity_event_groups`を同じトランザクションで登録する。
`UploadItem.id`を`Photo.id`に使うことで、確定直後にプロセスが中断しても再実行時に登録済みを判定できる。

```text
原本をHDD上で確定
  ↓
JSONサイドカーをHDD上で確定
  ↓
WebPサムネイルを内蔵SSD上で確定
  ↓
photos、photo_metadata、photo_derivatives、photo_sharesを追加
  ↓
共有写真ではphoto_activity_events、photo_activity_event_groupsを追加
  ↓
同一トランザクションでcommit
```

DBのcommitに失敗した場合は、確定済み原本、JSON、およびサムネイルの削除を試み、削除できなかった場合は
孤立ファイルとして復旧対象にする。

複数ファイルのrenameとDBのcommitは単一トランザクションにできないため、定期的または管理操作によって
一部だけ存在する原本、JSON、サムネイル、DB未登録のファイル、および原本や派生画像が欠損したDBレコードを
検出できるようにする。

## マイグレーション方針

開発初期の変更履歴は、実データの投入前にDBを完全リセットし、`20260715_01`の単一ベースラインへ統合した。
このベースラインは、統合時点で実装済みだった認証、写真、アルバム、家族グループ、招待、再開可能アップロード、
掃除タスクの全テーブル、制約、外部キー、インデックスを空のPostgreSQLへ直接作成する。

今後のスキーマ変更はベースラインを書き換えず、機能単位の新しいマイグレーションとして追加する。
`20260715_02`では、この方針に従って`photo_derivatives`を追加した。
`20260715_03`では、`pg_trgm`拡張と元ファイル名・メモの部分一致検索用GINインデックスを追加した。
`20260715_04`では、家族グループ単位の`shopping_items`と購入状態検索用インデックスを追加した。
`20260716_05`では、共有メモの最終更新者と更新日時を追加し、既存行は写真のアップロードユーザーと従来の更新日時で
バックフィルした。
`20260716_06`では、ユーザー別お気に入り、一括アップロードの共有グループ、アルバムの所属グループと表紙を追加し、
共有行を`photo_id`と`group_id`だけの現行形式へ単純化した。
従来の`family`写真は所有者が所属する全グループへ共有し、既存アルバムは作成者が最初に所属したグループへ割り当てる。
アルバム内写真には割り当て先グループへの共有行を追加し、割り当て先のない開発中の旧アルバムは撤去する。
このrevisionは旧共有データを不可逆に変換するためdowngradeを明示的に拒否する。変更前のrevisionを適用済みの
開発DBはリセットして履歴を再適用する。マイグレーション後は管理コマンドでJSONサイドカーをDBの共有状態へ同期する。
`20260716_07`では、共有写真の新着イベント、その対象グループ、表示集約用の操作ID、およびユーザーごとの既読位置を
追加した。既存写真は新着としてバックフィルせず、マイグレーション適用後のアップロードと共有追加からイベントを記録する。
実データを保持する環境へ適用する変更には、必要なバックフィルと、downgradeまたはバックアップからの復元手順を含める。
`20260717_08`では写真のゴミ箱ライフサイクル、`20260717_09`では保守実行履歴、`20260717_10`では
Push購読、通知設定、および通知Outboxを追加した。`20260720_11`ではOutboxのclaim時刻とtoken、および
購読端末単位の配信状態を追加した。開発DBはリセット可能なため既存ダミーデータのバックフィルは行わない。
`20260723_12`ではグループ名の一意制約を追加し、`20260723_13`では管理監査ログとグループ参加依頼を追加した。
人物検出、タグ、シーン分類などは、各機能の必要性と仕様が決まった時点で個別に追加する。

アプリケーション起動時の`create_all()`でスキーマを暗黙生成しない。すべてのスキーマ変更を
Alembicの履歴として残し、既存データを保持したまま適用・ロールバックできる単位にする。

## 当面作成しないテーブル

- 人物検出結果と解析ジョブ
- タグ
- 顔認識または個人識別結果
- シーン分類結果

これらは必要性とデータの関係が明確になってから設計する。

## 保守・通知テーブル

`administrative_audit_events`はシステムまたはグループ単位の管理操作、実行者のIDと当時のユーザー名、対象、
秘密情報を含まないJSON詳細、および実行日時を保持する。ユーザー・グループを物理削除しても監査行を保持できるよう、
実行者とグループIDには外部キーを設定しない。

`maintenance_runs`は保守ジョブ種別、実行状態、開始・終了日時、構造化サマリー、および秘密情報を除いた失敗理由を
保持する。`push_subscriptions`はユーザーとログインセッションへ関連付け、endpointと暗号鍵を保存する。
`notification_preferences`は写真共有、掃除期限、買い物追加の有効状態をユーザー単位で保持する。
`notification_outbox`は受信者と重複防止キーを一意にし、本体ユースケースと同じトランザクションで登録する。
`claimed_at`と`claim_token`でWorkerの所有権と停止判定を管理する。`notification_deliveries`はOutboxとPush購読の
複合主キーを持ち、端末ごとの試行回数、成功・失敗状態、完了日時、および秘密情報を含まないエラーコードを保持する。
