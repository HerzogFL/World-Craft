extends CharacterBody2D

# --- 节点引用 ---
@onready var sprite: Sprite2D = $Sprite2D
@onready var navigation_agent: NavigationAgent2D = $NavigationAgent2D
@onready var chat_bubble: Label = $ChatBubble
@onready var chat_bubble_timer: Timer = $ChatBubble/ChatBubbleTimer
@onready var name_label: Label = $NameLabel

@onready var animation_player: AnimationPlayer = $AnimationPlayer

# --- “灵魂”接口 ---
@export var character_name: String = "Default NPC"
@export var is_agent: bool = false
@export var soul_file: String = ""
var ai_schedule: Dictionary = {}
var ai_memory: Array = []
var ai_dialogue: Dictionary = {}
var is_god_controlled: bool = false

# --- 内部 AI 状态 ---
var ai_current_task_string: String = ""
var ai_current_action: String = ""
var ai_current_target_name: String = ""
const AI_MOVE_SPEED: float = 70.0
const GOD_MOVE_SPEED: float = 150.0
const NAVIGATION_TARGET_REACHED_DISTANCE: float = 50.0
const DIALOGUE_RANGE: float = 50.0
const CHARACTER_PHYSICS_LAYER = 2


var current_anim_state: String = "idle_down"

# 对话冷却
const DIALOGUE_COOLDOWN_TIME: float = 30.0
var _dialogue_cooldown: float = 0.0

# 追踪计时器
const TARGET_UPDATE_INTERVAL: float = 0.5
var _target_update_timer: float = 0.0


func _ready():
	print("NPC '%s' (is_agent: %s) 已进入场景。" % [character_name, is_agent])
	if not soul_file.is_empty():
		load_soul_data()
	else:
		print("  - 警告: %s 没有提供 soul_file。" % character_name)

	# 1. 设置自己的物理层
	set_collision_layer_value(CHARACTER_PHYSICS_LAYER, true)

	var style_box = StyleBoxFlat.new()
	style_box.bg_color = Color.WHITE # 白色背景
	style_box.border_width_left = 2; style_box.border_width_right = 2
	style_box.border_width_top = 2; style_box.border_width_bottom = 2
	style_box.border_color = Color.BLACK # 黑色边框
	chat_bubble.add_theme_stylebox_override("normal", style_box)
	chat_bubble.set("theme_override_colors/font_color", Color.BLACK) # 移除颜色设置
	chat_bubble.get_theme_font("font").antialiasing = TextServer.FONT_ANTIALIASING_NONE
	chat_bubble.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	chat_bubble.size.x = 150 # 设置固定宽度
	chat_bubble.visible = false
	
	# 3. 设置导航完成距离
	navigation_agent.target_desired_distance = NAVIGATION_TARGET_REACHED_DISTANCE
	
	# 4. 连接时钟
	WorldClock.schedule_tick.connect(on_schedule_tick)
	call_deferred("on_schedule_tick", WorldClock.get_current_time_string())

	# 5. 设置名字标签文本
	if name_label:
		name_label.text = character_name
	else:
		printerr("错误: %s 场景中找不到 'NameLabel' 子节点！" % scene_file_path if owner else "当前场景")
	# 确保 NPC 在场景加载时播放正确的初始动画
	update_animation(Vector2.ZERO) # (传入 0 向量，会自动播放 idle_down)
	
# --- “灵魂”加载 (只读 res://) ---
func load_soul_data():
	var load_path = "res://npc_souls/" + soul_file 
	if not FileAccess.file_exists(load_path):
		printerr("错误: 找不到灵魂文件: %s" % load_path); return
	var file = FileAccess.open(load_path, FileAccess.READ); var content = file.get_as_text(); file.close()
	var json = JSON.parse_string(content)
	if json:
		print("  - %s 成功加载灵魂: %s" % [character_name, load_path])
		self.ai_schedule = json.get("schedule", {}); self.ai_dialogue = json.get("dialogue", {})
		self.ai_memory = json.get("memory", []) # 读取记忆
	else: printerr("错误: 解析灵魂文件失败: %s" % load_path)

# --- “肉体”设置 ---
func set_texture(tex: Texture2D):
	if sprite: sprite.texture = tex
	else: await ready; sprite.texture = tex

# --- 上帝模式接口 ---
func set_god_control(is_active: bool):
	is_god_controlled = is_active
	if is_active:
		print("上帝模式已激活: %s" % character_name)
		navigation_agent.target_position = global_position
		ai_current_action = ""
		ai_current_target_name = ""
		_dialogue_cooldown = 0
	else:
		print("上帝模式已停用: %s" % character_name)
		call_deferred("on_schedule_tick", WorldClock.get_current_time_string())


