#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因组选择预测模块
用于加载已训练好的模型，对新的基因型数据进行表型预测
Author: Shen Yan
Email: yanshen@caas.cn
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import joblib
from pathlib import Path
from typing import Dict, List, Union, Optional, Any
import warnings
warnings.filterwarnings("ignore")

# -------------------- 模型定义 --------------------
class Encoder(nn.Module):
    def __init__(self, input_dim, hidden_dims):
        super().__init__()
        layers = []
        last = input_dim
        for h in hidden_dims:
            layers += [nn.Linear(last, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.2)]
            last = h
        self.net = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.net(x)

class MultiHeadDecoder(nn.Module):
    def __init__(self, encoder_out_dim, decoder_hidden, n_tasks):
        super().__init__()
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(encoder_out_dim, decoder_hidden),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(decoder_hidden, 1)
            ) for _ in range(n_tasks)
        ])
    
    def forward(self, z):
        return torch.cat([head(z) for head in self.heads], dim=1)

class MultiTaskModel(nn.Module):
    def __init__(self, input_dim, encoder_dims, decoder_hidden, n_tasks):
        super().__init__()
        self.encoder = Encoder(input_dim, encoder_dims)
        self.decoder = MultiHeadDecoder(encoder_dims[-1], decoder_hidden, n_tasks)
    
    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)

# -------------------- 预测器类 --------------------
class GenomicPredictor:
    def __init__(self, model_path, scaler_path, device='auto'):
        """
        初始化基因组预测器
        
        Args:
            model_path: 训练好的模型文件路径 (.pt)
            scaler_path: 标准化器文件路径 (.pkl)
            device: 计算设备 ('auto', 'cpu', 'cuda')
        """
        self.device = self._get_device(device)
        self.scaler = self._load_scaler(scaler_path)
        self.model = self._load_model(model_path)
        self.trait_names = list(self.scaler.keys())
        
    def _get_device(self, device):
        if device == 'auto':
            return 'cuda' if torch.cuda.is_available() else 'cpu'
        return device
    
    def _load_scaler(self, scaler_path):
        """加载标准化器"""
        return joblib.load(scaler_path)
    
    def _load_model(self, model_path):
        """加载训练好的模型"""
        # 从scaler推断模型参数
        n_tasks = len(self.scaler)
        
        # 这些参数需要与训练时保持一致
        encoder_dims = [2048, 1024, 512]  # 默认值，应该从模型配置文件读取
        decoder_dim = 256
        
        # 需要从第一个输入数据推断input_dim，这里先设置为None
        model = None
        
        # 加载模型状态字典
        state_dict = torch.load(model_path, map_location=self.device)
        
        # 从状态字典推断input_dim
        input_dim = state_dict['encoder.net.0.weight'].shape[1]
        
        # 创建模型
        model = MultiTaskModel(input_dim, encoder_dims, decoder_dim, n_tasks)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        
        return model
    
    def preprocess_genotype(self, geno_data):
        """
        预处理基因型数据，支持动态特征匹配
        
        Args:
            geno_data: pandas DataFrame或numpy array，基因型数据
            
        Returns:
            torch.Tensor: 预处理后的基因型数据
        """
        if isinstance(geno_data, pd.DataFrame):
            X = geno_data.values.astype(np.float32)
            feature_names = geno_data.columns.tolist()
        else:
            X = geno_data.astype(np.float32)
            feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        
        # 获取模型期望的输入维度
        expected_input_dim = self.model.encoder.net[0].in_features
        current_input_dim = X.shape[1]
        
        print(f"当前输入维度: {current_input_dim}, 模型期望维度: {expected_input_dim}")
        
        # 处理维度不匹配的情况
        if current_input_dim != expected_input_dim:
            X_processed = self._handle_dimension_mismatch(X, feature_names, expected_input_dim)
        else:
            X_processed = X
        
        # 转换为torch tensor
        X_tensor = torch.tensor(X_processed, dtype=torch.float32).to(self.device)
        
        return X_tensor
    
    def _handle_dimension_mismatch(self, X, feature_names, expected_dim):
        """
        处理输入维度不匹配的情况
        
        Args:
            X: 输入数据 (n_samples, n_features)
            feature_names: 特征名称列表
            expected_dim: 期望的特征维度
            
        Returns:
            numpy.ndarray: 处理后的数据
        """
        current_dim = X.shape[1]
        
        if current_dim < expected_dim:
            # 特征数量不足，进行填充
            print(f"⚠️ 输入特征数量({current_dim})少于模型期望({expected_dim})，将进行零填充")
            
            # 零填充到期望维度
            padding_size = expected_dim - current_dim
            padding = np.zeros((X.shape[0], padding_size), dtype=np.float32)
            X_processed = np.concatenate([X, padding], axis=1)
            
            print(f"✅ 已进行零填充，新维度: {X_processed.shape[1]}")
            
        elif current_dim > expected_dim:
            # 特征数量过多，进行截断或选择
            print(f"⚠️ 输入特征数量({current_dim})多于模型期望({expected_dim})，将选择前{expected_dim}个特征")
            
            X_processed = X[:, :expected_dim]
            
            print(f"✅ 已截断特征，新维度: {X_processed.shape[1]}")
            print(f"📋 使用的特征: {feature_names[:expected_dim][:10]}..." if len(feature_names) > 10 else f"📋 使用的特征: {feature_names[:expected_dim]}")
            
        else:
            # 维度完全匹配，直接使用原数据
            X_processed = X
            print(f"✅ 维度匹配，直接使用原数据: {X_processed.shape[1]}")
            
        return X_processed
    
    def predict(self, geno_data):
        """
        对基因型数据进行表型预测
        
        Args:
            geno_data: pandas DataFrame或numpy array，基因型数据
            
        Returns:
            dict: 包含预测结果的字典
        """
        # 预处理数据
        X = self.preprocess_genotype(geno_data)
        
        # 进行预测
        with torch.no_grad():
            pred_normalized = self.model(X).cpu().numpy()
        
        # 反标准化
        pred_original = np.empty_like(pred_normalized)
        for j, trait_name in enumerate(self.trait_names):
            scaler_info = self.scaler[trait_name]
            mean = scaler_info['mean']
            std = scaler_info['std']
            pred_original[:, j] = pred_normalized[:, j] * std + mean
        
        # 组织返回结果
        if isinstance(geno_data, pd.DataFrame):
            sample_names = geno_data.index.tolist()
        else:
            sample_names = [f'Sample_{i}' for i in range(len(pred_original))]
        
        # 创建预测结果DataFrame
        pred_df = pd.DataFrame(
            pred_original,
            index=pd.Index(sample_names),
            columns=pd.Index(self.trait_names)
        )
        
        return {
            'predictions': pred_df,
            'trait_names': self.trait_names,
            'sample_count': len(pred_original)
        }
    
    def predict_from_file(self, geno_file_path, output_file_path=None):
        """
        从文件读取基因型数据并进行预测
        
        Args:
            geno_file_path: 基因型数据文件路径
            output_file_path: 输出文件路径（可选）
            
        Returns:
            dict: 预测结果
        """
        # 读取基因型数据
        geno_data = pd.read_csv(geno_file_path, index_col=0)
        
        # 进行预测
        result = self.predict(geno_data)
        
        # 保存结果
        if output_file_path:
            result['predictions'].to_csv(output_file_path)
            print(f"预测结果已保存到: {output_file_path}")
        
        return result

