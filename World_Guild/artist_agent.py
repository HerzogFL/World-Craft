import time
import os
import json
import base64 
import re 
import random
import copy
import sys 
from asset_retriever import find_closest_reference_image
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import cv2
    import numpy as np
except ImportError:
    print("!!! 错误: 缺少 'opencv-python-headless' 或 'numpy' !!!")
    print("请运行: pip install opencv-python-headless numpy")
    exit(1)

from config import ARTIST_API_CONFIG
from api_client_utils import create_api_client

try:
    client = create_api_client(ARTIST_API_CONFIG, agent_name="Artist Agent")
    # 从配置中获取模型名称
    ARTIST_MODEL_NAME = ARTIST_API_CONFIG.get("model")
    if not ARTIST_MODEL_NAME:
        raise ValueError("'model' is not specified in ARTIST_API_CONFIG in config.py")
    print(f"[Artist Agent] Initialized API client, using model: {ARTIST_MODEL_NAME}")
except Exception as e:
    print(f"!!! Error loading Artist Agent config: {e}", file=sys.stderr)
    sys.exit(1)

CHARACTER_BASE_SHEET_DIR = "character_base_sheets"

CHARACTER_SHEET_MAP = {
    "female_base.png": {
        "woman", "female", "girl", "beauty", "lady", "waitress",
        "nurse", "actress", "secretary", "hostess",
        "gal", "lass", "miss"
    },
    "male_base.png": {
        "man", "male", "boy", "guy", "waiter",
        "doctor", "actor", "engineer", "policeman",
        "chap", "lad", "bloke"
    },
    "old_woman_base.png": {
        "old woman", "grandmother", "elderly woman",
        "granny", "grandma", "senior woman", "mature woman"
    },
    "old_man_base.png": {
        "old man", "grandfather", "elderly man",
        "grandpa", "granddad", "senior man", "mature man"
    },
    "child_base.png": {
        "child", "kid", "little one", "toddler", "youngster","student"  
    },
}
DEFAULT_CHARACTER_SHEET = "male_base.png"



TILE_SIZE = 16 # 1 个单位格子 = 16 像素

COLOR_PRESETS_BGR = {
    "red": [140, 150, 190],
    "white": [210, 220, 225],
    "blue": [220, 180, 170],
    "grey": [200, 200, 200],
    "green": [150, 190, 150],
    "yellow": [150, 210, 220],
    "brown": [116, 144, 192],
    "black": [50, 50, 50],
    "purple": [180, 150, 170],
    "beige": [215, 228, 235],
    "cream": [240, 250, 255],
    "mint": [220, 230, 210],
    "sky_blue": [235, 220, 200],
    "pale_pink": [225, 215, 230],
    "warm_grey": [210, 215, 220],
    "light_wood": [180, 200, 220],
    "terracotta": [190, 200, 220],
    "sage": [200, 210, 190],
    "lavender": [230, 210, 220],
    "grass_green": [120, 200, 120], 
    "hedge_green": [60, 100, 60],    
    "water_blue": [230, 200, 100],   
    "dirt_brown": [116, 144, 192],  
    "asphalt_grey": [80, 80, 80],   
    "sand_yellow": [180, 220, 240], 
    "snow_white": [250, 250, 240],  
    "rock_grey": [120, 120, 120],   
    "metal_grey": [180, 180, 180], 
    "wood_brown": [50, 100, 139],  
    "glass_blue": [240, 230, 200]   
}

WALL_TEXTURE_PRESETS = ["brick", "plaster", "noise", "stripes", "hedge", "fence", "glass", "metal", "rock", "books"]

FLOOR_TEXTURE_PRESETS = ["wood", "diamond", "marble", "checkerboard", "mosaic", "concrete", "gravel", "tiles", "carpet", "herringbone", "grass", "water", "dirt", "asphalt", "sand", "snow", "cobble"]


BLACK_LINE_COLOR = (0, 0, 0)
FLOATING_LINE_COLOR_LIGHT = np.array([220, 220, 220])
# ---


def parse_description(description: str) -> dict:
    """
    解析描述，优先匹配“语义材质”，然后匹配“颜色”。
    """
    desc_lower = description.lower()
    params = {
        "base_color_bgr": COLOR_PRESETS_BGR["grey"], 
        "wall_texture": None,
        "floor_texture": None
    }

    # --- A. 自然/户外 ---
    if "grass" in desc_lower or "lawn" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["grass_green"]
        params["floor_texture"] = "grass"
        return params 
    if "hedge" in desc_lower or "bush" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["hedge_green"]
        params["wall_texture"] = "hedge"
        return params
    if "water" in desc_lower or "pond" in desc_lower or "pool" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["water_blue"]
        params["floor_texture"] = "water"
        return params
    if "dirt" in desc_lower or "soil" in desc_lower or "earth" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["dirt_brown"]
        params["floor_texture"] = "dirt"
        return params
    if "sand" in desc_lower or "beach" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["sand_yellow"]
        params["floor_texture"] = "sand"
        return params
    if "snow" in desc_lower or "ice" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["snow_white"]
        params["floor_texture"] = "snow"
        return params

    # --- B. 建筑/结构 ---
    if "fence" in desc_lower or "picket" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["wood_brown"]
        params["wall_texture"] = "fence"
        return params
    if "glass" in desc_lower or "window wall" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["glass_blue"]
        params["wall_texture"] = "glass"
        return params
    if "metal" in desc_lower or "steel" in desc_lower or "iron" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["metal_grey"]
        params["wall_texture"] = "metal"
        return params
    if "rock" in desc_lower or "stone" in desc_lower or "cave" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["rock_grey"]
        params["wall_texture"] = "rock"

        if "floor" in desc_lower:
            params["floor_texture"] = "cobble"
        return params
    if "asphalt" in desc_lower or "road" in desc_lower or "street" in desc_lower:
        params["base_color_bgr"] = COLOR_PRESETS_BGR["asphalt_grey"]
        params["floor_texture"] = "asphalt"
        return params

    sorted_color_keys = sorted(COLOR_PRESETS_BGR.keys(), key=len, reverse=True)
    for color_name in sorted_color_keys:
        pattern = r"\b" + re.escape(color_name) + r"\b"
        if re.search(pattern, desc_lower):
            params["base_color_bgr"] = COLOR_PRESETS_BGR[color_name]
            break
            
    for texture in WALL_TEXTURE_PRESETS:
        if texture in desc_lower:
            params["wall_texture"] = texture
            break
    for texture in FLOOR_TEXTURE_PRESETS:
        if texture in desc_lower:
            params["floor_texture"] = texture
            break
    return params


