# 文件名: manager_agent.py
import os
import json
import sys
from config import MANAGER_API_CONFIG
from api_client_utils import create_api_client


try:
    client = create_api_client(MANAGER_API_CONFIG, agent_name="Manager Agent")
    
    # 【【【 关键修复：只读取 'model' 】】】
    DESIGN_MODEL_NAME = MANAGER_API_CONFIG.get("model")
    if not DESIGN_MODEL_NAME:
        raise ValueError("'model' is not specified in MANAGER_API_CONFIG in config.py")
    
    print(f"[Manager Agent] Using model/deployment: {DESIGN_MODEL_NAME}")
    
except Exception as e:
    print(f"!!! Error loading Manager Agent config: {e}", file=sys.stderr)
    sys.exit(1)


# ===================================================================
# 【【【 统一范例定义 (Single Source of Truth) 】】】
# ===================================================================
EXAMPLE_SCENE_JSON = {
    "metadata": {
        "scene_name": "The Verdant Scholar's Hub (Enhanced)",
        "grid_size": [35, 28],
        "description": "A bustling establishment. The interior is subdivided into a quiet reading zone and a social cafe area. The kitchen is fully equipped. The garden is romantic and well-lit.",
        "style_prompt": "16-bit pixel art, top-down RPG style, cozy lighting, clutter and details"
    },
    "assets": {
        "floor_dark_wood": {"type": "tile", "description": "Polished dark mahogany wood floor.", "base_size": [1, 1], "visual_size": [2, 2]},
        "floor_kitchen_tile": {"type": "tile", "description": "White and blue checkerboard tile.(floor)", "base_size": [1, 1], "visual_size": [2, 2]},
        "floor_garden_grass": {"type": "tile", "description": "Lush green grass.(floor)", "base_size": [1, 1], "visual_size": [2, 2]},
        "wall_brick_library": {"type": "tile", "description": "Vintage red brick wall with wood trim.(wall)", "base_size": [1, 1], "visual_size": [1, 6]},
        "wall_kitchen_white": {"type": "tile", "description": "Clean white tiled wall.", "base_size": [1, 1], "visual_size": [1, 5]},
        "wall_garden_hedge": {"type": "tile", "description": "Manicured green bush hedge.(wall)", "base_size": [1, 1], "visual_size": [1, 4]},
        
        "window_large_arched": {"type": "object", "description": "A large arched window letting in sunlight.", "base_size": [2, 1], "visual_size": [2, 3]},
        "bookshelf_tall": {"type": "object", "description": "Towering wooden bookshelf.", "base_size": [3, 2], "visual_size": [2, 4]},
        "bookshelf_wide": {"type": "object", "description": "A wider, lower bookshelf filled with magazines.", "base_size": [3, 2], "visual_size": [3, 2]},
        "table_long_study": {"type": "object", "description": "Long sturdy wooden table with lamps.", "base_size": [4, 2], "visual_size": [4, 3]},
        "table_cafe_round": {"type": "object", "description": "Small round wooden table for coffee.", "base_size": [2, 2], "visual_size": [2, 3]},
        "chair_library": {"type": "object", "description": "Cushioned wooden chair.", "base_size": [2, 2], "visual_size": [2, 3]},
        "chair_stool": {"type": "object", "description": "A simple wooden stool.", "base_size": [2, 2], "visual_size": [2, 3]},
        
        "bar_counter_L": {"type": "object", "description": "L-shaped wooden service counter.", "base_size": [4, 3], "visual_size": [4, 4]},
        "kitchen_stove": {"type": "object", "description": "Stainless steel industrial stove.", "base_size": [3, 2], "visual_size": [3, 4]},
        "kitchen_fridge": {"type": "object", "description": "A large silver double-door fridge.", "base_size": [3, 2], "visual_size": [3, 4]},
        "kitchen_sink_counter": {"type": "object", "description": "Counter with a sink and dirty dishes.", "base_size": [3, 2], "visual_size": [3, 3]},
        
        "plant_indoor_fern": {"type": "object", "description": "A potted fern plant.", "base_size": [2, 2], "visual_size": [2, 3]},
        "lamp_standing": {"type": "object", "description": "A tall vintage floor lamp casting warm light.", "base_size": [2, 2], "visual_size": [2, 3]},
        
        "fountain_stone": {"type": "object", "description": "Three-tiered stone fountain.", "base_size": [3, 3], "visual_size": [3, 4]},
        "table_garden_iron": {"type": "object", "description": "White iron garden table.", "base_size": [3, 3], "visual_size": [3, 4]},
        "chair_garden_iron": {"type": "object", "description": "White metal garden chair.", "base_size": [2, 2], "visual_size": [2, 3]},
        "lamp_street_garden": {"type": "object", "description": "Black iron street lamp.", "base_size": [2, 2], "visual_size": [2, 4]},
        "flower_bush_red": {"type": "object", "description": "Bush with red roses.", "base_size": [2, 2], "visual_size": [2, 2]},
        
        "door_glass": {"type": "object", "description": "Double glass door.", "base_size": [3, 2], "visual_size": [2, 4]},
        "rug_persian": {"type": "object", "description": "Intricate red Persian rug.", "base_size": [4, 3], "visual_size": [4, 3]},
        
        "agent_librarian": {"type": "agent", "description": "The librarian wearing white clothes and black glasses", "base_size": [1, 1], "visual_size": [2, 3]},
        "npc_student_f": {"type": "npc", "description": "A female student in white clothes", "base_size": [1, 1], "visual_size": [2, 3]},
        "npc_chef": {"type": "npc", "description": "A male chef wearing white clothes", "base_size": [1, 1], "visual_size": [2, 3]},
        "npc_hipster": {"type": "npc", "description": "A male customer wearing blue fashion clothes", "base_size": [1, 1], "visual_size": [2, 3]}
    },
    "layout": {
        "floor_layer": [
            {"asset_id": "floor_dark_wood", "command": "fill_rect", "area": [0, 0, 25, 20]},
            {"asset_id": "floor_kitchen_tile", "command": "fill_rect", "area": [25, 0, 10, 20]},
            {"asset_id": "floor_garden_grass", "command": "fill_rect", "area": [0, 20, 35, 8]}
        ],
        "wall_layer": [
            {"asset_id": "wall_brick_library", "command": "fill_rect", "area": [0, 0, 35, 1]},
            {"asset_id": "wall_brick_library", "command": "fill_rect", "area": [0, 1, 1, 19]},
            {"asset_id": "wall_brick_library", "command": "fill_rect", "area": [34, 1, 1, 19]},
            {"asset_id": "wall_kitchen_white", "command": "fill_rect", "area": [24, 1, 1, 10]},
            {"asset_id": "wall_garden_hedge", "command": "fill_rect", "area": [0, 19, 11, 1]},
            {"asset_id": "wall_garden_hedge", "command": "fill_rect", "area": [14, 19, 21, 1]},
            {"asset_id": "wall_garden_hedge", "command": "fill_rect", "area": [0, 20, 1, 7]},
            {"asset_id": "wall_garden_hedge", "command": "fill_rect", "area": [34, 20, 1, 7]},
            {"asset_id": "wall_garden_hedge", "command": "fill_rect", "area": [0, 27, 35, 1]}
        ],
        "object_layer": [
            
            { "asset_id": "window_large_arched", "position": [3, 0] },
            { "asset_id": "window_large_arched", "position": [10, 0] },
            { "asset_id": "window_large_arched", "position": [17, 0] },

            { "asset_id": "bookshelf_tall", "position": [1, 1] },
            { "asset_id": "bookshelf_tall", "position": [5, 1] },
            { "asset_id": "bookshelf_tall", "position": [1, 6] },
            { "asset_id": "bookshelf_wide", "position": [5, 6] },
            
            { "asset_id": "rug_persian", "position": [6, 12] },
            { "asset_id": "table_long_study", "position": [6, 12] },
            { "asset_id": "chair_library", "position": [4, 12] },
            { "asset_id": "chair_library", "position": [5, 12] },
            { "asset_id": "chair_library", "position": [8, 12] },
            { "asset_id": "chair_library", "position": [9, 12] },
            { "asset_id": "lamp_standing", "position": [3, 11] },

            { "asset_id": "table_cafe_round", "position": [15, 10] },
            { "asset_id": "chair_library", "position": [14, 10] },
            { "asset_id": "chair_library", "position": [17, 10] },
            { "asset_id": "table_cafe_round", "position": [15, 15] },
            { "asset_id": "chair_library", "position": [14, 15] },
            { "asset_id": "chair_library", "position": [17, 15] },
            { "asset_id": "plant_indoor_fern", "position": [18, 8] },

            { "asset_id": "bar_counter_L", "position": [20, 4] },
            { "asset_id": "chair_stool", "position": [20, 7] },
            { "asset_id": "chair_stool", "position": [21, 7] },

            { "asset_id": "kitchen_stove", "position": [26, 1] },
            { "asset_id": "kitchen_fridge", "position": [30, 1] },
            { "asset_id": "kitchen_sink_counter", "position": [32, 4] },

            { "asset_id": "door_glass", "position": [12, 20] },
            
            { "asset_id": "fountain_stone", "position": [28, 23] },
            { "asset_id": "flower_bush_red", "position": [26, 22] },
            { "asset_id": "flower_bush_red", "position": [32, 22] },
            
            { "asset_id": "table_garden_iron", "position": [6, 23] },
            { "asset_id": "chair_garden_iron", "position": [5, 23] },
            { "asset_id": "chair_garden_iron", "position": [8, 23] },
            { "asset_id": "table_garden_iron", "position": [15, 23] },
            { "asset_id": "chair_garden_iron", "position": [14, 23] },
            { "asset_id": "chair_garden_iron", "position": [17, 23] },
            { "asset_id": "lamp_street_garden", "position": [10, 22] },
            { "asset_id": "lamp_street_garden", "position": [20, 22] }
        ],
        "npc_layer": [
            { "asset_id": "agent_librarian", "position": [21, 5] },
            { "asset_id": "npc_student_f", "position": [5, 13] },
            { "asset_id": "npc_chef", "position": [28, 3] },
            { "asset_id": "npc_hipster", "position": [14, 11] }
        ]
    },
    "properties": {
        "floor_dark_wood": { "physics": "passable", "navigation": "walkable", "semantic_tag": "floor_main" },
        "floor_kitchen_tile": { "physics": "passable", "navigation": "walkable", "semantic_tag": "floor_kitchen" },
        "floor_garden_grass": { "physics": "passable", "navigation": "walkable", "semantic_tag": "floor_garden" },
        "wall_brick_library": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "wall" },
        "wall_kitchen_white": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "wall" },
        "wall_garden_hedge": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "fence" },
        "window_large_arched": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "window" },
        "bookshelf_tall": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "bookshelf" },
        "bookshelf_wide": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "bookshelf" },
        "table_long_study": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "table_study" },
        "table_cafe_round": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "table_cafe" },
        "kitchen_stove": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "stove" },
        "kitchen_fridge": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "fridge" },
        "kitchen_sink_counter": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "sink" },
        "bar_counter_L": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "counter" },
        "chair_library": { "physics": "passable", "navigation": "obstacle", "semantic_tag": "chair" },
        "chair_stool": { "physics": "passable", "navigation": "obstacle", "semantic_tag": "chair" },
        "chair_garden_iron": { "physics": "passable", "navigation": "obstacle", "semantic_tag": "chair" },
        "table_garden_iron": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "table_garden" },
        "fountain_stone": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "decoration" },
        "lamp_standing": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "light_source" },
        "lamp_street_garden": { "physics": "solid", "navigation": "obstacle", "semantic_tag": "light_source" },
        "door_glass": { "physics": "passable", "navigation": "walkable_door", "semantic_tag": "door_main" },
        "agent_librarian": {"character_name": "Mr. Bookman", "is_agent": True, "soul_file": "librarian_soul.json"},
        "npc_student_f": {"character_name": "Sarah", "is_agent": False, "soul_file": "student_soul.json"},
        "npc_chef": {"character_name": "Gordon", "is_agent": False, "soul_file": "chef_soul.json"},
        "npc_hipster": {"character_name": "Liam", "is_agent": False, "soul_file": "hipster_soul.json"},
    }
}



