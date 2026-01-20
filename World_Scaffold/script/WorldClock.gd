# res://WorldClock.gd (已升级为 1 分钟精度)
extends Node

# --- 信号 ---
# 当游戏内的“分钟”发生变化时 (例如 08:29 -> 08:30)，向所有 NPC 广播
signal schedule_tick(schedule_key) # e.g., "08:30"

# --- 时钟状态 ---
var is_running: bool = false
var time_scale: float = 60
var current_time_seconds: float = 25200.0 # 6:00 AM

# (旧 'current_schedule_tick' 已被 'current_minute_tick' 替换)
var current_minute_tick: int = -1 # 用于跟踪分钟变化

func start_clock():
	is_running = true
	print("【世界时钟】(1分钟精度) 已启动。时间流速: %fx" % time_scale)

func pause_clock():
	is_running = false

func set_time_scale(new_scale: float):
	time_scale = max(1.0, new_scale)

func _process(delta: float):
	if not is_running:
		return

	# 1. 推进时间
	current_time_seconds += delta * time_scale

	# 2. 处理一天结束 (回绕到 0)
	if current_time_seconds >= 86400.0:
		current_time_seconds -= 86400.0
		current_minute_tick = -1 # 重置分钟跟踪器

	# 3. 检查分钟是否变化
	# 60 秒 = 1 分钟
	var new_minute_tick = int(current_time_seconds / 60.0) 
	
	if new_minute_tick != current_minute_tick:
		current_minute_tick = new_minute_tick
		
		# 【关键】发出带 "HH:MM" 格式的信号
		var schedule_key = get_current_time_string() # e.g., "08:30"
		schedule_tick.emit(schedule_key)


# (get_current_snapped_schedule_key() 已被删除)
# (get_current_hour() 已被删除)

# 返回格式化的时间字符串，例如 "09:15"
# 这个函数现在也充当我们的 "schedule_key"
func get_current_time_string() -> String:
	var hour = int(current_time_seconds / 3600.0)
	var minute = int(fmod(current_time_seconds, 3600.0) / 60.0)
	return "%02d:%02d" % [hour, minute]
