# 文件名: agent_brain.gd (最终版: 修复状态机Bug + 集成世界感知 + 添加网络调试)
# 附加到: res://agent.tscn (CharacterBody2D 根节点)
extends CharacterBody2D

# --- 节点引用 ---
@onready var sprite: Sprite2D = $Sprite2D
@onready var http_request: HTTPRequest = $HTTPRequest
@onready var navigation_agent: NavigationAgent2D = $NavigationAgent2D
@onready var chat_bubble: Label = $ChatBubble
@onready var chat_bubble_timer: Timer = $ChatBubble/ChatBubbleTimer
@onready var name_label: Label = $NameLabel
@onready var opener_http_request: HTTPRequest = $OpenerHTTPRequest

@onready var animation_player: AnimationPlayer = $AnimationPlayer

# --- “灵魂”接口 ---
@export var character_name: String = "Default Agent"
@export var is_agent: bool = false
@export var soul_file: String = ""

# --- 内部AI状态 ---
var llm_api_key: String = ""
var llm_api_url: String = ""
var llm_model_name: String = ""
var llm_api_type: String = "openai" 
var ai_base_prompt: String = "" 
var ai_personality: String = ""
var ai_goals: Array = []
var ai_memory: Array = []
var ai_dialogue: Dictionary = {}

# --- AI 状态机 ---
var _is_awaiting_opener_content: bool = false
var _pending_dialogue_content: String = ""
var _current_opener_http_request: HTTPRequest = null 
var current_dynamic_plan: Dictionary = {}
var is_god_controlled: bool = false
var is_thinking: bool = false
var ai_current_task_string: String = ""
var ai_current_action: String = ""
var ai_current_target_name: String = ""
const AI_MOVE_SPEED: float = 70.0
const GOD_MOVE_SPEED: float = 150.0
const NAVIGATION_TARGET_REACHED_DISTANCE: float = 50.0
const DIALOGUE_RANGE: float = 50.0
const CHARACTER_PHYSICS_LAYER = 2

var current_anim_state: String = "idle_down"

const TARGET_UPDATE_INTERVAL: float = 0.5 
var _target_update_timer: float = 0.0

const WORLD_CONTEXT_PATH = "res://world/world_context.json"
var _world_context_cache: Dictionary = {} 

# ==================== 核心功能 ====================

func _ready():
	print("Agent '%s' (is_agent: %s) 已进入场景。" % [character_name, is_agent])
	if not soul_file.is_empty():
		load_soul_data()
	else:
		print("  - 警告: %s 没有提供 soul_file。" % character_name)
		
	if llm_api_key.is_empty() or llm_api_key == "PASTE_YOUR_LLM_API_KEY_HERE":
		printerr("  - %s 无法请求计划：API Key 未在 %s 中配置。" % [character_name, soul_file])
	else:
		call_deferred("request_daily_plan_from_llm") 

	set_collision_layer_value(CHARACTER_PHYSICS_LAYER, true)
	
	var style_box = StyleBoxFlat.new()
	style_box.bg_color = Color.WHITE 
	style_box.border_width_left = 2; style_box.border_width_right = 2
	style_box.border_width_top = 2; style_box.border_width_bottom = 2
	style_box.border_color = Color.BLACK 
	chat_bubble.add_theme_stylebox_override("normal", style_box)
	chat_bubble.set("theme_override_colors/font_color", Color.BLACK) 
	chat_bubble.get_theme_font("font").antialiasing = TextServer.FONT_ANTIALIASING_NONE
	chat_bubble.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	chat_bubble.size.x = 150 
	chat_bubble.visible = false
	
	navigation_agent.target_desired_distance = NAVIGATION_TARGET_REACHED_DISTANCE
	
	WorldClock.schedule_tick.connect(on_schedule_tick)
	call_deferred("on_schedule_tick", WorldClock.get_current_time_string())
	
	if name_label:
		name_label.text = character_name
	else:
		printerr("错误: %s 场景中找不到 'NameLabel' 子节点！" % scene_file_path if owner else "当前场景")
	# 6. 【【【 新增：初始化动画 】】】
	# 确保 NPC 在场景加载时播放正确的初始动画
	update_animation(Vector2.ZERO) # (传入 0 向量，会自动播放 idle_down)
	
