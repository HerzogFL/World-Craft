extends Node

enum RunMode {
	LISTEN_FOR_PYTHON,  # 模式1: (开发) 等待 Python 连接并发送指令
	LOAD_FROM_FILE      # 模式2: (游玩) 启动时直接加载本地 JSON 文件
}
@export var run_mode: RunMode = RunMode.LISTEN_FOR_PYTHON
@export_file("*.json") var file_to_load: String = "res://saved_levels/my_first_level.json"

# --- 网络设置 (无变化) ---
const PORT = 8080
var server = TCPServer.new()
var peer = null

# --- 节点引用 (将在 Godot 编辑器中设置) ---
@onready var floor_layer: TileMapLayer = $NavigationRegion2D/FloorLayer
@onready var wall_container: Node2D = $NavigationRegion2D/WorldYSort/WallContainer
@onready var object_container: Node2D = $NavigationRegion2D/WorldYSort/ObjectContainer
@onready var npc_container: Node2D = $NavigationRegion2D/WorldYSort/NpcContainer
@onready var world_y_sort: Node2D = $NavigationRegion2D/WorldYSort
@onready var navigation_region: NavigationRegion2D = $NavigationRegion2D
@onready var time_display_label: Label = $CanvasLayer/TimeDisplayLabel

# --- 资产设置 ---
const ASSET_DIR = "res://generated_assets/" # 共享文件夹
const TILE_SIZE = Vector2i(16, 16) # 瓦片大小
const NPC_SCENE_PATH = "res://scenes/npc.tscn"
const AGENT_SCENE_PATH = "res://scenes/agent.tscn" # 智能体模板

	
func _ready():
	if run_mode == RunMode.LISTEN_FOR_PYTHON:
		print("【运行模式】: 监听 Python 指令...")
		start_network_server() # 启动服务器
	elif run_mode == RunMode.LOAD_FROM_FILE:
		print("【运行模式】: 从文件加载...")
		load_scene_from_json_file(file_to_load) # 直接加载文件
	
func _process(_delta):
	# 1. 只有在“监听”模式下才检查网络
	if run_mode == RunMode.LISTEN_FOR_PYTHON:
		if server.is_connection_available():
			if peer != null:
				peer.disconnect_from_host()
			peer = server.take_connection()
			print("Python 客户端已连接！")
			
		if peer != null and peer.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			var available_bytes = peer.get_available_bytes()
			if available_bytes > 0:
				var data = peer.get_data(available_bytes)
				var json_string = data[1].get_string_from_utf8()
				handle_command(json_string)
		elif peer != null and peer.get_status() == StreamPeerTCP.STATUS_NONE:
			print("Python 客户端已断开连接。")
			peer = null
	
	# 2. 无论在哪种模式下，时钟 UI 都必须更新
	time_display_label.text = WorldClock.get_current_time_string()
	
	
func start_network_server():
	print("场景构建服务器启动中...")
	if server.listen(PORT) != OK:
		printerr("错误：无法在端口 %d 上启动服务器" % PORT)
		return
	print("服务器已在端口 %d 上成功启动，等待 Python 指令..." % PORT)

func load_scene_from_json_file(file_path: String):
	if not FileAccess.file_exists(file_path):
		printerr("加载错误: 找不到文件 %s" % file_path)
		return

	var file = FileAccess.open(file_path, FileAccess.READ)
	var content = file.get_as_text()
	file.close()
	
	var result = JSON.parse_string(content)
	if result == null:
		printerr("加载错误: 解析 JSON 失败 %s" % file_path)
		return
	
	var scene_data = result as Dictionary
	if scene_data.is_empty():
		printerr("加载错误: JSON 文件为空 %s" % file_path)
		return
	
	call_deferred("build_scene_procedurally", scene_data)


