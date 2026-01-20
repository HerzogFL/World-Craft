# 文件名: asset_retriever.py
import json
import os
import re

# 索引文件的路径
INDEX_FILE_PATH = "./asset_index.json"

ENGLISH_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "of", "in", 
    "on", "at", "to", "for", "with", "by", "and", "or"
}

_asset_index = None

def _load_index():
    """加载 (并缓存) 资产索引"""
    global _asset_index
    if _asset_index is not None:
        return _asset_index

    if not os.path.exists(INDEX_FILE_PATH):
        print(f"!!! [Asset Retriever] 警告: 索引文件 {INDEX_FILE_PATH} 不存在。")
        print(f"!!! [Asset Retriever] 请先运行 build_asset_index.py 脚本！")
        _asset_index = {} # 标记为已加载 (空)
        return _asset_index

    try:
        with open(INDEX_FILE_PATH, 'r', encoding='utf-8') as f:
            _asset_index = json.load(f)
            print(f"[Asset Retriever] 成功加载资产索引。")
            return _asset_index
    except Exception as e:
        print(f"!!! [Asset Retriever] 错误: 加载索引文件 {INDEX_FILE_PATH} 失败: {e}")
        _asset_index = {} # 标记为已加载 (空)
        return _asset_index

def _normalize_query_to_set(text: str) -> set:
    """
    将查询文本 ("cafe_sofa a comfortable sofa") 
    转换为标准化的关键词集合 ({"cafe", "sofa", "comfortable"})
    """
    # 1. "cafe_sofa a comfortable sofa" -> "cafe sofa a comfortable sofa"
    text_clean = text.replace('_', ' ').lower()
    
    # 2. 移除所有非字母数字
    text_clean = re.sub(r'[^a-z0-9\s]', '', text_clean)
    
    # 3. 分词、移除停用词、并返回一个 集合(set) 以便快速求交集
    tokens = {
        word for word in text_clean.split() 
        if word and word not in ENGLISH_STOP_WORDS
    }
    return tokens


def find_closest_reference_image(asset_id: str, details: dict) -> str | None:
    """
    【核心】执行两阶段检索算法 (Token Matching + Dimension Ranking)
    
    :param asset_id: e.g., "cafe_sofa"
    :param details: 包含 "description" 和 "visual_size" 的字典
    :return: 最佳匹配的【完整文件路径】或 None
    """
    index = _load_index()
    if not index or "assets" not in index:
        return None # 索引加载失败或为空

    # --- 1. 查询标准化 (Query Normalization) ---
    
    # 1a. 准备查询文本 ("cafe_sofa" + "a comfortable sofa")
    query_text = f"{asset_id} {details.get('description', '')}"
    
    # 1b. 查询关键词 (Qt): {"cafe", "sofa", "comfortable"}
    query_tokens = _normalize_query_to_set(query_text)
    
    if not query_tokens:
        return None # 查询无效

    # 1c. 查询尺寸 (Qdims): e.g., [2, 1]
    query_dims = details.get("visual_size", details.get("base_size", [1, 1]))

    
    # --- 2. 算法执行 ---
    
    best_match_path_relative = None
    # (我们使用曼哈顿距离，所以惩罚分越低越好)
    lowest_dimension_penalty = float('inf') 

    # 遍历索引中的每一篇文档 (D)
    for doc_id, doc in index["assets"].items():
        
        # --- 阶段 1: 文本过滤 (Set Intersection) ---
        
        doc_tokens = set(doc["tokens"]) # Dt: e.g., {"pink", "sofa"}
        
        intersection = query_tokens.intersection(doc_tokens)
        
        # 如果交集为空 (e.g., 搜 "sofa" 却匹配到 "bookshelf")，立即跳过
        if not intersection:
            continue
            
        # --- 阶段 2: 尺寸排序 (Manhattan Distance) ---
        
        doc_dims = doc["dimensions_tiles"] # Ddims: e.g., [2, 1]
        
        # 公式: P = |Qw - Dw| + |Qh - Dh|
        penalty = abs(query_dims[0] - doc_dims[0]) + \
                abs(query_dims[1] - doc_dims[1])
                
        # 如果这个文档的惩罚分更低，它就是新的“最佳匹配”
        if penalty < lowest_dimension_penalty:
            lowest_dimension_penalty = penalty
            best_match_path_relative = doc["path_relative"]
            
            # 优化：如果惩罚分为 0 (完美尺寸匹配)，我们没必要再搜了
            if penalty == 0:
                break
                
    # --- 3. 最终决策 ---
    
    if best_match_path_relative:
        print(f"  - [Retriever] 匹配成功 (Penalty={lowest_dimension_penalty}): {os.path.basename(best_match_path_relative)}")
        
        # 拼接完整路径并返回
        base_path = index.get("metadata", {}).get("base_path", ".")
        full_path = os.path.join(base_path, best_match_path_relative)
        
        if not os.path.exists(full_path):
            print(f"!!! [Retriever] 警告: 索引文件 '{best_match_path_relative}' 在磁盘上不存在！")
            return None
            
        return full_path

    # 未找到匹配
    print(f"  - [Retriever] '{asset_id}' 未能在索引中找到任何匹配。")
    return None