def add_brick_texture(img_bgr, brick_height=12, mortar_offset=8):
    height, width, _ = img_bgr.shape
    mortar_color_np = (np.array(img_bgr[0,0]) * 0.85).astype(np.uint8)
    mortar_color = tuple(mortar_color_np.tolist())
    
    img_with_texture = img_bgr.copy()
    
    for y in range(0, height, brick_height):
        cv2.line(img_with_texture, (0, y), (width - 1, y), mortar_color, 1, lineType=cv2.LINE_4)
        stagger_offset = (y // brick_height) % 2 * mortar_offset
        for x in range(0, width, brick_height * 2):
            start_x = (x + stagger_offset) % width
            cv2.line(img_with_texture, (start_x, y), (start_x, y + brick_height), mortar_color, 1, lineType=cv2.LINE_4)
    return img_with_texture

def add_noise_texture(img_bgr, noise_level=20):
    noise = np.random.randint(-noise_level, noise_level,
                            (img_bgr.shape[0], img_bgr.shape[1], 3),
                            dtype=np.int16)
    img_bgr_int = img_bgr.astype(np.int16)
    textured_img = np.clip(img_bgr_int + noise, 0, 255)
    return textured_img.astype(np.uint8)

def add_stripes_texture(img_bgr, stripe_width=12, stripe_color_offset=-25):
    height, width, _ = img_bgr.shape
    stripe_color_np = (np.array(img_bgr[0,0]) + stripe_color_offset).clip(0, 255).astype(np.uint8)
    stripe_color = tuple(stripe_color_np.tolist())
    img_with_texture = img_bgr.copy()
    for x in range(0, width, stripe_width * 2):
        cv2.rectangle(img_with_texture, (x, 0), (x + stripe_width, height - 1), stripe_color, -1)
    return img_with_texture

def add_grass_texture(img_bgr):
    """草地：噪点 + 随机竖线(草叶)"""
    # 1. 基础噪点
    base = add_noise_texture(img_bgr, 15)
    h, w = base.shape[:2]
    
    # 2. 随机草叶 (深绿色)
    blade_color = get_darker_color(base[0,0], 0.8)
    blade_color = tuple(blade_color.tolist())
    
    for _ in range(int(h * w * 0.1)): # 密度
        x = np.random.randint(0, w)
        y = np.random.randint(0, h-2)
        # 画一个小竖线
        base[y, x] = blade_color
        base[y+1, x] = blade_color
    return base

def add_hedge_texture(img_bgr):
    """树篱：强噪点 + 块状叶丛"""
    # 1. 深色底噪
    base = add_noise_texture(img_bgr, 30)
    h, w = base.shape[:2]
    
    # 2. 随机画一些亮色和暗色的小圆圈，模拟叶丛
    color_main = np.array(img_bgr[0,0])
    color_light = (color_main * 1.2).clip(0,255).astype(np.uint8).tolist()
    color_dark = (color_main * 0.7).clip(0,255).astype(np.uint8).tolist()
    
    for _ in range(int(h * w * 0.05)):
        x = np.random.randint(0, w)
        y = np.random.randint(0, h)
        radius = np.random.randint(1, 3)
        color = color_light if np.random.rand() > 0.5 else color_dark
        cv2.circle(base, (x, y), radius, color, -1)
    return base

def add_water_texture(img_bgr):
    """水面：水平波纹"""
    h, w = img_bgr.shape[:2]
    base = img_bgr.copy()
    
    # 波纹颜色 (亮蓝色)
    ripple_color = (np.array(img_bgr[0,0]) * 1.3).clip(0,255).astype(np.uint8).tolist()
    
    for y in range(0, h, 4): # 每隔4像素一行
        offset = (y // 4) % 2 * 4 # 交错
        for x in range(0, w, 8):
            start_x = (x + offset) % w
            end_x = min(start_x + 4, w)
            cv2.line(base, (start_x, y), (end_x, y), ripple_color, 1)
            
    return add_noise_texture(base, 5)

def add_dirt_texture(img_bgr):
    """土地：高对比度粗糙噪点"""
    return add_noise_texture(img_bgr, 40) 

def add_asphalt_texture(img_bgr):
    """柏油路：均匀的中等噪点"""
    return add_noise_texture(img_bgr, 25)

# --- 新增纹理函数 ---

def add_fence_texture(img_bgr):
    """木栅栏：垂直木条 + 横向横档"""
    base = img_bgr.copy()
    h, w = base.shape[:2]
    line_color = get_darker_color(base[0,0], 0.6)
    line_color = tuple(line_color.tolist())
    
    # 垂直木条 (每隔8像素)
    for x in range(4, w, 8):
        cv2.line(base, (x, 0), (x, h), line_color, 1)
    
    # 横向横档 (两条)
    cv2.line(base, (0, int(h*0.3)), (w, int(h*0.3)), line_color, 1)
    cv2.line(base, (0, int(h*0.7)), (w, int(h*0.7)), line_color, 1)
    
    return add_noise_texture(base, 10)

def add_glass_texture(img_bgr):
    """玻璃：亮色斜纹"""
    base = img_bgr.copy()
    h, w = base.shape[:2]
    highlight_color = (np.array(base[0,0]) * 1.2).clip(0,255).astype(np.uint8).tolist()
    
    # 画几条粗细不一的斜线
    for i in range(-h, w, 20):
        thickness = 1 if i % 40 != 0 else 2
        cv2.line(base, (i, 0), (i+h, h), highlight_color, thickness)
    return base

def add_rock_texture(img_bgr):
    """岩石：大块不规则噪点"""
    base = add_noise_texture(img_bgr, 40)
    h, w = base.shape[:2]
    # 随机画一些裂缝
    crack_color = get_darker_color(base[0,0], 0.5).tolist()
    for _ in range(5):
        x1, y1 = np.random.randint(0, w), np.random.randint(0, h)
        x2, y2 = x1 + np.random.randint(-5, 5), y1 + np.random.randint(-5, 5)
        cv2.line(base, (x1, y1), (x2, y2), crack_color, 1)
    return base

def add_sand_texture(img_bgr):
    """沙地：微小噪点 + 波浪痕迹"""
    base = add_noise_texture(img_bgr, 15)
    # 简单的水平波浪感
    ripple_color = get_darker_color(base[0,0], 0.9).tolist()
    h, w = base.shape[:2]
    for y in range(0, h, 5):
        for x in range(0, w, 10):
            cv2.line(base, (x, y), (x+5, y+1), ripple_color, 1)
    return base

def add_cobblestone_texture(img_bgr):
    """鹅卵石：随机圆圈"""
    base = img_bgr.copy()
    h, w = base.shape[:2]
    stone_color = get_darker_color(base[0,0], 0.8).tolist()
    grout_color = get_darker_color(base[0,0], 0.6).tolist()
    
    base[:] = grout_color # 先填缝隙色
    
    # 铺满圆石头
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            offset_x = np.random.randint(-2, 2)
            offset_y = np.random.randint(-2, 2)
            center = (x + 4 + offset_x, y + 4 + offset_y)
            radius = np.random.randint(3, 5)
            cv2.circle(base, center, radius, stone_color, -1)
    return add_noise_texture(base, 20)

def add_metal_texture(img_bgr):
    """金属：平滑 + 铆钉"""
    base = add_noise_texture(img_bgr, 5)
    h, w = base.shape[:2]
    rivet_color = get_darker_color(base[0,0], 0.5).tolist()
    # 四角铆钉
    cv2.circle(base, (2, 2), 1, rivet_color, -1)
    cv2.circle(base, (w-3, 2), 1, rivet_color, -1)
    cv2.circle(base, (2, h-3), 1, rivet_color, -1)
    cv2.circle(base, (w-3, h-3), 1, rivet_color, -1)
    return base

def get_darker_color(color_bgr_np, factor=0.85):
    """辅助函数：获取一个更暗的颜色"""
    return (color_bgr_np * factor).clip(0, 255).astype(np.uint8)

def add_wood_plank_texture(img_bgr, plank_width=8):
    """木板纹路：绘制垂直线条"""
    height, width, _ = img_bgr.shape
    line_color = tuple(get_darker_color(img_bgr[0,0], 0.8).tolist())
    
    img_with_texture = img_bgr.copy()
    for x in range(0, width, plank_width):
        cv2.line(img_with_texture, (x, 0), (x, height - 1), line_color, 1, lineType=cv2.LINE_4)
    return add_noise_texture(img_with_texture, 5) 

def add_checkerboard_texture(img_bgr, check_size=16):
    """方格纹路 (棋盘格)"""
    height, width, _ = img_bgr.shape
    dark_color = tuple(get_darker_color(img_bgr[0,0], 0.7).tolist())
    
    img_with_texture = img_bgr.copy()
    for y in range(0, height, check_size):
        for x in range(0, width, check_size):
            if (x // check_size) % 2 == (y // check_size) % 2:
                cv2.rectangle(img_with_texture, (x, y), (x + check_size, y + check_size), dark_color, -1)
    return img_with_texture

def add_tiles_texture(img_bgr, tile_size=16):
    """方砖纹路 (带灰缝)"""
    height, width, _ = img_bgr.shape
    grout_color = tuple(get_darker_color(img_bgr[0,0], 0.75).tolist())
    
    img_with_texture = img_bgr.copy()
    for x in range(0, width, tile_size):

        cv2.line(img_with_texture, (x, 0), (x, height - 1), grout_color, 1, lineType=cv2.LINE_4)
    for y in range(0, height, tile_size):
        cv2.line(img_with_texture, (0, y), (width - 1, y), grout_color, 1, lineType=cv2.LINE_4)
    return img_with_texture

def add_concrete_texture(img_bgr):
    """水泥纹路 (复用 noise)"""
    return add_noise_texture(img_bgr, noise_level=15)

def add_gravel_texture(img_bgr):
    """沙石纹路 (复用 noise, 更高对比度)"""
    return add_noise_texture(img_bgr, noise_level=30)

def add_carpet_texture(img_bgr):
    """地毯纹路 (轻微 noise)"""
    return add_noise_texture(img_bgr, noise_level=5)

# --- 占位符 (未来实现) ---
def add_marble_texture(img_bgr):
    """
    大理石纹路 (像素化)
    通过缩放低频噪点来模拟大块的、不规则的“云纹”
    """
    height, width, _ = img_bgr.shape
    
    small_noise = np.random.randint(0, 255, (4, 4), dtype=np.uint8)
    
    large_noise_map = cv2.resize(small_noise, (width, height), interpolation=cv2.INTER_NEAREST)
    
    color1 = img_bgr[0,0].astype(np.int16)
    color2 = get_darker_color(img_bgr[0,0], 0.8).astype(np.int16)
    
    img_bgr_int = img_bgr.astype(np.int16)
    
    for y in range(height):
        for x in range(width):
            mix_factor = large_noise_map[y, x] / 255.0
            # 线性插值
            new_color = (color1 * (1.0 - mix_factor)) + (color2 * mix_factor)
            img_bgr_int[y, x] = new_color
            
    return np.clip(img_bgr_int, 0, 255).astype(np.uint8)

def add_diamond_texture(img_bgr, step=16):
    """
    菱形纹路 (像素化)
    绘制 45 度角的斜线网格
    """
    height, width, _ = img_bgr.shape
    grout_color = tuple(get_darker_color(img_bgr[0,0], 0.75).tolist())
    
    img_with_texture = img_bgr.copy()
    
    for i in range(-height, width, step):
        cv2.line(img_with_texture, 
                (i, 0), (i + height, height),  # pt1, pt2
                grout_color, 1, 
                lineType=cv2.LINE_4)

    # 绘制 `y = -x + k` 形式的斜线 (\)
    for i in range(0, width + height, step):
        cv2.line(img_with_texture, 
                (i, 0), (i - height, height),  # pt1, pt2
                grout_color, 1, 
                lineType=cv2.LINE_4)

    return img_with_texture
def add_mosaic_texture(img_bgr, tile_size=8):
    """
    马赛克纹路 (像素化)
    绘制小方砖，并给每个小砖块一个随机的颜色偏移
    """
    height, width, _ = img_bgr.shape
    grout_color = tuple(get_darker_color(img_bgr[0,0], 0.75).tolist())
    
    # 1. 先绘制一个 8x8 的基础网格 (使用像素化线条)
    img_with_texture = img_bgr.copy()
    for x in range(0, width, tile_size):
        cv2.line(img_with_texture, (x, 0), (x, height - 1), grout_color, 1, lineType=cv2.LINE_4)
    for y in range(0, height, tile_size):
        cv2.line(img_with_texture, (0, y), (width - 1, y), grout_color, 1, lineType=cv2.LINE_4)

    # 2. 遍历每个小砖块 (内部) 并给予随机色偏
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            # 获取砖块内部区域 (避开灰缝)
            tile_region = img_with_texture[y+1 : y+tile_size-1, x+1 : x+tile_size-1]
            
            if tile_region.size > 0:
                # 随机一个轻微的 BGR 偏移量
                random_color_offset = np.random.randint(-12, 12, 3)
                
                # 计算新颜色 (注意要先转 int16 防止溢出)
                new_color_int = tile_region[0,0].astype(np.int16) + random_color_offset
                new_color = np.clip(new_color_int, 0, 255).astype(np.uint8)
                
                # 填充这个小砖块
                tile_region[:] = new_color
                
    return img_with_texture

def add_herringbone_texture(img_bgr, plank_width=16, plank_height=8):
    """
    人字纹 (像素化)
    绘制交错的 \/ \/ \/ 图案
    """
    height, width, _ = img_bgr.shape
    line_color = tuple(get_darker_color(img_bgr[0,0], 0.8).tolist())
    
    img_with_texture = img_bgr.copy()

    for y in range(-plank_height, height, plank_height):
        # 每一行都交错半个木板的宽度
        stagger = (y // plank_height) % 2 * (plank_width // 2)
        
        for x in range(-plank_width, width, plank_width):
            x_staggered = x + stagger
            
            # 绘制 \ (左半边)
            pt1_L = (x_staggered, y)
            pt2_L = (x_staggered + plank_width // 2, y + plank_height)
            cv2.line(img_with_texture, pt1_L, pt2_L, line_color, 1, lineType=cv2.LINE_4)
            
            # 绘制 / (右半边)
            pt1_R = (x_staggered + plank_width // 2, y + plank_height)
            pt2_R = (x_staggered + plank_width, y)
            cv2.line(img_with_texture, pt1_R, pt2_R, line_color, 1, lineType=cv2.LINE_4)

    return add_noise_texture(img_with_texture, 5) # 增加一点木纹

def _generate_procedural_wall_tile(width_px: int, height_px: int, params: dict, is_top_down: bool, save_path: str):
    base_color_bgr = params["base_color_bgr"]
    base_color_np = np.array(base_color_bgr)
    texture_type = params.get("wall_texture")
    
    img_bgr = np.zeros((height_px, width_px, 3), dtype=np.uint8)
    img_bgr[:] = base_color_bgr
    
    if is_top_down:
        top_section_end = TILE_SIZE
        bottom_section_start = height_px - TILE_SIZE
        
        if bottom_section_start > top_section_end:
            texture_region = img_bgr[top_section_end:bottom_section_start, :]
            
            # 【【【 路由更新 】】】
            if texture_type == "hedge": texture_region = add_hedge_texture(texture_region)
            elif texture_type == "brick": texture_region = add_brick_texture(texture_region)
            elif texture_type == "noise": texture_region = add_noise_texture(texture_region)
            elif texture_type == "stripes": texture_region = add_stripes_texture(texture_region)
            elif texture_type == "fence": texture_region = add_fence_texture(texture_region)
            elif texture_type == "glass": texture_region = add_glass_texture(texture_region)
            elif texture_type == "metal": texture_region = add_metal_texture(texture_region)
            elif texture_type == "rock": texture_region = add_rock_texture(texture_region)
            else: texture_region = add_noise_texture(texture_region, 10)
            
            img_bgr[top_section_end:bottom_section_start, :] = texture_region
        
        cv2.line(img_bgr, (0, 0), (width_px - 1, 0), BLACK_LINE_COLOR, 1, lineType=cv2.LINE_4)
        top_edge_y = TILE_SIZE - 1
        cv2.line(img_bgr, (0, top_edge_y), (width_px - 1, top_edge_y), BLACK_LINE_COLOR, 1, lineType=cv2.LINE_4)
        
        skirting_y_start = height_px - TILE_SIZE
        skirting_color = tuple(FLOATING_LINE_COLOR_LIGHT.tolist())
        
        # 特殊墙壁使用深色底座
        if texture_type in ["hedge", "fence", "rock"]:
            skirting_color = tuple(get_darker_color(base_color_np, 0.5).tolist())

        cv2.line(img_bgr, (0, skirting_y_start), (width_px - 1, skirting_y_start), skirting_color, 1, lineType=cv2.LINE_4)
                
        for y_offset in range(1, TILE_SIZE):
            y_current = skirting_y_start + y_offset
            if y_current >= height_px: break
            
            if texture_type not in ["hedge", "fence", "rock"]:
                fade_factor = 1.0 - (y_offset / TILE_SIZE)
                current_color_np = (FLOATING_LINE_COLOR_LIGHT * fade_factor) + (base_color_np * (1.0 - fade_factor))
                current_color_bgr = tuple(current_color_np.astype(np.uint8).tolist())
                cv2.line(img_bgr, (0, y_current), (width_px - 1, y_current), current_color_bgr, 1, lineType=cv2.LINE_4)
            else:
                cv2.line(img_bgr, (0, y_current), (width_px - 1, y_current), skirting_color, 1, lineType=cv2.LINE_4)

    else:
        cv2.line(img_bgr, (0, 0), (0, height_px - 1), BLACK_LINE_COLOR, 1, lineType=cv2.LINE_4)
        cv2.line(img_bgr, (width_px - 1, 0), (width_px - 1, height_px - 1), BLACK_LINE_COLOR, 1, lineType=cv2.LINE_4)
        
    b, g, r = cv2.split(img_bgr)
    alpha = np.full((height_px, width_px), 255, dtype=np.uint8)
    final_img_bgra = cv2.merge([b, g, r, alpha])
    cv2.imwrite(save_path, final_img_bgra)


def _generate_procedural_floor_tile(width_px: int, height_px: int, params: dict, save_path: str):
    base_color_bgr = params["base_color_bgr"]
    texture_type = params.get("floor_texture")
    
    img_bgr = np.zeros((height_px, width_px, 3), dtype=np.uint8)
    img_bgr[:] = base_color_bgr
    
    # 【【【 完整路由 (包括原有和新增) 】】】
    if texture_type == "wood": img_bgr = add_wood_plank_texture(img_bgr)
    elif texture_type == "checkerboard": img_bgr = add_checkerboard_texture(img_bgr)
    elif texture_type == "tiles": img_bgr = add_tiles_texture(img_bgr)
    elif texture_type == "concrete": img_bgr = add_concrete_texture(img_bgr)
    elif texture_type == "gravel": img_bgr = add_gravel_texture(img_bgr)
    elif texture_type == "carpet": img_bgr = add_carpet_texture(img_bgr)
    elif texture_type == "marble": img_bgr = add_marble_texture(img_bgr)
    elif texture_type == "diamond": img_bgr = add_diamond_texture(img_bgr)
    elif texture_type == "mosaic": img_bgr = add_mosaic_texture(img_bgr)
    elif texture_type == "herringbone": img_bgr = add_herringbone_texture(img_bgr)
    # --- 新增 ---
    elif texture_type == "grass": img_bgr = add_grass_texture(img_bgr)
    elif texture_type == "water": img_bgr = add_water_texture(img_bgr)
    elif texture_type == "dirt": img_bgr = add_dirt_texture(img_bgr)
    elif texture_type == "asphalt": img_bgr = add_asphalt_texture(img_bgr)
    elif texture_type == "sand": img_bgr = add_sand_texture(img_bgr)
    elif texture_type == "cobble": img_bgr = add_cobblestone_texture(img_bgr)
    elif texture_type == "snow": img_bgr = add_noise_texture(img_bgr, 10) # 雪地即白底噪点
    # --- 默认 ---
    else: img_bgr = add_noise_texture(img_bgr, noise_level=10)
    
    b, g, r = cv2.split(img_bgr)
    alpha = np.full((height_px, width_px), 255, dtype=np.uint8)
    final_img_bgra = cv2.merge([b, g, r, alpha])
    cv2.imwrite(save_path, final_img_bgra)


GLOBAL_STYLE_ATTRIBUTES = (
"大块像素风格 (pixel art style),",
"纯白色背景 (pure white background),", # <-- 已修改为纯白色
"独立且完整的物体或人物，无遮挡，无阴影 (isolated object, no shadow, no occlusion),",
"正面朝向镜头, 俯视视角 (slight God's perspective top-down view),"
"只能看到正面和顶面, 绝对不能看到任何侧面。(Can only see front and top, absolutely no side view.)"
)


def generate_real_image(
    asset_id: str, 
    details: dict, 
    scene_plan: dict,
    save_dir: str, 
    tile_size: int = 16
):
    """
    (V16 - Object 专用) 
    结合 "检索参考图" + "智能缩放" 的生成逻辑。
    适用于家具、装饰等静态物体。
    """
    
    # --- 1. 准备路径 ---
    final_file_path = os.path.join(save_dir, f"{asset_id}.png")
    
    # (调试文件夹，方便你看中间结果)
    debug_dir = os.path.join(save_dir, "debug_objects")
    if not os.path.exists(debug_dir): os.makedirs(debug_dir)
    
    description = details.get("description", "an object")
    
    # --- 2. 准备尺寸参数 (用于后续的智能缩放) ---
    base_size_tiles = details.get("base_size", [1, 1])
    visual_size_tiles = details.get("visual_size", base_size_tiles)
    
    # 目标参考尺寸 (像素)
    target_w_guide = visual_size_tiles[0] * tile_size
    target_h_guide = visual_size_tiles[1] * tile_size

    # --- 3. 检索参考图 ---
    print(f"  - [Retriever] 正在为 '{asset_id}' 检索参考图...")
    reference_image_path = find_closest_reference_image(asset_id, details)
    
    # --- 4. 构建 Prompt (参考生成模式) ---
    # 这是一个通用的 Prompt，无论有没有参考图都能用
    
    system_prompt = "You are a professional pixel art game asset designer."
    
    user_prompt = (
        f"Generate a high-quality pixel art asset.\n"
        f"**Object Name**: {asset_id}\n"
        f"**Description**: {description}\n"
        f"**Style**: 16-bit pixel art, Stardew Valley style, clean lines, solid colors.\n"
        f"pixel art style; isolated object, no shadow, no occlusion; slight God's perspective top-down view; Can only see front and top, absolutely no side view."
        f"**Background**: Pure white background (important!).\n"
    )

    messages = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
    ]

    # 如果找到了参考图，注入它！
    if reference_image_path:
        print(f"  - [Retriever] 注入参考图: {os.path.basename(reference_image_path)}")
        try:
            with open(reference_image_path, "rb") as img_file:
                b64_image = base64.b64encode(img_file.read()).decode('utf-8')
            
            # 添加图像到 Prompt
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_image}"}
            })
            
            # 添加具体的参考指令
            ref_instruction = (
                "\n\n**REFERENCE IMAGE INSTRUCTION:**\n"
                "An image is provided above. Use it as a **Structural Reference**.\n"
                "1. Keep the **Perspective** and **General Shape** similar to the reference image.\n"
                "2. But apply the **Materials, Colors, and Details** described in the text.\n"
                "3. Ensure the output is a single, isolated object on a white background."
            )
            messages[1]["content"][0]["text"] += ref_instruction
            
        except Exception as e:
            print(f"  - [Warning] 参考图加载失败: {e}。将降级为纯文生图。")
    else:
        print(f"  - [Retriever] 未找到参考图。使用纯文生图模式。")


    # --- 5. 调用 API (重试逻辑) ---
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  - [AI-Gen] 正在生成 (尝试 {attempt+1}/{MAX_RETRIES})...")
            start_time = time.time()
            
            completion = client.chat.completions.create(
                model=ARTIST_MODEL_NAME,
                messages=messages
            )
            
            # 解析 Base64
            content = completion.choices[0].message.content
            m = re.search(r'data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=\r\n]+)', content)
            
            if m:
                img_bytes = base64.b64decode(m.group(2))
                print(f"  - [AI-Gen] 成功接收图像 ({time.time() - start_time:.2f}s)")
                
                # --- 6. 后处理：OpenCV 智能缩放 (恢复原本好用的逻辑) ---
                np_arr = np.frombuffer(img_bytes, np.uint8)
                img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if img_bgr is None: raise ValueError("解码失败")

                # A. 抠图 (Crop)
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                # 假设白底，反转二值化寻找物体
                _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if not contours: raise ValueError("找不到物体轮廓 (可能是白图)")
                
                largest_cnt = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_cnt)
                
                # 提取物体 (带 Alpha)
                b, g, r = cv2.split(img_bgr)
                # 创建 mask: 轮廓内部为 255 (不透明), 外部为 0 (透明)
                alpha_mask = np.zeros_like(gray)
                cv2.drawContours(alpha_mask, [largest_cnt], -1, 255, -1)
                
                img_bgra = cv2.merge([b, g, r, alpha_mask])
                cropped = img_bgra[y:y+h, x:x+w]
                
                # B. 智能缩放 (V7 Logic)
                src_h, src_w = cropped.shape[:2]
                
                # 判断逻辑：是高物体还是扁物体？
                # 如果 visual 高度 > base 高度 -> 高物体 (Tall)
                # 否则 -> 扁物体/标准物体 (Flat/Standard)
                is_tall_object = visual_size_tiles[1] > base_size_tiles[1]
                
                final_size = (0, 0)
                
                if is_tall_object:
                    # 【高物体逻辑】：固定宽度，高度随动
                    # 目的：确保物体能“坐”在瓦片上，但高度可以很高（如衣柜、路灯）
                    print(f"    > 检测为高物体 (Tall): 固定宽度 {target_w_guide}")
                    scale = target_w_guide / src_w
                    new_w = target_w_guide
                    new_h = int(src_h * scale)
                    # 最小高度保护
                    new_h = max(tile_size, new_h)
                    final_size = (new_w, new_h)
                else:
                    # 【扁物体逻辑】：固定高度，宽度随动
                    # 目的：防止地毯、池塘被压扁。通常扁物体的高度就是瓦片高度。
                    # 如果 base 和 visual 一样大 (Standard)，我们也倾向于用这个，或者用 width。
                    # 你提到：如果一样大，按照宽度。
                    if visual_size_tiles == base_size_tiles:
                        print(f"    > 检测为标准物体 (Standard): 固定宽度 {target_w_guide}")
                        scale = target_w_guide / src_w
                        new_w = target_w_guide
                        new_h = int(src_h * scale)
                        new_h = max(tile_size, new_h)
                        final_size = (new_w, new_h)
                    else:
                        print(f"    > 检测为扁物体 (Flat): 固定高度 {target_h_guide}")
                        scale = target_h_guide / src_h
                        new_h = target_h_guide
                        new_w = int(src_w * scale)
                        new_w = max(tile_size, new_w)
                        final_size = (new_w, new_h)

                # C. 执行缩放并保存
                print(f"    > 缩放: {src_w}x{src_h} -> {final_size[0]}x{final_size[1]}")
                final_img = cv2.resize(cropped, final_size, interpolation=cv2.INTER_LANCZOS4)
                
                cv2.imwrite(final_file_path, final_img)
                print(f"  - [Artist Agent] 成功保存 Object: {final_file_path}")
                break # 成功退出重试循环

            else:
                print("  - [AI-Gen] 未找到图像数据，重试...")

        except Exception as e:
            print(f"  - [Error] 生成失败: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

def _post_process_sprite_sheet(base_image_path: str, ai_generated_path: str) -> bool:
    """
    1. 强制重置为原始尺寸。
    2. [核心修复] 计算交集：只有在 (原始骨架存在) 且 (AI生成内容不是背景白) 的地方才不透明。
    """
    try:
        # --- A. 加载原始基础图像 (带 Alpha) ---
        base_img = cv2.imread(base_image_path, cv2.IMREAD_UNCHANGED)
        if base_img is None:
            return False
            
        original_h, original_w = base_img.shape[:2]
        _, _, _, original_alpha = cv2.split(base_img) # 提取骨架 Alpha

        # --- B. 加载 AI 生成的图像 ---
        ai_img = cv2.imread(ai_generated_path, cv2.IMREAD_UNCHANGED)
        if ai_img is None:
            return False

        # --- C. 修复尺寸 ---
        if ai_img.shape[0] != original_h or ai_img.shape[1] != original_w:
            ai_img = cv2.resize(ai_img, (original_w, original_h), interpolation=cv2.INTER_NEAREST)

        # --- D. 【核心修复】逻辑变更 ---
        
        if ai_img.shape[2] == 4:
            ai_bgr = cv2.cvtColor(ai_img, cv2.COLOR_BGRA2BGR)
        else:
            ai_bgr = ai_img

        lower_white = np.array([240, 240, 240])
        upper_white = np.array([255, 255, 255])
        
        # 生成“背景掩码” (白色区域为 255，实体区域为 0)
        bg_mask = cv2.inRange(ai_bgr, lower_white, upper_white)
        
        content_mask = cv2.bitwise_not(bg_mask)

        final_alpha = cv2.bitwise_and(original_alpha, content_mask)


        # 5. 合并通道
        new_b, new_g, new_r = cv2.split(ai_bgr)
        final_bgra = cv2.merge([new_b, new_g, new_r, final_alpha])

        # 6. 保存
        cv2.imwrite(ai_generated_path, final_bgra)
        print(f"  - [Post-Process] 成功: 已剔除骨架内未填充的区域。")
        return True

    except Exception as e:
        print(f"  - [Post-Process] 严重错误: {e}")
        return False


def generate_character_sprite_sheet(
    client, 
    model_name: str,
    asset_id_for_log: str, 
    base_image_path: str, 
    description_prompt: str, 
    save_path: str,
    max_retries: int = 3,
    retry_delay_seconds: int = 2
):
    """
    使用 VLM (图生图) 来编辑一个基础精灵表。
    """
    
    # --- 1. 检查和加载基础图像 ---
    if not os.path.exists(base_image_path):
        print(f"  - !!! 错误: 找不到角色基础参考图: {base_image_path}")
        return False
        
    try:
        with open(base_image_path, "rb") as img_file:
            b64_image_data = base64.b64encode(img_file.read()).decode('utf-8')
        print(f"  - 成功加载基础参考图: {os.path.basename(base_image_path)}")
    except Exception as e:
        print(f"  - !!! 错误: 加载基础参考图失败: {e}")
        return False
        
# --- 3. 准备“图像编辑” Prompt (V3 - 硬性编辑规定) ---
    image_editing_prompt = (
        f"This is a basic sprite image. The first row is a static character facing forward (in idle state).\n"
        f"The second row is an animation sequence of walking to the right, showing only the side face.\n"
        f"The third row is an animation sequence of walking upward. (Ensure the face is not visible, showing the back of the hair/clothes).\n"
        f"The fourth row is an animation sequence of walking to the left, showing only the side face.\n"
        f"The fifth row is an animation sequence of walking downward, with the full front view visible.\n\n"
        f"**Your task is to edit the character's appearance based on this image**\n"
        f"You can only change the character's clothes and hairstyle. The movements and positions must not be altered.\n"
        f"Ensure the consistency of the character's appearance across different movements.\n"
        f"Do not modify the transparent background, image aspect ratio, or dimensions.\n"
        f"**Character appearance description**: {description_prompt}\n"
    )

    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": image_editing_prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_image_data}"
                }
            }
        ]}
    ]

    print(f"  - 正在为 '{description_prompt}' 请求 AI 图像编辑...")
    print(f" ---------------- PROMPT (Text only) ----------------")
    print(f" {image_editing_prompt}")
    print(f" ----------------------------------------------------")

    # --- 3. 调用 API (带重试逻辑) ---
    for attempt in range(max_retries):
        try:
            print(f"  - 正在尝试第 {attempt + 1}/{max_retries} 次 API 调用...")
            start_time = time.time()
            
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            
            end_time = time.time()
            
            content = completion.choices[0].message.content
            m = re.search(r'data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=\r\n]+)', content)
            
            if m:
                # --- 4. 成功！解码并保存 ---
                img_format = m.group(1)
                img_b64 = m.group(2)
                
                print(f"  - [AI-Edit] 成功接收到 Base64 响应 (格式: {img_format}, 用时: {end_time - start_time:.2f}s)")
                
                img_bytes = base64.b64decode(img_b64)
                
                with open(save_path, "wb") as f:
                    f.write(img_bytes)
                
                print(f"  - [AI-Edit] 正在调用后处理器 (修复尺寸和透明度)...")
                post_process_success = _post_process_sprite_sheet(
                    base_image_path, # (原始基础图)
                    save_path        # (刚保存的 AI 图)
                )
                
                if not post_process_success:
                    print(f"  - [AI-Edit] AI生成成功，但【后处理失败】。此资产将不可用。")
                    return False # <-- 失败
                
                print(f"  - [Artist Agent] 成功保存并处理【角色精灵表】: {save_path}")
                return True # <-- 成功
                
            else:
                # API 成功，但未返回图像
                print(f"❌ (尝试 {attempt + 1}) 生成失败: 未在模型响应中找到 Base64 图像数据。")
                print(f"   服务器返回: {content[:200]}...")

        except Exception as e:
            # API 失败 (例如网络错误)
            print(f"❌ (尝试 {attempt + 1}) 请求时发生意外错误: {e}")
        
        if attempt < max_retries - 1:
            print(f"   ...将在 {retry_delay_seconds} 秒后重试...")
            time.sleep(retry_delay_seconds)
            
    print(f"❌ '{asset_id_for_log}' 达到最大重试次数，放弃。") # <-- (已从 'filename' 修复)
    return False # <-- 失败