func handle_command(json_string: String):
	print("收到指令: ", json_string)
	var result = JSON.parse_string(json_string)
	if result == null:
		printerr("错误: 解析 JSON 失败")
		return
		
	var command = result as Dictionary
	var action = command.get("action", "")
	
	# --- 分支 1: 构建场景 ---
	if action == "build_scene_from_json":
		var scene_data = command.get("payload", null) as Dictionary
		if scene_data:
			build_scene_procedurally(scene_data)
		else:
			printerr("错误: 'build_scene_from_json' 指令缺少 'payload' 数据")
			
	# --- 分支 2: 高清截图 (新增) ---
	elif action == "take_screenshot":
		var payload = command.get("payload", {}) as Dictionary
		var path = payload.get("path", "user://screenshot_4k.png")
		capture_hd_screenshot_without_moving_nodes(path)
		
	else:
		printerr("错误: 未知的 action: %s" % action)


func build_scene_procedurally(data: Dictionary) -> void:
	
	print("开始全自动场景构建...")

	floor_layer.z_index = -5
	
	for child in world_y_sort.get_children():
		child.queue_free()
		
	floor_layer.navigation_enabled = false
	
	var assets = data.get("assets", {}) as Dictionary
	var properties = data.get("properties", {}) as Dictionary
	var layout = data.get("layout", {}) as Dictionary
	
	

	var metadata = data.get("metadata", {}) as Dictionary
	var grid_size_arr = metadata.get("grid_size", [25, 20]) # 从 JSON 读取
	var map_dims = Vector2i(grid_size_arr[0], grid_size_arr[1])

	# 格式: { Vector2i(x, y): float_height_in_pixels }

	
	# 步骤 A: 动态创建 TileSet (你的代码, 原封不动)
	print("  - 步骤 A: 动态创建 TileSet...")
	var tile_set = TileSet.new()
	tile_set.add_physics_layer()
	tile_set.add_navigation_layer()
	var source_id_map = {}
	var current_source_id = 0
	for asset_id in assets:
		var asset_details = assets[asset_id] as Dictionary
		if asset_details.get("type") == "tile": # 只处理 "tile"
			var asset_path = ASSET_DIR.path_join(asset_id + ".png")
			if not FileAccess.file_exists(asset_path):
				printerr("错误: 找不到资产文件 %s" % asset_path); continue
			
			var img = Image.new()
			var err = img.load(asset_path)
			if err != OK:
				printerr("错误: 加载图像失败 %s (错误码: %s)" % [asset_path, err]); continue
			
			var tex = ImageTexture.create_from_image(img)
			if tex == null:
				printerr("错误: 从图像创建纹理失败 %s (图像可能已损坏或为空)" % asset_path)
				continue # 跳过这个损坏的资产
			var atlas_source = TileSetAtlasSource.new()
			atlas_source.texture = tex
			var atlas_coord = Vector2i.ZERO
			# 从 JSON 读取 visual_size
			var v_size_arr = asset_details.get("visual_size", [1, 1])
			var v_size_vec = Vector2i(v_size_arr[0], v_size_arr[1])
			atlas_source.create_tile(atlas_coord, v_size_vec)
			tile_set.add_source(atlas_source, current_source_id)
			
			source_id_map[asset_id] = {
				"source_id": current_source_id, 
				"atlas_coord": atlas_coord,
				"texture": tex,
				"visual_size": v_size_vec
			}
			
			var tile_data = atlas_source.get_tile_data(atlas_coord, 0)
			#set_tile_properties(tile_data, properties.get(asset_id, {}) as Dictionary)
			set_tile_properties(tile_data, properties.get(asset_id, {}) as Dictionary, v_size_vec)
			current_source_id += 1
	floor_layer.tile_set = tile_set
	print("  - TileSet 创建完毕，包含 %d 个瓦片源。" % current_source_id)
	
	
	# 步骤 B: 绘制 TileMap 图层 (你的代码, 原封不动)
	print("  - 步骤 B: 绘制瓦片图层 (仅地板)...") 
	for cmd_item in layout.get("floor_layer", []):
		var cmd = cmd_item as Dictionary
		var map_info = source_id_map.get(cmd.get("asset_id"))
		
		if map_info and cmd.get("command") == "fill_rect":
			var area_arr = cmd.get("area", [0, 0, 1, 1])
			var rect = Rect2i(area_arr[0], area_arr[1], area_arr[2], area_arr[3])
			var tile_visual_size = map_info.get("visual_size", Vector2i(1, 1))
			var tile_w = max(1, tile_visual_size.x) # 步长至少为 1
			var tile_h = max(1, tile_visual_size.y) # 步长至少为 1
 			# 使用 2x2 (tile_w, tile_h) 的步长来循环
			for x in range(rect.position.x, rect.end.x, tile_w):
				for y in range(rect.position.y, rect.end.y, tile_h):
					floor_layer.set_cell(Vector2i(x, y), map_info.source_id, map_info.atlas_coord)

	print("  - 步骤 B.5: 实例化墙壁...")
	for cmd_item in layout.get("wall_layer", []):
		var cmd = cmd_item as Dictionary
		var asset_id = cmd.get("asset_id")
		
		var map_info = source_id_map.get(asset_id)
		if not map_info:
			printerr("错误: 找不到墙壁 '%s' 的资产信息" % asset_id)
			continue
			
		var tex = map_info.texture as Texture2D
		if tex == null:
			printerr("错误: 墙壁 '%s' 的纹理为空" % asset_id)
			continue

		# 2. 获取属性 (用于物理)
		var props = properties.get(asset_id, {}) as Dictionary
		
		# 3. 解析指令
		var command = cmd.get("command")
		var area_arr = cmd.get("area", [0, 0, 1, 1])
		var rect = Rect2i(area_arr[0], area_arr[1], area_arr[2], area_arr[3])
		
		if command == "fill_rect":
			var wall_pixel_height = tex.get_height()
			# 遍历这个矩形覆盖的所有格子
			for wx in range(rect.position.x, rect.end.x):
				for wy in range(rect.position.y, rect.end.y):
					grid_wall_height_map[Vector2i(wx, wy)] = wall_pixel_height
		
		# 4. 调用新的 Sprite 填充函数
		if command == "fill_rect":
			#_fill_rect_with_sprites(wall_container, rect, tex, props)
			#_fill_rect_with_sprites(world_y_sort, rect, tex, props)
			_fill_rect_with_sprites(world_y_sort, rect, tex, props, map_dims)
		elif command == "draw_rect_outline":
			# (你也可以创建一个 _draw_rect_with_sprites 函数)
			printerr("警告: 'draw_rect_outline' 尚未实现为 Sprites")
		
	print("  - 步骤 C: 实例化对象...")
	for cmd_item in layout.get("object_layer", []):
		var cmd = cmd_item as Dictionary
		var asset_id = cmd.get("asset_id")
		if assets.get(asset_id, {}).get("type") != "object": continue 
		
		var asset_path = ASSET_DIR.path_join(asset_id + ".png")
		if not FileAccess.file_exists(asset_path):
			printerr("错误: 找不到对象资产 %s" % asset_path); continue
		
		var img = Image.new()
		var err = img.load(asset_path)
		if err != OK:
			printerr("错误: 加载图像失败 %s" % asset_path); continue
			
		var tex = ImageTexture.create_from_image(img)
		var texture_size = tex.get_size() 
		
		var tile_pos = Vector2i(cmd.get("position")[0], cmd.get("position")[1])
		var world_pos_center = floor_layer.map_to_local(tile_pos)
		
		var sprite = Sprite2D.new()
		sprite.texture = tex
		sprite.name = asset_id
		sprite.centered = false
		sprite.offset = Vector2(-texture_size.x / 2.0, -texture_size.y)
		sprite.position = world_pos_center
		
		var props = properties.get(asset_id, {}) as Dictionary
		var asset_details = assets.get(asset_id, {}) as Dictionary
		var json_size_array = asset_details.get("base_size", null)
		
		var obstacle_base_size = texture_size 
		var obj_base_h = 1 
		
		if json_size_array != null and json_size_array.size() == 2:
			obstacle_base_size = Vector2(json_size_array[0], json_size_array[1]) * Vector2(TILE_SIZE)
			obj_base_h = json_size_array[1]

		# --- 智能墙面附着判定 ---
		var is_hanging = false
		var target_wall_h = 0.0
		#var is_tolerance_snap = false 
		
		# 判定 1: 坐标重合
		if tile_pos in grid_wall_height_map:
			is_hanging = true
			target_wall_h = grid_wall_height_map[tile_pos]
			
		## 判定 2: 邻接且单层厚度
		#elif (tile_pos + Vector2i.UP) in grid_wall_height_map:
			#if obj_base_h == 1: 
				#is_hanging = true
				#is_tolerance_snap = true 
				#target_wall_h = grid_wall_height_map[tile_pos + Vector2i.UP]
				#print("    > [吸附] 挂件 '%s' @ %s 吸附到上方墙壁" % [asset_id, tile_pos])

		if is_hanging:
			var obj_pixel_h = texture_size.y
			
			# 检查约束: 物体高度必须 <= 墙壁高度
			if obj_pixel_h <= target_wall_h:
				
				# 1. 垂直提升算法: (墙高 - 物体高) / 2
				# 结果: 物体将在墙面上垂直居中
				var lift_amount = (target_wall_h - obj_pixel_h) / 2.0
				sprite.position.y -= lift_amount
				
				## 2. 位置修正 (如果是从地板吸附上来的)
				#if is_tolerance_snap:
					#sprite.position.y -= TILE_SIZE.y 
				
				# 3. 提升层级
				sprite.z_index = 1 
				
				print("    > [生效] 挂件 '%s' 垂直居中, 提升 %.1f px" % [asset_id, lift_amount])
			else:
				print("    > [跳过] 挂件 '%s' 高度 (%.1f) 超过墙高 (%.1f), 取消悬挂" % [asset_id, obj_pixel_h, target_wall_h])
				
				
		# -----------------------------------------------------
		var is_floor_decor = false
		var phys = props.get("physics", "")
		var nav = props.get("navigation", "")
		var sem_tag = props.get("semantic_tag", "")
		
		# 规则：可穿过 + 可行走 + 不是门 = 地毯/污渍
		if phys == "passable" and nav == "walkable":
			is_floor_decor = true
		
		# 规则：或者明确标记为 rug/carpet
		if "rug" in asset_id or "carpet" in asset_id or "rug" in sem_tag or "carpet" in sem_tag:
			is_floor_decor = true
			
		# 排除：门
		if "door" in sem_tag or nav == "walkable_door":
			is_floor_decor = false
			
		if is_floor_decor:
			# 强制放在最底层，让人踩在上面
			sprite.z_index = -1
			print("    > [层级] 识别为地毯/装饰 '%s' -> z_index = -1" % asset_id)
		# -------------------------------------------
		
		var semantic_tag = props.get("semantic_tag", "")
		if not semantic_tag.is_empty():
			sprite.add_to_group(semantic_tag)
			
		set_object_properties(sprite, props, obstacle_base_size)
		world_y_sort.add_child(sprite)
		
		
	# 步骤 D: 实例化 NPC 和 Agent
	print("  - 步骤 D: 实例化 NPC 和 智能体...")
	for cmd_item in layout.get("npc_layer", []): 
		var cmd = cmd_item as Dictionary
		var asset_id = cmd.get("asset_id")
		var asset_details = assets.get(asset_id, {}) as Dictionary
		var props = properties.get(asset_id, {}) as Dictionary
		var tile_pos = Vector2i(cmd.get("position")[0], cmd.get("position")[1])
		var asset_type = asset_details.get("type", "")
		
		# 根据类型，调用新的实例化函数
		if asset_type == "npc" or asset_type == "agent":
			instantiate_character(asset_id, asset_type, props, tile_pos)

	print("  - 步骤 E: 烘焙导航网格...")
	var nav_poly_resource = NavigationPolygon.new()
	nav_poly_resource.set_parsed_collision_mask_value(1, true)
	nav_poly_resource.agent_radius = TILE_SIZE.x
	navigation_region.navigation_polygon = nav_poly_resource
	navigation_region.bake_navigation_polygon()
	await navigation_region.bake_finished
	print("  - 导航网格烘焙完毕！")
	
	# 新增 步骤 F: 启动世界时钟
	print("  - 步骤 F: 启动世界时钟...")
	WorldClock.start_clock() # <--- 在这里启动

	print("全自动场景构建完毕！")

