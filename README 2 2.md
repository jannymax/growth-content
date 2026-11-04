# growth-content

> 文档描述设计与运行方式；每天自动更新是否成功，须查 GitHub Actions、最新提交与数据文件，不能仅凭本说明判断。

每日成长内容仓库。现行定时入口复用已有三语研究内容库，配图从人工审阅的 `curated/photos.json` 取用，不再随机搜索图片。

## 配图标准（2026-11-04 用户确认）

以 Yunus Tuğ 的暮色麦田（10014507）及 Shiebi AL 的暮色草花（4223699）为已确认基准：光色细腻、后期完成度高、留白舒展、景深过渡自然，让人放松并产生向往。近景与远景均可；不固定题材或色调。每图检查后期，尊重原作已完成的调色，不机械套滤镜。

## 发布与补充

先实际看图、核对原作与许可，再将合适的 JPEG 放入 `curated/photos/`，在清单记录作者、作品页、许可和审核状态。仅 `approved` 可发布。按清单顺序选取，已发布 Pexels ID 不重复。初始储备仅两张，耗尽会明确失败并保留原有线上内容，不随机降级。补图后手动运行每日工作流可继续。

GitHub Actions 每天运行，生成成功后提交 main。沿用原来的图片 URL、日期 ID、JPEG 与三语数据结构，未修改 App。历史图片不覆盖，避免旧版缓存不刷新。图片来自 Pexels，许可：https://www.pexels.com/license/ 。精选图使用1440像素宽发布版本，保留完整构图和作者光色。

## 验证

`python -m unittest discover -s tests`

`python scripts/generate_daily_growth.py --validate-only`

本入口不再需要 Unsplash 或生图密钥；旧 Unsplash 函数仅保留兼容参考，不由发布路径调用。未提交本地生图实验或内部制作记录。