# --- 上帝模式接口 ---
func set_god_control(is_active: bool):
	is_god_controlled = is_active
	if is_active:
		print("上帝模式已激活: %s" % character_name)
		navigation_agent.target_position = global_position
		ai_current_action = ""
		ai_current_target_name = ""
	else:
		print("上帝模式已停用: %s" % character_name)
		call_deferred("on_schedule_tick", WorldClock.get_current_time_string())

# --- “灵魂”加载 ---
func load_soul_data():
	var load_path = "res://npc_souls/" + soul_file
	if not FileAccess.file_exists(load_path):
		printerr("错误: 找不到灵魂文件: %s" % load_path); return
	var file = FileAccess.open(load_path, FileAccess.READ); var content = file.get_as_text(); file.close()
	var json = JSON.parse_string(content)
	if json:
		print("  - %s 成功加载灵魂: %s" % [character_name, load_path])
		self.llm_api_key = json.get("api_key", "")
		self.llm_api_url = json.get("api_url", "")
		self.llm_model_name = json.get("model_name", "gpt-4o")
		self.llm_api_type = json.get("api_type", "openai").to_lower() 
		self.ai_base_prompt = json.get("base_prompt", "你是一个普通人。") 
		self.ai_personality = json.get("personality", "一个普通人")
		self.ai_goals = json.get("goals", [])
		self.ai_dialogue = json.get("dialogue", {})
		self.ai_memory = json.get("memory", [])
		self.current_dynamic_plan = json.get("current_dynamic_plan", {})
		if not self.current_dynamic_plan.is_empty():
			print("  - %s 成功加载【测试用】硬编码计划: %s" % [character_name, self.current_dynamic_plan])
	else: printerr("错误: 解析灵魂文件失败: %s" % load_path)

# --- “肉体”设置 ---
func set_texture(tex: Texture2D):
	if sprite:
		sprite.texture = tex
	else:
		await ready
		sprite.texture = tex

#func _physics_process(delta):
	#if is_god_controlled:
		#var move_direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		#velocity = move_direction * GOD_MOVE_SPEED
		#navigation_agent.set_velocity(velocity)
		#
	#else:
		#if is_thinking:
			#velocity = Vector2.ZERO 
			#navigation_agent.set_velocity(velocity) 
			#
		#elif navigation_agent.is_navigation_finished():
			#velocity = Vector2.ZERO 
			#
			#var completed_action = ai_current_action 
			#var completed_target = ai_current_target_name
			#
			#if not ai_current_action.is_empty():
				#ai_current_action = ""
				#ai_current_target_name = ""
				#ai_current_task_string = "" # 【【【 修复：清除“上一个任务” 】】】
#
			#if completed_action == "talk_to" and not completed_target.is_empty():
				#var target_node = find_character_by_name(completed_target)
				#if is_instance_valid(target_node):
					#initiate_dialogue_on_arrival(target_node)
				#else: 
					#log_memory_event("想和 %s 说话，但他/她好像不见了。" % completed_target)
#
		#else: # 还在移动中
			#if ai_current_action == "talk_to":
				#update_target_position(delta)
			#
			#var next_path_pos = navigation_agent.get_next_path_position()
			#var ideal_velocity = global_position.direction_to(next_path_pos) * AI_MOVE_SPEED
			#navigation_agent.set_velocity(ideal_velocity)
			#velocity = navigation_agent.get_velocity()
	#
	#move_and_slide()