func _internal_fill_rect(layer: TileMapLayer, rect: Rect2i, source_id: int, atlas_coord: Vector2i):

	for x in range(rect.position.x, rect.end.x):
		for y in range(rect.position.y, rect.end.y):
			layer.set_cell(Vector2i(x, y), source_id, atlas_coord)

func draw_rect_outline(layer: TileMapLayer, rect: Rect2i, source_id: int, atlas_coord: Vector2i):

	for x in range(rect.position.x, rect.end.x):
		layer.set_cell(Vector2i(x, rect.position.y), source_id, atlas_coord)
		layer.set_cell(Vector2i(x, rect.end.y - 1), source_id, atlas_coord)
	for y in range(rect.position.y, rect.end.y):
		layer.set_cell(Vector2i(rect.position.x, y), source_id, atlas_coord)
		layer.set_cell(Vector2i(rect.end.x - 1, y), source_id, atlas_coord)

func set_tile_properties(tile_data: TileData, props: Dictionary, tile_size_in_cells: Vector2i):
	
	var tile_pixel_size = tile_size_in_cells * TILE_SIZE # e.g., (2,2) * (16,16) = (32, 32)
	var half_pixel_size = tile_pixel_size / 2.0         # e.g., (16, 16)
	
		# --- 物理层设置 (使用中心原点) ---
	if props.get("physics") == "solid":
		var centered_square_polygon = PackedVector2Array([
			Vector2(-half_pixel_size.x, -half_pixel_size.y), # Top-left
			Vector2( half_pixel_size.x, -half_pixel_size.y), # Top-right
			Vector2( half_pixel_size.x,  half_pixel_size.y), # Bottom-right
			Vector2(-half_pixel_size.x,  half_pixel_size.y)  # Bottom-left
		])
		tile_data.set_collision_polygons_count(0, 1)
		tile_data.set_collision_polygon_points(0, 0, centered_square_polygon)
		
		# --- 导航层设置 (同样使用中心原点) ---
	if props.get("navigation") == "walkable":
		var nav_poly = NavigationPolygon.new()
		var centered_outline = PackedVector2Array([
			Vector2(-half_pixel_size.x, -half_pixel_size.y), # Top-left
			Vector2( half_pixel_size.x, -half_pixel_size.y), # Top-right
			Vector2( half_pixel_size.x,  half_pixel_size.y), # Bottom-right
			Vector2(-half_pixel_size.x,  half_pixel_size.y)  # Bottom-left
		])
		nav_poly.add_outline(centered_outline)
		nav_poly.make_polygons_from_outlines() # (保留此警告)
		tile_data.set_navigation_polygon(0, nav_poly)