# --- 提示工程：定义 LLM 的角色和输出格式 ---

# 1. 系统提示：设定 LLM 的身份和核心规则
SYSTEM_PROMPT = """
你是一位专业的像素风2.5D游戏场景设计师。你的任务是根据用户的文本描述，生成一个完整的、符合特定 schema 的场景规划 JSON 对象。

【绝对规则】:
1.  你的输出**必须**是一个结构完整的 JSON 对象。
2.  **绝对不要**在 JSON 对象前后添加任何额外的文字、解释或 Markdown 代码块。
3.  严格遵守下面用户提示中提供的 JSON schema 和结构。
4.  NPC本身的碰撞半径是 16 像素 (即 base_size 为 [1, 1])，视觉大小为 32x48 像素 (visual_size 为 [2, 3])。注意场景中道路留出足够空间。
5.  道具合并: 非交互式小道具（如杯子、书本、台灯）不能独立生成资产。必须将其作为文本描述合并到宿主物体（如桌子、柜子）的 `description` 中（例如：'A table with books' 而不是分开生成 table 和 book）。

6.  * **`base_size` (物理底座)**: 物体在地面上的物理占地面积。
    * **`visual_size` (视觉精灵图)**: 完整的精灵图尺寸, **必须包含物体本身的高度**。
    * `visual_size` 的 Y 轴**几乎总是**大于 `base_size` 的 Y 轴。
    * 一个标准NPC大小为 `visual_size: [2, 3]`, 参考这个体积设计其他组件。

7.  比例参考:
    * **地板**: base=[1,1], visual=[2,2] (强制)。
    * **NPC**: base=[1,1], visual=[2,3]。
    * **家具**: 椅子 base=[2,2], visual=[2,2]; 桌子 base=[2,2], visual=[2,3]; 门 base=[3,1], visual=[3,4]; 吧台 base=[6,2], visual=[6,4]。
    * **原则**: 高度大于面积的物体（如门、吧台）的 `visual_size` 通常大于 `base_size` 的高度以体现2.5D透视。

8.  【墙壁规则】
    * **定义**: 只需定义一个墙壁资产 (如 `wall_red_brick`)，程序会自动处理顶面和侧面。
    * **描述**: 必须包含 **颜色** 和 **材质** 关键词。
    * **可用材质库**: brick, plaster, noise, stripes, hedge, fence, glass, metal, rock, books
    * **可用颜色库**: red, white, blue, grey, green, yellow, brown, black, purple, beige, cream, mint, sky_blue, pale_pink, warm_grey, light_wood, terracotta, sage, lavender, grass_green, hedge_green, water_blue, dirt_brown, asphalt_grey, sand_yellow, snow_white, rock_grey, metal_grey, wood_brown, glass_blue.

9.  【地板规则】
    * **尺寸**: `type` 必须是 "tile", `visual_size` **必须强制**是 `[2, 2]`。
    * **描述**: 必须包含 **颜色** 和 **材质** 关键词。
    * **可用材质库**:
        - 室内: wood, diamond, marble, checkerboard, mosaic, tiles, carpet, herringbone
        - 室外/道路: concrete, gravel, asphalt, cobble
        - 自然地形: grass, water, dirt, sand, snow

10.  * **拒绝空旷**: 场景**必须**感觉紧凑且设计合理。**绝对不要**留下大片无意义的空地。
    * **创建区域 (Zoning)**: 使用墙壁或隔断 (Partition) 将大空间分割成更小的、有特定功能的区域（例如：吧台区、散座区、包间、后厨、洗手间）。
    * **填充空间**: 在合适的地方（如墙边、角落）放置装饰性物体（如盆栽 `potted_plant`、书架 `bookshelf`、地毯 `rug`）来填充空间，增加“精致感”。

11. **2.5D 布局约束 (Stardew Valley View)**
    这是一个 2.5D 俯视视角。玩家只能看到“水平”墙壁（例如 `area: [0, 0, 40, 1]`）的**正面**。
    玩家**看不到**“垂直”墙壁（例如 `area: [0, 1, 1, 30]`）的正面。
    因此，**绝对不要**将 `type: "object"` 的资产（特别是 'window', 'poster', 'painting' 等装饰物）放置在“垂直”（左侧或右侧）的墙壁区域上。这些物体**只能**被放置在“水平”的墙壁上。

12. **侧面墙壁通道 (Side Wall Openings)**
    * 由于 2.5D 视角限制，侧面（垂直）墙壁无法展示门的正面。
    * 因此，**不需要**为侧面墙壁生成单独的 'Door' 资产。
    * 若需在侧墙设置入口，只需在 `wall_layer` 的 `fill_rect` 布局中**留出空隙 (Gap)** 即可，让地面自然延伸过去。
"""