func _physics_process(delta):
	if is_god_controlled:
		var move_direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		velocity = move_direction * GOD_MOVE_SPEED
		navigation_agent.set_velocity(velocity)
		
	else:
		if is_thinking:
			# "is_thinking" = 正在思考“回复”。必须冻结。
			velocity = Vector2.ZERO 
			navigation_agent.set_velocity(velocity) 
			
		elif _is_awaiting_opener_content and navigation_agent.is_navigation_finished():
			velocity = Vector2.ZERO
			navigation_agent.set_velocity(velocity)
		
		elif navigation_agent.is_navigation_finished():
			# 已到达，且不处于任何思考状态。
			velocity = Vector2.ZERO 
			
			var completed_action = ai_current_action 
			var completed_target = ai_current_target_name
			
			if not ai_current_action.is_empty():
				ai_current_action = ""
				ai_current_target_name = ""
				ai_current_task_string = ""

			if completed_action == "talk_to" and not completed_target.is_empty():
				var target_node = find_character_by_name(completed_target)
				if is_instance_valid(target_node):
					# 【【【 MODIFIED: 检查是否有准备好的开场白 】】】
					if not _pending_dialogue_content.is_empty():
						# 情况 A: LLM 内容已准备好，立刻说出来
						initiate_dialogue_on_arrival(target_node, _pending_dialogue_content)
						_pending_dialogue_content = "" # 用完后清除
					else:
						# 情况 B: 内容为空。
						# 这意味着任务被取消了，或者 LLM 请求失败了。
						log_memory_event("到达 %s 附近，但无话可说 (可能被新任务中断)。" % completed_target)
				else: 
					log_memory_event("想和 %s 说话，但他/她好像不见了。" % completed_target)
					# 确保清除状态
					_is_awaiting_opener_content = false
					_pending_dialogue_content = ""
					_current_opener_http_request = null
		
		else: # 还在移动中
			if ai_current_action == "talk_to":
				update_target_position(delta)
			
			var next_path_pos = navigation_agent.get_next_path_position()
			var ideal_velocity = global_position.direction_to(next_path_pos) * AI_MOVE_SPEED
			navigation_agent.set_velocity(ideal_velocity)
			velocity = navigation_agent.get_velocity()
	# --- 【【【 核心修改：在移动前更新动画 】】】 ---
	# (这会同时作用于“上帝模式”和“AI 模式”)
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
	# (只有在新状态和旧状态不同时，才播放，防止卡顿)
	if new_anim_state != current_anim_state:
		current_anim_state = new_anim_state
		animation_player.play(current_anim_state)

# ==================== AI 辅助函数 ====================

func _load_world_context() -> Dictionary:
	if not _world_context_cache.is_empty():
		return _world_context_cache
	if not FileAccess.file_exists(WORLD_CONTEXT_PATH):
		printerr("错误: 找不到世界上下文文件: %s" % WORLD_CONTEXT_PATH)
		return {}
	var file = FileAccess.open(WORLD_CONTEXT_PATH, FileAccess.READ)
	var content = file.get_as_text()
	file.close()
	var json = JSON.parse_string(content)
	if json:
		_world_context_cache = json
		print("  - %s 成功加载世界上下文。" % character_name)
		return _world_context_cache
	else:
		printerr("错误: 解析世界上下文文件失败: %s" % WORLD_CONTEXT_PATH)
		return {}

## --- 时钟信号 ---
#func on_schedule_tick(current_key: String):
	#if is_god_controlled or is_thinking: return 
	#
	#if current_dynamic_plan.has(current_key):
		#
		#var new_task = current_dynamic_plan[current_key]
		#
		#if new_task != ai_current_task_string and ai_current_action.is_empty(): 
			#
			#print("'%s' (D-AI) 收到新任务: %s -> %s" % [character_name, current_key, new_task])
			#ai_current_task_string = new_task 
			#
			#var parsed_task = parse_task_string(new_task)
			## 注意：我们现在几乎可以忽略 action 变量了
			#var action = parsed_task["action"]; var target_name_or_tag = parsed_task["target"]
			#
			#if target_name_or_tag.is_empty():
				## 任务格式无效 (例如 "MOVE_TO []" 或 "Wander around")
				#navigation_agent.target_position = global_position
				#ai_current_action = ""; ai_current_target_name = ""; ai_current_task_string = ""
				#log_memory_event("计划无效或没有目标，决定待在原地。")
				#return
#
			#
			## 1. 优先尝试将目标视为一个“角色”
			#var target_node = find_character_by_name(target_name_or_tag)
			#
			#if is_instance_valid(target_node):
				## 2. 成功！ 找到了一个角色，意图必定是 "talk_to"
				## 无论 action 是 "TALK_TO", "MOVE_TO", "MEET", "交流" 还是 "FIND"，
				## 只要目标是个角色，我们就去和他/她交谈。
				#
				#ai_current_action = "talk_to"
				#ai_current_target_name = target_name_or_tag
				#navigation_agent.target_position = target_node.global_position 
				#log_memory_event("计划去找 %s。" % target_name_or_tag) # 统一日志
				#print("%s (D-AI) 准备去找角色: %s (初始位置 %s)" % [character_name, target_name_or_tag, navigation_agent.target_position])
				#
			#else:
				## 3. 失败！ 找不到叫这个名字的角色，假定它是一个“地点” (如 'bar_counter')
				## 意图必定是 "move_to"
				#
				#ai_current_action = "move_to"
				#ai_current_target_name = "" # 目标是地点，不是角色
				#log_memory_event("计划去 %s。" % target_name_or_tag)
				#
				## 4. (重要) 现在才调用 find_and_move_to_target，
				## 它会处理地点查找，如果地点也找不到，它内部会处理失败并重置状态。
				#find_and_move_to_target(target_name_or_tag) 
				#
