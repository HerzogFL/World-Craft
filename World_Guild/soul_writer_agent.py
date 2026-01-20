# 文件名: soul_writer_agent.py
import os
import json
import random
from typing import Union
from config import SOUL_API_CONFIG

# ===================================================================
# 模拟日程生成
# ===================================================================
def _simulate_schedule_generation(character_name: str, scene_plan: dict) -> dict:
    """
    (模拟 LLM) 为 NPC 生成一个基于场景上下文的日程表。
    它会读取场景中所有可用的 semantic_tag 来创建日程。
    """
    print(f"  [Soul Writer] 模拟为 {character_name} 生成日程...")
    
    # 1. 从 scene_plan 中提取所有可用的“地点”语义标签
    valid_tags = []
    if "properties" in scene_plan and "assets" in scene_plan:
        for asset_id, prop in scene_plan["properties"].items():
            # 确保这个资产不是角色
            asset_type = scene_plan["assets"].get(asset_id, {}).get("type", "")
            if asset_type in ("tile", "object"):
                # 获取语义标签
                tag = prop.get("semantic_tag")
                # 过滤掉无意义的标签
                if tag and tag not in ("floor", "wall"):
                    if f"[{tag}]" not in valid_tags:
                        valid_tags.append(f"[{tag}]")

    # 2. 如果没有找到可用标签，返回一个空日程
    if not valid_tags:
        print(f"  [Soul Writer] 警告: 找不到可用的 semantic_tag 来为 {character_name} 生成日程。")
        return {}

    # 3. 随机生成一个简单的 3 步日程
    # (确保 'main_door' 总是在最后，如果它存在的话)
    loc1 = random.choice(valid_tags)
    loc2 = random.choice(valid_tags)
    
    # 尝试找到一个门作为离开点
    door_tags = [t for t in valid_tags if "door" in t]
    loc3 = random.choice(door_tags) if door_tags else random.choice(valid_tags)

    schedule = {
        "09:00": f"去 {loc1} 附近看看",
        "11:30": f"在 {loc2} 休息",
        "15:00": f"准备从 {loc3} 离开"
    }
    
    return schedule

