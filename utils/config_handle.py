import yaml
from utils.path_tool import get_abs_path

def load_config(filename) -> dict:
    config_path = get_abs_path("config")/filename

    with config_path.open("r",encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config,dict):
        raise TypeError(f"配置文件必须时非空的字典：{config_path}")

    if not config:
        raise ValueError(f"配置文件 {config_path} 为空")
    return config

chroma_conf = load_config("chroma.yaml")
rag_conf = load_config("rag.yaml")