USER_PROMPT_TEMPLATE = """
    你是一个专业的2D游戏场景设计师。请根据以下用户请求，设计一个结构化的游戏场景。

    ---
    **用户请求**: "{user_request}"
    ---

    请严格按照以下 **JSON Schema** 和 **范例 (Example)** 来构建你的输出。

    ### 【JSON Schema 规则说明】

    1. **metadata (元数据)**:
        - `scene_name`: 场景名称 (String)。
        - `grid_size`: 场景大小 [宽, 高]。
        - `description`: 场景整体风格描述 (English Only)。
        - `style_prompt`: 用于美术生成的风格提示词。

    2. **assets (资产库)**: 
        - `key`: 资产唯一ID (String)。
        - `type`: 必须是 "tile", "object", "npc", "agent" 之一。
        - `description`: 美术生成提示词 (English Only)。
            - **严禁**使用动作动词 (如 "walking", "talking", "wiping")，仅描述静态外观。
            - 墙/地描述必须含 "wall" 或 "floor"。
            - NPC/Agent 描述必须含类别词 ("man", "woman", "boy", "girl", "male", "female")。
            - *正确示范*: "A male barista wearing a cream apron"
            - *错误示范*: "A male barista wiping a cup"
        - `base_size`: 物理碰撞体积 [宽, 高] (单位: 瓦片)。
            - 墙壁装饰厚度通常为 1。
            - 可阻挡物体的厚度至少为 2。
        - `visual_size`: 视觉贴图尺寸 [宽, 高]。
            - **高度规则**: 对于有高度的物体 (如书架, 墙壁, 站立的人,`visual_size` 的高度(y) 必须 **大于** `base_size` 的高度。
            - 扁平物体 (如地毯) 两者尺寸相同。

    3. **layout (布局)**:
        - **仅限4个图层**: `floor_layer`, `wall_layer`, `object_layer`, `npc_layer`。
        - **NPC/Agent 位置**: 必须放置在 `npc_layer`。
        - `position`: [x, y] 表示资产的**底边中点**坐标 (Bottom-Center)，而非左上角或几何中心。
        - `command`: "fill_rect" 用于大面积铺设 (仅限 floor/wall)。

    4. **properties (游戏属性)**:
        - 必须为 `assets` 中的每个 key 定义属性。
        - `physics`: "passable" (可通过) 或 "solid" (实心/阻挡)。
        - `navigation`: "walkable", "obstacle", "walkable_door"。
        - `is_agent`: 使用 JSON 布尔值 `true` 或 `false` (不要用 Python 的 True/False)。
        - `soul_file`: 关联的配置文件名 (如 "bob.json")。

    ---
    ### 【完整范例 (Example)】
    请完全模仿以下 JSON 的结构、字段命名和逻辑关系进行输出：
    ```json
    {example_json}
    ```
    """