func _physics_process(delta):
	if _dialogue_cooldown > 0:
		_dialogue_cooldown -= delta

	if is_god_controlled:
		# --- 1. 上帝模式 ---
		var move_direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		velocity = move_direction * GOD_MOVE_SPEED
		navigation_agent.set_velocity(velocity)
	else:
		# --- 2. 默认 AI 模式 ---
		var navigation_finished = navigation_agent.is_navigation_finished()

		if navigation_finished:
			velocity = Vector2.ZERO # 停下
			
			# 到达后检查是否要对话
			if ai_current_action == "talk_to" and not ai_current_target_name.is_empty():
				# 仅在到达目标时执行一次对话尝试
				if _dialogue_cooldown <= 0:
					var target_node = find_character_by_name(ai_current_target_name)
					if is_instance_valid(target_node):
						# 导航完成就触发对话 (依赖 target_desired_distance)
						print("DEBUG: %s 到达 %s 附近，触发对话！" % [character_name, ai_current_target_name])
						initiate_dialogue(target_node) # initiate_dialogue 会设置冷却并清除状态
					else:
						print("DEBUG: %s 到达目的地但目标 %s 已消失。" % [character_name, ai_current_target_name])
						# 即使目标消失，任务也结束
						ai_current_action = ""
						ai_current_target_name = ""
				# else: # 在冷却中，到达后什么也不做，等待冷却结束或新任务

			# 清除已完成的非对话任务状态
			elif not ai_current_action.is_empty() and ai_current_action != "talk_to":
				# print("DEBUG: %s 完成任务 '%s'。清除状态。" % [character_name, ai_current_action])
				ai_current_action = ""
				ai_current_target_name = ""

		else: # 还在移动中
			# 如果目标是人，才需要更新追踪
			if ai_current_action == "talk_to":
				update_target_position(delta) 
			
			var next_path_pos = navigation_agent.get_next_path_position()
			var ideal_velocity = global_position.direction_to(next_path_pos) * AI_MOVE_SPEED
			navigation_agent.set_velocity(ideal_velocity)
			velocity = navigation_agent.get_velocity()
		
	update_animation(velocity)
	
	move_and_slide()
	

func update_animation(move_velocity: Vector2):
	if not is_instance_valid(animation_player):
		return # 动画播放器还未准备好

	var new_anim_state = current_anim_state

	if move_velocity.length_squared() > 0:
		# --- A. 正在移动 ---
		# (我们使用 "abs" 来找到哪个方向的“力”更大)
		if abs(move_velocity.x) > abs(move_velocity.y):
			# 优先左右
			if move_velocity.x > 0:
				new_anim_state = "walk_right"
			else:
				new_anim_state = "walk_left"
		else:
			# 优先上下
			if move_velocity.y > 0:
				new_anim_state = "walk_down"
			else:
				new_anim_state = "walk_up"
	else:
		# --- B. 停止移动 ---
		# (我们切换到与之前行走方向匹配的“站立”动画)
		if current_anim_state.begins_with("walk_"):
			# e.g., "walk_down" -> "idle_down"
			new_anim_state = current_anim_state.replace("walk_", "idle_")

	# --- C. 播放动画 ---
	if new_anim_state != current_anim_state:
		current_anim_state = new_anim_state
		animation_player.play(current_anim_state)

# ==================== AI 辅助函数 ====================

# --- 时钟信号 ---
#func on_schedule_tick(current_key: String): 
	#if is_god_controlled: return 
	#if ai_schedule.has(current_key):
		#var new_task = ai_schedule[current_key]
		#if new_task != ai_current_task_string and ai_current_action.is_empty(): 
			#print("'%s' 收到新任务: %s -> %s" % [character_name, current_key, new_task])
			#ai_current_task_string = new_task
			#var parsed_task = parse_task_string(new_task)
			#var action = parsed_task["action"]; var target_name_or_tag = parsed_task["target"]
			#if target_name_or_tag.is_empty():
				#navigation_agent.target_position = global_position; return
			#if action.contains("找") or action.contains("Talk to"):
				#ai_current_action = "talk_to"; ai_current_target_name = target_name_or_tag
				#var target_node = find_character_by_name(target_name_or_tag)
				#if is_instance_valid(target_node):
					#navigation_agent.target_position = target_node.global_position
					#print("%s 准备去找 %s 聊天 (初始位置 %s)" % [character_name, target_name_or_tag, navigation_agent.target_position])
				#else:
					#printerr("错误: %s 找不到要聊天的 '%s'" % [character_name, target_name_or_tag])
					#ai_current_action = ""; ai_current_target_name = ""; navigation_agent.target_position = global_position
			#else:
				#ai_current_action = "move_to"; ai_current_target_name = ""
				#find_and_move_to_target(target_name_or_tag)
				#

