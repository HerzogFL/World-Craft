import os
import json
def save_scene_to_file(scene_plan: dict, project_path: str, filename: str = "my_first_level.json") -> str:
    """
    将场景规划字典保存为 JSON 文件。
    
    :param scene_plan: 场景规划字典
    :param project_path: Godot 项目的根路径
    :param filename: 要保存的文件名
    :return: 成功则返回完整保存路径, 失败则返回 None
    """
    save_dir = os.path.join(project_path, "saved_levels")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    
    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(scene_plan, f, ensure_ascii=False, indent=4) 
            
        print(f"\n[Main] 场景规划已成功保存到: {save_path}")
        return save_path
    except Exception as e:
        print(f"\n[Main] 错误：保存 JSON 失败: {e}")
        return None