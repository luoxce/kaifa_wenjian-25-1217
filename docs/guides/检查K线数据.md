# K线图表空白问题排查指南

## 问题诊断步骤

### 1. 检查数据库是否有数据

在浏览器控制台（F12）中运行：
```javascript
fetch('/api/database/candles?symbol=BTC&timeframe=15m&limit=10')
  .then(r => r.json())
  .then(data => console.log('数据:', data))
```

如果返回 `count: 0` 或 `data: []`，说明数据库中没有数据。

### 2. 下载历史数据

运行以下命令下载15分钟数据：
```bash
python update_market_data.py --initial-sync --timeframe 15m --days 365
```

### 3. 检查浏览器控制台

打开浏览器开发者工具（F12），查看Console标签页，检查是否有错误信息：
- 如果看到 "Chart not initialized"，说明图表初始化有问题
- 如果看到 "No data returned from API"，说明数据库中没有数据
- 如果看到网络错误，检查API服务是否正常运行

### 4. 检查API服务

确保FastAPI服务正在运行：
```bash
uvicorn fastapi_app:app --reload
```

### 5. 手动测试API

在浏览器中访问：
```
http://localhost:8000/api/database/candles?symbol=BTC&timeframe=15m&limit=10
```

应该返回JSON格式的K线数据。

## 常见问题

### 问题1：数据库中没有数据
**解决方案**：运行数据采集脚本下载历史数据

### 问题2：图表容器尺寸为0
**解决方案**：已修复，图表会自动设置默认尺寸

### 问题3：时间戳格式错误
**解决方案**：已修复，时间戳会自动转换为秒级

### 问题4：API返回错误
**解决方案**：检查数据库文件是否存在，路径是否正确

## 快速修复

如果图表仍然空白，请：

1. 刷新页面（Ctrl+F5 强制刷新）
2. 检查浏览器控制台错误信息
3. 确认数据库中有数据
4. 检查网络请求是否成功（F12 -> Network标签）