#func set_object_properties(node: Node2D, props: Dictionary, texture_size: Vector2):
	#var created_solid_body = false 
	#if props.get("physics") == "solid":
		#var body = StaticBody2D.new()
		#var shape_node = CollisionShape2D.new()
		#var rect_shape = RectangleShape2D.new()
		#rect_shape.size = texture_size
		#
		#shape_node.position = Vector2(0, -texture_size.y / 2.0)
		#
		#shape_node.shape = rect_shape
		#body.add_child(shape_node)
		#node.add_child(body)
		#created_solid_body = true # <-- 2. 如果创建了物理体，就设置标志
#
	##if props.get("navigation") == "obstacle":
#
	#if props.get("navigation") == "obstacle" and not created_solid_body:
		#var obstacle = NavigationObstacle2D.new()
		#var half_size = texture_size / 2.0
		#var centered_vertices = PackedVector2Array([
			#Vector2(-half_size.x, -half_size.y), # Top-left
			#Vector2( half_size.x, -half_size.y), # Top-right
			#Vector2( half_size.x,  half_size.y), # Bottom-right
			#Vector2(-half_size.x,  half_size.y)  # Bottom-left
		#])
		#obstacle.vertices = centered_vertices
		#obstacle.position = Vector2(0, -texture_size.y / 2.0)
		#node.add_child(obstacle)


