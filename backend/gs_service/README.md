# 基因组选择预测API使用说明

## 概述

本项目现在支持两种功能：
1. **训练模式**：上传基因型数据和表型数据，训练新的基因组选择模型
2. **预测模式**：使用已训练好的模型，仅上传基因型数据即可预测表型值

## 新增预测功能

### 1. 同步预测接口

**接口地址**: `POST /predict_phenotype`

**描述**: 使用已训练好的模型对基因型数据进行表型预测，立即返回结果。

**请求参数**:
- `genotype`: 基因型数据CSV文件（必需）
  - 格式：第一列为样本名，其余列为SNP标记
  - 示例：`sample,snp1,snp2,snp3,...`

**响应示例**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "sample_count": 10,
  "trait_names": ["trait1", "trait2"],
  "download_links": {
    "predictions": "/download/550e8400-e29b-41d4-a716-446655440000/predictions.csv",
    "stats": "/download/550e8400-e29b-41d4-a716-446655440000/prediction_stats.json"
  }
}
```

### 2. 异步预测接口

**接口地址**: `POST /predict_phenotype_async`

**描述**: 提交预测任务到后台队列，适用于大量数据的处理。

**请求参数**: 同同步接口

**响应示例**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "预测任务已提交，请使用/predict_status/{task_id}查询结果"
}
```

### 3. 预测状态查询

**接口地址**: `GET /predict_status/{task_id}`

**描述**: 查询预测任务的状态和结果。

**响应示例**:
```json
{
  "status": "completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "sample_count": 10,
  "trait_names": ["trait1", "trait2"],
  "prediction_time": "2024-01-01T12:00:00",
  "download_links": {
    "predictions": "/download/550e8400-e29b-41d4-a716-446655440000/predictions.csv",
    "stats": "/download/550e8400-e29b-41d4-a716-446655440000/prediction_stats.json"
  }
}
```

### 4. 预测器信息查询

**接口地址**: `GET /predictor_info`

**描述**: 获取当前预测器的状态和支持的性状信息。

**响应示例**:
```json
{
  "status": "ready",
  "trait_names": ["trait1", "trait2"],
  "trait_count": 2,
  "device": "cuda"
}
```

## 使用示例

### Python示例

```python
import requests

# 1. 检查预测器状态
response = requests.get("http://localhost:8000/predictor_info")
print(response.json())

# 2. 上传基因型数据进行预测
with open("geno_test.csv", "rb") as f:
    files = {"genotype": ("geno_test.csv", f, "text/csv")}
    response = requests.post("http://localhost:8000/predict_phenotype", files=files)

result = response.json()
print(f"预测完成，任务ID: {result['task_id']}")

# 3. 下载预测结果
download_url = f"http://localhost:8000{result['download_links']['predictions']}"
response = requests.get(download_url)
with open("predictions.csv", "w") as f:
    f.write(response.text)
```

### curl示例

```bash
# 检查预测器状态
curl -X GET "http://localhost:8000/predictor_info"

# 上传文件进行预测
curl -X POST "http://localhost:8000/predict_phenotype" \
     -F "genotype=@geno_test.csv"

# 下载预测结果
curl -X GET "http://localhost:8000/download/{task_id}/predictions.csv" \
     -o predictions.csv
```

## 数据格式要求

### 基因型数据格式 (CSV)

```csv
sample,snp1,snp2,snp3,snp4
S1,0,1,2,1
S2,2,1,0,1
S3,1,0,1,0
```

- 第一列：样本名称
- 其余列：SNP标记值（通常为0, 1, 2）
- 文件编码：UTF-8
- 分隔符：逗号

## 输出文件说明

### predictions.csv
包含每个样本的表型预测值：
```csv
sample,trait1,trait2
S1,12.34,56.78
S2,23.45,67.89
```

### prediction_stats.json
包含预测任务的统计信息：
```json
{
  "task_id": "xxx",
  "sample_count": 10,
  "trait_names": ["trait1", "trait2"],
  "prediction_time": "2024-01-01T12:00:00",
  "model_dir": "/app/results/model_xxx"
}
```

## 模型要求

预测功能需要以下文件：
1. `*_model_best.pt`: 训练好的PyTorch模型文件
2. `*_scaler.pkl`: 标准化器文件
3. 这些文件应位于 `/app/models/` 目录或 `/app/results/` 的子目录中

## 错误处理

常见错误及解决方案：

1. **模型未找到**: 确保已训练模型并且模型文件存在
2. **数据格式错误**: 检查CSV文件格式，确保第一列为样本名
3. **内存不足**: 对于大数据集，使用异步预测接口
4. **GPU不可用**: 系统会自动切换到CPU模式

## 测试

运行测试脚本验证功能：
```bash
python test_predict_api.py
```

## 技术细节

- **框架**: FastAPI + PyTorch
- **模型**: Multi-task深度学习模型
- **异步任务**: Celery (可选)
- **数据处理**: pandas + numpy
- **模型保存**: PyTorch state_dict + joblib