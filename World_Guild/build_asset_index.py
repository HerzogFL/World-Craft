# 文件名: build_asset_index.py
import os
import json
import re

INDEX_SAVE_PATH = "./asset_index.json"

ENGLISH_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "of", "in", 
    "on", "at", "to", "for", "with", "by", "and", "or"
}

DIMENSION_REGEX = re.compile(r'_(\d+)x(\d+)(?=\.[^.]+$)')

def normalize_text_to_tokens(text: str) -> list[str]:
    """
    将文件名文本 ("a_pink_sofa") 转换为标准化关键词 (["pink", "sofa"])
    """
    # 1. "a_pink_sofa" -> "a pink sofa" (小写并替换_)
    text_clean = text.replace('_', ' ').lower()
    
    # 2. 移除所有非字母数字 (保留空格)
    text_clean = re.sub(r'[^a-z0-9\s]', '', text_clean)
    
    # 3. 分词并移除停用词
    tokens = [
        word for word in text_clean.split() 
        if word and word not in ENGLISH_STOP_WORDS
    ]
    return tokens

# 【【【 核心修改：函数现在接收 asset_pack_path 】】】
def build_index(asset_pack_path: str):
    """
    遍历素材包，构建索引
    :param asset_pack_path: main.py 动态计算出的素材库【完整路径】
    """
    print(f"--- [Index Builder] 正在扫描素材包: {asset_pack_path} ---")
    
    if not os.path.exists(asset_pack_path):
        print(f"!!! [Index Builder] 错误: 路径不存在: {asset_pack_path}")
        print(f"!!! [Index Builder] 请检查 main.py 中的 GODOT_PROJECT_PATH 和 ASSET_PACK_FOLDER_NAME 配置。")
        return False

    asset_database = {
        "metadata": {
            "base_path": os.path.abspath(asset_pack_path)
        },
        "assets": {} # 存储所有资产条目
    }
    
    total_files = 0
    indexed_files = 0
    
    for root, _, files in os.walk(asset_pack_path):
        for file in files:
            if not file.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            total_files += 1
            file_path = os.path.join(root, file)
            
            # --- 1. 解析尺寸 ---
            match = DIMENSION_REGEX.search(file.lower())
            if not match:
                print(f"  - [跳过] 无法从文件名解析尺寸: {file}")
                continue
                
            dimensions_tiles = [int(match.group(1)), int(match.group(2))]

            # --- 2. 解析文本和关键词 ---
            base_name = os.path.splitext(file)[0]
            text_part = DIMENSION_REGEX.sub('', base_name)
            
            if not text_part:
                print(f"  - [跳过] 文件名中缺少描述: {file}")
                continue
                
            tokens = normalize_text_to_tokens(text_part)

            # --- 3. 存储条目 ---
            relative_path = os.path.relpath(file_path, asset_pack_path)
            doc_id = relative_path.replace("\\", "/")
            
            asset_database["assets"][doc_id] = {
                "path_relative": doc_id,
                "dimensions_tiles": dimensions_tiles, 
                "tokens": tokens
            }
            
            indexed_files += 1
            if indexed_files % 100 == 0:
                print(f"  ...已索引 {indexed_files} 个文件...")

    # --- 4. 保存索引 ---
    try:
        with open(INDEX_SAVE_PATH, 'w', encoding='utf-8') as f:
            json.dump(asset_database, f, indent=2)
        print(f"\n--- [Index Builder] 索引构建完毕! ---")
        print(f"  总共扫描 {total_files} 个文件。")
        print(f"  成功索引 {indexed_files} 个资产。")
        print(f"  索引已保存到: {INDEX_SAVE_PATH}")
        return True 
    except Exception as e:
        print(f"\n!!! [Index Builder] 错误: 无法保存索引文件: {e}")
        return False

if __name__ == "__main__":
    build_index()