func set_object_properties(node: Node2D, props: Dictionary, obstacle_base_size: Vector2):
	var created_solid_body = false # 
	
	# --- 1. 物理层 ---
	if props.get("physics") == "solid":
		var body = StaticBody2D.new()
		var shape_node = CollisionShape2D.new()
		var rect_shape = RectangleShape2D.new()

		rect_shape.size = obstacle_base_size

		shape_node.position = Vector2(0, -obstacle_base_size.y / 2.0)
		
		shape_node.shape = rect_shape
		body.add_child(shape_node)
		node.add_child(body)
		created_solid_body = true

	# --- 2. 导航层 ---
	if props.get("navigation") == "obstacle" and not created_solid_body:
		var obstacle = NavigationObstacle2D.new()
		
		var half_size = obstacle_base_size / 2.0
		
		var centered_vertices = PackedVector2Array([
			Vector2(-half_size.x, -half_size.y), # Top-left
			Vector2( half_size.x, -half_size.y), # Top-right
			Vector2( half_size.x,  half_size.y), # Bottom-right
			Vector2(-half_size.x,  half_size.y)  # Bottom-left
		])
		obstacle.vertices = centered_vertices
		
		obstacle.position = Vector2(0, -obstacle_base_size.y / 2.0)
		
		node.add_child(obstacle)