# -------------------- 便利函数 --------------------
def load_predictor(model_dir, device='auto'):
    """
    从模型目录加载预测器
    
    Args:
        model_dir: 包含模型文件的目录路径
        device: 计算设备
        
    Returns:
        GenomicPredictor: 预测器实例
    """
    model_dir = Path(model_dir)
    
    # 查找模型文件
    model_files = list(model_dir.glob('*_model_best.pt'))
    if not model_files:
        raise FileNotFoundError(f"在 {model_dir} 中未找到模型文件 (*_model_best.pt)")
    model_path = model_files[0]
    
    # 查找scaler文件
    scaler_files = list(model_dir.glob('*_scaler.pkl'))
    if not scaler_files:
        raise FileNotFoundError(f"在 {model_dir} 中未找到标准化器文件 (*_scaler.pkl)")
    scaler_path = scaler_files[0]
    
    return GenomicPredictor(model_path, scaler_path, device)

# -------------------- 测试代码 --------------------
if __name__ == '__main__':
    # 示例使用
    import sys
    
    if len(sys.argv) < 4:
        print("使用方法: python predict.py <model_dir> <geno_file> <output_file>")
        sys.exit(1)
    
    model_dir = sys.argv[1]
    geno_file = sys.argv[2]
    output_file = sys.argv[3]
    
    try:
        # 加载预测器
        predictor = load_predictor(model_dir)
        print(f"已加载模型，支持预测的性状: {predictor.trait_names}")
        
        # 进行预测
        result = predictor.predict_from_file(geno_file, output_file)
        
        print(f"预测完成！")
        print(f"样本数量: {result['sample_count']}")
        print(f"性状数量: {len(result['trait_names'])}")
        
    except Exception as e:
        print(f"预测失败: {e}")
        sys.exit(1)