# --- 时钟信号 ---
func on_schedule_tick(current_key: String):
	if is_god_controlled: return 
	
	if current_dynamic_plan.has(current_key):
		var new_task = current_dynamic_plan[current_key]

		# 1. 检查是否是*不同*的任务
		if new_task != ai_current_task_string and not ai_current_action.is_empty():
			 # 【【【 核心: 任务中断逻辑 】】】
			 # 这是一个新任务，但旧任务还没完成！
			print("'%s' 收到新任务，放弃旧任务: %s" % [character_name, ai_current_task_string])
			 
			 # 如果正在等待“开场白”，立刻取消该网络请求
			if _is_awaiting_opener_content and is_instance_valid(_current_opener_http_request):
				print("SCHE-CANCEL: 放弃了上一个未完成的对话生成。")
				_current_opener_http_request.cancel_request()
			 
			 # 重置所有状态，准备新任务
			_is_awaiting_opener_content = false
			_pending_dialogue_content = ""
			_current_opener_http_request = null
			is_thinking = false # 重置“回复”思考状态
			ai_current_action = ""
			ai_current_target_name = ""
			 # ai_current_task_string 将在下面被新任务覆盖
		
		# 2. 如果我们是空闲的 (或刚刚被中断变为空闲)
		if ai_current_action.is_empty():
			# 检查这是否是同一个任务（防止时钟重复触发）
			if new_task == ai_current_task_string:
				return

			print("'%s' (D-AI) 收到新任务: %s -> %s" % [character_name, current_key, new_task])
			ai_current_task_string = new_task # 认领新任务
			
			var parsed_task = parse_task_string(new_task)
			var target_name_or_tag = parsed_task["target"]

			if target_name_or_tag.is_empty():
				navigation_agent.target_position = global_position; ai_current_task_string = ""; return

			# 【【【 使用你之前的健壮逻辑：基于“目标”判断 】】】
			var target_node = find_character_by_name(target_name_or_tag)
			
			if is_instance_valid(target_node):
				# 意图: talk_to
				ai_current_action = "talk_to"
				ai_current_target_name = target_name_or_tag
				navigation_agent.target_position = target_node.global_position
				log_memory_event("计划去找 %s。" % target_name_or_tag)
				
				# 【【【 NEW: 立即开始思考开场白 】】】
				_request_opening_dialogue(target_node.character_name, opener_http_request)
			else:
				# 意图: move_to
				ai_current_action = "move_to"
				ai_current_target_name = "" 
				log_memory_event("计划去 %s。" % target_name_or_tag)
				find_and_move_to_target(target_name_or_tag)

# --- 更新追踪目标位置 ---
func update_target_position(delta: float):
	if ai_current_action != "talk_to" or ai_current_target_name.is_empty():
		return
		
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
			ai_current_action = ""
			ai_current_target_name = ""


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
func find_and_move_to_target(target_tag: String):
	var potential_targets = get_tree().get_nodes_in_group(target_tag)
	if potential_targets.is_empty(): 
		printerr("错误: %s 找不到 '%s'" % [character_name, target_tag])
		ai_current_action = "" 
		ai_current_target_name = ""
		ai_current_task_string = "" # 【【【 修复：清除“上一个任务” 】】】
		navigation_agent.target_position = global_position
		return
	var target_node = potential_targets.pick_random()
	if is_instance_valid(target_node) and target_node.has_method("get_global_position"):
		navigation_agent.target_position = target_node.get_global_position()
		print("%s (D-AI) GOTO: %s" % [character_name, target_tag])
	else: 
		printerr("错误: %s 找到的 '%s' 节点没有位置。" % [character_name, target_tag])
		ai_current_action = "" 
		ai_current_target_name = ""
		ai_current_task_string = "" # 【【【 修复：清除“上一个任务” 】】】
		navigation_agent.target_position = global_position


# ==================== 对话系统 ====================

