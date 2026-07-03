# growth-content

这个仓库每天自动更新一条儿童成长内容：

- 从真实儿童发展/育儿相关研究里选 1 篇文献
- 生成 1 条较完整的三语成长短句
- 保留研究依据简述和家庭实践建议
- 下载一张竖版、安静、有留白的背景图
- 写入 `growth-feed.json`、`content_pool.json` 和 `images/`

## 现在的自动化方式

每天定时任务会直接提交到 `main` 分支，不再每天创建一个需要手动合并的 PR。

如果当天已经有内容，程序会自动跳过；如果文献、模型或图片接口失败，程序会停止，不会写入半截 JSON。

## 需要的 GitHub Secrets

仓库需要配置：

- `UNSPLASH_ACCESS_KEY`：用于下载背景图片

`GITHUB_TOKEN` 由 GitHub Actions 自动提供，不需要手动添加。

## 内容质量规则

新版本会尽量避免：

- 重复使用同一篇文献
- 把一篇旧文献拆成很多天反复发
- 生成过短、太浅的总结
- 使用太像以前的中文短句
- 重复使用同一张 Unsplash 图片
- 使用看起来过于相似的背景图
- 写坏 `growth-feed.json`

## 手动检查

如果想检查当前 JSON 是否健康，可以在本地运行：

```bash
python scripts/generate_daily_growth.py --validate-only
```

如果本地没有安装依赖，GitHub Actions 仍然会在云端自动安装并运行。
