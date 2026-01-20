import os
import json
import time

# --- 从我们的独立文件中导入 Agent 功能 ---
from artist_agent import run_artist_agent
from soul_writer_agent import generate_npc_souls, generate_world_context
from godot_client import send_command
from save_scene import save_scene_to_file
from generation_workflow import generate_and_iterate_scene
from build_asset_index import build_index, INDEX_SAVE_PATH

# ===================================================================
# 主函数 (只负责协调)
# ===================================================================

def main():
    # 1. 设置 Godot 项目路径 
    GODOT_PROJECT_PATH = ""
    ASSET_PACK_FOLDER_NAME = "External_Asset_Pack"

    # --- 【【【 调试开关 】】】 ---
    USE_EXISTING_PLAN = True  # True: 使用本地现有 JSON; False: 从头生成
    EXISTING_PLAN_PATH = "" # 现有文件的路径
    # ---------------------------

    # --- 启动检查与索引构建 ---
    print("--- [Main] 正在启动... ---")
    ASSET_PACK_PATH = os.path.join(GODOT_PROJECT_PATH, ASSET_PACK_FOLDER_NAME)
    
    if not os.path.exists(GODOT_PROJECT_PATH):
        print(f"!!! 错误: Godot 项目路径不存在: {GODOT_PROJECT_PATH}"); return

    if not os.path.exists(INDEX_SAVE_PATH):
        print(f"--- [Main] 正在自动构建索引...")
        if not build_index(ASSET_PACK_PATH):
            print(f"!!! [Main] 索引构建失败。"); return
    else:
        print(f"--- [Main] 成功加载资产索引。 ---")

    final_plan_from_loop = None

    # --- 2. 获取场景规划 (生成 或 加载) ---
    if USE_EXISTING_PLAN:
        print(f"\n--- [Main] 模式: 加载现有文件 '{EXISTING_PLAN_PATH}' ---")
        if os.path.exists(EXISTING_PLAN_PATH):
            with open(EXISTING_PLAN_PATH, 'r', encoding='utf-8') as f:
                final_plan_from_loop = json.load(f)
            print("--- 加载成功。 ---")
        else:
            print(f"!!! 错误: 找不到文件 {EXISTING_PLAN_PATH}")
            return
    else:
        print(f"\n--- [Main] 模式: 启动 AI 生成工作流 ---")
        
        original_task_prompt = "一个阴森的，黑暗的古堡，里面还有一些神秘的人物和物品"
    
        final_plan_from_loop = generate_and_iterate_scene(
            original_prompt=original_task_prompt,
            max_repair_attempts=1 
        )

    if not final_plan_from_loop:
        print("\n[Main] !!! 未能获取有效规划。程序终止。 !!!"); return
        
    print(f"\n--- 场景规划准备就绪。开始后续处理... ---")

    # 3. Artist Agent (生成贴图)
    print("\n--- 2. Artist Agent 正在生成贴图... ---")
    processed_scene_plan = run_artist_agent(final_plan_from_loop, GODOT_PROJECT_PATH)

    # 4. Soul Writer Agent
    print("\n--- 3. Soul Writer Agent 正在生成灵魂... ---")
    generate_npc_souls(processed_scene_plan, GODOT_PROJECT_PATH)

    # 5. World Writer Agent
    print("\n--- 4. World Context Agent 正在生成世界上下文... ---")
    generate_world_context(processed_scene_plan, GODOT_PROJECT_PATH)

    # 6. 保存最终结果
    print("\n--- 5. 正在保存最终场景... ---")
    final_save_path = save_scene_to_file(processed_scene_plan, GODOT_PROJECT_PATH, "my_final_scene.json")
    
    if final_save_path:
        print(f" ✅ 最终 JSON 已保存: {final_save_path}")
        # print(json.dumps(processed_scene_plan, indent=4, ensure_ascii=False))

    # 7. 发送给 Godot
    print("\n[Main] 正在发送给 Godot...")
    send_command({
        "action": "build_scene_from_json",
        "payload": processed_scene_plan
    })
    print("[Main] 指令已发送。")

if __name__ == "__main__":
    main()