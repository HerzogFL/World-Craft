# api_client_utils.py
import sys
from openai import OpenAI, AzureOpenAI

def create_api_client(config: dict, agent_name: str = "Agent"):
    """
    (辅助函数) 根据配置字典创建一个 OpenAI 或 AzureOpenAI 客户端。
    """
    api_type = config.get("type", "openai")
    
    try:
        if api_type == "azure":
            print(f"[{agent_name}] 正在初始化 AzureOpenAI 客户端，端点: {config.get('azure_endpoint')}")
            if not all([config.get("azure_endpoint"), config.get("api_key"), config.get("api_version")]):
                raise ValueError("对于 'azure' 类型, 'azure_endpoint', 'api_key', 和 'api_version' 都是必需的。")
            return AzureOpenAI(
                azure_endpoint=config["azure_endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"]
            )
        
        elif api_type == "openai":
            print(f"[{agent_name}] 正在初始化 OpenAI 兼容客户端...")
            if not config.get("api_key"):
                raise ValueError("对于 'openai' 类型, 'api_key' 是必需的 (如果不需要密钥，请使用 'NA')。")
            custom_base_url = config.get("base_url")
            
            if custom_base_url:
                print(f"[{agent_name}]   > 发现自定义 base_url: {custom_base_url}")
                return OpenAI(
                    base_url=custom_base_url,
                    api_key=config["api_key"]
                )
            else:
                print(f"[{agent_name}]   > 未发现 base_url，使用默认 OpenAI 端点。")
                return OpenAI(
                    api_key=config["api_key"]
                )
        
        else:
            raise ValueError(f"未知的 API 类型 '{api_type}'。必须是 'azure' 或 'openai' 之一。")

    except Exception as e:
        print(f"!!! [{agent_name}] 从 config.py 初始化 API 客户端时出错: {e}", file=sys.stderr)
        sys.exit(1) 