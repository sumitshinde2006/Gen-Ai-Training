
from data.sample_records import records
print("\nALL VARIETIES")

for item in records:
    print(item["variety_name"], "-", item["category"])

keyword = input("\nSearch variety: ").lower()

print("\nSEARCH RESULTS")

for item in records:
    if keyword in item["variety_name"].lower():
        print(item["variety_name"])


onion = 0
garlic = 0

for item in records:

    if item["category"] == "onion":
        onion += 1

    elif item["category"] == "garlic":
        garlic += 1


print("\nCATEGORY COUNT")
print("Onion:", onion)
print("Garlic:", garlic)
print("Total:", len(records))
