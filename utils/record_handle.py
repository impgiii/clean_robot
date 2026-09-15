import csv
from utils.config_handle import agent_conf
from utils.path_tool import get_abs_path

def get_usage_record(user_id,month)->dict|None:
    user_id = user_id.strip()
    month = month.strip()

    file_path = get_abs_path(agent_conf["external_data_path"])

    with file_path.open("r",encoding="utf-8",newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if(row["用户ID"]==user_id and row["时间"]==month):
                return row

    return None

