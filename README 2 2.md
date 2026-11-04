# growth-content

> 文档描述设计与运行方式；每天自动更新是否成功，须查 GitHub Actions、最新提交与数据文件，不能仅凭本说明判断。

每日成长内容仓库。现行定时入口按 content_pool.json 数组顺序取 status=ready 的三语教材知识内容，配图从人工审阅的 `curated/photos.json` 取用，不再随机搜索图片。

## 配图标准（2026-11-04 用户确认）

以 Yunus Tuğ 的暮色麦田（10014507）及 Shiebi AL 的暮色草花（4223699）为已确认基准：光色细腻、后期完成度高、留白舒展、景深过渡自然，让人放松并产生向往。近景与远景均可；不固定题材或色调。每图检查后期，尊重原作已完成的调色，不机械套滤镜。

## 发布与补充

先实际看图、核对原作与许可，再将合适的 JPEG 放入 `curated/photos/`，在清单记录作者、作品页、许可和审核状态。仅 `approved` 可发布。按清单顺序选取，已发布 Pexels ID 不重复。初始储备仅两张，耗尽会明确失败并保留原有线上内容，不随机降级。补图后手动运行每日工作流可继续。

GitHub Actions 每天运行，生成成功后提交 main。沿用原来的图片 URL、日期 ID、JPEG 与三语数据结构，未修改 App。历史图片不覆盖，避免旧版缓存不刷新。图片来自 Pexels，许可：https://www.pexels.com/license/ 。精选图使用1440像素宽发布版本，保留完整构图和作者光色。

## 验证

`python -m unittest discover -s tests`

`python scripts/generate_daily_growth.py --validate-only`

本入口不再需要 Unsplash 或生图密钥；旧 Unsplash 函数仅保留兼容参考，不由发布路径调用。未提交本地生图实验或内部制作记录。

## 教材队列（2026-11-04）

每周一北京时间09:00由本地Codex任务检查库存并灵活研读补充，顺序为教育心理学全书、儿童成长与发展全书、理解人的发展全书。本地资料与进度位于 KIKI/research/daily-growth-textbooks；原书不上传本公开仓库。该任务需要电脑与Codex运行。

章节不绑定发布天数：内容丰富可按完整小节分批研读，内容少且库存不足可接着下一章；每条须有独立知识增量，不固定每章条数。按14至28天合格库存作为工作目标，充足时无需强制生成。分批记录小节与已推送条目进度，整章完成后才切到下一章。

每章输出 JSON 的 items 数组。每条包含稳定 id、跨教材统一 concept_id、status=ready、topic、quote（三语）、source_summary、可选 practical_takeaway；source 必须包含 title/year/url/authors/edition/chapter/pages；review 的 source_checked/standalone/semantic_dedup_checked/translations_checked 均须为 true。审核必须真实执行，结构校验不能证明科学准确性。保留必要不确定性，不强行写建议，不凑七条。

`python scripts/import_chapter.py /absolute/path/chapter-NN.json` 会验证后追加入库；相同ID相同内容重跑不重复，相同ID内容冲突拒绝。跨书概念ID及文字相似度防重，语义重复另由每周研读审核。

每周入库后仅提交 content_pool.json 和已审核新增配图。每天北京时间06:00（GitHub调度可能延迟）发布队首一条，不追补漏掉的日期。重复运行同日无动作。没有合格稿件或图片会失败保留现有线上内容，不改写旧语录凑数。工作流将内容状态、feed与图片在同一提交中推送；推送失败应重新同步后重跑。周任务不得携带未提交的其他修改发布。

建议储备28条；这是目标不是已达库存。初始已将教育心理学第1章的4条三语内容审核入库，下次从第2章继续。现有精选图片仅两张，周任务需持续补充已实际审图、核对许可的图片；不足须报告，不降低审美标准。