# --- Agent 主动发起对话 (到达后) ---
#func initiate_dialogue_on_arrival(target_node):
	#var message = ai_dialogue.get("default", "你好！")
	#show_chat_bubble(message) 
	#if target_node.has_method("receive_dialogue"):
		#target_node.receive_dialogue(self, message) 
	#log_memory_event("到达并主动对 %s 说了: '%s'" % [target_node.character_name, message]) 
# --- Agent 主动发起对话 (到达后) ---
func initiate_dialogue_on_arrival(target_node, message_to_say: String):
	# 【【【 MODIFIED: 不再使用默认 "你好" 】】】
	if message_to_say.is_empty():
		message_to_say = "(...)" # 备用，以防万一
	show_chat_bubble(message_to_say) 
	if target_node.has_method("receive_dialogue"):
		target_node.receive_dialogue(self, message_to_say) 
	log_memory_event("到达并主动对 %s 说了: '%s'" % [target_node.character_name, message_to_say])


# --- 接收对话 ---
func receive_dialogue(from_node: CharacterBody2D, message_content: String):
	if is_thinking:
		print("DEBUG: %s 正在思考，忽略了 %s 的消息。" % [character_name, from_node.character_name])
		return 
		
	if is_god_controlled: return 
	log_memory_event("听到 %s 说: '%s'" % [from_node.character_name, message_content])
	call_deferred("generate_llm_reply", from_node, message_content) 

# --- 调用 LLM 生成回复 ---
func generate_llm_reply(from_node, message_content):
	if is_thinking: return 
	#show_chat_bubble("...") 
	
	var llm_reply = await request_dialog_from_llm(from_node.character_name, message_content) 
	
	show_chat_bubble(llm_reply) 
	if is_instance_valid(from_node) and from_node.has_method("receive_dialogue"):
		from_node.receive_dialogue(self, llm_reply) 
		log_memory_event("回复 %s: '%s'" % [from_node.character_name, llm_reply]) 

# --- 显示气泡 ---
func show_chat_bubble(text: String):
	chat_bubble.text = text
	chat_bubble.visible = true
	chat_bubble_timer.start() 

# ==================== 日志系统 ====================
func log_memory_event(event_text: String, thought: String = ""):
	var log_entry = {"time": WorldClock.get_current_time_string(), "event": event_text, "thought": thought}
	ai_memory.append(log_entry)
	var save_path = "res://npc_souls/" + soul_file
	
	var soul_data_to_save = {
		"api_key": llm_api_key, 
		"api_url": llm_api_url, 
		"api_type": llm_api_type, 
		"model_name": llm_model_name,
		"base_prompt": ai_base_prompt, 
		"personality": ai_personality, 
		"goals": ai_goals, 
		"dialogue": ai_dialogue,
		"memory": ai_memory,
		"current_dynamic_plan": current_dynamic_plan 
	}
	
	var file = FileAccess.open(save_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(soul_data_to_save, "  ")); 
		file.close()
	else: printerr("错误: 无法写入记忆文件到 res://: %s (错误码: %s)" % [save_path, FileAccess.get_open_error()])

