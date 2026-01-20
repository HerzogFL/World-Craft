# 文件名: godot_client.py
import socket
import json

def send_command(command_dict, host='127.0.0.1', port=8080):
    """连接到 Godot 服务器并发送一个 JSON 指令"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            command_json = json.dumps(command_dict, ensure_ascii=False)
            payload = command_json.encode('utf-8')
            s.sendall(payload)
            # 打印部分指令，避免刷屏
            print(f"[Godot Client] 成功发送指令 (部分): {command_json[:200]}...")
    except ConnectionRefusedError:
        print(f"错误: 连接被拒绝。请确认 Godot 服务器正在运行于 {host}:{port}。")
    except Exception as e:
        print(f"发送失败: {e}")