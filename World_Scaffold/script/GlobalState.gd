extends Node

# 这个变量将全局存储当前被“上帝”选中的角色
var selected_character = null

# 当选择发生变化时发出信号（可选，但很有用）
signal selection_changed(character_node)

# 全局函数，用于设置新选择的角色
func set_selected(character):
	# 如果点击的是同一个角色，什么也不做
	if selected_character == character:
		return

	# 1. 取消选中旧的角色
	if is_instance_valid(selected_character):
		# 告诉旧角色它不再受上帝控制
		selected_character.set_god_control(false)

	# 2. 存储新选中的角色
	selected_character = character

	# 3. 选中新的角色
	if is_instance_valid(selected_character):
		# 告诉新角色它现在受上帝控制
		selected_character.set_god_control(true)
	
	# 4. 发出信号
	selection_changed.emit(selected_character)
