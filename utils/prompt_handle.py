from utils.path_tool import get_abs_path

def load_prompt(relative_path):
    path = get_abs_path(relative_path)

    if not path.is_file():
        raise FileNotFoundError(f"提示词文件不存在:{path}")

    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(f"提示词文件为空:{path}")

    return content

