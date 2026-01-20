# 文件名: enricher_agent.py
import sys
import json
from config import ENRICHER_API_CONFIG
from api_client_utils import create_api_client

# --- 1. 从 config.py 初始化 API 客户端 ---
# (此部分无变化)
try:
    client = create_api_client(ENRICHER_API_CONFIG, agent_name="Enricher Agent")
    ENRICHER_MODEL_NAME = ENRICHER_API_CONFIG.get("model")
    if not ENRICHER_MODEL_NAME:
        raise ValueError("'model' is not specified in ENRICHER_API_CONFIG in config.py")
    
    print(f"[Enricher Agent] Using model/deployment: {ENRICHER_MODEL_NAME}")
    
except Exception as e:
    print(f"!!! Error loading Enricher Agent config: {e}", file=sys.stderr)
    sys.exit(1)


ENRICHER_SYSTEM_PROMPT = """
你是一个专业的“游戏关卡设计师”。你的任务是把用户充满“氛围感”的模糊描述，**转译**成一个**“物体导向”(Object-Oriented)** 的空间蓝图。

【你的核心规则】：
1.  **【重点】简化/删除氛围：** **必须**删除或极大简化无法被渲染的纯氛围描写。
    * (错误示范): "混着烘焙咖啡豆的焦香漫在空气里。"
    * (正确示范): (直接删除，或转译为 "吧台上有一个咖啡机")。
2.  **【重点】增加物体和分区：** **必须**合乎逻辑地增加场景的复杂性。
    * 如果描述中没有，请**主动添加**功能区（如“吧台区”、“散座区”）。
    * 主动添加装饰性物体（如“窗户”、“挂画”、“盆栽”、“地毯”）。
3.  **【重点】建立空间关系：** **必须**使用清晰的语言描述布局。
    * 使用“入口在南侧”、“一进门是XX”、“XX的左手边是YY”、“XX的尽头是ZZ”、“沿着*顶部*墙壁有AA”这样的短语。
4.  **【2.5D视角约束】：** 这是一个 2.5D 俯视视角。
    * 所有“窗户”、“挂画”等**只能**被放置在“顶部/后方”的墙壁上。
    * **绝对不要**在“左侧”或“右侧”的墙壁上添加装饰。
5.  **【输出格式】：** 你的输出**只能**是扩充和转译后的文本描述，不要有任何额外的寒暄。
"""

ENRICHER_USER_PROMPT_TEMPLATE = """
请将以下【用户场景描述】转译为一个“物体导向”的【空间蓝图】。

---
**【【【 范例 1 】】】**

【用户场景描述】：
"一个黑暗风格的古堡，其中有几个地狱犬在游荡"

【空间蓝图】：
"一个黑暗风格的古堡，入口在南侧。一进入大门，是一个长长的石制走廊，地面铺着红地毯。顶部（后方）的墙上挂着几面旗帜和火把。有两只地狱犬在走廊巡逻。走廊的左侧是一扇橡木门，通向图书馆，里面有书架和一张桌子。走廊的右侧是一个拱门，通向一个王座大厅，大厅尽头（顶部）是一个破碎的王座。"

---
**【【【 范例 2 】】】**

【用户场景描述】：
"午后三点的阳光斜斜切进 “青屿咖啡馆”，木格窗把光线筛成细碎的金斑，落在深棕色实木吧台上。吧台后，穿米白围裙的咖啡师正用布擦着骨瓷杯，蒸汽从意式咖啡机里缓缓冒出来，混着烘焙咖啡豆的焦香漫在空气里。靠窗的四套桌椅各坐着人，穿浅蓝毛衣的女生对着笔记本敲字，手边的拿铁拉花还没散；角落的老夫妻分食一块柠檬挞。最里侧的小池塘养着几尾金鱼，水面飘着片睡莲叶子。风铃在门口轻轻晃，每阵风吹过，都裹着暖香在店里转一圈。"

【空间蓝图】：
"一个舒适的咖啡馆, 入口在南侧, 门口挂着一个风铃。主要区域是深棕色木地板。顶部(后方)的墙壁是米白色的, 并开有一扇木格窗。窗户下方是一个L形的深棕色实木吧台, 吧台上有一台意式咖啡机。吧台后站着一位穿米白围裙的咖啡师。靠窗的区域是散座区，有四套桌椅。一个穿浅蓝毛衣的女生和一对老夫妻坐在那里。在场景的最里侧（背部），有一个装饰性的小池塘，里面有金鱼和睡莲。场景的右侧有几个独立的空隔间，用隔断墙分开，里面有桌椅。"

---
**【【【 你的任务 (Your Task) 】】】**

【用户场景描述】：
"{user_request}"

【空间蓝图】：
"""


# --- 3. Agent 主函数 ---
# (此部分无变化)
def enrich_prompt(prompt: str, use_llm: bool = True) -> str:
    """
    Enricher Agent 负责将简单的用户提示扩充为丰富的场景描述。
    
    :param prompt: 用户的原始简单提示。
    :param use_llm: 布尔值开关。
    :return: 扩充后的丰富提示（如果失败，则返回原始提示）。
    """
    if not use_llm:
        print("[Enricher Agent] Mode: Skipping enrichment (Debug). Returning original prompt.")
        return prompt

    print(f"[Enricher Agent] Connecting to LLM API to enrich prompt...")
    
    full_prompt = ENRICHER_USER_PROMPT_TEMPLATE.format(user_request=prompt)
    
    try:
        response = client.chat.completions.create(
            model=ENRICHER_MODEL_NAME,
            messages=[
                {"role": "system", "content": ENRICHER_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            temperature=0.7 # 提高一点创造力
        )
        
        enriched_prompt = response.choices[0].message.content
        
        # 清理 LLM 可能添加的额外引号或标签
        enriched_prompt = enriched_prompt.strip().strip('"')
        if "【扩充后的描述】：" in enriched_prompt:
            enriched_prompt = enriched_prompt.split("【扩充后的描述】：")[-1].strip()
        
        print("[Enricher Agent] Prompt enrichment successful.")
        return enriched_prompt

    except Exception as e:
        print(f"[Enricher Agent] LLM API call failed: {e}")
        print("[Enricher Agent] Warning: Returning original prompt as fallback.")
        return prompt