func instantiate_character(asset_id: String, asset_type: String, props: Dictionary, tile_pos: Vector2i):
	
	var scene_path = AGENT_SCENE_PATH if asset_type == "agent" else NPC_SCENE_PATH
	
	if not ResourceLoader.exists(scene_path, "PackedScene"):
		printerr("错误: 找不到模板: %s。请创建 %s 场景。" % [scene_path, scene_path])
		return
		
	var scene_template = load(scene_path)
	var npc_instance = scene_template.instantiate()
	
	npc_instance.name = props.get("character_name", asset_id)
	for key in props:
		# 检查实例是否有这个属性 (例如 "soul_file", "is_agent")
		if npc_instance.has_method("set"): # 适用于 @export 变量
			npc_instance.set(key, props[key])
			
	# 1. 自动根据类型添加组 (例如 "npc" 或 "agent")
	if not asset_type.is_empty():
		npc_instance.add_to_group(asset_type)

	# 2. 自动添加 JSON 中定义的语义标签 (例如 "shopkeeper")
	var semantic_tag = props.get("semantic_tag", "")
	if not semantic_tag.is_empty():
		npc_instance.add_to_group(semantic_tag)
		
	var nav_agent = npc_instance.get_node_or_null("NavigationAgent2D")
	if nav_agent:
		nav_agent.radius = 2*TILE_SIZE.x
	else:
		printerr("错误: %s 场景中找不到 'NavigationAgent2D' 子节点!" % scene_path)
	
	var tex_path = ASSET_DIR.path_join(asset_id + ".png")
	if FileAccess.file_exists(tex_path):
		var img = Image.new()
		var err = img.load(tex_path)
		
		if err == OK:
			var tex = ImageTexture.create_from_image(img)
			# 假设 npc.tscn/agent.tscn 上的脚本有 "set_texture" 方法
			if npc_instance.has_method("set_texture"):
				npc_instance.set_texture(tex)
		else:
			printerr("警告: 加载NPC纹理失败 %s (错误码: %s)" % [tex_path, err])
	else:
		printerr("警告: 找不到NPC纹理: %s" % tex_path)

	# 4. 放置到世界中
	var local_pos_center = floor_layer.map_to_local(tile_pos)
	var global_pos_center = floor_layer.to_global(local_pos_center)
	world_y_sort.add_child(npc_instance)
	npc_instance.global_position = global_pos_center
	
	print("    - 成功实例化 %s: %s (灵魂: %s)" % [asset_type, npc_instance.name, props.get("soul_file", "无")])
	
