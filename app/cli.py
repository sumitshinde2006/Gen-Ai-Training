
# app/cli.py

from app.records import load_records, search, count_by, get_by_id


while True:

    print("\n===== KANDAGUIDE DATABASE =====")
    print("1. Show all varieties")
    print("2. Search variety")
    print("3. Count varieties")
    print("4. Search by ID")
    print("0. Exit")

    choice = input("Enter choice: ")

    if choice == "1":

        for item in load_records():
            print(item["variety_name"], "-", item["category"])

    elif choice == "2":

        keyword = input("Enter variety name: ")

        results = search(keyword)

        if results:
            for item in results:
                print(item)
        else:
            print("No variety found.")

    elif choice == "3":

        print("Onion:", count_by("onion"))
        print("Garlic:", count_by("garlic"))

    elif choice == "4":

        record_id = int(input("Enter record ID: "))

        result = get_by_id(record_id)

        if result:
            print(result)
        else:
            print("Record not found.")

    elif choice == "0":

        print("Thank you for using KandaGuide!")
        break

    else:
        print("Invalid choice!")