# --- 时钟信号 ---
func on_schedule_tick(current_key: String): 
	if is_god_controlled: return 
	
	if ai_schedule.has(current_key):
		var new_task = ai_schedule[current_key]
		
		if new_task != ai_current_task_string and ai_current_action.is_empty(): 
			print("'%s' 收到新任务: %s -> %s" % [character_name, current_key, new_task])
			ai_current_task_string = new_task 
			
			var parsed_task = parse_task_string(new_task)
			# 注意：我们现在几乎可以忽略 action 变量了
			var action = parsed_task["action"]; var target_name_or_tag = parsed_task["target"]
			
			if target_name_or_tag.is_empty():
				# 任务格式无效 (例如 "MOVE_TO []" 或 "Wander around")
				navigation_agent.target_position = global_position
				ai_current_action = ""; ai_current_target_name = ""; ai_current_task_string = ""
				log_memory_event("计划无效或没有目标，决定待在原地。")
				return
			
			# 1. 优先尝试将目标视为一个“角色”
			var target_node = find_character_by_name(target_name_or_tag)
			
			if is_instance_valid(target_node):
				# 2. 成功！ 找到了一个角色，意图必定是 "talk_to"
				# 无论 action 是 "TALK_TO", "MOVE_TO", "MEET", "交流" 还是 "FIND"
				
				ai_current_action = "talk_to"
				ai_current_target_name = target_name_or_tag
				navigation_agent.target_position = target_node.global_position 
				log_memory_event("计划去找 %s。" % target_name_or_tag) # 统一日志
				print("%s 准备去找角色: %s (初始位置 %s)" % [character_name, target_name_or_tag, navigation_agent.target_position])
				
			else:
				# 3. 失败！ 找不到叫这个名字的角色，假定它是一个“地点” (如 'bar_counter')
				# 意图必定是 "move_to"
				
				ai_current_action = "move_to"
				ai_current_target_name = "" # 目标是地点，不是角色
				log_memory_event("计划去 %s。" % target_name_or_tag)
				
				# 4. (重要) 现在才调用 find_and_move_to_target，
				# 它会处理地点查找
				find_and_move_to_target(target_name_or_tag) 
				

# --- 更新追踪目标位置 ---
func update_target_position(delta: float):
	if ai_current_action != "talk_to" or ai_current_target_name.is_empty(): return
	_target_update_timer -= delta
	if _target_update_timer <= 0:
		_target_update_timer = TARGET_UPDATE_INTERVAL
		var target_node = find_character_by_name(ai_current_target_name)
		if is_instance_valid(target_node):
			var current_target_pos = target_node.global_position
			if not navigation_agent.is_navigation_finished() and navigation_agent.target_position.distance_to(current_target_pos) > 1.0:
				navigation_agent.target_position = current_target_pos
		else:
			print("%s 追踪的目标 %s 不再有效，停止追踪。" % [character_name, ai_current_target_name])
			navigation_agent.target_position = global_position
			ai_current_action = ""; ai_current_target_name = ""

# --- 任务解析器 ---
func parse_task_string(task_string: String) -> Dictionary:
	var result = {"action": "", "target": ""}; var start_bracket = task_string.find("["); var end_bracket = task_string.find("]", start_bracket)
	if start_bracket != -1 and end_bracket != -1:
		result["target"] = task_string.substr(start_bracket + 1, end_bracket - start_bracket - 1)
		result["action"] = task_string.substr(0, start_bracket).strip_edges()
	else: result["action"] = task_string
	return result

# --- 查找角色 ---
func find_character_by_name(char_name: String):
	var characters = get_tree().get_nodes_in_group("npc") + get_tree().get_nodes_in_group("agent")
	for char_node in characters:
		if is_instance_valid(char_node) and char_node.has_method("get") and char_node.get("character_name") == char_name:
			return char_node
		elif is_instance_valid(char_node) and char_node.name == char_name: 
			return char_node
	return null