#func _fill_rect_with_sprites(container: Node2D, rect: Rect2i, tex: Texture2D, props: Dictionary, map_dims: Vector2i):
	#var texture_size = tex.get_size()
	#var TILE_HALF_WIDTH = TILE_SIZE.x / 2.0  # 8.0 像素
	#var TILE_FULL_HEIGHT = TILE_SIZE.y       # 16.0 像素
	#
	#for x in range(rect.position.x, rect.end.x):
		#for y in range(rect.position.y, rect.end.y):
			#
			## 1. 计算逻辑位置
			#var tile_pos = Vector2i(x, y)
			## 2. 计算该逻辑位置在世界中的像素坐标 (瓦片的中心点)
			#var world_pos_center = floor_layer.map_to_local(tile_pos)
			#
			## 3. 【【【 你要的 "Trick" 补偿逻辑 】】】
			#var offset_trick = Vector2.ZERO
			#
			## 检查是不是在最左边的墙 (x=0)
			## 并且这个 rect 本身就是从 x=0 开始的 (防止移动内部墙)
			#if tile_pos.x == 0 and rect.position.x == 0:
				#offset_trick.x = -50 # 向左移动 8 像素
#
			## 检查是不是在最右边的墙 (x=24)
			## 并且这个 rect 的 x 坐标是 24 (map_dims.x - 1)
			#elif tile_pos.x == map_dims.x - 1 and rect.position.x == map_dims.x - 1:
				#offset_trick.x = -TILE_HALF_WIDTH # 也向左移动 8 像素
				#
			## 检查是不是在最后边的墙 (y=0)
			## 并且这个 rect 本身就是从 y=0 开始的
			#if tile_pos.y == 0 and rect.position.y == 0:
				## map_to_local 给了 y=16 (瓦片中心)
				## 我们想让墙的底边在 y=0
				#offset_trick.y = -TILE_FULL_HEIGHT # 向上移动 16 像素
			#
			## 【【【 补偿逻辑结束 】】】
			#
			## 3. 创建 Sprite
			#var sprite = Sprite2D.new()
			#sprite.texture = tex
			#sprite.name = "%s_(%d,%d)" % [tex.resource_path.get_file().get_basename(), x, y]
			#
			## 4. 【核心：使用 "底边中点" 对齐法】
			#sprite.centered = false 
			#sprite.offset = Vector2(-texture_size.x / 2.0, -texture_size.y)
			#sprite.position = world_pos_center
			#
			## 5. 添加语义标签 (例如 "wall")
			#var semantic_tag = props.get("semantic_tag", "")
			#if not semantic_tag.is_empty():
				#sprite.add_to_group(semantic_tag)
			#
			## 6. 设置物理/导航属性
			#set_object_properties(sprite, props, TILE_SIZE)
			#
			## 7. 添加到 Y-Sort 容器中
			#container.add_child(sprite)
			
