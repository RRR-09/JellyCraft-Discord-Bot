import json
import csv

with open("analytics_processed.csv", "r") as csv_file:
    analytics = csv.DictReader(csv_file)    
    for row in analytics:  # todo: figure out a better way to get the last row of a dictreader
        last_row = row
hours_played = []
for player in last_row:  # skip the first item, its a label
    try:
        name = player.strip()
        time = float(last_row[player].strip())
        hours_played.append((time,name))
    except ValueError:
        continue
hours_played = sorted(hours_played, reverse=True)
for player_number in range(len(hours_played)):
    minutes = hours_played[player_number][0]
    name = hours_played[player_number][1]
    timespan = round(minutes/60,1)
    timespan_units = "hrs"
    if timespan == 0:
        timespan = minutes
        timespan_units = "min"
    print(f"#{player_number+1} - {name} ({timespan} {timespan_units})")
