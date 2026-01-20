import json

# --- 导入此工作流所需的 Agent ---
from enricher_agent import enrich_prompt
from manager_agent_zh import get_scene_plan, repair_scene_plan
from validator_agent import run_validator
from critic_agent import run_critic

# ===================================================================
# 【【【 新增：硬性规则执行器 (Hard Rule Enforcer) 】】】
# ===================================================================
def _enforce_hard_constraints(plan: dict) -> dict:
    """
    在验证之前，强制修正 JSON 中那些已知的不符合规范的数值。
    这比让 LLM 自己去修要快得多，也稳得多。
    """
    if not plan or "assets" not in plan:
        return plan
        
    # print(f"--- [Workflow] 正在执行硬性规则筛查... ---")
    
    for asset_id, details in plan["assets"].items():
        asset_type = details.get("type")
        description = details.get("description", "").lower()
        
        # --- 规则 1: 地板 (Floor) 必须是 visual_size [2, 2] ---
        # 识别逻辑：type=tile 且 (ID含floor 或 描述含floor)
        if asset_type == "tile" and ("floor" in asset_id.lower() or "floor" in description):
            current_base = details.get("base_size", [0, 0])
            current_visual = details.get("visual_size", [0, 0])
            
            # 强制修正
            if current_base != [1, 1] or current_visual != [2, 2]:
                print(f"  - [Auto-Fix] 修正地板 '{asset_id}': Base{current_base}->[1,1], Visual{current_visual}->[2,2]")
                details["base_size"] = [1, 1]
                details["visual_size"] = [2, 2]


    return plan


def _run_manager_with_validation(task_prompt: str, base_plan: dict = None, max_validator_loops: int = 3) -> dict:
    """
    原子执行单元：生成 -> 强制修正 -> 验证 -> 修复 -> 强制修正 -> ...
    """
    
    current_plan = None
    
    # --- 1. Manager 生成 (v-draft) ---
    print(f"\n--- [Manager] 正在根据任务生成草稿... ---")
    if base_plan is None:
        current_plan = get_scene_plan(task_prompt, use_llm=False)
    else:
        current_plan = repair_scene_plan(base_plan, task_prompt, use_llm=True)
    
    # 【【【 关键插入 1：生成后立即强制修正 】】】
    current_plan = _enforce_hard_constraints(current_plan)

    # --- 2. Validator 内部循环 (最多3次) ---
    for i in range(max_validator_loops):
        print(f"--- [Validator 内部循环 {i + 1}/{max_validator_loops}] 正在检查 Manager 草稿... ---")
        
        # 运行代码QA
        validator_report = run_validator(current_plan)
        
        if not validator_report:
            # 验证通过！
            print(f"--- [Validator 内部循环 {i + 1}] 验证通过。---")
            return current_plan 
            
        # 验证失败，需要修复
        print(f"--- [Validator 内部循环 {i + 1}] 发现物理错误: {validator_report} ---")
        print(f"--- [Manager] 正在修复物理错误... ---")
        
        # 让 Manager 修复 Validator 发现的“代码级”错误
        current_plan = repair_scene_plan(current_plan, validator_report, use_llm=True) 
        
        # 【【【 关键插入 2：修复后再次强制修正 】】】
        # 防止 Manager 在修复碰撞时，又把尺寸改回错误的数值
        current_plan = _enforce_hard_constraints(current_plan)
    
    print(f"\n!!! 警告: [Validator] 达到最大尝试次数 ({max_validator_loops})。")
    print(f"!!! 将使用最后一次修复的版本（可能仍有物理问题）。")
    return current_plan


def generate_and_iterate_scene(original_prompt: str, max_repair_attempts: int = 1) -> dict | None:
    
    # --- 0. 丰富提示 ---
    print("--- 0. Enricher Agent 正在丰富提示... ---")
    enriched_prompt = enrich_prompt(original_prompt, use_llm=True)
    print(f"--- 0. 生成的提示内容：... ---{enriched_prompt}")
    
    
    # --- 1. 初始生成 (V1) ---
    print(f"\n==========================================")
    print(f" 高层循环: 初始生成 (V1)")
    print(f"==========================================")
    
    current_plan = _run_manager_with_validation(
        task_prompt=enriched_prompt,
        base_plan=None,
        max_validator_loops=3
    )
    
    # --- 2. 迭代修复循环 ---
    for i in range(max_repair_attempts):
        print(f"\n--- [Critic] 正在进行第 {i + 1}/{max_repair_attempts} 次语义评估... ---")
        
        # 步骤 A: Critic 审查
        critic_report = run_critic(current_plan, use_vlm=True)

        # 步骤 B: 检查 Critic 报告
        if not critic_report:
            print(f"\n--- [Critic] 评估通过！语义合理。 ---")
            print(f"--- 高层循环在第 {i + 1} 次评估中完美结束。 ---")
            break 

        # 步骤 C: Critic 不满意，准备修复
        print(f"\n--- [Critic] 提出语义建议: {critic_report} ---")
        print(f"\n==========================================")
        print(f" 高层循环: 修复 {i + 1}/{max_repair_attempts}")
        print(f"==========================================")

        repair_task_prompt = (
            f"【原始任务】:\n{enriched_prompt}\n\n"
            f"【上次的错误报告】:\n{critic_report}\n\n"
            f"【本次任务】:\n请在保持原始任务不变的前提下，根据上述错误报告，修复场景规划。"
        )

        # 步骤 D: 调用“原子单元”进行修复
        current_plan = _run_manager_with_validation(
            task_prompt=repair_task_prompt,
            base_plan=current_plan, 
            max_validator_loops=3
        )

    if max_repair_attempts > 0:
        print(f"\n--- [Main Workflow] 达到最大修复次数 ({max_repair_attempts})。停止迭代。 ---")

    return current_plan