REPAIR_SYSTEM_PROMPT = SYSTEM_PROMPT


REPAIR_USER_PROMPT_TEMPLATE = """
    你之前生成的场景 JSON 方案存在一些错误。
    请根据以下“错误报告”，对“原始 JSON”进行修改，并输出一个**完整且已修复**的 JSON 对象。

    【【【 绝对规则 】】】:
    1.  你的输出**必须**是一个结构完整的 JSON 对象。
    2.  **绝对不要**在 JSON 对象前后添加任何额外的文字、解释或 Markdown 代码块（例如 ```json ... ```）。
    3.  确保修复错误的同时，不要引入新的错误。
    4.  **最小化修改原则**:
    * 你的首要任务是**精确修复**`错误报告`中提到的所有问题。
    * 对于原始 JSON 中**未被报告**有错误的部分，**必须尽最大努力保留其原样**。
    * **绝对不要**因为你个人的“审美”或“偏好”而去修改一个功能上正确的、且未被报告有误的条目。

    ---
    **原始 JSON**:
    ```json
    {original_json_str}
    ```
    ---
    **错误报告 (请修复以下所有问题)**:
    {error_report}
    ---
    请仔细思考然后输出已修复的、完整的 JSON 对象：
    """



def _call_llm_for_scene_plan(prompt: str) -> dict | None: 
    """ Internal function, responsible for calling the LLM API and processing the response. """ 
    print("[Manager Agent] Connecting to LLM API to generate scene...")
    full_prompt = USER_PROMPT_TEMPLATE.format(user_request=prompt)

    try:
        response = client.chat.completions.create(
            # 【【【 修改：使用 DESIGN_MODEL_NAME 】】】
            model=DESIGN_MODEL_NAME, 
            messages=[
                # {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        print("[Manager Agent] LLM response received, parsing JSON...")
        
        return json.loads(response_content)

    except Exception as e:
        print(f"[Manager Agent] LLM API call or JSON parsing failed: {e}")
        return None

def _call_llm_for_repair(plan_str: str, report: str) -> dict | None: 
    """ Internal function, calls LLM with the repair prompt. """ 
    print("[Manager Agent] Connecting to LLM API to repair scene...") 
    full_prompt = REPAIR_USER_PROMPT_TEMPLATE.format( original_json_str=plan_str, error_report=report )

    try:
        response = client.chat.completions.create(
            model=DESIGN_MODEL_NAME,
            messages=[
                # {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        print("[Manager Agent] LLM repair response received, parsing JSON...")
        
        return json.loads(response_content)

    except Exception as e:
        print(f"[Manager Agent] LLM API repair call or JSON parsing failed: {e}")
        return None



def get_scene_plan(prompt: str, use_llm: bool = True) -> dict:
    """
    Manager Agent 负责生成场景 JSON。
    它会尝试调用 LLM，如果失败，则返回一个备用的硬编码场景。
    
    :param prompt: 用户的场景描述。
    :param use_llm: 布尔值开关。True (默认) 则尝试 LLM, False 则立即使用备用计划。
    """
    print(f"[Manager Agent] 收到任务: '{prompt}'。")

    if use_llm:
        print("[Manager Agent] 模式: 尝试使用 LLM 生成。")
        llm_plan = _call_llm_for_scene_plan(prompt)

        if llm_plan:
            print("[Manager Agent] LLM 统一规划生成完毕。")
            return llm_plan
        else:
            print("[Manager Agent] LLM 生成失败，将使用备用硬编码计划。")
            return get_fallback_plan()
    else:
        print("[Manager Agent] 模式: 手动选择使用备用硬编码计划 (调试)。")
        return get_fallback_plan()


def repair_scene_plan(base_plan: dict, report: str, use_llm: bool = True) -> dict: 
    """ 
    Manager Agent 负责根据“错误报告”修复现有的场景 JSON。
    :param base_plan: 上一版（有错误）的场景 JSON (dict)
    :param report: Validator (代码QA) 或 Critic (VLM QA) 生成的错误报告 (str)
    :param use_llm: 布尔值开关。
    :return: 修复后的场景 JSON (dict)
    """
    print(f"[Manager Agent] 收到修复任务。")
    print(f"[Manager Agent] 错误报告: {report}")

    if not use_llm:
        print("[Manager Agent] 模式: LLM 被禁用，无法修复。返回原始计划。")
        return base_plan

    try:
        # 将 dict 序列化为字符串，以便送入 LLM
        plan_str = json.dumps(base_plan, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Manager Agent] 无法序列化 base_plan: {e}。返回原始计划。")
        return base_plan

    # 尝试从 LLM 获取修复后的规划
    llm_repaired_plan = _call_llm_for_repair(plan_str, report)

    if llm_repaired_plan:
        print("[Manager Agent] LLM 修复规划生成完毕。")
        return llm_repaired_plan
    else:
        # 如果 LLM 修复失败，返回原始的（未修复的）计划
        print("[Manager Agent] LLM 修复失败，将返回上一版（未修复）的计划。")
        return base_plan


def get_fallback_plan() -> dict: 
    """ 
    【【【 已升级：V4 精致备用计划 】】】
    返回一个备用的硬编码场景计划 (直接使用定义的范例)。
    """ 
    return EXAMPLE_SCENE_JSON