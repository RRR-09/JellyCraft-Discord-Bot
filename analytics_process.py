import json

with open("analytics.json", "r") as json_file:
    analytics = json.load(json_file)
users = {}
sorted_usernames = []
# Establish a dict of all users
for entry in analytics:
    if entry["user"] is None:
        continue
    if entry["user"] in users:
        continue
    users[entry["user"]] = {"total_time": 0, "online_since": 0, "intervals": []}
    sorted_usernames.append(entry["user"])

sorted(sorted_usernames)

intervals = []
current_interval_list = []
epoch = analytics[0]["time"]
current_interval = epoch
interval_amount = 60 * 60
interval_tracker = 0


def sort_key(item):
    return item[0]


do_skip_count = 0
for entry in analytics:
    if entry["user"] is None:
        continue

    if entry["time"] > current_interval + interval_amount:
        interval_tracker += 1
        # noinspection SpellCheckingInspection
        for user in users:
            interval_list = users[user]["intervals"]
            time_online = users[user]["total_time"]
            # if user == "Krhona":
            #     time_online /= 3
            interval_list.append(str(round(time_online / 60, 1)))
            users[user]["intervals"] = interval_list
        current_interval += interval_amount
    name = entry["user"]
    action = entry["action"]
    if action == "joined":
        users[name]["online_since"] = float(entry["time"])
    elif action == "left":
        if users[name]["online_since"] == 0:
            print(f"ERROR WITH {name}")
            continue
        time_online = float(entry["time"]) - users[name]["online_since"]
        users[name]["total_time"] += time_online
        users[name]["online_since"] = 0

header_row = ["Server online time in hours"]
for name in sorted_usernames:
    header_row.append(name)
csv = [header_row]

import math
from datetime import datetime, timedelta

current_datetime = datetime.fromtimestamp(epoch)
for interval_index in range(interval_tracker):
    days_past = math.floor(interval_index / 4)
    current_interval = str(datetime.strftime(current_datetime, "%Y-%m-%d"))
    row = [current_interval]
    for name in sorted_usernames:
        row.append(str(users[name]["intervals"][interval_index]))
    csv.append(row)
    current_datetime = current_datetime + timedelta(minutes=interval_amount / 60)

csv_string = ""
for row in csv:
    csv_string += ", ".join(row) + "\n"
with open("analytics_processed.csv", "w") as f:
    f.write(csv_string)

"""header_row = ["Name"]
interval_tracker = 0.25
for intervals in range(interval_tracker):
    header_row.append(str(interval_tracker))
    interval_tracker += 0.25
    
csv = [header_row]
for name in sorted_usernames:
    csv.append(users[name]["intervals"])

csv_string = ""
for row in csv:
    csv_string += ", ".join(row) + "\n"
with open("analytics_processed.csv", "w") as f:
    f.write(csv_string)"""
