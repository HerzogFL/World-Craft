

# enricher Agent
# 该 Agent 负责将用户的简单提示 "扩充" 为一个丰富的、细节明确的提示。
ENRICHER_API_CONFIG = {
    "type": "openai",
    "model": "gpt-4.1",
    "base_url": "",
    "api_key": "" # <--- 在此替换你的密钥
}


# Manager Agent
# 该 Agent 负责调用 LLM (如 GPT-4o) 生成场景布局的 JSON。
MANAGER_API_CONFIG = {
    "type": "openai",
    "model": "gemini-3-pro-preview",
    "base_url": "",
    "api_key": "" # <--- 在此替换你的密钥
}

# Critic Agent
CRITIC_API_CONFIG = {
    "type": "openai",
    "model": "gpt-4.1",
    "base_url": "",
    "api_key": "" # <--- 在此替换你的密钥
}

#Artist Agent。
# 该 Agent 负责调用文生图模型 (如 DALL-E, SD, 或你的 Gemini) 生成资产图像。
ARTIST_API_CONFIG = {
    "type": "openai",
    "model": "gemini-3-pro-image-preview",
    "base_url": "",
    "api_key": "" # <--- 在此替换你的密钥
}

# In-Game Soul Agent
# 该 Agent (soul_writer) 负责将此配置 *写入* 到 .json 灵魂文件中，
SOUL_API_CONFIG = {
    "type": "openai",
    "model": "gpt-4.1",
    "base_url": "",
    "api_key": "" # <--- 在此替换你的密钥
}


    # azure示例:
    # "type": "azure",
    # "model": "gpt-4o",
    # "azure_endpoint": "",
    # "api_key": "", 
    # "api_version": ""

    # # OpenAI 示例:
    # "type": "openai",
    # "model": "gpt-4o",
    # "api_key": "sk-YOUR_OPENAI_KEY_HERE"

    # # Custom (vLLM) 示例:
    # "type": "custom",
    # "model": "your-local-model-name",
    # "base_url": "http://127.0.0.1:8000/v1",
    # "api_key": "NA" # vLLM 通常不需要密钥