func _fill_rect_with_sprites(container: Node2D, rect: Rect2i, tex: Texture2D, props: Dictionary, map_dims: Vector2i):
	var texture_size = tex.get_size()
	
	var TILE_HALF_WIDTH = TILE_SIZE.x / 2.0  # 8.0 像素
	
	print(map_dims.y)
	print("=========================================================================")
	
	var is_top_rect = (rect.position.y == 0 and rect.position.x == 0 and rect.size.x == map_dims.x)
	#var is_bottom_rect = (rect.position.y == map_dims.y and rect.position.x == 0 and rect.size.x == map_dims.x)
	var is_bottom_rect = (rect.position.y == map_dims.y)
	
	var is_left_rect = (rect.position.x == 0 and rect.position.y > 0 and rect.size.x == 1)
	var is_right_rect = (rect.position.x == map_dims.x - 1 and rect.position.y > 0 and rect.size.x == 1)

	for x in range(rect.position.x, rect.end.x):
		for y in range(rect.position.y, rect.end.y):
			
			var tile_pos = Vector2i(x, y)
			
			# 1. 获取全局基础坐标 (无变化)
			var base_local_pos = floor_layer.map_to_local(tile_pos)
			var base_global_pos = floor_layer.to_global(base_local_pos)
			
			var offset_trick = Vector2.ZERO  
			var scale_trick = Vector2(1.0, 1.0) 
			
			if is_left_rect:
				# A. 这是左侧墙 (x=0)
				offset_trick.x = -TILE_HALF_WIDTH # 向左移动 8
			
			elif is_right_rect:
				# B. 这是右侧墙 (x=24)
				offset_trick.x = TILE_HALF_WIDTH # 向右移动 8
			
			elif is_top_rect or is_bottom_rect:
				# C. 这是顶部墙 (y=0) 或 底部墙 (y=19)
				if tile_pos.x == 0:
					# 墙角-最左 (x=0)
					scale_trick.x = 1.5 
					offset_trick.x = - (TILE_HALF_WIDTH / 2.0) # -4 像素
					
				elif tile_pos.x == map_dims.x - 1:
					# 墙角-最右 (x=24)
					scale_trick.x = 1.5
					offset_trick.x = (TILE_HALF_WIDTH / 2.0) # +4 像素
			
			# 3. 创建 Sprite (无变化)
			var sprite = Sprite2D.new()
			sprite.texture = tex
			sprite.name = "%s_(%d,%d)" % [tex.resource_path.get_file().get_basename(), x, y]
			
			# 4. 对齐法 (无变化)
			sprite.centered = false 
			sprite.offset = Vector2(-texture_size.x / 2.0, -texture_size.y)
			
			# 5. 应用缩放 (无变化)
			sprite.scale = scale_trick
			
			# 6. 设置物理/导航
			
			# 将 Vector2i(TILE_SIZE) 转换为 Vector2
			var scaled_base_size = Vector2(TILE_SIZE) * scale_trick
			
			set_object_properties(sprite, props, scaled_base_size)
			
			# 7. 添加到场景 (无变化)
			container.add_child(sprite)
			
			# 8. 设置全局坐标 (无变化)
			sprite.global_position = base_global_pos + offset_trick


func _unhandled_input(event):
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.is_pressed():
		
		print("上帝模式: 点击了空白处 (取消选择)")
		
		GlobalState.set_selected(null) # 取消选择



func capture_hd_screenshot_without_moving_nodes(save_path: String):
	print("📸 准备进行 8K 截图 (纯净原色版)...")
	
	# --- 1. 基础参数 ---
	var map_width_in_tiles = 80
	var map_height_in_tiles = 80
	var tile_size = 16 
	var map_pixel_size = Vector2(map_width_in_tiles * tile_size, map_height_in_tiles * tile_size)
	var target_size = Vector2i(7280, 7280) # 8K
	
	# --- 2. 创建 Viewport ---
	var sub_viewport = SubViewport.new()
	sub_viewport.size = target_size
	
	sub_viewport.world_2d = get_viewport().world_2d
	
	sub_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	
	sub_viewport.disable_3d = true
	sub_viewport.use_hdr_2d = false
	
	sub_viewport.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	sub_viewport.snap_2d_transforms_to_pixel = true
	sub_viewport.snap_2d_vertices_to_pixel = true
	

	var zoom_x = float(target_size.x) / map_pixel_size.x
	var zoom_y = float(target_size.y) / map_pixel_size.y
	var best_zoom = min(zoom_x, zoom_y)
	
	var temp_camera = Camera2D.new()
	sub_viewport.add_child(temp_camera)
	temp_camera.global_position = map_pixel_size / 2.0
	temp_camera.zoom = Vector2(best_zoom, best_zoom)
	
	add_child(sub_viewport)
	
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	
	# --- 5. 获取图像 ---
	var tex = sub_viewport.get_texture()
	var img = tex.get_image()
	
	if img:
		img.save_png(save_path)
		print("✅ 截图保存成功: ", save_path)
	
	sub_viewport.queue_free()