def process_single_asset(asset_id, details, original_properties, save_dir, character_base_dir, client, artist_model_name):
    """
    [多线程工人函数] 处理单个资产的生成逻辑。
    返回: (原始ID, 生成的Assets字典, 生成的Properties字典, 需要标记删除的墙壁ID)
    """
    asset_type = details.get("type")
    description = details.get("description", "").lower()
    
    # 本次任务产生的结果容器
    generated_assets = {}     
    generated_props = {}      
    wall_id_to_delete = None  # 仅针对程序化墙壁

    try:
        # --- 逻辑 A: 程序化墙壁 (Procedural Wall) ---
        if (asset_type == "tile" and "wall" in description) or (asset_id.startswith("wall_") and "clock" not in asset_id):
            print(f" [Thread] 🧱 处理墙壁: '{asset_id}'")
            wall_id_to_delete = asset_id # 标记这个ID稍后需要在 layout 中被替换
            
            params = parse_description(description)
            asset_id_top = f"{asset_id}_top"
            asset_id_side = f"{asset_id}_side"
            
            # 计算尺寸
            top_size_tiles = details.get("visual_size", [1, 8])
            top_width_px = top_size_tiles[0] * TILE_SIZE
            top_height_px = top_size_tiles[1] * TILE_SIZE
            side_width_px = 1 * TILE_SIZE
            side_height_px = top_height_px 
            
            # 生成 Top 贴图
            path_top = os.path.join(save_dir, f"{asset_id_top}.png")
            _generate_procedural_wall_tile(top_width_px, top_height_px, params, True, path_top)
            
            # 生成 Side 贴图
            path_side = os.path.join(save_dir, f"{asset_id_side}.png")
            _generate_procedural_wall_tile(side_width_px, side_height_px, params, False, path_side)

            # 构造返回数据
            new_top = copy.deepcopy(details)
            new_top["description"] = f"Top-Down view of {asset_id}"
            
            new_side = copy.deepcopy(details)
            new_side["description"] = f"Side-view of {asset_id}"
            new_side["visual_size"] = top_size_tiles

            generated_assets[asset_id_top] = new_top
            generated_assets[asset_id_side] = new_side
            
            if asset_id in original_properties:
                generated_props[asset_id_top] = copy.deepcopy(original_properties[asset_id])
                generated_props[asset_id_side] = copy.deepcopy(original_properties[asset_id])

        # --- 逻辑 B: 程序化地板 (Procedural Floor) ---
        elif (asset_type == "tile" and "floor" in description) or (asset_id.startswith("floor_") and "clock" not in asset_id):
            print(f" [Thread] 🟫 处理地板: '{asset_id}'")
            params = parse_description(description)
            floor_size_tiles = details.get("visual_size", [2, 2])
            floor_width_px = floor_size_tiles[0] * TILE_SIZE
            floor_height_px = floor_size_tiles[1] * TILE_SIZE
            
            path_floor = os.path.join(save_dir, f"{asset_id}.png")
            # 地板生成极快，通常不跳过，若想跳过可在此加 os.path.exists 判断
            _generate_procedural_floor_tile(floor_width_px, floor_height_px, params, save_path=path_floor)
            
            generated_assets[asset_id] = details
            if asset_id in original_properties:
                generated_props[asset_id] = original_properties[asset_id]

        # --- 逻辑 C: AI 物体 (Object) ---
        elif asset_type == "object":
            final_object_path = os.path.join(save_dir, f"{asset_id}.png")
            if os.path.exists(final_object_path):
                print(f" [Thread] ⏩ [Cache] 物体 '{asset_id}' 已存在，跳过。")
            else:
                print(f" [Thread] 🛋️ [AI-Gen] 正在生成物体: '{asset_id}'...")
                # 调用生成函数 (注意：generate_real_image 内部包含重试逻辑)
                generate_real_image(
                    asset_id, 
                    details, 
                    {"assets": {}, "properties": {}}, # 传递空 plan 上下文即可，目前逻辑不太依赖它
                    save_dir, 
                    tile_size=TILE_SIZE
                )
            
            generated_assets[asset_id] = details
            if asset_id in original_properties:
                generated_props[asset_id] = original_properties[asset_id]

        # --- 逻辑 D: AI 角色 (NPC/Agent) ---
        elif asset_type == "npc" or asset_type == "agent":
            final_save_path = os.path.join(save_dir, f"{asset_id}.png")
            if os.path.exists(final_save_path):
                print(f" [Thread] ⏩ [Cache] 角色 '{asset_id}' 已存在，跳过。")
            else:
                print(f" [Thread] 👤 [AI-Edit] 正在生成角色: '{asset_id}'...")
                description_prompt = details.get("description", "一个普通人")
                
                # --- 匹配基础骨架 ---
                base_sheet_name = DEFAULT_CHARACTER_SHEET
                desc_lower = description_prompt.lower()
                found_sheet = False
                for sheet_name, keywords in CHARACTER_SHEET_MAP.items():
                    for keyword in keywords:
                        if keyword in desc_lower:
                            base_sheet_name = sheet_name
                            found_sheet = True
                            break
                    if found_sheet: break
                
                base_sheet_path = os.path.join(character_base_dir, base_sheet_name)
                
                # 调用生成函数
                generate_character_sprite_sheet(
                    client,
                    artist_model_name,
                    asset_id,
                    base_sheet_path,
                    description_prompt,
                    final_save_path
                )

            generated_assets[asset_id] = details
            if asset_id in original_properties:
                generated_props[asset_id] = original_properties[asset_id]

        # --- 逻辑 E: 其他未知类型 ---
        else:
            print(f" [Thread] ❓ 跳过未知类型: '{asset_id}'")
            generated_assets[asset_id] = details
            if asset_id in original_properties:
                generated_props[asset_id] = original_properties[asset_id]
                
    except Exception as e:
        print(f"!!! [Thread Error] 处理 '{asset_id}' 时发生异常: {e}")
        # 即使出错，也要把原始信息填回去，防止 JSON 缺失
        generated_assets[asset_id] = details
        
    return asset_id, generated_assets, generated_props, wall_id_to_delete


