# 本地Qwen模型使用说明

## 概述

系统现在支持使用本地Qwen模型进行回测，无需调用DeepSeek API，可以节省API费用并提高响应速度。

## 支持的部署方式

### 1. llamafactory直接调用（推荐，最简单）

如果你已经通过llamafactory下载了Qwen模型，可以直接使用这种方式，无需额外部署服务。

**配置**：
```yaml
strategy:
  use_llm: true
  llm_strategy: "balanced"
  llm_provider: "llamafactory_qwen"
  llm_model_path: "models/qwen/Qwen2___5-1___5B-Instruct"  # 你的模型目录（也可以写绝对路径）
  # llm_quantization_bit: 4  # 可选，4或8，用于节省显存
```

**前提条件**：
1. 已安装llamafactory：`pip install llamafactory transformers torch`
2. 模型路径正确（目录里需要有 `config.json`）

**优点**：
- 最简单，无需额外服务
- 直接调用，延迟最低
- 支持量化，节省显存
- 适合已有llamafactory模型的用户

**适用场景**：回测、开发测试、已有llamafactory模型

### 快速自检（推荐）

把模型放到 `models/` 后，可以先跑一次自检：

```bash
# Windows 可用 py，其它系统用 python
py check_llm.py --provider llamafactory_qwen --model-path models/qwen/Qwen2___5-1___5B-Instruct
```

### 2. Ollama

Ollama是最简单的方式来运行本地模型。

#### 安装Ollama

1. 访问 https://ollama.ai 下载并安装Ollama
2. 或者使用命令行安装（Linux/Mac）：
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

#### 下载Qwen模型

```bash
# 下载Qwen模型（根据你的需求选择版本）
ollama pull qwen2.5:0.5b  # 最小模型（推荐先用它跑通流程）
# 或者：
ollama pull qwen
# 或者下载特定版本
ollama pull qwen:7b
ollama pull qwen:14b
```

#### 配置

在 `backtest_config.yaml` 中设置：

```yaml
strategy:
  use_llm: true
  llm_strategy: "balanced"
  llm_provider: "local_qwen_ollama"
  llm_model_name: "qwen2.5:0.5b"  # Ollama中的模型名称（示例：qwen2.5:0.5b）
  # llm_api_base: "http://localhost:11434"  # 可选，默认是 http://localhost:11434
```

#### 环境变量（可选）

如果需要使用不同的Ollama地址，可以设置环境变量：

```bash
export OLLAMA_API_BASE=http://localhost:11434
```

### 2. VLLM

如果你使用VLLM部署模型（通常用于生产环境）。

#### 启动VLLM服务

```bash
# 启动VLLM服务
python -m vllm.entrypoints.openai.api_server \
    --model /path/to/your/qwen/model \
    --port 8000
```

#### 配置

在 `backtest_config.yaml` 中设置：

```yaml
strategy:
  use_llm: true
  llm_strategy: "balanced"
  llm_provider: "local_qwen_vllm"
  llm_model_name: "qwen"  # 或你的模型路径
  # llm_api_base: "http://localhost:8000"  # 可选，默认是 http://localhost:8000
```

#### 环境变量（可选）

```bash
export VLLM_API_BASE=http://localhost:8000
```

## Web界面使用

1. 访问交易平台：http://localhost:8000/trading
2. 选择"回测"模式
3. 在"LLM模型"下拉菜单中选择：
   - **DeepSeek API** - 使用DeepSeek云端API
   - **本地Qwen (Ollama)** - 使用本地Ollama部署的Qwen模型
   - **本地Qwen (VLLM)** - 使用本地VLLM部署的Qwen模型
   - **本地Qwen (模型路径)** - 直接用本地模型目录（llamafactory 方式）
4. 如果选择 Ollama/VLLM，会显示"模型名称"输入框；如果选择"模型路径"，会显示"模型路径"输入框
5. 设置其他回测参数
6. 点击"运行回测"

## 命令行使用

### 方式1：修改配置文件

编辑 `backtest_config.yaml`：

```yaml
strategy:
  use_llm: true
  llm_provider: "local_qwen_ollama"
  llm_model_name: "qwen"
```

然后运行：

```bash
python run_backtest.py --config backtest_config.yaml
```

### 方式2：通过API

```bash
curl -X POST "http://localhost:8000/api/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "config_path": "backtest_config.yaml",
    "start_date": "2024-11-01",
    "end_date": "2024-12-01",
    "strategy_config": {
      "llm_provider": "local_qwen_ollama",
      "llm_model_name": "qwen"
    }
  }'
```

## 测试连接

在运行回测前，建议先测试本地模型服务是否正常：

### 测试Ollama

```bash
# 检查Ollama是否运行
curl http://localhost:11434/api/tags

# 测试模型
curl http://localhost:11434/api/generate -d '{
  "model": "qwen",
  "prompt": "Hello",
  "stream": false
}'
```

### 测试VLLM

```bash
# 检查VLLM是否运行
curl http://localhost:8000/health

# 测试模型
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 性能对比

- **DeepSeek API**: 
  - 优点：无需本地资源，响应稳定
  - 缺点：需要API密钥，有调用费用，可能有速率限制

- **本地Qwen (Ollama)**:
  - 优点：免费，无速率限制，数据隐私
  - 缺点：需要本地GPU/CPU资源，首次调用可能较慢

- **本地Qwen (VLLM)**:
  - 优点：性能最优，适合生产环境
  - 缺点：需要更多资源，配置较复杂

## 故障排除

### 问题1：无法连接到Ollama

**错误信息**：`无法连接到Ollama服务`

**解决方案**：
1. 确保Ollama服务正在运行：`ollama serve`
2. 检查端口是否正确（默认11434）
3. 检查防火墙设置

### 问题2：模型不存在

**错误信息**：`model not found`

**解决方案**：
1. 检查模型是否已下载：`ollama list`
2. 如果未下载，运行：`ollama pull qwen`
3. 检查配置文件中的模型名称是否正确

### 问题3：响应超时

**错误信息**：`timeout`

**解决方案**：
1. 增加超时时间（代码中默认120秒）
2. 检查模型大小是否适合你的硬件
3. 考虑使用更小的模型版本

### 问题4：内存不足

**解决方案**：
1. 使用更小的模型版本（如qwen:7b而不是qwen:14b）
2. 增加系统内存
3. 使用量化模型

## 推荐配置

### 开发/测试环境
- 使用Ollama + qwen:7b
- 配置简单，资源需求较低

### 生产环境
- 使用VLLM + 完整模型
- 性能最优，支持并发

## 注意事项

1. **首次调用较慢**：本地模型首次加载需要时间，后续调用会更快
2. **资源需求**：确保有足够的GPU/CPU和内存
3. **模型版本**：不同版本的Qwen模型性能可能不同，建议测试后选择
4. **回测速度**：使用本地模型时，回测速度取决于模型响应时间

## 下一步

- 正式上线时，可以切换到DeepSeek最新模型
- 或者继续使用本地模型，根据性能需求选择Ollama或VLLM