# --- 寻路到物体 ---
#func find_and_move_to_target(target_tag: String):
	#var potential_targets = get_tree().get_nodes_in_group(target_tag)
	#if potential_targets.is_empty(): printerr("错误: %s 找不到 '%s'" % [character_name, target_tag]); return
	#var target_node = potential_targets.pick_random()
	#if is_instance_valid(target_node) and target_node.has_method("get_global_position"):
		#navigation_agent.target_position = target_node.global_position
		#print("%s GOTO: %s" % [character_name, target_tag])
	#else: printerr("错误: %s 找到的 '%s' 节点无效或没有位置。" % [character_name, target_tag])
	
# --- 寻路到物体 ---
func find_and_move_to_target(target_tag: String):
	var potential_targets = get_tree().get_nodes_in_group(target_tag)
	
	if potential_targets.is_empty(): 
		printerr("错误: %s 找不到 '%s'" % [character_name, target_tag])
		ai_current_action = ""
		ai_current_target_name = ""
		ai_current_task_string = "" # 清除“上一个任务”
		navigation_agent.target_position = global_position
		return

	var target_node = potential_targets.pick_random()
	
	if is_instance_valid(target_node) and target_node.has_method("get_global_position"):
		navigation_agent.target_position = target_node.get_global_position()
		print("%s GOTO: %s" % [character_name, target_tag])
	else: 
		printerr("错误: %s 找到的 '%s' 节点无效或没有位置。" % [character_name, target_tag])
		ai_current_action = ""
		ai_current_target_name = ""
		ai_current_task_string = "" # 清除“上一个任务”
		navigation_agent.target_position = global_position


# --- NPC 主动发起对话 (按计划) ---
func initiate_dialogue(target_node):
	if _dialogue_cooldown > 0:
		print("DEBUG: %s 尝试发起对话，但仍在冷却中。" % character_name)
		ai_current_action = ""
		ai_current_target_name = ""
		navigation_agent.target_position = global_position # 停止导航
		return

	var message = ai_dialogue.get("default", "...")
	show_chat_bubble(message)
	if is_instance_valid(target_node) and target_node.has_method("receive_dialogue"):
		target_node.receive_dialogue(self, message)
	else:
		print("DEBUG: %s 尝试与无效目标 %s 对话。" % [character_name, target_node])

	if is_instance_valid(target_node):
		log_memory_event("主动对 %s 说了: '%s'" % [target_node.character_name, message])
	
	_dialogue_cooldown = DIALOGUE_COOLDOWN_TIME
	navigation_agent.target_position = global_position # 这一行在 _physics_process 中处理
	ai_current_action = "" # 这一行在 _physics_process 中处理
	ai_current_target_name = ""


# --- 接收对话 ---
func receive_dialogue(from_node: CharacterBody2D, message_content: String):
	if not is_instance_valid(from_node): return 
	log_memory_event("听到 %s 说: '%s'" % [from_node.character_name, message_content])
	if _dialogue_cooldown <= 0:
		var reply = ai_dialogue.get("default", "(无话可说)") 
		show_chat_bubble(reply)
		call_deferred("_send_reply", from_node, reply)
		_dialogue_cooldown = DIALOGUE_COOLDOWN_TIME
	else:
		print("DEBUG: %s 收到对话，但在冷却中，不回复。" % character_name)

# --- 回复 ---
func _send_reply(target_node, message):
	if is_instance_valid(target_node) and target_node.has_method("receive_dialogue"):
		target_node.receive_dialogue(self, message)
		log_memory_event("回复 %s: '%s'" % [target_node.character_name, message])

# --- 显示气泡 ---
func show_chat_bubble(text: String):
	chat_bubble.text = text
	# Label 会根据 _ready 中设置的 size.x 和 autowrap_mode 自动调整高度
	# 我们只需要确保它可见
	chat_bubble.visible = true
	chat_bubble_timer.start() # 启动隐藏计时器

func log_memory_event(event_text: String, thought: String = ""):
	var log_entry = {"time": WorldClock.get_current_time_string(), "event": event_text, "thought": thought}
	ai_memory.append(log_entry)
	var save_path = "res://npc_souls/" + soul_file
	var soul_data_to_save = { "schedule": ai_schedule, "dialogue": ai_dialogue, "memory": ai_memory }
	var file = FileAccess.open(save_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(soul_data_to_save, "  ")); file.close()
		# print("  - [日志] %s 记忆已【直接写入】: %s" % [character_name, save_path])
	else: printerr("错误: 无法写入记忆文件到 res://: %s (错误码: %s)" % [save_path, FileAccess.get_open_error()])

# ==================== 信号处理 ====================
func _on_click_area_input_event(viewport: Node, event: InputEvent, shape_idx: int) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.is_pressed():
		GlobalState.set_selected(self)

func _on_chat_bubble_timer_timeout():
	chat_bubble.visible = false