func request_daily_plan_from_llm(): 
	if is_thinking: return
	if not current_dynamic_plan.is_empty():
		print("  - %s 检测到已有【测试计划】，跳过 LLM 请求。" % character_name)
		return
		
	is_thinking = true
	print("  - %s 正在向 LLM (%s) 请求当日计划..." % [character_name, llm_api_url])
	
	var world_context = _load_world_context()
	var world_objects = world_context.get("available_objects", [])
	var world_chars = world_context.get("available_characters", [])

	var system_prompt = "%s\n你的个性是: %s\n你的目标是: %s\n你过去的记忆是: %s" % [
		ai_base_prompt, 
		ai_personality, 
		ai_goals, 
		ai_memory
	]
	
	var user_prompt = """
	这是你所在环境 "%s" 的信息:
	- 可用物体/地点 (语义标签): %s
	- 在场角色 (包括你自己): %s

	请你根据goals去制定今天的详细日程表JSON，早晨八点之后你才会醒来，晚上11点入睡，模拟一个真实的人的日常，你所有的日志安排都要围绕你的goal去进行。
	键是'HH:MM'。
	【【【重要规则】】】: 每个任务的值必须严格遵循以下两种格式之一：
	1. "move to（go to,去找，到...） [地点标签]"  (例如: "move to [bar_counter]，去[bar_counter]，在[bar_counter]处坐下")
	2. "talk to(talk，去找，和，与...交流) [角色名称]" (例如: "talk to [Alice (NPC)]，去找[Alice (NPC)]交谈")

	【【【绝对不要】】】在值中包含你自己的名字 '[%s]' 或任何额外的描述性文字。

	例如，一个好的计划是: 
	{"09:00": "move to [bar_counter]", "11:00": "talk with [Alice (NPC)]"}
	""" % [
		world_context.get("scene_name", "这个地方"),
		world_objects,
		world_chars,
		character_name # <-- 把 Agent 自己的名字填入，明确告诉 LLM 不要用
	]

	var headers = [ "Content-Type: application/json" ]
	if llm_api_type == "azure":
		headers.append("api-key: " + llm_api_key)
	else: 
		headers.append("Authorization: Bearer " + llm_api_key)
		
	var body_dict = {
		"model": llm_model_name,
		"messages": [
			{"role": "system", "content": [{"type": "text", "text": system_prompt}]},
			{"role": "user", "content": [{"type": "text", "text": user_prompt}]}
		],
		"temperature": 0.7,
		"response_format": { "type": "json_object" }
	}
	
	var body_json = JSON.stringify(body_dict)
	

	print("DEBUG: [To LLM Plan] BODY: %s" % body_json)
	
	http_request.request(llm_api_url, headers, HTTPClient.METHOD_POST, body_json)
	
	var result = await http_request.request_completed; is_thinking = false
	var response_code = result[1]; var response_body_raw = result[3]
	

	var response_body_string = response_body_raw.get_string_from_utf8()
	print("DEBUG: [From LLM Plan] CODE: %s, RAW_RESPONSE: %s" % [response_code, response_body_string])
	
	if response_code == 200:
		var response_json = JSON.parse_string(response_body_string)
		
		if response_json and "choices" in response_json and response_json["choices"]:
			var message_content = response_json.get("choices", [])[0].get("message", {}).get("content", "{}")
			var plan_json = JSON.parse_string(message_content)
			if plan_json:
				self.current_dynamic_plan = plan_json
				print("  - %s 成功解析并存储计划: %s" % [character_name, current_dynamic_plan])
				call_deferred("on_schedule_tick", WorldClock.get_current_time_string())
			else: 
				printerr("  - %s LLM 回复的JSON格式错误: %s" % [character_name, message_content])
		else: 
			printerr("  - %s LLM 回复解析失败 (已打印原始回复)" % character_name)
	else: 
		printerr("  - %s LLM 请求失败! (已打印原始回复)" % [character_name])


func request_dialog_from_llm(from_name: String, message_content: String):
	if is_thinking: return "我正在想事情..."; is_thinking = true
	print("  - %s 正在向 LLM 请求对话回复 (关于: '%s' 说了 '%s')..." % [character_name, from_name, message_content])
	
	var world_context = _load_world_context()
	
	var system_prompt = "%s\n你的个性是: %s\n你的目标是: %s\n你在的地方有: %s 和 %s。" % [
		ai_base_prompt, 
		ai_personality, 
		ai_goals,
		world_context.get("available_objects", []),
		world_context.get("available_characters", [])
	]
	
	var history_prompt = ""; for entry in ai_memory.slice(-5): history_prompt += entry["time"] + ": " + entry["event"] + "\n"
	
	var user_prompt = "最近发生的事:\n%s\n现在 %s 对我说了: '%s'\n请简洁地回复。" % [
		history_prompt, 
		from_name, 
		message_content
	]
	
	var headers = [ "Content-Type: application/json" ]
	if llm_api_type == "azure":
		headers.append("api-key: " + llm_api_key)
	else: 
		headers.append("Authorization: Bearer " + llm_api_key)
		
	var body_dict = {
		"model": llm_model_name,
		"messages": [
			{"role": "system", "content": [{"type": "text", "text": system_prompt}]},
			{"role": "user", "content": [{"type": "text", "text": user_prompt}]}
		],
	}
	var body_json = JSON.stringify(body_dict)
	

	print("DEBUG: [To LLM Dialog] BODY: %s" % body_json)
	
	http_request.request(llm_api_url, headers, HTTPClient.METHOD_POST, body_json)
	
	var result = await http_request.request_completed; is_thinking = false
	var response_code = result[1]; var response_body_raw = result[3]

	var response_body_string = response_body_raw.get_string_from_utf8()
	print("DEBUG: [From LLM Dialog] CODE: %s, RAW_RESPONSE: %s" % [response_code, response_body_string])

	if response_code == 200:
		var response_json = JSON.parse_string(response_body_string)
		
		if response_json and "choices" in response_json and response_json["choices"]:
			var reply_text = response_json["choices"][0].get("message", {}).get("content", "(无法理解)")
			print("  - %s 收到 LLM 对话回复: '%s'" % [character_name, reply_text])
			return reply_text.strip_edges()
		else: 
			printerr("  - %s LLM 对话回复解析失败 (已打印原始回复)" % character_name)
			return "(思考中...)"
	else: 
		printerr("  - %s LLM 对话请求失败! (已打印原始回复)" % [character_name])
		return "(嗯...?)"
		
		
