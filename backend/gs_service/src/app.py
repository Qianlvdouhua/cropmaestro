import os, uuid, shutil, subprocess, json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from src.predict import load_predictor  # 引入预测功能
import pandas as pd
import tempfile

# -------------------- Celery 配置（可选） --------------------
# 如果需要异步处理，可以启用以下配置
# celery_app = Celery(
#     "gs_tasks",
#     broker="redis://localhost:6380/0",
#     backend="redis://localhost:6380/0"
# )

# -------------------- 目录配置 --------------------
# 结果目录
RESULT_ROOT = Path("results")  # 使用相对路径
UPLOAD_ROOT = Path("uploads")
RESULT_ROOT.mkdir(parents=True, exist_ok=True)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# -------------------- FastAPI --------------------
app = FastAPI(title="Multi-Task GS API")

# 全局预测器实例（延迟加载）
predictor = None

def get_predictor():
    """Get or initialize the predictor instance"""
    global predictor
    # 为了确保使用最新的代码，每次都重新加载预测器
    # if predictor is None:
    
    # 在第一次调用时加载预测器
    model_dir = "models"  # 默认模型目录（相对路径）
    
    # 检查默认模型目录
    if not Path(model_dir).exists():
        # 如果默认目录不存在，直接使用results目录
        model_dir = str(RESULT_ROOT)
        
        # 检查results目录中是否有模型文件
        model_files = list(Path(model_dir).glob("*_model_best.pt"))
        scaler_files = list(Path(model_dir).glob("*_scaler.pkl"))
        
        if not model_files or not scaler_files:
            # 如果results目录中没有，尝试查找子目录
            result_dirs = [d for d in Path(model_dir).glob("*") if d.is_dir()]
            if result_dirs:
                # 取最新的结果目录
                model_dir = str(max(result_dirs, key=lambda x: x.stat().st_mtime))
            else:
                raise HTTPException(500, "未找到训练好的模型文件")
    
    try:
        predictor = load_predictor(model_dir)
        print(f"✅ 已重新加载预测器，模型目录: {model_dir}")
    except Exception as e:
        raise HTTPException(500, f"加载模型失败: {str(e)}")
    
    return predictor

@app.post("/predict")
async def predict(
    vcf: UploadFile = File(..., description="VCF/CSV genotype"),
    traits: UploadFile = File(..., description="CSV phenotype"),
    epochs: int = Form(150, description="训练轮数")
):
    # 生成任务目录
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_ROOT / task_id
    task_dir.mkdir(exist_ok=True)

    geno_path = task_dir / "geno.csv"
    pho_path  = task_dir / "pho.csv"
    out_dir   = RESULT_ROOT / task_id

    with open(geno_path, "wb") as f:
        shutil.copyfileobj(vcf.file, f)
    with open(pho_path, "wb") as f:
        shutil.copyfileobj(traits.file, f)

    # 使用同步方式执行训练（简化版本）
    # 在生产环境中建议使用 Celery 异步处理
    try:
        cmd = [
            "python", "src/multi_genomic_selection.py",
            "--geno", str(geno_path),
            "--pho", str(pho_path),
            "--epochs", str(epochs),
            "--kfold", "3",
            "--out", str(out_dir)
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3600  # 1小时超时
        )
        if proc.returncode != 0:
            raise HTTPException(500, f"训练失败: {proc.stdout}")
        
        return {"task_id": task_id, "status": "completed", "message": "训练完成"}
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "训练超时")
    except Exception as e:
        raise HTTPException(500, f"训练错误: {str(e)}")

@app.get("/status/{task_id}")
async def status(task_id: str):
    """查询训练任务状态"""
    out_dir = RESULT_ROOT / task_id
    
    # 检查结果文件是否存在
    pred_file = out_dir / "result_pred.csv"
    metrics_file = out_dir / "result_metrics.txt"
    model_file = out_dir / "result_model_best.pt"
    
    if pred_file.exists() or metrics_file.exists() or model_file.exists():
        files = {}
        if pred_file.exists():
            files["pred_csv"] = f"/download/{task_id}/result_pred.csv"
        if metrics_file.exists():
            files["metrics"] = f"/download/{task_id}/result_metrics.txt"
        if model_file.exists():
            files["model"] = f"/download/{task_id}/result_model_best.pt"
        
        return {"status": "done", "files": files}
    else:
        return {"status": "not_found", "message": "任务不存在或尚未完成"}

@app.get("/download/{task_id}/{filename}")
async def download(task_id: str, filename: str):
    file_path = RESULT_ROOT / task_id / filename
    if not file_path.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(file_path)

