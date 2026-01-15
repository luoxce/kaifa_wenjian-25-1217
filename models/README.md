# 本地模型目录（不要提交权重）

把你下载的 HuggingFace / LLaMA-Factory 模型目录放在这里，例如：

- `models/qwen/Qwen2___5-1___5B-Instruct/`（有的下载工具会把 `.` 替换成 `___`，以你本地目录名为准）

然后在 `backtest_config.yaml` 里配置：

```yaml
strategy:
  llm_provider: "llamafactory_qwen"
  llm_model_path: "models/qwen/Qwen2___5-1___5B-Instruct"
```

注意：模型文件体积很大，建议在 git 中忽略 `models/`（仓库里只保留本 README）。