func _request_opening_dialogue(target_name: String, http_node: HTTPRequest):
	if is_thinking or _is_awaiting_opener_content: 
		print("DEBUG: 已在思考，无法请求开场白。")
		return
	if not is_instance_valid(http_node):
		printerr("OpenerHTTPRequest 节点无效!")
		return
	if http_node.is_processing():
		print("DEBUG: OpenerHTTPRequest 节点已在处理中。")
		return

	print("... %s 正在思考要对 %s 说的开场白 ..." % [character_name, target_name])
	_is_awaiting_opener_content = true
	_pending_dialogue_content = ""
	_current_opener_http_request = http_node # 存储引用，以便取消
	
	# --- 准备 Prompt ---
	var world_context = _load_world_context()
	var system_prompt = "%s\n你的个性是: %s\n你的目标是: %s。" % [
		ai_base_prompt, 
		ai_personality, 
		ai_goals
	]
	
	var history_prompt = ""; for entry in ai_memory.slice(-3): history_prompt += entry["time"] + ": " + entry["event"] + "\n"
	
	var user_prompt = """
	最近发生的事:
	%s
	你现在正要去主动找 [%s] 说话。
	请生成一句自然的、符合你个性的“开场白”。
	【【【重要】】】: 你的回复必须非常简洁，只包含你说的第一句话，不要包含任何括号或解释。
	例如: "嗨，%s！你有空吗？"
	注意回复内容要用英文！
	""" % [history_prompt, target_name, target_name.split(" ")[0]] # 尝试获取名字
	
	# --- 准备请求 ---
	var headers = [ "Content-Type: application/json" ]
	if llm_api_type == "azure":
		headers.append("api-key: " + llm_api_key)
	else: 
		headers.append("Authorization: Bearer " + llm_api_key)
		
	var body_dict = {
		"model": llm_model_name,
		"messages": [
			{"role": "system", "content": [{"type": "text", "text": system_prompt}]},
			{"role": "user", "content": [{"type": "text", "text": user_prompt}]}
		],
	}
	var body_json = JSON.stringify(body_dict)
	
	# --- 发送请求 (异步) ---
	http_node.request(llm_api_url, headers, HTTPClient.METHOD_POST, body_json)
	
	var result = await http_node.request_completed
	
	# --- 处理响应 ---
	_current_opener_http_request = null # 请求已完成，清除引用
	
	# 检查在我们等待时，任务是否已被新任务取消
	if not _is_awaiting_opener_content:
		print("DEBUG: 开场白请求已完成，但任务已被取消。")
		return

	_is_awaiting_opener_content = false # 我们不再等待
	
	var response_code = result[1]; var response_body_raw = result[3]
	var response_body_string = response_body_raw.get_string_from_utf8()
	
	if response_code == 200:
		var response_json = JSON.parse_string(response_body_string)
		if response_json and "choices" in response_json and response_json["choices"]:
			var reply_text = response_json.get("choices", [])[0].get("message", {}).get("content", "")
			_pending_dialogue_content = reply_text.strip_edges() # 存储结果
			print("... %s 已想好开场白: '%s'" % [character_name, _pending_dialogue_content])
		else:
			_pending_dialogue_content = "(...)" # 解析失败
			printerr("... %s 开场白解析失败: %s" % [character_name, response_body_string])
	else:
		printerr("... %s 开场白请求失败: %s" % [character_name, response_body_string])
		_pending_dialogue_content = "(嗯...?)" # 请求失败

# ==================== 信号处理 ====================

func _on_click_area_input_event(viewport: Node, event: InputEvent, shape_idx: int) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.is_pressed():
		GlobalState.set_selected(self)

func _on_chat_bubble_timer_timeout():
	chat_bubble.visible = false