def run_artist_agent(scene_plan: dict, godot_project_path: str) -> dict:
    """
    (V15 多线程版) 统一资产生成入口
    - 墙壁/地板 -> OpenCV 并行生成
    - 物体/NPC -> OpenAI 并行生成
    """
    print(f"\n[Artist Agent] (V15 Multi-threaded) 🚀 开始并行资产生成...")
    
    # --- 1. 设置路径 ---
    save_dir = os.path.join(godot_project_path, "generated_assets")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f" ➡️ 创建文件夹: {save_dir}")

    character_base_dir = os.path.join(godot_project_path, CHARACTER_BASE_SHEET_DIR)
    
    # 准备数据副本
    processed_plan = copy.deepcopy(scene_plan)
    original_assets = processed_plan.get("assets", {})
    original_properties = processed_plan.get("properties", {})
    
    # 结果容器 (将在主线程汇总)
    new_assets = {}
    new_properties = {}
    assets_to_delete = [] # 存储需要被重写的墙壁 ID

    # --- 2. 配置线程池 ---
    # 建议设置 5-8 个线程。太高可能导致 OpenAI 报 429 Rate Limit 错误。
    MAX_WORKERS = 5 
    tasks = []

    print(f"--- 正在提交任务到线程池 (Max Workers: {MAX_WORKERS}) ---")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        for asset_id, details in original_assets.items():
            future = executor.submit(
                process_single_asset,
                asset_id,
                details,
                original_properties,
                save_dir,
                character_base_dir,
                client,            # 传递全局 client
                ARTIST_MODEL_NAME  # 传递全局 model name
            )
            tasks.append(future)
        
        # 收集结果 (as_completed 会在某个任务一完成就立即返回)
        total_tasks = len(tasks)
        completed_count = 0
        
        for future in as_completed(tasks):
            completed_count += 1
            try:
                # 获取工人函数的返回值
                _, gen_assets, gen_props, wall_del = future.result()
                
                # 【主线程汇聚数据】
                new_assets.update(gen_assets)
                new_properties.update(gen_props)
                if wall_del:
                    assets_to_delete.append(wall_del)
                
                # 打印简略进度条
                print(f" ✅ 进度: [{completed_count}/{total_tasks}]", end="\r")
                
            except Exception as e:
                print(f"\n ❌ 任务结果获取失败: {e}")

    print(f"\n--- 所有线程任务执行完毕。 ---")

    # --- 3. JSON 自动重写 (Layout 修正) ---
    # (这部分逻辑必须在所有资产生成完后，在主线程串行执行)
    print("[Artist Agent] ➡️ [JSON] 正在重写 wall_layer 布局...")

    wall_layer_cmds = processed_plan.get("layout", {}).get("wall_layer", [])
    if not wall_layer_cmds:
        print("   (没有检测到 wall_layer，跳过布局重写)")
    
    for cmd in wall_layer_cmds:
        original_id = cmd.get("asset_id")
        
        # 如果这个 ID 是我们程序化处理过的 (e.g., "wall_red_brick")
        if original_id in assets_to_delete:
            area = cmd.get("area", [0, 0, 0, 0])
            x, y, w, h = area
            
            # V15 逻辑: 宽的(w > h)是 "Top", 窄的(h > w)是 "Side"
            if w > h:
                cmd["asset_id"] = f"{original_id}_top"
                # print(f"   - 重定向 '{original_id}' -> '{cmd['asset_id']}' (Top)")
            elif h > w:
                cmd["asset_id"] = f"{original_id}_side"
                # print(f"   - 重定向 '{original_id}' -> '{cmd['asset_id']}' (Side)")
            else:
                # (边缘情况) 1x1 的墙, 默认为 _top
                cmd["asset_id"] = f"{original_id}_top"
                # print(f"   - 重定向 '{original_id}' -> '{cmd['asset_id']}' (1x1 Default)")
    
    # 4. 更新 JSON 对象并返回
    processed_plan["assets"] = new_assets
    processed_plan["properties"] = new_properties
    
    print(f" ✅ 统一生成流程结束。图像已保存至: {save_dir}")
    
    # 返回【已处理】的 JSON
    return processed_plan