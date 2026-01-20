# 文件名: npc_brain.gd
# 附加到: res://npc.tscn (CharacterBody2D 根节点)
extends CharacterBody2D

# --- 节点引用 ---
@onready var sprite: Sprite2D = $Sprite2D

# --- “灵魂”接口 (由 scene_builder_server.gd 注入) ---
@export var character_name: String = "Default NPC"
@export var is_agent: bool = false
@export var soul_file: String = ""

# --- 内部AI状态 ---
var ai_schedule: Dictionary = {}
var ai_memory: Array = []

var is_player_controlled: bool = false
const PLAYER_SPEED = 150.0 # 玩家控制时的移动速度



func _ready():
	print("NPC '%s' (is_agent: %s) 已进入场景。" % [character_name, is_agent])
	if not soul_file.is_empty():
		load_soul_data()
	else:
		print("  - 警告: %s 没有提供 soul_file，将使用默认行为。" % character_name)

# --- “灵魂”加载 (无变化) ---
func load_soul_data():
	var soul_path = "res://npc_souls/" + soul_file
	if not FileAccess.file_exists(soul_path):
		printerr("错误: 找不到灵魂文件: %s" % soul_path); return
	var file = FileAccess.open(soul_path, FileAccess.READ)
	var content = file.get_as_text()
	var json = JSON.parse_string(content)
	if json:
		print("  - %s 成功加载灵魂: %s" % [character_name, soul_path])
		self.ai_schedule = json.get("schedule", {})
		self.ai_memory = json.get("memory", [])
	else:
		printerr("错误: 解析灵魂文件失败: %s" % soul_path)

# --- “肉体”设置 (无变化) ---
func set_texture(tex: Texture2D):
	if sprite:
		sprite.texture = tex
	else:
		await ready
		sprite.texture = tex



func _physics_process(delta):

	if is_player_controlled:
		handle_player_input()
	else:
		# 否则，执行AI逻辑
		execute_ai_behavior(delta)
		
	move_and_slide() # 统一执行移动


func execute_ai_behavior(delta):
	# (此处为未来实现的AI逻辑占位)
	# TODO: 
	# 1. 检查当前游戏时间
	# 2. 从 ai_schedule 获取当前固定任务
	# 3. 寻路到任务目标点
	
	# 确保AI不控制时速度为0
	velocity = Vector2.ZERO
	pass


func handle_player_input():
	# 读取 "ui_left", "ui_right" 等输入 (这些是Godot内置的)
	var move_direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = move_direction * PLAYER_SPEED


func take_control(is_controlled: bool):
	is_player_controlled = is_controlled
	if is_controlled:
		print("玩家现在控制: %s" % character_name)
	else:
		print("AI 现在控制: %s" % character_name)
		velocity = Vector2.ZERO # 释放控制时立刻停止
