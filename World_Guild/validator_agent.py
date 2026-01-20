import json
from typing import List, Dict, Any, Optional

# ===================================================================
# 核心：AABB 碰撞检测逻辑 (修复版)
# ===================================================================

def _calculate_aabb(obj_with_size: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    计算 AABB，并保留原始位置信息用于报错。
    """
    try:
        pos = obj_with_size.get("position")
        size = obj_with_size.get("base_size")
        
        if not pos or not size or len(pos) != 2 or len(size) != 2:
            return None
            
        pos_x, pos_y = pos[0], pos[1]
        size_w, size_h = size[0], size[1]
        
        if not all(isinstance(v, (int, float)) for v in [pos_x, pos_y, size_w, size_h]):
            return None

        half_width = size_w / 2.0
        
        return {
            "id": obj_with_size.get("asset_id", "unknown"),
            "pos": [pos_x, pos_y], # 【关键】存储真实位置
            "x_min": pos_x - half_width,
            "x_max": pos_x + half_width,
            "y_min": pos_y - size_h,
            "y_max": pos_y
        }
    except Exception as e:
        print(f"[Validator] AABB 计算失败: {e}")
        return None

def _check_intersection(rect_a: Dict[str, float], rect_b: Dict[str, float]) -> bool:
    """ 检查重叠 """
    if rect_a["x_max"] <= rect_b["x_min"]: return False
    if rect_a["x_min"] >= rect_b["x_max"]: return False
    if rect_a["y_max"] <= rect_b["y_min"]: return False
    if rect_a["y_min"] >= rect_b["y_max"]: return False
    return True

def check_collisions(plan_json: Dict[str, Any]) -> List[str]:
    """
    检查所有物体的物理碰撞 (带去重和正确的位置报告)。
    """
    errors = []
    objects_to_check = []
    
    # 1. 获取 Base Size 查找表
    assets_db = plan_json.get("assets", {})
    if not assets_db: return []
        
    size_lookup = {}
    for asset_id, details in assets_db.items():
        if details and "base_size" in details:
            size_lookup[asset_id] = details["base_size"]

    # 2. 收集布局中的物体
    layout = plan_json.get("layout", {})
    for layer in ["object_layer", "npc_layer"]:
        objects_to_check.extend(layout.get(layer, []))

    # 3. 计算 AABB 列表
    aabbs = []
    for obj_in_layout in objects_to_check:
        asset_id = obj_in_layout.get("asset_id")
        position = obj_in_layout.get("position")
        
        if not asset_id or not position: continue
            
        base_size = size_lookup.get(asset_id)
        if not base_size:
            # 检查是否是 passable (如椅子)，如果是则跳过碰撞检查
            props = plan_json.get("properties", {}).get(asset_id, {})
            if props.get("physics") == "passable":
                continue
            # 否则报错
            # errors.append(f"数据错误: '{asset_id}' 缺少 base_size。") 
            continue
        
        obj_data = { "asset_id": asset_id, "position": position, "base_size": base_size }
        aabb = _calculate_aabb(obj_data)
        if aabb:
            aabbs.append(aabb)

    # 4. N^2 碰撞检查 (带去重)
    reported_pairs = set() # 用于防止重复报告 (A撞B 和 B撞A)
    collision_count = 0
    
    n = len(aabbs)
    for i in range(n):
        for j in range(i + 1, n):
            rect_a = aabbs[i]
            rect_b = aabbs[j]
            
            if _check_intersection(rect_a, rect_b):
                # --- 去重逻辑 ---
                # 生成唯一键: (ID+Pos, ID+Pos) 排序
                key_a = f"{rect_a['id']}_{rect_a['pos']}"
                key_b = f"{rect_b['id']}_{rect_b['pos']}"
                pair_key = tuple(sorted([key_a, key_b]))
                
                if pair_key in reported_pairs:
                    continue # 这一对已经报过了
                
                reported_pairs.add(pair_key)
                
                # --- 记录错误 ---
                # 【关键】这里使用 rect_a['pos']，而不是外部变量
                errors.append(
                    f"碰撞错误: '{rect_a['id']}' (位置 {rect_a['pos']}) "
                    f"与 '{rect_b['id']}' (位置 {rect_b['pos']}) 发生重叠。"
                )
                collision_count += 1

    # 5. 错误数量控制 (避免 Context 爆炸)
    if len(errors) > 5:
        return errors[:5] + [f"... (以及另外 {len(errors) - 5} 个碰撞错误)"]
        
    return errors


def check_asset_definitions(plan_json: Dict[str, Any]) -> List[str]:
    """
    检查 layout 中使用的 asset_id 是否都在 assets 中定义。
    (这是你“组件缺失”方案的更鲁棒的实现)
    """
    errors = []
    try:
        if "assets" not in plan_json or not plan_json["assets"]:
            return ["严重错误: JSON 中缺少 'assets' 字段。"]
            
        asset_keys = set(plan_json["assets"].keys())
        layout_keys_seen = set()
        
        layout = plan_json.get("layout", {})
        layers_to_check = ["floor_layer", "wall_layer", "object_layer", "npc_layer"]
        
        for layer_name in layers_to_check:
            layer_content = layout.get(layer_name)
            if layer_content is None:
                # 允许图层缺失，但不允许它不是一个列表（如果存在）
                continue
            if not isinstance(layer_content, list):
                errors.append(f"布局错误: '{layer_name}' 不是一个列表 (list)。")
                continue

            for item in layer_content:
                if not isinstance(item, dict):
                    errors.append(f"布局错误: '{layer_name}' 中有一个条目不是字典 (dict)。")
                    continue
                
                asset_id = item.get("asset_id")
                if not asset_id:
                    errors.append(f"布局错误: {layer_name} 中有一个条目缺少 'asset_id'。")
                    continue
                
                layout_keys_seen.add(asset_id)
        
        # 检查在 layout 中使用、但未在 assets 中定义的 ID
        missing_definitions = layout_keys_seen - asset_keys
        if missing_definitions:
            for asset_id in missing_definitions:
                errors.append(f"组件缺失错误: 布局中使用了 '{asset_id}'，但它未在 'assets' 字典中定义。")

    except Exception as e:
        errors.append(f"资产定义检查失败: {e}")
        
    return errors

# ===================================================================
# 主入口函数
# ===================================================================

def run_validator(plan_json: Dict[str, Any]) -> Optional[str]:
    """
    运行所有基于代码的确定性检查。
    
    :param plan_json: D:/Projects/T-bridge/agents/validator_agent.py 待检查的场景 JSON (dict)
    :return: 如果有错误，返回一个格式化的错误报告 (str)；
            如果
            没有错误，返回 None。
    """
    print("[Validator] 正在运行代码QA检查...")
    
    # 确保 plan_json 是一个 dict
    if not isinstance(plan_json, dict):
        print(f"[Validator] 错误: 传入的 plan_json 不是一个字典 (dict)。类型: {type(plan_json)}")
        return "严重错误: 接收到的数据不是一个有效的 JSON 字典。"

    all_errors = []

    # 1. 检查组件缺失
    # 这一步必须最先运行，因为它确保了后续步骤的引用是有效的
    all_errors.extend(check_asset_definitions(plan_json))
    
    # 如果在第一步就发现了严重错误，可能需要提前返回
    if all_errors:
        print(f"[Validator] 发现 {len(all_errors)} 个基础定义问题。")
        # 暂时不提前返回，以便收集所有错误，但这是一个选项
        pass

    # 2. 检查碰撞
    all_errors.extend(check_collisions(plan_json))
    
    # 3. ... (未来可以添加更多检查，例如：检查坐标是否越界) ...

    if not all_errors:
        print("[Validator] 所有代码QA检查通过。")
        return None
    
    # 如果有错误，格式化成一个报告字符串
    print(f"[Validator] 发现 {len(all_errors)} 个代码QA问题。")
    report = "\n".join(f"- {error}" for error in all_errors)
    return report