# ===================================================================
# 灵魂文件生成 (主函数)
# ===================================================================
def generate_npc_souls(scene_plan: dict, project_path: str):
    """
    遍历 scene_plan, 为所有 "npc" 和 "agent" 生成灵魂文件。
    - NPC: 会获得一个模拟生成的 "schedule"。
    - Agent: 会获得一个空的 "current_dynamic_plan"。
    """
    print("\n[Soul Writer Agent] 开始生成灵魂文件...")
    
    # 1. 确定灵魂文件的保存路径
    souls_dir = os.path.join(project_path, "npc_souls")
    os.makedirs(souls_dir, exist_ok=True)
    
    assets = scene_plan.get("assets", {})
    properties = scene_plan.get("properties", {})
    
    # 2. 遍历所有资产
    for asset_id, asset_info in assets.items():
        asset_type = asset_info.get("type")
        
        if asset_type in ("npc", "agent"):
            prop = properties.get(asset_id)
            if not prop:
                print(f"  [Soul Writer] Error: Could not find properties for {asset_id}, skipping.")
                continue
                
            character_name = prop.get("character_name", "Unknown")
            safe_name = character_name.lower().replace(' ', '_').replace('(', '').replace(')', '')
            soul_file = prop.get("soul_file", f"{safe_name}_soul.json")
            is_agent = prop.get("is_agent", False)
            
            print(f"  [Soul Writer] Creating soul for '{character_name}' (Agent: {is_agent})...")

            # 4. 【【【 核心逻辑：根据类型分配日程和 API 】】】
            npc_schedule = {}
            agent_dynamic_plan = {}
            api_config_to_write = {} # 默认为空

            if is_agent:
                # Agent: 从 config.py 读取 API 配置
                print(f"  [Soul Writer] Is Agent. Embedding API configuration from config.py...")
                
                cfg = SOUL_API_CONFIG 
                
                # 动态构建 Godot 需要的 API URL
                api_url = ""
                api_type = cfg.get("type", "custom")
                
                model_name = cfg.get("model") 
                if not model_name:
                    print(f"  [Soul Writer] 警告: 'model' 未在 config.py 的 SOUL_API_CONFIG 中配置!")
                    model_name = "gpt-4o"

                
                if api_type == "azure":
                    endpoint = cfg.get('azure_endpoint', '').rstrip('/')
                    version = cfg.get('api_version', '')
                    api_url = f"{endpoint}/openai/deployments/{model_name}/chat/completions?api-version={version}"
                
                elif api_type == "openai":
                    custom_base_url = cfg.get("base_url")
                    if custom_base_url:
                        # 使用 config.py 中提供的 base_url
                        endpoint = custom_base_url.rstrip('/')
                        api_url = f"{endpoint}/chat/completions"
                    else:
                        # 使用默认的 OpenAI URL
                        api_url = "https://api.openai.com/v1/chat/completions"
                
                elif api_type == "custom":
                    endpoint = cfg.get('base_url', '').rstrip('/')
                    api_url = f"{endpoint}/chat/completions"

                # 这是将写入 .json 文件的字典
                api_config_to_write = {
                    "api_type": api_type,
                    "api_key": cfg.get("api_key", "NA"),
                    "model_name": model_name, # 供 Godot 内的 AI 逻辑使用
                    "api_url": api_url         # Godot Agent 实际调用的 URL
                }
                
                agent_dynamic_plan = {} # Agent 获得一个空的动态计划
            
            else:
                # NPC: 获得一个模拟的、硬编码的日程
                npc_schedule = _simulate_schedule_generation(character_name, scene_plan)
                # api_config_to_write 保持为空
            
            # 5. 定义灵魂文件的完整结构
            soul_data = {
                # --- Agent (LLM) 配置 ---
                **api_config_to_write,
                
                # --- 角色基础设定 ---
                "base_prompt": f"You are an AI agent named {character_name}.",
                "personality": "A regular person",
                "goals": [f"Spend a day in {scene_plan['metadata']['scene_name']}"],
                
                # --- 记忆和对话 (默认为空) ---
                "memory": [],
                "dialogue": {
                    "default": "Hello there."
                },
                
                # --- 日程规划 (核心) ---
                "schedule": npc_schedule,              # <--- NPC 使用
                "current_dynamic_plan": agent_dynamic_plan # <--- Agent 使用
            }
            
            # 6. 保存文件
            try:
                save_path = os.path.join(souls_dir, soul_file)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(soul_data, f, ensure_ascii=False, indent=4)
                print(f"  [Soul Writer] 成功保存: {soul_file}")
            except Exception as e:
                print(f"  [Soul Writer] 错误: 保存 {soul_file} 失败: {e}")

# ===================================================================
# 世界上下文生成 (Agent 感知世界用)
# ===================================================================
def generate_world_context(scene_plan: dict, project_path: str):
    """
    为 Agent 的 LLM 生成一个 "world_context.json" 文件。
    这能让 Agent 知道场景中有什么物体和哪些人。
    """
    print("\n[World Writer] 正在生成世界上下文 (world_context.json)...")
    
    world_dir = os.path.join(project_path, "world")
    os.makedirs(world_dir, exist_ok=True)
    save_path = os.path.join(world_dir, "world_context.json")
    
    available_objects = []
    available_characters = []

    assets = scene_plan.get("assets", {})
    properties = scene_plan.get("properties", {})

    # 遍历所有资产，将其分类
    for asset_id, asset_info in assets.items():
        prop = properties.get(asset_id)
        if not prop:
            continue
            
        asset_type = asset_info.get("type")
        
        if asset_type in ("npc", "agent"):
            # 添加角色
            char_name = prop.get("character_name")
            if char_name:
                available_characters.append(char_name)
        
        elif asset_type == "object":
            # 添加物体/地点的语义标签
            tag = prop.get("semantic_tag")
            if tag and tag not in available_objects:
                available_objects.append(tag)

    # 组装世界上下文
    world_data = {
        "scene_name": scene_plan.get("metadata", {}).get("scene_name", "未命名场景"),
        "available_objects": available_objects,
        "available_characters": available_characters
    }
    
    # 保存文件
    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(world_data, f, ensure_ascii=False, indent=4)
        print(f"[World Writer] 成功保存世界上下文: {save_path}")
    except Exception as e:
        print(f"[World Writer] 错误: 保存 world_context.json 失败: {e}")