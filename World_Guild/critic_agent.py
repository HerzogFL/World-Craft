import os
import json
import sys
import io
import base64
from typing import List, Dict, Any, Optional

# 关键：导入 Pillow (PIL) 用于绘图
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("!!! 错误: Critic Agent 需要 'Pillow' 库来绘制布局草图。", file=sys.stderr)
    print("!!! 请运行: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# --- 从我们的独立文件中导入 ---
from config import CRITIC_API_CONFIG
from api_client_utils import create_api_client

# --- 初始化 Critic 的 VLM 客户端 ---
try:
    client = create_api_client(CRITIC_API_CONFIG, agent_name="Critic Agent")
    CRITIC_MODEL_NAME = CRITIC_API_CONFIG.get("model")
    if not CRITIC_MODEL_NAME:
        raise ValueError("'model' is not specified in CRITIC_API_CONFIG in config.py")
    print(f"[Critic Agent] Using VLM model: {CRITIC_MODEL_NAME}")
    
except Exception as e:
    print(f"!!! Error loading Critic Agent config: {e}", file=sys.stderr)
    sys.exit(1)

# ===================================================================
# 核心功能 1：提取尺寸数据 (用于 Task 1)
# ===================================================================

def _extract_size_data(plan_json: Dict[str, Any]) -> str:
    """
    (辅助函数)
    正如你的提议，我们不发送整个 JSON，而是提取一个简化的、
    专注于尺寸的列表，以便 VLM 检查比例。
    """
    print("[Critic Agent] 正在提取资产尺寸数据...")
    size_data = []
    assets = plan_json.get("assets", {})
    
    for asset_id, details in assets.items():
        size_data.append({
            "asset_id": asset_id,
            "type": details.get("type"),
            "description": details.get("description"),
            "base_size (WxH)": details.get("base_size"),
            "visual_size (WxH)": details.get("visual_size")
        })
        
    return json.dumps(size_data, indent=2, ensure_ascii=False)

# ===================================================================
# 核心功能 2：生成布局草图 (用于 Task 2)
# ===================================================================
# 瓦片大小（像素）- 用于绘制草图
SKETCH_TILE_SIZE = 16 
# 颜色
COLOR_WALL = "#888888"
COLOR_OBJECT = "#333333"
COLOR_NPC = "#FF0000" # 红色
COLOR_TEXT = "#000000"


def _generate_layout_sketch(plan_json: Dict[str, Any]) -> str:
    """
    (辅助函数)
    按照你的要求，生成一个简笔画布局图：
    - 框框大小 = base_size
    - 框框内有文字 = asset_id
    """
    print("[Critic Agent] 正在生成布局草图...")
    try:
        grid_size = plan_json.get("metadata", {}).get("grid_size", [25, 20])
        layout = plan_json.get("layout", {})
        assets = plan_json.get("assets", {})
        
        img_width = grid_size[0] * SKETCH_TILE_SIZE
        img_height = grid_size[1] * SKETCH_TILE_SIZE
        
        # 创建一个白色背景的图像
        img = Image.new('RGB', (img_width, img_height), 'white')
        draw = ImageDraw.Draw(img)
        
        # 尝试加载一个字体
        try:
            # 你可以指定一个 .ttf 字体路径以获得更好的效果
            font = ImageFont.load_default()
        except IOError:
            print("[Critic Agent] 警告: 无法加载默认字体。")
            font = None

        # --- 【【【 BUG 修复：第 1 步：创建 base_size 的查找字典 】】】 ---
        size_lookup = {}
        for asset_id, details in assets.items():
            if details and "base_size" in details:
                size_lookup[asset_id] = details["base_size"]
        # -------------------------------------------------------------

        # 1. 绘制墙壁 (灰色粗框)
        for wall in layout.get("wall_layer", []):
            if wall.get("command") == "fill_rect":
                area = wall.get("area") # [x, y, w, h]
                if not area or len(area) != 4: continue
                x1 = area[0] * SKETCH_TILE_SIZE
                y1 = area[1] * SKETCH_TILE_SIZE
                x2 = (area[0] + area[2]) * SKETCH_TILE_SIZE
                y2 = (area[1] + area[3]) * SKETCH_TILE_SIZE
                draw.rectangle([x1, y1, x2, y2], outline=COLOR_WALL, width=2, fill="#E0E0E0")

        # 2. 绘制物体和 NPC (使用 AABB 逻辑)
        items_to_draw = layout.get("object_layer", []) + layout.get("npc_layer", [])
        
        for item in items_to_draw:
            # 使用与 Validator 相同的 AABB 计算逻辑
            pos = item.get("position")
            asset_id = item.get("asset_id", "N/A")
            
            # --- 【【【 BUG 修复：第 2 步：从查找字典中获取 base_size 】】】 ---
            size = size_lookup.get(asset_id)
            # -------------------------------------------------------------
            
            item_type = assets.get(asset_id, {}).get("type", "object")
            
            if not pos or not size or len(pos) != 2 or len(size) != 2:
                # 如果 尺寸(size) 为空 (因为 assets 里就没有)，则跳过绘制
                continue

            pos_x_tile, pos_y_tile = pos[0], pos[1]
            size_w_tile, size_h_tile = size[0], size[1]
            
            if not all(isinstance(v, (int, float)) for v in [pos_x_tile, pos_y_tile, size_w_tile, size_h_tile]):
                print(f"[Critic Agent] 警告: {asset_id} 的 position 或 base_size 含有无效数据。跳过绘制。")
                continue

            if size_w_tile <= 0 or size_h_tile <= 0:
                continue

            half_width_tile = size_w_tile / 2.0
            
            # 计算像素坐标
            px_x1 = (pos_x_tile - half_width_tile) * SKETCH_TILE_SIZE
            px_y1 = (pos_y_tile - size_h_tile) * SKETCH_TILE_SIZE
            px_x2 = (pos_x_tile + half_width_tile) * SKETCH_TILE_SIZE
            px_y2 = pos_y_tile * SKETCH_TILE_SIZE
            
            color = COLOR_NPC if item_type in ["npc", "agent"] else COLOR_OBJECT
            
            # 绘制矩形
            draw.rectangle([px_x1, px_y1, px_x2, px_y2], outline=color, width=1)
            # 绘制文字
            draw.text((px_x1 + 2, px_y1 + 2), asset_id, fill=COLOR_TEXT, font=font)

        # 3. 将图像转换为 Base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")

        try:
            save_path = "output/critic_sketch.png"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img.save(save_path)
            print(f"[Critic Agent] 布局草图已保存到 {save_path}")
        except Exception as save_e:
            print(f"!!! [Critic Agent] 警告: 无法保存草图文件: {save_e}", file=sys.stderr)
        # ------------------------------------

        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        print("[Critic Agent] 布局草图生成完毕。")
        return img_base64

    except Exception as e:
        print(f"!!! [Critic Agent] 生成布局草图失败: {e}", file=sys.stderr)
        return ""


# ===================================================================
# VLM 提示工程 (Prompt Engineering)
# ===================================================================

CRITIC_SYSTEM_PROMPT = """
    你是一个资深的游戏关卡设计师和QA（质量保证）专家。
    你的任务是审查一个由AI生成的2.5D像素游戏场景设计。
    你将收到两部分信息：
    1. 【尺寸数据】：一个 JSON 列表，包含所有资产的 `base_size` (物理底座) 和 `visual_size` (视觉贴图)。
    2. 【布局草图】：一张简笔画，显示了物体在场景中的位置和 `base_size`。

    你的工作是找出**比例失调**和**布局不合理**的问题。

    【规则】
    1. 严格按照“绝对规则”检查尺寸数据。
    2. 仔细分析草图，找出布局中的“语义错误”。
    3. 你的回答**必须**是一个 JSON 对象。
    4. 如果没有发现任何问题，返回 `{{ "errors": [] }}`。
    5. 如果发现问题，在 "errors" 列表中添加描述。
    """

CRITIC_USER_PROMPT_TEMPLATE = """
    请对以下游戏场景设计进行审查。
    ---
    **第 1 部分：资产尺寸数据 (用于比例检查)**
    ```json
    {size_data_str}
    ```
    ---
    **第 2 部分：布局草图 (用于语义检查)** [请查看你下方看到的图片]
    ---

    **你的审查任务：**

    **任务 1：审查【尺寸数据】的合理性**

    * **绝对尺寸：** `visual_size` 是否符合常识？(例如：NPC [1, 10] 是错误的)。
    * **相对尺寸：** 资产间的尺寸是否合理？(例如：`chair` [3, 3] 不应该比 `table` [2, 2] 的 `base_size` 更大)。
    * **一致性：** 对于高度要明显高于底座的物体，比如衣柜，书架等等`visual_size` 的 Y 轴是否（通常）大于 `base_size` 的 Y 轴？
            ** 但是对于一些相对扁平的物体，比如地毯,池塘等等，`visual_size` 的 Y 轴通常要等于 `base_size` 的 Y 轴。

    **任务 2：审查【布局草图】的合理性**

    * **1. 布局语义合理性 (Semantic Appropriateness):** 布局是否符合基本逻辑和常识？
        * (例如：`toilet` (马桶) **绝对不应该**出现在 `kitchen` (厨房) 或 `main_seating_area` (主要座位区) 中。)
        * (例如：`main_door` (主入口) 处**绝对不能**被大型障碍物（如 `plant_deco`, `bookshelf`）堵塞，除非它是一个有意义的屏风 (`partition`)。)

    * **2. 空旷度 (Emptiness):**
        * 场景中是否存在大片（例如 10x10 瓦片以上）**无意义**的空白区域？
        * (注意：如果场景描述是一个“大型会议室”或“广场”，则留白是允许的。但对于“咖啡馆”、“商店”或“办公室”，**必须**使用装饰物或家具来填充空间，避免空旷感。)
        
    请以 JSON 格式返回你的审查报告： (如果没有问题，返回 `{{ "errors": [] }}`。如果发现问题，请描述问题。)
    """

# ===================================================================
# VLM API 调用
# ===================================================================
def _call_vlm_for_critique(size_data_str: str, image_base64: str) -> Optional[dict]:
    """ (辅助函数) 调用 VLM API (多模态) """
    print("[Critic Agent] 正在连接 VLM API 进行评估...")

    user_prompt = CRITIC_USER_PROMPT_TEMPLATE.format(size_data_str=size_data_str)

    messages = [
        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                # 1. 文本部分：提示
                {"type": "text", "text": user_prompt},
                
                # 2. 图像部分：草图
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": "low" # 草图不需要高分辨率
                    }
                }
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model=CRITIC_MODEL_NAME,
            messages=messages,
            # 许多 VLM API (如 Azure) 不支持 response_format，我们手动解析 JSON
            # response_format={"type": "json_object"}, 
            max_tokens=1024 
        )
        
        response_content = response.choices[0].message.content
        print("[Critic Agent] VLM 响应已收到。")

        # 尝试从 VLM 的回复中提取 JSON
        # (VLM 可能会在 JSON 前后添加 "```json ... ```" 或其他文本)
        json_start = response_content.find('{')
        json_end = response_content.rfind('}')
        
        if json_start != -1 and json_end != -1:
            json_str = response_content[json_start : json_end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as json_err:
                print(f"[Critic Agent] VLM 返回了格式错误的 JSON。错误: {json_err}")
                print(f"[Critic Agent] 原始 JSON 字符串: {json_str}")
                return {"errors": [f"VLM JSON 解析失败: {json_err}", f"原始响应: {response_content}"]}
        else:
            print(f"[Critic Agent] VLM 未返回有效的 JSON 对象。原始响应: {response_content}")
            # 即使不是 JSON，也要将其视为一个“错误报告”
            return {"errors": [f"VLM 非结构化响应: {response_content}"]}

    except Exception as e:
        print(f"!!! [Critic Agent] VLM API 调用或 JSON 解析失败: {e}", file=sys.stderr)
        return None
# ===================================================================
# 主入口函数
# ===================================================================
def run_critic(plan_json: Dict[str, Any], use_vlm: bool = True) -> Optional[str]:
    """ 
    运行 Critic (VLM QA) 检查。

    :param plan_json: 待检查的场景 JSON (dict)
    :param use_vlm: 是否启用 VLM 检查
    :return: 如果有错误，返回一个格式化的错误报告 (str)；
            如果没有错误，返回 None。
    """
    if not use_vlm:
        print("[Critic Agent] VLM 检查被禁用。")
        return None
        
    print("[Critic Agent] G] 正在运行 VLM QA 检查...")

    # 确保 plan_json 是一个 dict
    if not isinstance(plan_json, dict):
        print(f"[Critic Agent] 错误: 传入的 plan_json 不是一个字典 (dict)。")
        return "严重错误: Critic 接收到的数据不是一个有效的 JSON 字典。"

    # 1. 提取尺寸数据 (Task 1 Input)
    size_data_str = _extract_size_data(plan_json)

    # 2. 生成布局草图 (Task 2 Input)
    sketch_base64 = _generate_layout_sketch(plan_json)
    if not sketch_base64:
        return "严重错误: Critic 无法生成布局草图。"

    # 3. 调用 VLM
    report_json = _call_vlm_for_critique(size_data_str, sketch_base64)

    if not report_json:
        # API 调用失败
        return "严重错误: VLM API 调用失败，无法进行语义评估。"
        
    # 4. 解析 VLM 的 JSON 响应
    errors = report_json.get("errors", [])

    if not errors:
        print("[Critic Agent] VLM 评估通过，未发现语义问题。")
        return None
        
    # 5. 格式化错误报告
    print(f"[Critic Agent] VLM 发现 {len(errors)} 个语义问题。")
    report_str = "VLM 审查报告 (请修复以下高级问题):\n"
    report_str += "\n".join(f"- {error}" for error in errors)

    return report_str