@app.post("/predict_phenotype_text")
async def predict_phenotype_text(
    file_content: str = Form(..., description="CSV文件内容（文本格式）"),
    file_name: str = Form("data.csv", description="文件名")
):
    """
    基于已训练模型进行表型预测（接收文本格式的CSV内容）
    专门用于n8n工作流中处理文件内容
    """
    task_dir = None  # 初始化变量
    try:
        # 获取预测器实例
        predictor_instance = get_predictor()
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        task_dir = UPLOAD_ROOT / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 保存文件内容到临时文件
        geno_path = task_dir / file_name
        with open(geno_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # 读取基因型数据
        try:
            geno_data = pd.read_csv(geno_path, index_col=0)
        except Exception as e:
            raise HTTPException(400, f"基因型数据文件格式错误: {str(e)}")
        
        # 进行预测
        prediction_result = predictor_instance.predict(geno_data)
        
        # 准备输出目录
        out_dir = RESULT_ROOT / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存预测结果
        pred_file = out_dir / "predictions.csv"
        prediction_result['predictions'].to_csv(pred_file)
        
        # 保存预测统计信息
        stats_file = out_dir / "prediction_stats.json"
        stats = {
            "task_id": task_id,
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "prediction_time": pd.Timestamp.now().isoformat(),
            "input_file": file_name
        }
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 清理上传的临时文件
        shutil.rmtree(task_dir)
        
        return {
            "task_id": task_id,
            "status": "completed",
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "input_file": file_name,
            "download_links": {
                "predictions": f"/download/{task_id}/predictions.csv",
                "stats": f"/download/{task_id}/prediction_stats.json"
            }
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 清理临时文件
        if task_dir and task_dir.exists():
            shutil.rmtree(task_dir)
        raise HTTPException(500, f"预测失败: {str(e)}")

@app.post("/predict_phenotype_base64")
async def predict_phenotype_base64(
    file_content: str = Form(..., description="Base64编码的CSV文件内容"),
    file_name: str = Form(..., description="文件名")
):
    """
    基于已训练模型进行表型预测（接受Base64编码的文件）
    用于解决n8n文件传输问题
    """
    task_dir = None  # 初始化变量
    try:
        import base64
        import io
        
        # 获取预测器实例
        predictor_instance = get_predictor()
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        task_dir = UPLOAD_ROOT / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 解码Base64文件内容
        try:
            file_bytes = base64.b64decode(file_content)
            file_content_str = file_bytes.decode('utf-8')
        except Exception as e:
            raise HTTPException(400, f"Base64解码失败: {str(e)}")
        
        # 保存文件
        geno_path = task_dir / file_name
        with open(geno_path, 'w', encoding='utf-8') as f:
            f.write(file_content_str)
        
        # 读取基因型数据
        try:
            geno_data = pd.read_csv(geno_path, index_col=0)
        except Exception as e:
            raise HTTPException(400, f"基因型数据文件格式错误: {str(e)}")
        
        # 进行预测
        prediction_result = predictor_instance.predict(geno_data)
        
        # 准备输出目录
        out_dir = RESULT_ROOT / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存预测结果
        pred_file = out_dir / "predictions.csv"
        prediction_result['predictions'].to_csv(pred_file)
        
        # 保存预测统计信息
        stats_file = out_dir / "prediction_stats.json"
        stats = {
            "task_id": task_id,
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "prediction_time": pd.Timestamp.now().isoformat(),
            "input_file": file_name
        }
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 清理上传的临时文件
        shutil.rmtree(task_dir)
        
        return {
            "task_id": task_id,
            "status": "completed",
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "input_file": file_name,
            "download_links": {
                "predictions": f"/download/{task_id}/predictions.csv",
                "stats": f"/download/{task_id}/prediction_stats.json"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 清理临时文件
        if task_dir and task_dir.exists():
            shutil.rmtree(task_dir)
        raise HTTPException(500, f"预测失败: {str(e)}")

@app.post("/predict_phenotype")
async def predict_phenotype(
    genotype: UploadFile = File(..., description="基因型数据CSV文件")
):
    """
    基于已训练模型进行表型预测
    只需要上传基因型数据，无需表型数据
    """
    try:
        # 获取预测器实例
        predictor_instance = get_predictor()
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        task_dir = UPLOAD_ROOT / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 保存上传的基因型文件
        geno_path = task_dir / "genotype.csv"
        with open(geno_path, "wb") as f:
            shutil.copyfileobj(genotype.file, f)
        
        # 读取基因型数据
        try:
            geno_data = pd.read_csv(geno_path, index_col=0)
        except Exception as e:
            raise HTTPException(400, f"基因型数据文件格式错误: {str(e)}")
        
        # 进行预测
        prediction_result = predictor_instance.predict(geno_data)
        
        # 准备输出目录
        out_dir = RESULT_ROOT / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存预测结果
        pred_file = out_dir / "predictions.csv"
        prediction_result['predictions'].to_csv(pred_file)
        
        # 保存预测统计信息
        stats_file = out_dir / "prediction_stats.json"
        stats = {
            "task_id": task_id,
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "prediction_time": pd.Timestamp.now().isoformat()
        }
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 清理上传的临时文件
        shutil.rmtree(task_dir)
        
        return {
            "task_id": task_id,
            "status": "completed",
            "sample_count": prediction_result['sample_count'],
            "trait_names": prediction_result['trait_names'],
            "download_links": {
                "predictions": f"/download/{task_id}/predictions.csv",
                "stats": f"/download/{task_id}/prediction_stats.json"
            }
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 处理其他异常
        raise HTTPException(500, f"预测失败: {str(e)}")

@app.post("/predict_phenotype_async")
async def predict_phenotype_async(
    genotype: UploadFile = File(..., description="基因型数据CSV文件")
):
    """
    异步预测接口（适用于大量数据）
    返回task_id，可通过/predict_status/{task_id}查询状态
    """
    try:
        # 生成任务ID
        task_id = str(uuid.uuid4())
        task_dir = UPLOAD_ROOT / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 保存上传的基因型文件
        geno_path = task_dir / "genotype.csv"
        with open(geno_path, "wb") as f:
            shutil.copyfileobj(genotype.file, f)
        
        # 使用同步方式进行预测（简化版本）
        # 在生产环境中建议使用 Celery 异步处理
        
        # 这里直接调用预测函数，而不是异步任务
        try:
            # 获取预测器实例
            predictor_instance = get_predictor()
            
            # 读取基因型数据
            geno_data = pd.read_csv(geno_path, index_col=0)
            
            # 进行预测
            prediction_result = predictor_instance.predict(geno_data)
            
            # 准备输出目录
            out_dir = RESULT_ROOT / task_id
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存预测结果
            pred_file = out_dir / "predictions.csv"
            prediction_result['predictions'].to_csv(pred_file)
            
            # 保存预测统计信息
            stats_file = out_dir / "prediction_stats.json"
            stats = {
                "sample_count": prediction_result['sample_count'],
                "trait_names": prediction_result['trait_names'],
                "prediction_time": pd.Timestamp.now().isoformat()
            }
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            # 清理上传的临时文件
            shutil.rmtree(task_dir)
            
            return {
                "task_id": task_id,
                "status": "completed",
                "sample_count": prediction_result['sample_count'],
                "trait_names": prediction_result['trait_names'],
                "download_links": {
                    "predictions": f"/download/{task_id}/predictions.csv",
                    "stats": f"/download/{task_id}/prediction_stats.json"
                }
            }
            
        except Exception as e:
            # 清理上传的临时文件
            if task_dir.exists():
                shutil.rmtree(task_dir)
            raise HTTPException(500, f"预测失败: {str(e)}")
        
    except Exception as e:
        raise HTTPException(500, f"提交预测任务失败: {str(e)}")

@app.get("/predict_status/{task_id}")
async def predict_status(task_id: str):
    """
    查询预测任务状态
    """
    out_dir = RESULT_ROOT / task_id
    pred_file = out_dir / "predictions.csv"
    stats_file = out_dir / "prediction_stats.json"
    
    if pred_file.exists() and stats_file.exists():
        # 任务完成
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        
        return {
            "status": "completed",
            "task_id": task_id,
            "sample_count": stats.get("sample_count", 0),
            "trait_names": stats.get("trait_names", []),
            "prediction_time": stats.get("prediction_time"),
            "download_links": {
                "predictions": f"/download/{task_id}/predictions.csv",
                "stats": f"/download/{task_id}/prediction_stats.json"
            }
        }
    else:
        # 任务还在进行中或不存在
        return {
            "status": "processing" if out_dir.exists() else "not_found",
            "task_id": task_id
        }

@app.get("/predictor_info")
async def predictor_info():
    """
    获取预测器信息
    """
    try:
        predictor_instance = get_predictor()
        return {
            "status": "ready",
            "trait_names": predictor_instance.trait_names,
            "trait_count": len(predictor_instance.trait_names),
            "device": predictor_instance.device
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/reset_predictor")
async def reset_predictor():
    """
    重置预测器，强制重新加载模型
    """
    global predictor
    predictor = None
    try:
        new_predictor = get_predictor()
        return {
            "status": "success",
            "message": "预测器已重置",
            "trait_names": new_predictor.trait_names,
            "device": new_predictor.device
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"重置失败: {str(e)}"
        }