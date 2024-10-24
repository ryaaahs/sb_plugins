import json

json_data = []

#TODO Import the file using os.path, than hardcoding the address
BOOST_DIR = "C:\\Users\\Desktop\\Games\\sbpe\\sblootlogger"

# Load JSON data
# Open the file containing JSON objects
with open(BOOST_DIR + "\\boost_collector.log", "r") as file:

    # Read each line from the file
    for line in file:
        # Parse the JSON object from the line and append it to the list
        json_data.append(json.loads(line))

# Initialize an empty dictionary to hold unique items
unique_items = {}

# Function to process each item
def process_item(item):
    name = item['name']
    boosts = item['boosts']

    # If the name is not in unique_items, add it
    if name not in unique_items:
        unique_items[name] = {"name": name, "boosts": []}

    for boost in boosts:
        enum = boost['enum']
        stat = boost['stat']
        val = boost['val']

        # Check if this boost is already in the boosts list for this item
        boost_exists = False
        for existing_boost in unique_items[name]['boosts']:
            if existing_boost['boost_enum'] == enum and existing_boost['boost_id'] == stat:
                boost_exists = True
                # If the value is not already in the values list, add it
                if val not in existing_boost['values']:
                    existing_boost['values'].append(val)
                break

        # If the boost does not exist, create a new boost object
        if not boost_exists:
            unique_items[name]['boosts'].append({
                "boost_enum": enum,
                "boost_id": stat,
                "values": [val]
            })

# Process each item in the JSON data
for item in json_data:
    process_item(item)

# Convert the unique_items dictionary back to JSON
output_json = json.dumps(list(unique_items.values()))
output_json = json.loads(output_json)
print(output_json)

# Print the output JSON
with open(BOOST_DIR + "\\formattted_boost_file.json", 'w+') as file:
    json.dump(output_json, file, indent=4, sort_keys=False)
