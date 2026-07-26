# 人物検出の暫定提案

English version: [person-detection.md](./person-detection.md)

## 状態と目的

人物検出は未実装であり、現在のロードマップやAPI・DB契約には含めない。写真枚数や検索上の課題から必要性が
明確になった場合に、精度、処理負荷、ライセンス、および保守コストを再評価して着手を判断する。

採用する場合は、個人の写真整理で「人物あり」の写真を絞り込めることを目的とする。人物の存在確認だけを行い、
顔認識、個人識別、年齢・性別などの属性推定、およびシーン分類は対象外とする。解析は自宅PC内で完結させ、写真を
外部のAIサービスへ送信しない。

## 想定する機能境界

- 軽量な物体検出DNNで人物クラスだけを検出する
- 写真ごとに人物の有無、検出人数、最大信頼度を保存する
- Reactの写真一覧へ「人物あり」フィルターを追加する
- 原本を変更せず、解析結果だけをPostgreSQLへ保存する
- アップロード完了を推論で待たせず、保存後の別処理として解析する
- モデル名とバージョンを保存し、モデル変更後に再解析できるようにする
- 人物未検出と未解析・解析失敗を区別し、人物未検出を自動的に風景写真とは扱わない

## 想定するバックエンド構成

```text
app/features/photos/
└── person_detection/
    ├── detector.py
    ├── models.py
    ├── service.py
    └── worker.py
```

- `detector.py`: モデルの読み込み、前処理、人物クラスの検出
- `models.py`: 人物検出結果と解析状態
- `service.py`: 解析対象の取得、推論、結果保存、失敗処理
- `worker.py`: FastAPIリクエストとは別に解析するエントリーポイント

モデル固有APIは`detector.py`へ閉じ込める。最初は1枚を手動解析するコマンドで精度と処理時間を確認し、必要性が
確認できた後に継続Workerへ発展させる。

## 処理フロー

```text
原本、JSONサイドカー、サムネイルを確定
  ↓
Photoと人物解析pendingを同じDBトランザクションで登録
  ↓
アップロードAPIは成功を返す
  ↓
Workerがpendingを取得
  ↓
人物クラスだけを検出
  ↓
結果、モデル情報、解析日時をPostgreSQLへ保存
```

DNN推論中はDB行ロックを保持しない。モデルは写真ごとに読み込まず、Worker起動時に1回だけ読み込む。CPUで
1枚ずつ処理する構成から開始し、実測が必要性を示すまでGPUや分散処理を導入しない。

## 暫定データモデル

`photo_person_analyses`は`photo_id`を主キー兼外部キーとし、1枚につき現在の解析状態と最新結果を最大1件保持する。
解析履歴は初期案に含めない。

| Column | PostgreSQL type | Null | 用途 |
| --- | --- | --- | --- |
| `photo_id` | `UUID` | No | Primary key、`photos.id`への外部キー |
| `status` | `VARCHAR(16)` | No | `pending`、`processing`、`succeeded`、`failed` |
| `has_person` | `BOOLEAN` | Yes | 人物が1件以上検出されたか |
| `person_count` | `INTEGER` | Yes | 検出人数 |
| `max_confidence` | `DOUBLE PRECISION` | Yes | 最大信頼度 |
| `model_name` | `TEXT` | Yes | 使用したモデル名 |
| `model_version` | `TEXT` | Yes | モデルまたは重みのバージョン |
| `attempt_count` | `SMALLINT` | No | 解析開始を試みた回数 |
| `error_message` | `TEXT` | Yes | 最後の失敗理由 |
| `queued_at` | `TIMESTAMPTZ` | No | 解析待ち登録日時 |
| `started_at` | `TIMESTAMPTZ` | Yes | 最後の解析開始日時 |
| `analyzed_at` | `TIMESTAMPTZ` | Yes | 解析成功日時 |

主な制約案は次のとおりとする。

- `attempt_count`と`person_count`は0以上、`max_confidence`は0以上1以下
- `has_person`と`person_count`が両方設定されている場合は`has_person = (person_count > 0)`
- `succeeded`の場合だけ判定結果、モデル情報、および`analyzed_at`を保持する
- `failed`の場合だけ`error_message`を必須とする
- 再解析で`pending`へ戻すときは、古い判定結果、モデル情報、完了日時、およびエラーをクリアする
- 写真を将来削除する場合は`ON DELETE CASCADE`で解析レコードも削除する

複数Workerを許可する場合は、短いトランザクション内で`FOR UPDATE SKIP LOCKED`を使って古い`queued_at`から
1件取得し、`processing`へ更新してから推論する。異常終了した`processing`を再試行できるよう、`started_at`と
`attempt_count`を使用する。再試行間隔と最大回数は実装時に決定する。

## モデルとデータの管理

- 自宅PCのCPUで候補モデルの処理時間と精度を比較する
- 採用前にモデルとライブラリのライセンスを確認する
- Ultralytics YOLOを採用する場合はAGPL-3.0への対応方針を明示する
- 重みは内蔵SSDへ保存し、Gitへコミットしない
- 入手元、バージョン、可能であればチェックサムを記録する
- 推論用の縮小画像は一時データとし、外付けHDD上の原本を変更しない
- 実際の個人写真をテストや精度評価用としてリポジトリへ追加しない

## テスト案

- 通常の単体テストでは実モデルを読み込まず、テスト用Detectorへ差し替える
- 人物あり、人物なし、推論失敗、再試行、および再解析を検証する
- Workerが同じ写真を同時取得しないことをPostgreSQL統合テストで検証する
- 実モデルによる精度確認を通常のテストから分離する
- モデルのダウンロードや外部ネットワークを通常のテスト実行で要求しない

## 着手前に決める事項

- 実利用上、人物フィルターが必要な写真枚数と検索課題
- 使用するモデル、信頼度閾値、ライセンス、重みの配置先
- Workerの起動方式、再試行、停止、監視
- 再解析時の負荷と進捗表示
- バックアップ対象と、再生成可能な情報の境界
